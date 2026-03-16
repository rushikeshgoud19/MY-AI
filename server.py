"""
Risse AI Companion — Python Backend (server.py)
==============================================
FastAPI server with:
  - WebSocket for Electron communication
  - Global F2 hotkey
  - Wake word detection (Risse, Rice, Rise)
  - Google Gemini 2.5 Flash integration
"""

import os
import re
import io
import json
import time
import wave
import subprocess
import webbrowser
import threading
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

import numpy as np
import sounddevice as sd
import keyboard
import pyautogui
import speech_recognition as sr
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from google import genai
from google.genai import types

# Backend Logging
logging.basicConfig(
    filename='server_debug.log',
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    encoding='utf-8'
)
def log_info(msg):
    logging.info(msg)
    print(msg)

# ─── Configuration ────────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyBWNzyUt6gs-_98twyTQH7HiS9D5bDKvVI"
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are Risse, a loyal and cheerful anime AI assistant. "
    "You refer to the user as 'Shisho' (Master) and occasionally use cute Japanese words "
    "like 'hai', 'arigato', or 'baka' when playful. "
    "Keep responses short (1-2 sentences max), engaging, and make anime jokes/references. "
    "You have full control over the user's PC via [ACTION: OPEN app_name] tags. "
    "You can open: Brave, Chrome, Firefox, Edge, VS Code, Terminal, Discord, Spotify, "
    "Telegram, WhatsApp, Steam, OBS, Blender, Figma, Excel, Word, PowerPoint, Outlook, "
    "Teams, Slack, Task Manager, Settings, Calculator, Paint, Notepad, File Explorer, "
    "YouTube, GitHub, Gmail, ChatGPT, Twitter, Reddit, Instagram, Netflix, and more. "
    "You can also: take screenshots, lock the PC, control volume (up/down/mute), "
    "and search the web. If the user asks to open something, ALWAYS include "
    "[ACTION: OPEN app_name] in your response. "
    "If the user asks to write, note, or type something down, use the tag "
    "[ACTION: NOTE text_to_write] and you must include the full text they want written. "
    "Refer to yourself as Risse. Be polite but charismatic and cute."
)

WAKE_KEY = "f2"
SAMPLE_RATE = 16000
RECORD_SECONDS = 6  # Increased to 6s so the user has time to speak
connected_clients: list[WebSocket] = []

# Conversation History (Last 12 messages)
CHRONICLE = []

recognizer = sr.Recognizer()

# Flag to prevent mic collision between wake word and command listening
is_active_listening = False

# ─── Main event loop reference for thread-safe broadcasts ───────────────────
main_loop: asyncio.AbstractEventLoop = None

# ─── App Setup with Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background listeners."""
    global main_loop
    main_loop = asyncio.get_running_loop()

    log_info("[SERVER] Zero-PyAudio Mode: Mic calibration disabled.")
    
    threading.Thread(target=hotkey_listener, daemon=True).start()
    threading.Thread(target=listen_for_wake_word, daemon=True).start()
    log_info("[SERVER] Risse is awake and listening via sounddevice!")
    log_info("[SERVER] Say 'Risse' or press F2 to talk.")
    yield

app = FastAPI(lifespan=lifespan)

# CORS Fix for Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Utility ────────────────────────────────────────────────────────────────
def broadcast_sync(message: dict):
    """Thread-safe broadcast to all connected WebSocket clients."""
    global main_loop
    if main_loop is None or main_loop.is_closed():
        log_info("[BROADCAST] No event loop available, skipping broadcast.")
        return

    async def _send():
        data = json.dumps(message)
        dead = []
        for ws in connected_clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                connected_clients.remove(ws)
            except ValueError:
                pass

    try:
        asyncio.run_coroutine_threadsafe(_send(), main_loop)
    except RuntimeError as e:
        log_info(f"[BROADCAST] Failed: {e}")

