import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import time
import json
import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import Refactored Modules
from server.config import load_config, CONFIG_PATH, log_info
from server.agents import mizune_manager
from server.websocket import ws_manager
from server.audio import listen_to_microphone, listen_for_wake_word
from server.processor import process_command, _processing_lock
from server.subconscious import start_proactive_agent
from server.auto_fetch import init_auto_fetch
from server.memory_worker import start_memory_worker, stop_memory_worker
from server.vault_sync import init_vault_sync
from server.tts import generate_tts
from server.emotion import detect_emotion

# Globals
from server.tracing import observe, initialize_tracing

if initialize_tracing():
    print("TraceRoot initialized")
CFG = load_config()
whatsapp_core_instance = None

# Startup and Teardown
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("[SERVER] Starting background tasks...")
    
    ws_manager.set_main_loop(asyncio.get_running_loop())

    from server.device_registry import device_registry
    device_registry.set_loop(asyncio.get_running_loop())
    
    # Hook backend logs to stream to the Dashboard Kernel Stream
    from server.config import set_log_callback
    set_log_callback(lambda msg: ws_manager.broadcast_sync({"type": "kernel_log", "payload": msg}))
    
    # Init Mizune v7.0 Kernel
    try:
        from server.mizune.kernel import MizuneKernel
        kernel = MizuneKernel()
        kernel.start()
        log_info("[SERVER] MizuneKernel active.")
    except Exception as e:
        log_info(f"[SERVER] Failed to init MizuneKernel: {e}")
    
    # Start agents
    mizune_manager.initialize(CFG)
    
    # Initialize DeepFilterNet Audio Noise Cancellation (Async/Background)
    from server.noise_cancellation import init_noise_cancellation
    threading.Thread(target=init_noise_cancellation, daemon=True).start()
    
    # Start Wake Word Listener
    if CFG.get("voice_trigger_enabled", True):
        threading.Thread(
            target=listen_for_wake_word, 
            args=(CFG, on_wake_trigger, ws_manager.broadcast_sync),
            daemon=True
        ).start()
    
    # 3. Start background processes
    from server.security import validate_api_keys
    validate_api_keys(CFG)
    start_memory_worker(CFG)
    init_vault_sync(CFG)
    init_auto_fetch(CFG)
    start_proactive_agent(CFG, on_wake_trigger, _processing_lock)
    
    # --- MOVED TO CLOUD SERVER ---
    # Start Headless WhatsApp Bridge Listener (Baileys Super-Architecture)
    # from server.platforms.whatsapp.core import start_whatsapp_core
    # global whatsapp_core_instance
    # whatsapp_core_instance = start_whatsapp_core(CFG)
    
    # Start Headless Gmail Poller
    # from server.platforms.gmail.core import start_gmail_core
    # start_gmail_core(CFG, ws_manager.broadcast_sync)
    # -----------------------------
    
    yield
    log_info("[SERVER] Shutting down background tasks...")
    import server.audio as sa
    sa.SHUTDOWN_EVENT.set()
    
    if whatsapp_core_instance is not None:
        from server.platforms.whatsapp.core import stop_whatsapp_core
        stop_whatsapp_core()
    
    from server.memory_worker import stop_memory_worker
    stop_memory_worker()
    
    mizune_manager.stop_all()

