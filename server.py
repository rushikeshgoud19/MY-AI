import os
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
CFG = load_config()
whatsapp_core_instance = None

# Startup and Teardown
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("[SERVER] Starting background tasks...")
    
    ws_manager.set_main_loop(asyncio.get_running_loop())
    
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
                            res = await asyncio.to_thread(process_command, text, CFG, ws_manager.broadcast_sync)
                            if res:
                                ws_manager.broadcast_sync({"type": "speak", "text": res})
                                try:
                                    from server.tts import generate_tts
                                    from server.audio import play_audio_bytes
                                    audio_bytes = await generate_tts(res, CFG)
                                    if audio_bytes:
                                        play_audio_bytes(audio_bytes)
                                except Exception as e:
                                    log_info(f"[WS] TTS generation error: {e}")
                            ws_manager.broadcast_sync({"type": "status", "text": "Idle"})

                        asyncio.create_task(handle_chat())
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