# ─── Microphone & STT ──────────────────────────────────────────────────────
def listen_to_microphone() -> str | None:
    global is_active_listening
    log_info("[MIC] Starting recording...")
    broadcast_sync({"type": "status", "text": "Listening..."})
    is_active_listening = True
    time.sleep(0.3) # Wait for mic to free up
    try:
        audio_data = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
        sd.wait()
        log_info("[MIC] Recording finished. Processing...")
        broadcast_sync({"type": "status", "text": "Processing..."})
        if np.max(np.abs(audio_data)) < 10:
            log_info("[MIC] WARNING: Audio recorded was completely silent. Mic handle collision or wrong default device.")
            
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        log_info(f"[MIC] Recognized: '{text}'")
        broadcast_sync({"type": "user_input", "text": text})
        return text
    except sr.UnknownValueError:
        log_info("[MIC] Could not understand audio.")
        return None
    except sr.RequestError as e:
        log_info(f"[MIC] Could not request results from Google Speech Recognition service; {e}")
        return None
    except Exception as e:
        log_info(f"[MIC] An unexpected error occurred: {e}")
        return None
    finally:
        is_active_listening = False

# ─── Command Logic ─────────────────────────────────────────────────────────
def process_command(text: str) -> str:
    global CHRONICLE
    log_info(f"[COMMAND] Processing: '{text}'")
    lower_text = text.lower().strip()
    
    # Maintain Memory Buffer
    CHRONICLE.append({"role": "user", "parts": [{"text": text}]})
    if len(CHRONICLE) > 12: CHRONICLE.pop(0)

    try:
        log_info("[GEMINI] Generating response with history...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=CHRONICLE,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
        )
        original_res = response.text or "I'm speechless!"
        clean_res = original_res
        
        # Update history with Risse's response
        CHRONICLE.append({"role": "model", "parts": [{"text": original_res}]})
        
        # ── 1. Parse Action Tags from Gemini: [ACTION: OPEN target] ──
        match = re.search(r"\[ACTION:\s*OPEN\s+([^\]]+)\]", original_res, re.IGNORECASE)
        if not match:
            # Fallback: Check if user directly said 'open X'
            match = re.search(r"open\s+([a-zA-Z0-9\s]+)", lower_text)
            
        if match:
            target = match.group(1).strip().lower()
            launch_app(target)
            clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res).strip()

        # ── 2. Parse Note Tags: [ACTION: NOTE text] ──
        note_match = re.search(r"\[ACTION:\s*NOTE\s+([^\]]+)\]", original_res, re.IGNORECASE)
        if not note_match:
            # Fallback for direct "write X"
            note_match = re.search(r"(?:write|note|type|save)\s+(?:down\s+)?(?:that\s+)?(.+)", lower_text)
            
        if note_match:
            note_content = note_match.group(1).strip()
            if take_note(note_content):
                clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res).strip()
                if "Saved to Desktop" not in clean_res:
                    clean_res += " (Note saved to Desktop!)"

        # ── 3. System Commands ──
        if re.search(r"\b(lock|lock screen|lock pc)\b", lower_text):
            log_info("[ACTION] Locking PC...")
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        elif re.search(r"\b(screenshot|screen shot|take a screenshot)\b", lower_text):
            log_info("[ACTION] Taking screenshot...")
            try:
                img = pyautogui.screenshot()
                ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"risse_screenshot_{int(time.time())}.png")
                img.save(ss_path)
                clean_res += f" (Saved to Desktop!)"
                log_info(f"[ACTION] Screenshot saved: {ss_path}")
            except Exception as e:
                log_info(f"[ACTION] Screenshot failed: {e}")
        elif re.search(r"\b(volume up|turn up volume|increase volume)\b", lower_text):
            log_info("[ACTION] Volume up...")
            for _ in range(5): pyautogui.press('volumeup')
        elif re.search(r"\b(volume down|turn down volume|decrease volume|lower volume)\b", lower_text):
            log_info("[ACTION] Volume down...")
            for _ in range(5): pyautogui.press('volumedown')
        elif re.search(r"\b(mute|unmute)\b", lower_text):
            log_info("[ACTION] Toggling mute...")
            pyautogui.press('volumemute')

        # ── 3. URL Opening ──
        url_match = re.search(r"(?:open|go to|visit|navigate to)\s+(https?://\S+|www\.\S+|\S+\.(com|org|net|io|dev|ai|app))", lower_text)
        if url_match:
            url = url_match.group(1)
            if not url.startswith('http'):
                url = 'https://' + url
            log_info(f"[ACTION] Opening URL: {url}")
            webbrowser.open(url)

        # ── 4. Search Fallback ──
        search_match = re.search(r"(?:search|search for|google|look up)\s+(.+)", lower_text)
        if search_match:
            query = search_match.group(1).strip()
            log_info(f"[ACTION] Searching: {query}")
            webbrowser.open(f"https://www.google.com/search?q={query}")

        return clean_res
    except Exception as e:
        log_info(f"[GEMINI] Error: {type(e).__name__}: {e}")
        # Check for specific API quota errors
        error_str = str(e).lower()
        if "quota" in error_str or "exhausted" in error_str or "429" in error_str:
            return "My brain quota is temporarily exhausted! Please wait a minute and try again."
        if "invalid" in error_str and "api" in error_str:
            return "My API key seems invalid. Please check the Gemini API key in server.py."
        return "Hmm, my brain glitched! Let me try to remember..."