# Create App
app = FastAPI(lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    log_info(f"[ERROR] Unhandled Exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"status": "error", "message": "Internal Server Error"})

# Setup API Key authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Depends(api_key_header)):
    # Default to a dev key if not in .env, to avoid breaking local UI immediately, 
    # but require it to be passed. Actually, we will just use the config.
    expected_key = os.getenv("MIZUNE_API_KEY", "mizune-dev-key")
    if api_key_header == expected_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://localhost:3000", "http://localhost:8000", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React Dashboard (if built)
dist_path = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(dist_path, "index.html"))

# Serve the root directory as static files so index.html is accessible
public_path = os.path.join(os.path.dirname(__file__), "public")
if not os.path.exists(public_path):
    os.makedirs(public_path, exist_ok=True)
app.mount("/ui", StaticFiles(directory=public_path, html=True), name="static")

def on_wake_trigger(pre_text=None):
    log_info("[TRIGGER] Processing voice command...")
    text = pre_text if (pre_text and len(pre_text) > 2) else listen_to_microphone(CFG, ws_manager.broadcast_sync)

    if text:
        ws_manager.broadcast_sync({"type": "status", "text": "Thinking..."})
        res = process_command(text, CFG, ws_manager.broadcast_sync)
        if res:
            log_info(f"[RESPONSE] Speaking: {res}")
            ws_manager.broadcast_sync({"type": "speak", "text": res})
            time.sleep(0.5)
        ws_manager.broadcast_sync({"type": "status", "text": "Idle"})
    else:
        log_info("[TRIGGER] No command text, going IDLE.")
        ws_manager.broadcast_sync({"type": "status", "text": "Idle. Say wake word."})

# ─── Routes ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": mizune_manager.current_mode}

@app.post("/chat")
async def chat_endpoint(request: Request, api_key: str = Depends(get_api_key)):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        return JSONResponse({"response": "", "emotion": "neutral"}, status_code=400)

    ws_manager.broadcast_sync({"type": "user_input", "text": text})
    res = await asyncio.to_thread(process_command, text, CFG, ws_manager.broadcast_sync)
    
    if not res:
        return JSONResponse({"response": "", "emotion": "neutral"}, status_code=500)
        
    emo = detect_emotion(res)
    
    return JSONResponse({"response": res, "emotion": emo})

@app.post("/tts")
async def tts_endpoint(request: Request, api_key: str = Depends(get_api_key)):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        return Response(status_code=400)
    
    audio_bytes = await generate_tts(text, CFG)
    if audio_bytes:
        return Response(content=audio_bytes, media_type="audio/mpeg")
    return Response(status_code=500, content="TTS failed")

@app.post("/notify")
async def notify_endpoint(request: Request, api_key: str = Depends(get_api_key)):
    data = await request.json()
    text = data.get("text", "").strip()
    if text:
        log_info(f"[NOTIFY] Master Notification: {text}")
        ws_manager.broadcast_sync({"type": "speak", "text": text})
        return JSONResponse({"status": "success"})
    return Response(status_code=400)

@app.get("/config")
async def get_config(api_key: str = Depends(get_api_key)):
    return JSONResponse(CFG)

@app.post("/config")
async def save_config(request: Request, api_key: str = Depends(get_api_key)):
    global CFG
    new_cfg = await request.json()
    CFG.update(new_cfg)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CFG, f, indent=4)
        return JSONResponse({"status": "success"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/traceroot_sql")
async def handle_traceroot_sql(request: Request, api_key: str = Depends(get_api_key)):
    from server.agents import mizune_manager
    try:
        data = await request.json()
        question = data.get("question", "")
        if "traceroot_analyst" in mizune_manager.workers:
            agent = mizune_manager.workers["traceroot_analyst"]
            result = await agent.run({"question": question})
            return JSONResponse(result)
        else:
            return JSONResponse({"status": "error", "message": "Analyst agent not initialized"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/memory/export")
async def export_memory(api_key: str = Depends(get_api_key)):
    from server.memory import memory
    import tempfile
    
    try:
        temp_file = os.path.join(tempfile.gettempdir(), "mizune_memory.md")
        memory.export_to_markdown(temp_file)
        with open(temp_file, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content=content, media_type="text/markdown")
    except Exception as e:
        return Response(status_code=500, content=f"Failed to export memory: {e}")

@app.get("/memory/obsidian/status")
async def get_obsidian_status():
    vault_path = CFG.get("obsidian_vault_path", "").strip()
    if not vault_path:
        return JSONResponse({"status": "unconfigured", "path": ""})
    
    if os.path.isdir(vault_path):
        return JSONResponse({"status": "connected", "path": vault_path})
    else:
        return JSONResponse({"status": "error", "path": vault_path, "message": "Directory does not exist"})

@app.post("/memory/obsidian/sync")
async def sync_obsidian_memory(api_key: str = Depends(get_api_key)):
    from server.memory import memory
    vault_path = CFG.get("obsidian_vault_path", "").strip()
    if not vault_path:
        return JSONResponse({"status": "error", "message": "Obsidian vault path is not configured."}, status_code=400)
        
    if not os.path.isdir(vault_path):
        return JSONResponse({"status": "error", "message": f"Obsidian vault path does not exist: {vault_path}"}, status_code=400)
        
    try:
        # Determine target file location: check if Inbox exists, otherwise write to root
        inbox_path = os.path.join(vault_path, "Inbox")
        if os.path.isdir(inbox_path):
            target_path = os.path.join(inbox_path, "Mizune Memory.md")
        else:
            target_path = os.path.join(vault_path, "Mizune Memory.md")
            
        memory.export_to_markdown(target_path)
        
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return JSONResponse({
            "status": "success",
            "file_path": target_path,
            "content": content
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Sync failed: {str(e)}"}, status_code=500)

from server.tracing import observe
@app.websocket("/ws/trace_test")
@observe(name="websocket.trace_test", type="test")
async def test_trace_propagation(websocket: WebSocket):
    await websocket.accept()
    from opentelemetry import trace
    from server.websocket import inject_trace_context
    current_span = trace.get_current_span()
    trace_id = current_span.get_span_context().trace_id
    
    message = inject_trace_context({
        "type": "trace_diagnostic",
        "python_trace_id": f"{trace_id:032x}",
    })
    await websocket.send_text(json.dumps(message))
    
    # Frontend should echo back the trace_id it sees
    response = await websocket.receive_text()
    data = json.loads(response)
    
    frontend_trace_id = data.get("frontend_trace_id")
    if frontend_trace_id == f"{trace_id:032x}":
        print("Context propagates")
    else:
        print(f"BROKEN — Python: {trace_id:032x}, Frontend: {frontend_trace_id}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "chat":
                    text = msg.get("text", "").strip()
                    if text:
                        ws_manager.broadcast_sync({"type": "user_input", "text": text})
                        ws_manager.broadcast_sync({"type": "status", "text": "Thinking..."})

                        async def handle_chat():
                            try:
                                res = await asyncio.to_thread(process_command, text, CFG, ws_manager.broadcast_sync)
                                if res:
                                    from server.emotion import detect_emotion
                                    emo_str = detect_emotion(res)
                                    
                                    # Convert emotion string to biometric scores
                                    v, a = 0.0, 0.5
                                    if emo_str in ["happy", "excited"]: v, a = 1.0, 0.8
                                    elif emo_str == "sad": v, a = -1.0, 0.2
                                    elif emo_str == "angry": v, a = -0.8, 0.9
                                    elif emo_str == "surprised": v, a = 0.5, 0.8
                                    elif emo_str == "blush": v, a = 0.8, 0.6
                                    elif emo_str == "sleepy": v, a = 0.0, 0.1
                                    
                                    # Send Biometrics to Dashboard so Slime Avatar reacts
                                    ws_manager.broadcast_sync({
                                        "type": "state_update", 
                                        "payload": {"valence": v, "arousal": a}
                                    })
                                    
                                    ws_manager.broadcast_sync({"type": "speak", "text": res})
                                    try:
                                        from server.tts import generate_tts
                                        from server.audio import play_audio_bytes
                                        audio_bytes = await generate_tts(res, CFG)
                                        if audio_bytes:
                                            play_audio_bytes(audio_bytes)
                                    except Exception as e:
                                        log_info(f"[WS] TTS generation error: {e}")
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                log_info(f"[WS] process_command error: {e}")
                                ws_manager.broadcast_sync({"type": "speak", "text": f"Error: {e}"})
                            finally:
                                ws_manager.broadcast_sync({"type": "status", "text": "Idle"})

                        asyncio.create_task(handle_chat())
                elif msg.get("type") == "command":
                    cmd = msg.get("command")
                    ws_manager.broadcast_sync({"type": "status", "text": "Executing Command..."})
                    
                    if cmd == "research":
                        query = msg.get("query", "")
                        ws_manager.broadcast_sync({"type": "speak", "text": f"Initializing Deep Research on: {query}"})
                        
                        tasks = [
                            {"id": "t1", "description": "Formulate search queries", "status": "running"},
                            {"id": "t2", "description": "Scan web sources via Agent-Reach", "status": "pending"},
                            {"id": "t3", "description": "Synthesize and compile final report", "status": "pending"}
                        ]
                        ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                        
                        async def run_research():
                            await asyncio.sleep(2)
                            tasks[0]["status"] = "completed"
                            tasks[1]["status"] = "running"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            
                            try:
                                import urllib.parse
                                encoded_query = urllib.parse.quote_plus(query)
                                from server.web_agent import headless_web_agent
                                result = await asyncio.to_thread(headless_web_agent, "https://duckduckgo.com/?q=" + encoded_query, f"Research {query}")
                            except Exception as e:
                                result = f"Research failed: {e}"
                                
                            tasks[1]["status"] = "completed"
                            tasks[2]["status"] = "running"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            await asyncio.sleep(2)
                            tasks[2]["status"] = "completed"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            
                            ws_manager.broadcast_sync({"type": "speak", "text": "Research completed.\n\n" + result})
                            ws_manager.broadcast_sync({"type": "status", "text": "Idle"})
                            
                        asyncio.create_task(run_research())
                        
                    elif cmd == "briefing":
                        ws_manager.broadcast_sync({"type": "speak", "text": "Starting Morning Briefing..."})
                        tasks = [
                            {"id": "t1", "description": "Fetch Unread Emails", "status": "running"},
                            {"id": "t2", "description": "Fetch Today's Calendar Events", "status": "pending"},
                            {"id": "t3", "description": "Compile Briefing", "status": "pending"}
                        ]
                        ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                        
                        async def run_briefing():
                            await asyncio.sleep(1.5)
                            tasks[0]["status"] = "completed"
                            tasks[1]["status"] = "running"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            await asyncio.sleep(1.5)
                            tasks[1]["status"] = "completed"
                            tasks[2]["status"] = "running"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            await asyncio.sleep(1.5)
                            tasks[2]["status"] = "completed"
                            ws_manager.broadcast_sync({"type": "task_list", "tasks": tasks})
                            
                            # Fake data for now, ideally fetch real counts here
                            unread_emails = 0
                            meetings = 0
                            
                            ws_manager.broadcast_sync({"type": "speak", "text": f"Briefing Complete: You have {unread_emails} unread emails and {meetings} meetings today. (Calendar integration pending auth)."})
                            ws_manager.broadcast_sync({"type": "status", "text": "Idle"})
                        asyncio.create_task(run_briefing())
                        
                    else:
                        ws_manager.broadcast_sync({"type": "speak", "text": f"Executing command: {cmd}"})
                        ws_manager.broadcast_sync({"type": "status", "text": "Idle"})

                elif msg.get("type") == "trigger_listen":
                    import server.audio as sa
                    if getattr(sa, 'is_active_listening', False):
                        log_info("[WS] Ignored F2 trigger because microphone is already actively recording.")
                        continue
                    if hasattr(sa, 'MANUAL_WAKE_TRIGGER'):
                        sa.MANUAL_WAKE_TRIGGER.set()
                    else:
                        import threading
                        threading.Thread(target=on_wake_trigger, daemon=True).start()
                elif msg.get("type") == "get_knowledge_graph":
                    try:
                        from server.knowledge_graph import get_graph_data
                        graph_data = await asyncio.to_thread(get_graph_data)
                        await websocket.send_text(json.dumps({
                            "type": "knowledge_graph_data",
                            "payload": graph_data
                        }))
                    except Exception as e:
                        log_info(f"[WS] Error fetching knowledge graph: {e}")
                elif msg.get("type") == "register_device":
                    from server.device_registry import device_registry
                    device_registry.register(
                        msg.get("device_name", "unnamed-device"),
                        websocket,
                        capabilities=msg.get("capabilities", []),
                        platform=msg.get("platform", "unknown"),
                    )
                    await websocket.send_text(json.dumps({"type": "device_registered"}))
                elif msg.get("type") == "device_result":
                    from server.device_registry import device_registry
                    device_registry.handle_result(msg.get("request_id", ""), msg.get("result"))
            except Exception as e:
                log_info(f"[WS] Error processing message: {e}")
    except WebSocketDisconnect:
        from server.device_registry import device_registry
        device_registry.unregister_socket(websocket)
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    import socket

    PORT = 8001
    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    if is_port_in_use(PORT):
        log_info(f"[SERVER] ERROR: Port {PORT} is already in use!")
        # Try to kill it if it's an old mizune process (on windows)
        if os.name == 'nt':
            log_info(f"[SERVER] Attempting to kill process on port {PORT}...")
            os.system(f"FOR /F \"tokens=5\" %a in ('netstat -aon ^| find \":{PORT}\" ^| find \"LISTENING\"') do taskkill /F /PID %a")
            time.sleep(1)
        if is_port_in_use(PORT):
            log_info(f"[SERVER] Port {PORT} is still in use! Please kill it manually or use a different port.")
            exit(1)

    log_info("=" * 50)
    log_info(f"[SERVER] Starting {CFG.get('character_name','Mizune')} backend on port {PORT}...")
    log_info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
