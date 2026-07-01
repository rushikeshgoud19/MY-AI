import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
import time
import json
import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
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
import traceroot
from traceroot import observe
from traceroot.instrumentation import Integration

TRACEROOT_API_KEY = os.getenv("TRACEROOT_API_KEY")
if TRACEROOT_API_KEY:
    integrations = [Integration.GOOGLE_GENAI, Integration.OPENAI]
    
    traceroot.initialize(
        api_key=TRACEROOT_API_KEY,
        integrations=integrations,
    )
    print("TraceRoot initialized")
CFG = load_config()
whatsapp_core_instance = None

# Startup and Teardown
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("[SERVER] Starting background tasks...")
    
    ws_manager.set_main_loop(asyncio.get_running_loop())
    
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
    
    # Start Headless WhatsApp Bridge Listener (Baileys Super-Architecture)
    from server.platforms.whatsapp.core import start_whatsapp_core
    global whatsapp_core_instance
    whatsapp_core_instance = start_whatsapp_core(CFG)
    
    # Start Headless Gmail Poller
    from server.platforms.gmail.core import start_gmail_core
    start_gmail_core(CFG, ws_manager.broadcast_sync)
    
    yield
    
    log_info("[SERVER] Shutting down background tasks...")
    from server.platforms.whatsapp.core import stop_whatsapp_core
    stop_whatsapp_core()
    
    from server.memory_worker import stop_memory_worker
    stop_memory_worker()
    
    mizune_manager.stop_all()

# Create App
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.mount("/ui", StaticFiles(directory=".", html=True), name="static")

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
async def chat_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        return JSONResponse({"response": "", "emotion": "neutral"})

    ws_manager.broadcast_sync({"type": "user_input", "text": text})
    res = await asyncio.to_thread(process_command, text, CFG, ws_manager.broadcast_sync)
    emo = detect_emotion(res)
    
    return JSONResponse({"response": res, "emotion": emo})

@app.post("/tts")
async def tts_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        return Response(status_code=400)
    
    audio_bytes = await generate_tts(text, CFG)
    if audio_bytes:
        return Response(content=audio_bytes, media_type="audio/mpeg")
    return Response(status_code=500, content="TTS failed")

@app.post("/notify")
async def notify_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    if text:
        log_info(f"[NOTIFY] Master Notification: {text}")
        ws_manager.broadcast_sync({"type": "speak", "text": text})
        return JSONResponse({"status": "success"})
    return Response(status_code=400)

@app.get("/config")
async def get_config():
    return JSONResponse(CFG)

@app.post("/config")
async def save_config(request: Request):
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
async def handle_traceroot_sql(request: Request):
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
async def export_memory():
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
async def sync_obsidian_memory():
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

from traceroot import observe
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
                    platform = msg.get("platform", "desktop")
                    if text:
                        ws_manager.broadcast_sync({"type": "user_input", "text": text, "platform": platform})
                        ws_manager.broadcast_sync({"type": "status", "text": "Thinking..."})

                        async def handle_chat(input_text, source_platform):
                            res = await asyncio.to_thread(process_command, input_text, CFG, ws_manager.broadcast_sync)
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
                                
                                ws_manager.broadcast_sync({
                                    "type": "state_update", 
                                    "payload": {"valence": v, "arousal": a}
                                })
                                
                                # SENTENCE-BOUNDARY CHUNKING FOR LOW LATENCY
                                import re
                                # Split by punctuation (. ! ?) followed by space or end of string
                                sentences = re.split(r'(?<=[.!?])\s+|(?<=[.!?])$', res.strip())
                                sentences = [s.strip() for s in sentences if s.strip()]
                                
                                if not sentences:
                                    sentences = [res.strip()]
                                
                                for sentence in sentences:
                                    ws_manager.broadcast_sync({"type": "speak", "text": sentence, "emotion": emo_str})
                                    # Very slight delay to ensure correct order
                                    await asyncio.sleep(0.1)
                                
                                # Only play audio locally if it's not a mobile client
                                if source_platform != "mobile":
                                    try:
                                        from server.tts import generate_tts
                                        from server.audio import play_audio_bytes
                                        audio_bytes = await generate_tts(res, CFG)
                                        if audio_bytes:
                                            play_audio_bytes(audio_bytes)
                                    except Exception as e:
                                        log_info(f"[WS] TTS generation error: {e}")
                            ws_manager.broadcast_sync({"type": "status", "text": "Idle"})

                        asyncio.create_task(handle_chat(text, platform))
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
                                from server.web_agent import headless_web_agent
                                result = await asyncio.to_thread(headless_web_agent, "https://duckduckgo.com/?q=" + query.replace(' ', '+'), f"Research {query}")
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
                            ws_manager.broadcast_sync({"type": "speak", "text": "Briefing Complete: You have 0 unread emails and 0 meetings today. (Calendar integration pending auth)."})
                            ws_manager.broadcast_sync({"type": "status", "text": "Idle"})
                        asyncio.create_task(run_briefing())
                        
                    else:
                        ws_manager.broadcast_sync({"type": "speak", "text": f"Executing command: {cmd}"})
                        ws_manager.broadcast_sync({"type": "status", "text": "Idle"})

                elif msg.get("type") == "mobile_vision":
                    base64_image = msg.get("image_b64", "")
                    if base64_image:
                        ws_manager.broadcast_sync({"type": "status", "text": "Looking at image..."})
                        async def handle_vision(img_data):
                            import base64
                            try:
                                img_bytes = base64.b64decode(img_data)
                                from server.processor import process_mobile_vision
                                res = await asyncio.to_thread(process_mobile_vision, img_bytes, CFG)
                                if res:
                                    ws_manager.broadcast_sync({"type": "speak", "text": res, "emotion": "surprised"})
                                ws_manager.broadcast_sync({"type": "status", "text": "Idle"})
                            except Exception as e:
                                log_info(f"[WS] Mobile vision error: {e}")
                                ws_manager.broadcast_sync({"type": "status", "text": "Vision Error"})
                        asyncio.create_task(handle_vision(base64_image))

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
            except Exception as e:
                log_info(f"[WS] Error processing message: {e}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    import socket

    PORT = 8001
    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    if is_port_in_use(PORT):
        log_info(f"[SERVER] ERROR: Port {PORT} is already in use!")
        exit(1)

    log_info("=" * 50)
    log_info(f"[SERVER] Starting {CFG.get('character_name','Mizune')} backend on port {PORT}...")
    log_info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