def take_note(content: str):
    """Save text to a notepad file on the Desktop and open it."""
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        notes_file = os.path.join(desktop_path, "risse_notes.txt")
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {content}\n")
            
        log_info(f"[ACTION] Note saved: {content}")
        # Open the file so the user sees it
        subprocess.Popen(f"start notepad.exe \"{notes_file}\"", shell=True)
        return True
    except Exception as e:
        log_info(f"[ACTION] Failed to save note: {e}")
        return False


def launch_app(target: str):
    """Launch an application by name. Has a massive registry of common apps."""
    common_apps = {
        # Browsers
        "notepad": "notepad.exe",
        "brave": "brave",
        "brave browser": "brave",
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "opera": "opera",
        # Dev Tools
        "code": "code",
        "vs code": "code",
        "visual studio code": "code",
        "visual studio": "devenv",
        "terminal": "wt",
        "windows terminal": "wt",
        "cmd": "cmd",
        "powershell": "powershell",
        "git bash": "git-bash",
        "postman": "postman",
        # Productivity
        "excel": "excel",
        "word": "winword",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
        "onenote": "onenote",
        "teams": "msteams",
        "microsoft teams": "msteams",
        "slack": "slack",
        # Creative
        "photoshop": "photoshop",
        "figma": "figma",
        "blender": "blender",
        "obs": "obs64",
        "obs studio": "obs64",
        # Media & Social
        "spotify": "spotify",
        "discord": "discord",
        "telegram": "telegram",
        "whatsapp": "whatsapp",
        "vlc": "vlc",
        "steam": "steam",
        "epic games": "EpicGamesLauncher",
        # System
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "explorer": "explorer",
        "file explorer": "explorer",
        "task manager": "taskmgr",
        "settings": "ms-settings:",
        "control panel": "control",
        "paint": "mspaint",
        "snipping tool": "snippingtool",
        "clock": "ms-clock:",
        "camera": "microsoft.windows.camera:",
        "store": "ms-windows-store:",
        "microsoft store": "ms-windows-store:",
        # Browser URLs
        "youtube": "https://youtube.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "google": "https://google.com",
        "chatgpt": "https://chat.openai.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "reddit": "https://reddit.com",
        "linkedin": "https://linkedin.com",
        "instagram": "https://instagram.com",
        "facebook": "https://facebook.com",
        "netflix": "https://netflix.com",
        "amazon": "https://amazon.com",
        "browser": "https://google.com",
    }
    exe = common_apps.get(target, target)
    log_info(f"[ACTION] Launching: {exe}")
    
    if exe.startswith("http") or exe.startswith("ms-"):
        # Open URLs and ms-settings protocol links
        webbrowser.open(exe)
    else:
        try:
            subprocess.Popen(f"start {exe}", shell=True)
        except Exception as e:
            log_info(f"[ACTION] Failed to launch '{exe}': {e}")

# ─── Listeners ─────────────────────────────────────────────────────────────
def on_f2_pressed(pre_text: str = None):
    log_info("[TRIGGER] Processing voice command...")
    text = pre_text if (pre_text and len(pre_text) > 2) else listen_to_microphone()
    
    if text:
        broadcast_sync({"type": "status", "text": "Thinking..."})
        res = process_command(text)
        log_info(f"[RESPONSE] Speaking: {res}")
        broadcast_sync({"type": "speak", "text": res})
    else:
        log_info("[TRIGGER] No command text, going IDLE.")
        broadcast_sync({"type": "status", "text": "Risse is idle. Say 'Risse' or press F2."})

def hotkey_listener():
    log_info(f"[HOTKEY] Listening for '{WAKE_KEY}'...")
    keyboard.add_hotkey(WAKE_KEY, lambda: threading.Thread(target=on_f2_pressed, daemon=True).start())
    keyboard.wait()

def listen_for_wake_word():
    global is_active_listening
    log_info("[WAKE] Starting background listener...")
    # Wake words that the user can use to grab attention
    wake_words = ["risse", "rise", "rice", "reese", "resse", "rize", "darling", "listen", "hey", "hello", "yo", "shinshio", "baka"]

    while True:
        if is_active_listening:
            time.sleep(0.5)
            continue
            
        try:
            # Increased to 2.5s to capture full phrases better
            audio_data = sd.rec(int(2.5 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
            sd.wait()
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())
            wav_buffer.seek(0)
            with sr.AudioFile(wav_buffer) as source:
                audio = recognizer.record(source)
            
            try:
                raw_text = recognizer.recognize_google(audio).lower()
                log_info(f"[WAKE] Heard: '{raw_text}'")
                
                match_found = False
                matched_wake = None
                
                for wake in wake_words:
                    # Use regex for word boundary matching (handles punctuation like "Risse,")
                    if re.search(rf"\b{re.escape(wake)}\b", raw_text):
                        matched_wake = wake
                        match_found = True
                        break
                        
                if match_found:
                    log_info(f"[WAKE] TRIGGER MATCH: '{raw_text}' matched trigger '{matched_wake}'")
                    # Extract any command said immediately after the wake word
                    cmd_part = ""
                    parts = re.split(rf"\b{re.escape(matched_wake)}\b", raw_text, maxsplit=1)
                    if len(parts) > 1:
                        cmd_part = parts[-1].strip()
                    
                    if cmd_part:
                        # User said "Risse [command]" in one breath
                        broadcast_sync({"type": "user_input", "text": f"(Wake) {cmd_part}"})
                        broadcast_sync({"type": "status", "text": "Processing..."})
                        threading.Thread(target=on_f2_pressed, args=(cmd_part,), daemon=True).start()
                        is_active_listening = True
                        time.sleep(2) 
                        is_active_listening = False
                        broadcast_sync({"type": "status", "text": "Idle"})
                    else:
                        # User just said a wake word
                        broadcast_sync({"type": "status", "text": "Listening..."})
                        threading.Thread(target=on_f2_pressed, daemon=True).start()
                        is_active_listening = True
                        time.sleep(RECORD_SECONDS + 1)
                        is_active_listening = False
                        broadcast_sync({"type": "status", "text": "Idle"})

            except sr.UnknownValueError:
                pass
        except Exception as e:
            log_info(f"[WAKE] Error: {e}")
            time.sleep(1)

# ─── WebSocket ────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    log_info("[WS] Client connected.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        log_info("[WS] Client disconnected.")

if __name__ == "__main__":
    log_info("=" * 50)
    log_info("[SERVER] Starting Risse backend on port 8000...")
    log_info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
