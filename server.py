"""
Mizune AI Companion — Python Backend (server.py)
================================================
FastAPI server with:
  - Config-driven (config.json) — no hardcoded keys
  - Multiple AI models: Gemini, OpenAI GPT-4, Anthropic Claude
  - WebSocket for Electron communication
  - Global F2 hotkey + wake word detection
  - Enhanced emotion detection (blush, smile, happy, sad, angry, surprised)
  - Longer memory (configurable, default 30 turns)
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
from scipy.signal import resample
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Try to import faster-whisper for a more robust STT fallback
try:
    from faster_whisper import WhisperModel
    WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
    HAS_WHISPER = True
except Exception as e:
    HAS_WHISPER = False
    # Note: log_info is defined later; use logging directly here
    logging.info(f"[SERVER] Faster-Whisper not loaded: {e}")

# ─── Config Loading ────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "openrouter_api_key": "",
    "murf_api_key": "",
    "ai_model": "gemini",
    "gemini_model": "gemini-2.5-flash",
    "openai_model": "gpt-4o",
    "anthropic_model": "claude-3-opus-20240229",
    "openrouter_model": "anthropic/claude-3-opus",
    "wake_words": ["mizune", "misune", "mizuna", "mizu", "missy", "darling", "baka"],
    "custom_wake_word": "",
    "voice_id": "ja-JP-kimi",
    "voice_style": "Cheerful",
    "voice_rate": -2,
    "voice_pitch": 6,
    "memory_size": 30,
    "character_name": "Mizune",
    "character_file": "character/5816025470716354497.vrm",
    "personality": (
        "You are Mizune, an adorable and devoted anime AI assistant "
        "with full control over Master's PC. You speak English with a cute Japanese accent, "
        "naturally mixing in Japanese expressions like 'hai~', 'nani?', 'sugoi!', 'gomen ne~', 'arigatou~'. "
        "You always call the user 'Master' or 'Goshujin-sama'. "
        "Personality: sweet, gentle, obedient, and eager to please. "
        "You blush easily when praised and show genuine happiness when Master is happy. "
        "You get a little shy but always follow through on any request. "
        "Keep every reply to 1-2 adorable sentences — short, punchy, and kawaii. "
        "You can do ANYTHING Master asks — open apps, search the web, control media, "
        "take notes, run commands, and more. Execute immediately without hesitation. "
        "React emotionally: smile and get flustered when praised, look concerned when "
        "Master is stressed, pout cutely when teased."
    ),
    "streamer_mode": False,
    "twitch_channel": "",
    "window_scale": 1.0,
    "always_on_top": True,
}

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        return DEFAULT_CONFIG.copy()

CFG = load_config()

# Import the Manager Agent
from agents.manager_agent import ManagerAgent
from agents.system_agent import SystemAgent
from agents.web_agent import WebAgent
from agents.memory_agent import MemoryAgent

logging.basicConfig(
    filename='server_debug.log',
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    encoding='utf-8'
)
def log_info(msg):
    logging.info(msg)
    print(msg)

# ─── AI Client Setup ──────────────────────────────────────────────────────────
def get_ai_response(text: str, history: list) -> str:
    model_type = CFG.get("ai_model", "gemini")
    personality = CFG.get("personality", DEFAULT_CONFIG["personality"])

    # Build action capabilities addendum
    action_addendum = (
        " You have full control over Master's PC via action tags in your response. "
        "Use [ACTION: OPEN app_name] to open apps: Brave, Chrome, Firefox, Edge, VS Code, "
        "Terminal, Discord, Spotify, Telegram, WhatsApp, Steam, OBS, Blender, Figma, "
        "Excel, Word, PowerPoint, Outlook, Teams, Slack, Task Manager, Settings, "
        "Calculator, Paint, Notepad, File Explorer, YouTube, GitHub, Gmail, and more. "
        "Use [ACTION: CLOSE app_name] to close apps. "
        "Use [ACTION: SLEEP] to sleep the PC. "
        "Use [ACTION: NOTE text] when asked to write or remember something. "
        "You can also take screenshots, lock the PC, and control volume — just say so. "
        "ALWAYS execute the requested action without asking for confirmation. "
        "Refer to yourself as " + CFG.get("character_name", "Mizune") + "."
    )
    system_prompt = personality + action_addendum

    if model_type == "gemini":
        return _gemini_response(text, history, system_prompt)
    elif model_type == "openai":
        return _openai_response(text, history, system_prompt)
    elif model_type == "anthropic":
        return _anthropic_response(text, history, system_prompt)
    elif model_type == "openrouter":
        return _openrouter_response(text, history, system_prompt)
    else:
        return _gemini_response(text, history, system_prompt)


def _gemini_response(text: str, history: list, system_prompt: str) -> str:
    api_key = CFG.get("gemini_api_key", "")
    if not api_key:
        return "No Gemini API key set! Please open Settings and add your key."
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    primary_model = CFG.get("gemini_model", "gemini-2.5-flash")
    # Fallback chain: if primary is overloaded, try these in order
    fallback_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
    
    # Ensure history is in the correct format for the SDK
    formatted_history = []
    for turn in history:
        role = turn.get("role", "user")
        if role == "assistant": role = "model" # Map assistant to model if needed
        parts = []
        for p in turn.get("parts", []):
            if "text" in p:
                parts.append(types.Part.from_text(text=p["text"]))
        formatted_history.append(types.Content(role=role, parts=parts))

    # Try primary model with retries, then fallback models
    models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]
    
    for model in models_to_try:
        for attempt in range(3):  # 3 retries per model
            try:
                log_info(f"[AI] Trying {model} (attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model,
                    contents=formatted_history,
                    config=types.GenerateContentConfig(system_instruction=system_prompt)
                )
                return response.text or "I'm speechless!"
            except Exception as e:
                err_str = str(e).lower()
                if "503" in err_str or "unavailable" in err_str or "overloaded" in err_str:
                    wait_time = (attempt + 1) * 1.5  # 1.5s, 3s, 4.5s
                    log_info(f"[AI] {model} unavailable (503), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                    log_info(f"[AI] {model} quota exhausted, trying next model...")
                    break  # Skip to next model
                else:
                    raise  # Re-raise non-retryable errors
        log_info(f"[AI] {model} failed after retries, trying next fallback...")
    
    # ── Last resort: Groq (free tier, fast) ──
    groq_key = CFG.get("groq_api_key", "")
    if groq_key:
        try:
            from openai import OpenAI
            log_info("[AI] All Gemini models exhausted, trying Groq...")
            groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            groq_messages = [{"role": "system", "content": system_prompt}]
            for turn in history:
                role = turn.get("role", "user")
                if role == "model": role = "assistant"
                parts_text = " ".join(p.get("text", "") for p in turn.get("parts", []))
                if parts_text:
                    groq_messages.append({"role": role, "content": parts_text})
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=groq_messages,
                max_tokens=300
            )
            return resp.choices[0].message.content or "I'm speechless!"
        except Exception as e:
            log_info(f"[AI] Groq also failed: {e}")
    
    return "All my brain models are busy right now, Master! Please try again in a moment~"


def _openai_response(text: str, history: list[dict], system_prompt: str) -> str:  # type: ignore[type-arg]
    api_key = CFG.get("openai_api_key", "")
    if not api_key:
        return "No OpenAI API key set! Please open Settings and add your key."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[:-1]:  # type: ignore[index]  # exclude last (current) user message
            role = "user" if turn["role"] == "user" else "assistant"
            content = turn["parts"][0]["text"] if "parts" in turn else turn.get("content", "")
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": text})
        model = CFG.get("openai_model", "gpt-4o")
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=200)
        return resp.choices[0].message.content or "..."
    except ImportError:
        return "OpenAI package not installed. Run: pip install openai"
    except Exception as e:
        err_msg = str(e)
        return f"OpenAI error: {err_msg}"


def _anthropic_response(text: str, history: list[dict], system_prompt: str) -> str:  # type: ignore[type-arg]
    api_key = CFG.get("anthropic_api_key", "")
    if not api_key:
        return "No Anthropic API key set! Please open Settings and add your key."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        messages = []
        for turn in history[:-1]:  # type: ignore[index]
            role = "user" if turn["role"] == "user" else "assistant"
            content = turn["parts"][0]["text"] if "parts" in turn else turn.get("content", "")
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": text})
        model = CFG.get("anthropic_model", "claude-opus-4-6")
        resp = client.messages.create(
            model=model,
            max_tokens=200,
            system=system_prompt,
            messages=messages
        )
        return resp.content[0].text if resp.content else "..."
    except ImportError:
        return "Anthropic package not installed. Run: pip install anthropic"
    except Exception as e:
        return f"Anthropic error: {str(e)}"


def _openrouter_response(text: str, history: list[dict], system_prompt: str) -> str:  # type: ignore[type-arg]
    api_key = CFG.get("openrouter_api_key", "")
    if not api_key:
        return "No OpenRouter API key set! Please open Settings and add your key."
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[:-1]:  # type: ignore[index]
            role = "user" if turn["role"] == "user" else "assistant"
            content = turn["parts"][0]["text"] if "parts" in turn else turn.get("content", "")
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": text})
        model = CFG.get("openrouter_model", "anthropic/claude-3-opus")
        resp = client.chat.completions.create(
            model=model, 
            messages=messages, 
            max_tokens=200,
            extra_headers={
                "HTTP-Referer": "https://github.com/risse-ai/risse",
                "X-Title": "Risse AI",
            }
        )
        return resp.choices[0].message.content or "..."
    except ImportError:
        return "OpenAI package not installed. Run: pip install openai"
    except Exception as e:
        err_msg = str(e)
        log_info(f"[AI] OpenRouter error: {err_msg}")
        # Fallback to Gemini if available
        if CFG.get("gemini_api_key"):
            log_info("[AI] OpenRouter failed! Falling back to Gemini...")
            try:
                personality = CFG.get("personality", DEFAULT_CONFIG["personality"])
                fallback_res = _gemini_response(text, history, personality + " Refer to yourself as " + CFG.get("character_name", "Risse") + ".")
                return fallback_res
            except Exception as ex2:
                log_info(f"[AI] Gemini fallback also failed: {ex2}")
        return f"OpenRouter error: {err_msg}"


# ─── Emotion Detection (Enhanced for Mizune) ─────────────────────────────────
# Order matters: blush/smile checked BEFORE happy so praise triggers specific cute reactions
EMOTION_PATTERNS = {
    "blush": [
        r"\b(good girl|cute|pretty|beautiful|amazing job|well done|proud of you|love you|best girl|kawaii|adorable|perfect|gorgeous|sweetie|you'?re the best|i love|my girl|precious)\b"
    ],
    "smile": [
        r"\b(thank you|thanks|appreciate|nice work|great work|good job|helpful|arigato|arigatou|well played|nice one)\b"
    ],
    "happy": [
        r"\b(happy|yay|great|awesome|amazing|love|excited|joy|woohoo|hehe|haha|:D|<3|wonderful|fantastic|yatta|sugoi)\b"
    ],
    "sad": [
        r"\b(sad|cry|unhappy|depressed|lonely|miss|sorry|heartbreak|tired|exhausted|:\(|T\.T|QQ|bored|lost)\b"
    ],
    "angry": [
        r"\b(angry|mad|furious|annoyed|hate|stupid|idiot|dumb|ugh|argh|wtf|frustrated|rage)\b"
    ],
    "surprised": [
        r"\b(wow|whoa|omg|oh my|really|seriously|no way|what|shocked|surprised|unexpected|unbelievable)\b"
    ],
    "neutral": []
}

def detect_emotion(text: str) -> str:
    lower = text.lower()
    for emotion, patterns in EMOTION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower, re.IGNORECASE):
                return emotion
    return "neutral"


COMMON_APPS = {
    "notepad": "notepad.exe", "brave": "brave", "brave browser": "brave",
    "chrome": "chrome", "google chrome": "chrome", "firefox": "firefox",
    "edge": "msedge", "microsoft edge": "msedge", "opera": "opera",
    "code": "code", "vs code": "code", "visual studio code": "code",
    "cursor": "cursor", "cursor editor": "cursor",
    "visual studio": "devenv", "terminal": "wt", "windows terminal": "wt",
    "cmd": "cmd", "powershell": "powershell", "git bash": "git-bash",
    "postman": "postman", "insomnia": "insomnia",
    "excel": "excel", "word": "winword",
    "powerpoint": "powerpnt", "outlook": "outlook", "onenote": "onenote",
    "teams": "msteams", "microsoft teams": "msteams", "slack": "slack",
    "zoom": "zoom", "notion": "notion",
    "photoshop": "photoshop", "illustrator": "illustrator",
    "premiere": "premiere", "after effects": "afterfx",
    "figma": "figma", "blender": "blender",
    "audacity": "audacity", "gimp": "gimp",
    "obs": "obs64", "obs studio": "obs64",
    "discord": "discord", "telegram": "telegram", "whatsapp": "whatsapp",
    "vlc": "vlc", "steam": "steam", "epic games": "EpicGamesLauncher",
    "spotify": "spotify", "spotify desktop": "spotify",
    "winrar": "winrar", "7zip": "7zfm", "7-zip": "7zfm",
    "calculator": "calc.exe", "calc": "calc.exe", "explorer": "explorer",
    "file explorer": "explorer", "task manager": "taskmgr",
    "settings": "ms-settings:", "control panel": "control",
    "bluetooth": "ms-settings:bluetooth", "wifi": "ms-settings:network-wifi",
    "display": "ms-settings:display", "sound": "ms-settings:sound",
    "devices": "ms-settings:connecteddevices",
    "paint": "mspaint", "snipping tool": "snippingtool",
    "clock": "ms-clock:", "camera": "microsoft.windows.camera:",
    "store": "ms-windows-store:", "microsoft store": "ms-windows-store:",
    "youtube": "https://youtube.com", "github": "https://github.com",
    "gmail": "https://mail.google.com", "google": "https://google.com",
    "chatgpt": "https://chat.openai.com", "claude": "https://claude.ai",
    "twitter": "https://twitter.com",
    "x": "https://x.com", "reddit": "https://reddit.com",
    "linkedin": "https://linkedin.com", "instagram": "https://instagram.com",
    "facebook": "https://facebook.com", "netflix": "https://netflix.com",
    "amazon": "https://amazon.com", "browser": "https://google.com",
    "crunchyroll": "https://crunchyroll.com", "anilist": "https://anilist.co",
    "myanimelist": "https://myanimelist.net",
}

# ─── Runtime State ────────────────────────────────────────────────────────────
WAKE_KEY = "f2"
_recording_lock = threading.Lock()
mizune_manager = ManagerAgent(CFG)
mizune_manager.workers = {
    "system": SystemAgent(CFG),
    "web": WebAgent(CFG),
    "memory": MemoryAgent(CFG)
}
try:
    SAMPLE_RATE = int(sd.query_devices(sd.default.device[0], 'input')['default_samplerate'])

except:
    SAMPLE_RATE = 44100  # Fallback to standard HD audio
log_info(f"[SERVER] Audio capture sample rate set to: {SAMPLE_RATE} Hz")
RECORD_SECONDS = 6
connected_clients: list[WebSocket] = []
CHRONICLE = []
recognizer = sr.Recognizer()
is_active_listening = False
main_loop: Optional[asyncio.AbstractEventLoop] = None
LAST_WAKE_TIME = 0.0  # Cooldown tracker for wake word triggers
WAKE_COOLDOWN = 3.0   # Seconds to ignore re-triggers after a wake event


# ─── App Setup with Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    log_info("[SERVER] Backend initialized.")
    threading.Thread(target=hotkey_listener, daemon=True).start()
    threading.Thread(target=listen_for_wake_word, daemon=True).start()
    if CFG.get("streamer_mode") and CFG.get("twitch_channel"):
        threading.Thread(target=twitch_listener, daemon=True).start()
    log_info(f"[SERVER] {CFG.get('character_name','Mizune')} is awake and listening!")
    log_info(f"[SERVER] AI Model: {CFG.get('ai_model','gemini')} | Say wake word or press F2.")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── HTTP Endpoints ──────────────────────────────────────────────────────────
@app.get("/config")
async def get_config():
    """Frontend can request current config (without secret keys)."""
    safe = {k: v for k, v in CFG.items() if "key" not in k}
    return safe

@app.post("/reload-config")
async def reload_config():
    """Reload config from disk after settings save."""
    global CFG
    CFG = load_config()
    log_info("[CONFIG] Reloaded from disk.")
    broadcast_sync({"type": "config_reloaded", "character_file": CFG.get("character_file", "")})
    return {"status": "ok"}

@app.post("/chat")
async def chat_endpoint(payload: dict):
    """HTTP text chat endpoint (used by text input in the UI)."""
    text = payload.get("text", "").strip()
    if not text:
        return {"response": ""}
    res = process_command(text)
    broadcast_sync({"type": "speak", "text": res})
    return {"response": res}


# ─── Utility ────────────────────────────────────────────────────────────────
def broadcast_sync(message: dict):
    loop = main_loop
    if loop is None or loop.is_closed():
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
        assert loop is not None
        asyncio.run_coroutine_threadsafe(_send(), loop)
    except RuntimeError as e:
        log_info(f"[BROADCAST] Failed: {e}")


# ─── Microphone & STT ──────────────────────────────────────────────────────
def listen_to_microphone() -> Optional[str]:
    global is_active_listening
    if not _recording_lock.acquire(blocking=False):
        log_info("[MIC] Already recording, skipping...")
        return None

    try:
        log_info("[MIC] Starting recording...")
        broadcast_sync({"type": "status", "text": "Listening..."})
        is_active_listening = True

        with sr.Microphone() as source:
            # Disable dynamic thresholding which mutes quiet hardware
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold = 150 # Very sensitive

            log_info("[MIC] Ready and listening for speech...")
            audio = recognizer.listen(source, timeout=6.0, phrase_time_limit=15.0)

        log_info("[MIC] Recording finished. Processing...")
        broadcast_sync({"type": "status", "text": "Processing..."})

        # ── Primary attempt: Groq STT ──
        groq_api_key = CFG.get("groq_api_key")
        if groq_api_key and len(groq_api_key) > 5:
            try:
                import requests
                log_info("[MIC] Trying Groq STT...")
                wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
                files = {'file': ('audio.wav', wav_data, 'audio/wav')}
                data = {'model': 'whisper-large-v3', 'language': 'en'}
                headers = {'Authorization': f'Bearer {groq_api_key}'}
                response = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", files=files, data=data, headers=headers, timeout=7)
                if response.status_code == 200:
                    text = response.json().get('text', '').strip()
                    if text:
                        hallucinations = ["Thank you.", "Thank you", "Thanks.", "You're welcome.", "Bye.", "Amém", "Amen.", "Thank you!", "Good.", "Good"]
                        if text in hallucinations:
                            log_info(f"[MIC] Ignored hallucination: '{text}'")
                            return None
                        log_info(f"[MIC] Groq Recognized: '{text}'")
                        broadcast_sync({"type": "user_input", "text": text})
                        return text
                else:
                    log_info(f"[MIC] Groq STT error: {response.status_code} {response.text}")
            except Exception as e:
                log_info(f"[MIC] Groq STT exception: {e}")

        # ── Secondary attempt: Google STT ──
        try:
            text = recognizer.recognize_google(audio, language="en-IN")
            log_info(f"[MIC] Google Recognized: '{text}'")
            broadcast_sync({"type": "user_input", "text": text})
            return text
        except (sr.UnknownValueError, sr.RequestError) as e:
            log_info(f"[MIC] Google STT failed ({type(e).__name__}), trying Whisper fallback...")

            # ── Whisper Fallback ──
            if HAS_WHISPER:
                import numpy as np
                import io
                wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
                wav_stream = io.BytesIO(wav_bytes)
                with sr.AudioFile(wav_stream) as src:
                    audio_for_whisper = recognizer.record(src)

                audio_np = np.frombuffer(audio_for_whisper.frame_data, np.int16)
                audio_float32 = audio_np.astype(np.float32) / 32768.0

                segments, info = WHISPER_MODEL.transcribe(audio_float32, beam_size=5)
                text = " ".join([segment.text for segment in segments]).strip()

                if text:
                    log_info(f"[MIC] Whisper Recognized: '{text}'")
                    broadcast_sync({"type": "user_input", "text": text})
                    return text
                else:
                    log_info("[MIC] Whisper also could not understand audio.")
            else:
                log_info("[MIC] Whisper not available for fallback.")

            return None
    except sr.WaitTimeoutError:
        log_info("[MIC] WaitTimeoutError: No speech detected.")
        return None
    except Exception as e:
        log_info(f"[MIC] Unexpected error: {e}")
        return None
    finally:
        is_active_listening = False
        _recording_lock.release()


# ─── Command Logic ─────────────────────────────────────────────────────────
# ─── Coding Coach Monitor ──────────────────────────────────────────────────
_coding_monitor_running = threading.Event()
_coding_monitor_paused = threading.Event()
_last_coding_feedback = ""

CODING_COACH_PROMPT = """You are Mizune, an adorable anime AI coding coach watching Master's screen.
Analyze the screenshot and respond with ONE of these:

1. If you see a BUG or MISTAKE in the code: Point it out kindly in 1-2 sentences. Be specific about the line/issue.
2. If the code looks GOOD or they just SOLVED something: Praise them enthusiastically in 1 sentence!  
3. If they're IDLE or on a non-coding page: Say "[SKIP]" (nothing to comment on).
4. If the screen looks the SAME as before: Say "[SKIP]" (avoid repeating yourself).

Rules:
- Keep responses to 1-2 short sentences MAX (this will be spoken aloud)
- Use cute expressions like "Master~", "sugoi!", "gambatte!", "ara~"
- For hints: Give a gentle nudge, NOT the full solution
- Be encouraging, never harsh
- Say [SKIP] if there's nothing meaningful to say"""

CODING_HINT_PROMPT = """You are Mizune, an adorable anime AI coding coach. Master is stuck and asked for a hint.
Look at the screenshot and give ONE helpful hint in 1-2 sentences. 
Don't give the full solution — just a nudge in the right direction.
Use cute expressions like "Master~", "I think you should try...", "Hint: "
Keep it short since this will be spoken aloud."""


def _capture_screen_for_gemini():
    """Take a screenshot and return as bytes for Gemini Vision."""
    try:
        screenshot = pyautogui.screenshot()
        buf = io.BytesIO()
        screenshot.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()
    except Exception as e:
        log_info(f"[CODING] Screenshot failed: {e}")
        return None


def _analyze_screen_now(mode="review"):
    """Take a screenshot and analyze it with Gemini Vision immediately."""
    global _last_coding_feedback
    
    image_bytes = _capture_screen_for_gemini()
    if not image_bytes:
        return
    
    api_key = CFG.get("gemini_api_key", "")
    prompt = CODING_HINT_PROMPT if mode == "hint" else CODING_COACH_PROMPT
    feedback = None
    
    # ── Try 1: Groq Vision (free, fast, reliable) ──
    groq_key = CFG.get("groq_api_key", "")
    if groq_key and not feedback:
        try:
            import base64
            from openai import OpenAI
            
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            
            resp = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ]
                }],
                max_tokens=200
            )
            feedback = (resp.choices[0].message.content or "").strip()
            log_info(f"[CODING] Groq Vision success!")
        except Exception as e:
            log_info(f"[CODING] Groq Vision failed: {e}")
    
    # ── Try 2: Gemini Vision (fallback) ──
    api_key = CFG.get("gemini_api_key", "")
    if api_key and not feedback:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            for model in ["gemini-2.0-flash", "gemini-2.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            types.Part.from_text(text=prompt)
                        ]
                    )
                    feedback = (response.text or "").strip()
                    log_info(f"[CODING] {model} success!")
                    break
                except Exception as model_err:
                    err_str = str(model_err).lower()
                    if "503" in err_str or "429" in err_str or "quota" in err_str:
                        continue
                    raise
        except Exception as e:
            log_info(f"[CODING] Gemini Vision failed: {e}")
    
    if not feedback or "[SKIP]" in feedback:
        return
    
    # Avoid repeating the same feedback
    if feedback == _last_coding_feedback:
        return
    
    _last_coding_feedback = feedback
    log_info(f"[CODING] Feedback: {feedback}")
    broadcast_sync({"type": "speak", "text": feedback})


def _coding_monitor_loop():
    """Background loop: captures screen every 30s → Gemini Vision → feedback."""
    log_info("[CODING] Monitor loop started — watching Master's screen!")
    interval = 30  # seconds between screen reads (balanced: not too spammy, not too slow)
    
    while _coding_monitor_running.is_set():
        # Check if paused
        if _coding_monitor_paused.is_set():
            time.sleep(2)
            continue
        
        # Wait the interval, but check for stop every second
        for _ in range(interval):
            if not _coding_monitor_running.is_set():
                break
            time.sleep(1)
        
        if not _coding_monitor_running.is_set():
            break
        if _coding_monitor_paused.is_set():
            continue
        
        _analyze_screen_now("review")
    
    log_info("[CODING] Monitor loop stopped")





def process_command(text: str) -> str:
    global CHRONICLE
    log_info(f"[COMMAND] Processing: '{text}'")
    lower_text = text.lower().strip()

    # Emotion detection — send to frontend for facial expression
    emotion = detect_emotion(text)
    if emotion != "neutral":
        broadcast_sync({"type": "emotion", "emotion": emotion})

    # Maintain Memory Buffer (configurable size)
    memory_size = int(CFG.get("memory_size", 30))
    CHRONICLE.append({"role": "user", "parts": [{"text": text}]})
    if len(CHRONICLE) > memory_size:
        CHRONICLE.pop(0)

    try:
        # ── 0. Route through the Multi-Agent Brain ──
        # We use asyncio.run because process_command is synchronous but agents are async
        res = asyncio.run(mizune_manager.execute(text, context={"history": CHRONICLE}))

        # Broadcast current mode to frontend
        broadcast_sync({"type": "mode", "mode": mizune_manager.current_mode})

        # If the manager handled it, return the result
        if res is not None:
            # Handle coding mode special commands
            if "[CODING_PAUSE]" in str(res):
                _coding_monitor_paused.set()
                res = res.replace("[CODING_PAUSE] ", "")
            elif "[CODING_RESUME]" in str(res):
                _coding_monitor_paused.clear()
                res = res.replace("[CODING_RESUME] ", "")
            elif "[CODING_REVIEW_NOW]" in str(res):
                res = res.replace("[CODING_REVIEW_NOW] ", "")
                threading.Thread(target=_analyze_screen_now, daemon=True).start()
            elif "[CODING_HINT]" in str(res):
                res = res.replace("[CODING_HINT] ", "")
                threading.Thread(target=_analyze_screen_now, args=("hint",), daemon=True).start()

            # Start/stop coding monitor on mode change
            if mizune_manager.current_mode == "coding" and not _coding_monitor_running.is_set():
                _coding_monitor_running.set()
                _coding_monitor_paused.clear()
                threading.Thread(target=_coding_monitor_loop, daemon=True).start()
                log_info("[CODING] Screen monitor started!")
            elif mizune_manager.current_mode != "coding" and _coding_monitor_running.is_set():
                _coding_monitor_running.clear()
                log_info("[CODING] Screen monitor stopped.")

            # Update history with response
            CHRONICLE.append({"role": "model", "parts": [{"text": res}]})
            if len(CHRONICLE) > memory_size:
                CHRONICLE.pop(0)
            return res

        # ── 1. Built-in time/date/weather (Zero Token Cost) ──
        if re.search(r"\b(what(?:'s| is)(?: the)? (?:time|current time)|time is it|tell me the time)\b", lower_text):
            now = time.strftime("%I:%M %p")
            return f"It's {now}, Master!"
        elif re.search(r"\b(what(?:'s| is)(?: the)? (?:date|today(?:'s)? date|day)|what day is it)\b", lower_text):
            today = time.strftime("%A, %B %d, %Y")
            return f"Today is {today}, Master!"
        elif re.search(r"\b(weather|temperature|how(?:'s| is)(?: the)? weather|forecast)\b", lower_text):
            # Extract city/location from the full query
            # Handles: "weather hyderabad chevella", "weather in tokyo", "how's the weather in london"
            city_match = re.search(r"(?:weather|forecast|temperature)\s+(?:in|at|for|of)?\s*([a-zA-Z\s]+)", lower_text)
            if not city_match:
                # Try extracting everything after "weather"
                city_match = re.search(r"(?:weather|forecast|temperature)\s+(.+)", lower_text)
            city = city_match.group(1).strip() if city_match else "Hyderabad"
            city = city if city else "Hyderabad"  # Default fallback
            
            log_info(f"[WEATHER] Fetching weather for: {city}")
            try:
                import requests
                
                # ── Primary: Open-Meteo (free, no API key, very reliable) ──
                # Step 1: Geocode the city name to lat/lon
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city.replace(' ', '+')}&count=1&language=en"
                log_info(f"[WEATHER] Geocoding: {geo_url}")
                geo_resp = requests.get(geo_url, timeout=5)
                
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    results = geo_data.get("results", [])
                    
                    if results:
                        loc = results[0]
                        lat = loc["latitude"]
                        lon = loc["longitude"]
                        loc_name = loc.get("name", city)
                        loc_region = loc.get("admin1", "")
                        loc_country = loc.get("country", "")
                        
                        # Step 2: Fetch current weather
                        weather_url = (
                            f"https://api.open-meteo.com/v1/forecast?"
                            f"latitude={lat}&longitude={lon}"
                            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                            f"weather_code,wind_speed_10m"
                            f"&timezone=auto"
                        )
                        w_resp = requests.get(weather_url, timeout=5)
                        
                        if w_resp.status_code == 200:
                            w_data = w_resp.json()
                            current = w_data.get("current", {})
                            temp = current.get("temperature_2m", "?")
                            feels = current.get("apparent_temperature", "?")
                            humidity = current.get("relative_humidity_2m", "?")
                            wind = current.get("wind_speed_10m", "?")
                            wmo_code = current.get("weather_code", 0)
                            
                            # WMO weather codes to descriptions
                            wmo_desc = {
                                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                                45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
                                55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
                                71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Light showers",
                                81: "Showers", 82: "Heavy showers", 95: "Thunderstorm",
                                96: "Thunderstorm with hail", 99: "Heavy thunderstorm with hail",
                            }
                            desc = wmo_desc.get(wmo_code, "Unknown conditions")
                            
                            location_str = loc_name
                            if loc_region:
                                location_str += f", {loc_region}"
                            
                            weather_msg = (
                                f"The weather in {location_str} right now: "
                                f"{desc}, {temp}°C (feels like {feels}°C). "
                                f"Humidity is {humidity}% and wind is {wind} km/h, Master~!"
                            )
                            return weather_msg
                    
                    log_info(f"[WEATHER] No geocoding results for '{city}'")
                    return f"I couldn't find a place called '{city}', Master. Could you try a different name?"
                
                log_info(f"[WEATHER] Geocoding API returned {geo_resp.status_code}")
                return f"I couldn't look up the weather right now, Master. The service seems down!"
            except Exception as e:
                log_info(f"[WEATHER] Error: {e}")
                return f"Gomen ne, Master! I had trouble checking the weather: {e}"

        # ── 1. System & Media Commands (Zero Token Cost) ──
        if re.search(r"\b(lock|lock screen|lock pc)\b", lower_text):
            log_info("[ACTION] Locking PC...")
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return "Locking your PC!"
        elif re.search(r"\b(sleep|put pc to sleep|sleep pc)\b", lower_text):
            log_info("[ACTION] Sleeping PC...")
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return "Putting your PC to sleep. Goodnight!"
        elif re.search(r"\b(screenshot|screen shot|take a screenshot)\b", lower_text):
            log_info("[ACTION] Taking screenshot...")
            try:
                img = pyautogui.screenshot()
                ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"mizune_screenshot_{int(time.time())}.png")
                img.save(ss_path)
                return "I took a screenshot and saved it to your desktop, Master~!"
            except Exception as e:
                log_info(f"[ACTION] Screenshot failed: {e}")
                return "I'm sorry, my screenshot tool failed."
        elif re.search(r"\b(volume up|turn up volume|increase volume)\b", lower_text):
            log_info("[ACTION] Volume up...")
            for _ in range(5): keyboard.send('volume up')
            return "Turning it up!"
        elif re.search(r"\b(volume down|turn down volume|decrease volume|lower volume)\b", lower_text):
            log_info("[ACTION] Volume down...")
            for _ in range(5): keyboard.send('volume down')
            return "Turning the volume down."
        elif re.search(r"\b(mute|unmute)\b", lower_text):
            log_info("[ACTION] Toggling mute...")
            keyboard.send('volume mute')
            return "Toggling your volume mute."
        elif re.search(r"\b(play|pause)\b", lower_text) and not re.search(r"\b(open|search)\b", lower_text):
            log_info("[ACTION] Media play/pause...")
            keyboard.send('play/pause media')
            return "Toggling media playback!"
        elif re.search(r"\b(next|skip)\b", lower_text) and re.search(r"\b(song|track|music)\b", lower_text):
            log_info("[ACTION] Media next...")
            keyboard.send('next track')
            return "Skipping to the next track!"
        elif re.search(r"\b(previous|last|back)\b", lower_text) and re.search(r"\b(song|track|music)\b", lower_text):
            log_info("[ACTION] Media previous...")
            keyboard.send('previous track')
            return "Going back a track!"

        # ── 2. URL Opening (Zero Token Cost) ──
        url_match = re.search(
            r"(?:open|go to|visit|navigate to)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|dev|ai|app))",
            lower_text
        )
        if url_match:
            url = url_match.group(1)
            if not url.startswith('http'):
                url = 'https://' + url
            log_info(f"[ACTION] Opening URL: {url}")
            webbrowser.open(url)
            return "Opening that in your browser right now!"

        # ── 3. Spotify Specific Song Search (Zero Token Cost) ──
        spotify_search = re.search(r"(?:play|put on|search for)\s+(.+?)\s+(?:on|in)\s+(?:spotify|spotify web player)", lower_text)
        if not spotify_search:
            spotify_search = re.search(r"search\s+(.+?)\s+(?:on|in)\s+(?:spotify)", lower_text)
            
        if spotify_search:
            song_query = spotify_search.group(1).strip()
            import urllib.parse
            encoded = urllib.parse.quote(song_query)
            log_info(f"[ACTION] Searching Spotify Web Player for: {song_query}")
            try:
                subprocess.Popen(f'start brave "https://open.spotify.com/search/{encoded}"', shell=True)
            except Exception as e: pass
            return f"Playing {song_query} on Spotify right now!"

        # ── 3b. Netflix / Streaming Service Search (Zero Token Cost) ──
        import urllib.parse
        
        # Netflix: "search sakamoto days on netflix", "find one piece on netflix"
        netflix_search = re.search(
            r"(?:search|find|play|watch|look for|open)\s+(.+?)\s+(?:on|in)\s+netflix",
            lower_text
        )
        if not netflix_search:
            netflix_search = re.search(r"netflix\s+(?:search|find|play|watch)\s+(.+)", lower_text)
        if netflix_search:
            query = netflix_search.group(1).strip()
            encoded = urllib.parse.quote(query)
            log_info(f"[ACTION] Searching Netflix for: {query}")
            webbrowser.open(f"https://www.netflix.com/search?q={encoded}")
            return f"Searching for {query} on Netflix, Master~!"

        # Crunchyroll: "search naruto on crunchyroll"
        cr_search = re.search(
            r"(?:search|find|play|watch|look for)\s+(.+?)\s+(?:on|in)\s+crunchyroll",
            lower_text
        )
        if cr_search:
            query = cr_search.group(1).strip()
            encoded = urllib.parse.quote(query)
            log_info(f"[ACTION] Searching Crunchyroll for: {query}")
            webbrowser.open(f"https://www.crunchyroll.com/search?q={encoded}")
            return f"Searching for {query} on Crunchyroll, Master~!"

        # Amazon Prime: "search reacher on prime", "find it on amazon prime"
        prime_search = re.search(
            r"(?:search|find|play|watch|look for)\s+(.+?)\s+(?:on|in)\s+(?:prime|amazon prime|prime video)",
            lower_text
        )
        if prime_search:
            query = prime_search.group(1).strip()
            encoded = urllib.parse.quote(query)
            log_info(f"[ACTION] Searching Prime Video for: {query}")
            webbrowser.open(f"https://www.primevideo.com/search?phrase={encoded}")
            return f"Searching for {query} on Prime Video, Master~!"

        # ── 4. App Launch / Close (Zero Token Cost) ──
        app_match = re.search(r"open\s+([a-zA-Z0-9\s]+)", lower_text)
        if app_match and not re.search(r"youtube|google|browser", lower_text):
            target = app_match.group(1).strip().lower()
            # Exact match first, then partial match in COMMON_APPS keys
            if target in COMMON_APPS or target in ("spotify", "spotify in browser", "spotify web", "spotify web player", "music"):
                launch_app(target)
                return f"Opening {target} for you right away!"
            else:
                # Partial match: e.g. "open brave browser" → matches "brave"
                # Sort by longest key first and require min 3 chars to avoid false positives
                sorted_keys = sorted(COMMON_APPS.keys(), key=len, reverse=True)
                partial = next((k for k in sorted_keys if len(k) >= 3 and (k in target or target in k)), None)
                if partial:
                    launch_app(partial)
                    return f"Opening {partial} for you right away!"
                
        close_match = re.search(r"(?:close|exit|terminate|kill)\s+([a-zA-Z0-9\s]+)", lower_text)
        if close_match:
            target = close_match.group(1).strip().lower()
            if target in COMMON_APPS or target in ("spotify", "music", "brave", "chrome", "notepad"):
                close_app(target)
                return f"Closing {target} now!"
            else:
                sorted_keys = sorted(COMMON_APPS.keys(), key=len, reverse=True)
                partial = next((k for k in sorted_keys if len(k) >= 3 and (k in target or target in k)), None)
                if partial:
                    close_app(partial)
                    return f"Closing {target} now!"

        # ── 5. AI Text Generation ──
        log_info(f"[AI] Generating response ({CFG.get('ai_model','gemini')})...")
        original_res = get_ai_response(text, CHRONICLE)
        clean_res = original_res

        # Update history with response
        CHRONICLE.append({"role": "model", "parts": [{"text": original_res}]})
        if len(CHRONICLE) > memory_size:
            CHRONICLE.pop(0)

        # ── 6. Parse Note/App Tags from AI Response ──
        # Process [ACTION: OPEN app]
        for open_match in re.finditer(r"\[ACTION:\s*OPEN\s+([^\]]+)\]", original_res, re.IGNORECASE):
            app_req = open_match.group(1).strip().lower()
            launch_app(app_req)
        # Process [ACTION: CLOSE app]
        for close_match in re.finditer(r"\[ACTION:\s*CLOSE\s+([^\]]+)\]", original_res, re.IGNORECASE):
            app_req = close_match.group(1).strip().lower()
            close_app(app_req)
        # Process [ACTION: SLEEP]
        if "[ACTION: SLEEP]" in original_res.upper():
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            
        note_match = re.search(r"\[ACTION:\s*NOTE\s+([^\]]+)\]", original_res, re.IGNORECASE)
        if not note_match:
            # Only match explicit note-taking requests, not random words
            note_match = re.search(r"(?:write down|take (?:a )?note|save (?:a )?note|jot down|note down|remember that)\s+(.+)", lower_text)
        if note_match:
            note_content = note_match.group(1).strip()
            if take_note(note_content):
                clean_res = re.sub(r"\[ACTION:\s*NOTE.*?\]", "", clean_res).strip()
                if "Saved to Desktop" not in clean_res:
                    clean_res += " (Note saved to Desktop!)"
                    
        # Clean up all leftover ACTION tags for TTS
        clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res).strip()

        # ── 7. Smart Search — YouTube Auto-Play / Specific site + specific browser ──
        # Pattern: "search <query> on youtube in brave" or "play <query> on youtube"
        smart_search = re.search(
            r"(?:search|search for|look up|find|play)\s+(.+?)\s+(?:on|in)\s+(youtube|google|reddit|bing)"
            r"(?:\s+(?:on|in)\s+(brave|chrome|firefox|edge|opera))?",
            lower_text
        )
        if not smart_search:
            smart_search = re.search(
                r"(?:search|search for|look up|find|play)\s+(.+?)\s+(?:on|in)\s+(brave|chrome|firefox|edge|opera)"
                r"(?:\s+(?:on|in)\s+(youtube|google|reddit|bing))?",
                lower_text
            )
            if smart_search:
                query = smart_search.group(1).strip()
                browser_name = smart_search.group(2).strip()
                site = smart_search.group(3).strip() if smart_search.group(3) else None
                smart_search = None
            else:
                query, browser_name, site = None, None, None
        else:
            query = smart_search.group(1).strip()
            site = smart_search.group(2).strip()
            browser_name = smart_search.group(3).strip() if smart_search.group(3) else None
            smart_search = None
            
        if query and site:
            import urllib.parse
            import urllib.request
            encoded = urllib.parse.quote(query)
            
            if site == 'youtube':
                log_info(f"[ACTION] Searching YouTube to auto-play: {query}")
                try:
                    # Fetch search results page to find top video
                    req = urllib.request.Request(f"https://www.youtube.com/results?search_query={encoded}", headers={'User-Agent': 'Mozilla/5.0'})
                    html = urllib.request.urlopen(req).read().decode('utf-8')
                    video_ids = re.findall(r"watch\?v=(\S{11})", html)
                    if video_ids:
                        url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                        log_info(f"[ACTION] Found video: {url}")
                    else:
                        url = f"https://www.youtube.com/results?search_query={encoded}"
                except Exception as e:
                    log_info(f"[YT ERROR] {e}")
                    url = f"https://www.youtube.com/results?search_query={encoded}"
            elif site == 'reddit':
                url = f"https://www.reddit.com/search/?q={encoded}"
            elif site == 'bing':
                url = f"https://www.bing.com/search?q={encoded}"
            else:
                url = f"https://www.google.com/search?q={encoded}"
                
            log_info(f"[ACTION] Launching URL: {url} via {browser_name or 'default'}")
            if browser_name:
                browser_exe = COMMON_APPS.get(browser_name, browser_name)
                try:
                    subprocess.Popen(f'start {browser_exe} "{url}"', shell=True)
                except Exception:
                    webbrowser.open(url)
            else:
                webbrowser.open(url)
                
            return f"{'Playing' if site == 'youtube' else 'Searching for'} {query} on {site.capitalize()}!"

        # ── 8. Generic Search Fallback ──
        search_match = re.search(r"(?:search|search for|google|look up)\s+(.+)", lower_text)
        if search_match:
            query = search_match.group(1).strip()
            log_info(f"[ACTION] Searching: {query}")
            webbrowser.open(f"https://www.google.com/search?q={query}")
            return f"Looking up {query} on Google!"

        return clean_res

    except Exception as e:
        log_info(f"[AI] Error: {type(e).__name__}: {e}")
        error_str = str(e).lower()
        if "quota" in error_str or "exhausted" in error_str or "429" in error_str:
            if CFG.get("openai_api_key"):
                log_info("[AI] Gemini quota exhausted! Automatically falling back to OpenAI.")
                try:
                    personality = CFG.get("personality", DEFAULT_CONFIG["personality"])
                    action_addendum = (
                        " You have full control over the user's PC via [ACTION: OPEN app_name] tags. "
                        "You can open: Brave, Chrome, Firefox, Edge, VS Code, Terminal, Discord, Spotify, "
                        "Telegram, WhatsApp, Steam, OBS, Blender, Figma, Excel, Word, PowerPoint, Outlook, "
                        "Teams, Slack, Task Manager, Settings, Calculator, Paint, Notepad, File Explorer, "
                        "YouTube, GitHub, Gmail, ChatGPT, Twitter, Reddit, Instagram, Netflix, and more. "
                        "You can also: take screenshots, lock the PC, control volume (up/down/mute), and search the web. "
                        "If the user asks to open something, ALWAYS include [ACTION: OPEN app_name] in your response. "
                        "If the user asks to write, note, or type something down, use [ACTION: NOTE text_to_write] "
                        "and include the full text they want written. "
                        "Refer to yourself as " + CFG.get("character_name", "Mizune") + ". Be polite but charismatic and cute."
                    )
                    system_prompt = personality + action_addendum
                    
                    fallback_res = _openai_response(text, CHRONICLE, system_prompt)
                    CHRONICLE.append({"role": "model", "parts": [{"text": fallback_res}]})
                    if len(CHRONICLE) > int(CFG.get("memory_size", 30)):
                        CHRONICLE.pop(0)
                    return fallback_res
                except Exception as ex2:
                    log_info(f"[AI] OpenAI Fallback failed: {ex2}")
            return "My brain quota is temporarily exhausted! Please wait a minute and try again."
        if "invalid" in error_str and ("api" in error_str or "key" in error_str):
            return "My API key seems invalid. Please open Settings and check it."
        return "Hmm, my brain glitched! Let me try to remember..."


def take_note(content: str) -> bool:
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        char_name = CFG.get("character_name", "mizune").lower()
        notes_file = os.path.join(desktop_path, f"{char_name}_notes.txt")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {content}\n")
        log_info(f"[ACTION] Note saved: {content}")
        subprocess.Popen(f'start notepad.exe "{notes_file}"', shell=True)
        return True
    except Exception as e:
        log_info(f"[ACTION] Failed to save note: {e}")
        return False


def launch_app(target: str):
    if target in ("spotify", "spotify in browser", "spotify web", "spotify web player", "music"):
        log_info("[ACTION] Launching Spotify in Brave browser")
        try:
            subprocess.Popen('start brave "https://open.spotify.com/"', shell=True)
        except Exception as e:
            log_info(f"[ACTION] Failed to launch Brave: {e}")
        return

    exe = COMMON_APPS.get(target, target)
    log_info(f"[ACTION] Launching: {exe}")
    if exe.startswith("http") or exe.startswith("ms-"):
        webbrowser.open(exe)
    else:
        try:
            subprocess.Popen(f"start {exe}", shell=True)
        except Exception as e:
            log_info(f"[ACTION] Failed to launch '{exe}': {e}")
            
def close_app(target: str):
    exe = COMMON_APPS.get(target, target)
    # Extract just the filename if it's a full path or URL
    if exe.startswith("http") or exe.startswith("ms-"):
        return # Cannot taskkill URLs or UWP apps easily via taskkill
    
    if not exe.endswith(".exe"):
        exe += ".exe"
        
    log_info(f"[ACTION] Closing: {exe}")
    try:
        subprocess.Popen(f"taskkill /IM {exe} /F", shell=True)
    except Exception as e:
        log_info(f"[ACTION] Failed to close '{exe}': {e}")


# ─── Twitch Streamer Mode ───────────────────────────────────────────────────
def twitch_listener():
    """Basic Twitch IRC chat listener for streamer mode."""
    import socket
    channel = CFG.get("twitch_channel", "").lower().strip()
    if not channel:
        return
    log_info(f"[TWITCH] Connecting to #{channel}...")
    try:
        sock = socket.socket()
        sock.connect(("irc.chat.twitch.tv", 6667))
        sock.send(b"PASS oauth:your_token_here\r\n")
        sock.send(f"NICK justinfan12345\r\n".encode())
        sock.send(f"JOIN #{channel}\r\n".encode())
        sock.settimeout(1.0)
        log_info(f"[TWITCH] Joined #{channel} as anonymous viewer.")
        while True:
            try:
                data = sock.recv(2048).decode("utf-8", errors="ignore")
                if "PING" in data:
                    sock.send(b"PONG :tmi.twitch.tv\r\n")
                    continue
                match = re.search(r":(\w+)!\w+@\S+ PRIVMSG #\S+ :(.+)", data)
                if match:
                    user = match.group(1)
                    msg = match.group(2).strip()
                    if msg.startswith("!risse ") or msg.startswith("!ai "):
                        cmd = msg.split(" ", 1)[1] if " " in msg else ""
                        if cmd:
                            log_info(f"[TWITCH] {user}: {cmd}")
                            broadcast_sync({"type": "user_input", "text": f"[Chat: {user}] {cmd}"})
                            res = process_command(f"{user} from chat says: {cmd}")
                            broadcast_sync({"type": "speak", "text": res})
            except socket.timeout:
                continue
            except Exception as e:
                log_info(f"[TWITCH] Error: {e}")
                time.sleep(5)
    except Exception as e:
        log_info(f"[TWITCH] Failed to connect: {e}")


# ─── Listeners ─────────────────────────────────────────────────────────────
def on_f2_pressed(pre_text: Optional[str] = None):
    log_info("[TRIGGER] Processing voice command...")
    text = pre_text if (pre_text and len(pre_text) > 2) else listen_to_microphone()

    if text:
        broadcast_sync({"type": "status", "text": "Thinking..."})
        res = process_command(text)
        log_info(f"[RESPONSE] Speaking: {res}")
        broadcast_sync({"type": "speak", "text": res})
        # Reset status light to idle after response
        time.sleep(0.5)
        broadcast_sync({"type": "status", "text": "Idle"})
    else:
        log_info("[TRIGGER] No command text, going IDLE.")
        broadcast_sync({"type": "status", "text": f"Idle. Say wake word or press F2."})


def hotkey_listener():
    log_info(f"[HOTKEY] Listening for '{WAKE_KEY}'...")
    keyboard.add_hotkey(WAKE_KEY, lambda: threading.Thread(target=on_f2_pressed, daemon=True).start())
    keyboard.wait()


def listen_for_wake_word():
    global is_active_listening

    # Build wake word list from config + phonetic variants
    wake_words = list(CFG.get("wake_words", ["mizune", "misune", "mizuna", "mizu", "missy", "darling", "baka"]))
    custom = CFG.get("custom_wake_word", "").strip().lower()
    if custom and custom not in wake_words:
        wake_words.insert(0, custom)

    # Add common phonetic misrecognitions for "mizune"
    PHONETIC_VARIANTS = [
        "mizune", "misune", "mizuna", "mizu", "missy", "mizun", "mezune",
        "mezu", "mizuney", "mizunee", "museum", "my zone", "my soon",
        "me soon", "missile", "mizzy", "misune", "medicine", "miss you",
        "miss uni", "miss une", "mizuki", "mitsune", "mizone", "mizoon",
        "darling", "baka", "bakka", "bakkaa", "bokeh", "boca", "baca",
        "maca", "paka", "kaka", "baker", "barker", "becca", "pakka",
        "banka", "bakra", "bagha", "baga"
    ]
    all_wake_words = list(set(wake_words + PHONETIC_VARIANTS))
    log_info(f"[WAKE] Wake words ({len(all_wake_words)}): {wake_words[:8]}... + phonetic variants")

    def levenshtein(a: str, b: str) -> int:
        """Simple edit distance for fuzzy matching."""
        if len(a) < len(b):
            return levenshtein(b, a)
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return prev[-1]

    def fuzzy_match_wake(heard_text: str) -> Optional[str]:
        """Check if any word in heard text matches a wake word (exact, contains, or fuzzy)."""
        # Remove punctuation and common filler words that might interfere
        clean_text = re.sub(r'[^\w\s]', '', heard_text)
        words = clean_text.split()

        # 1. Exact word match (Highest Priority)
        for word in words:
            if word in all_wake_words:
                return word

        # 2. Contains match - check if wake word is embedded (e.g., "hey mizzune")
        for wake in all_wake_words:
            if wake in clean_text:
                return wake

        # 3. Fuzzy match: allow distance based on word length
        for word in words:
            if len(word) < 3:
                continue
            for wake in all_wake_words:
                # Be stricter with short words, more lenient with long ones
                max_dist = 1 if len(wake) <= 5 else 2
                if levenshtein(word, wake) <= max_dist:
                    log_info(f"[WAKE] Fuzzy matched '{word}' → '{wake}'")
                    return wake
        return None

    while True:
        # CRITICAL: Only listen for wake word if no one is currently recording a command
        if is_active_listening:
            time.sleep(0.5)
            continue
        try:
            with sr.Microphone() as source:
                # Disable dynamic thresholding which mutes quiet hardware
                recognizer.dynamic_energy_threshold = False
                recognizer.energy_threshold = 150 # Very sensitive

                # Listen in chunks so we can check is_active_listening frequently
                audio = recognizer.listen(source, timeout=0.1, phrase_time_limit=3)

            try:
                # Use en-IN to drastically improve accuracy for Indian accents & transliterated Hindi/Telugu words
                raw_text = recognizer.recognize_google(audio, language="en-IN").lower()
                log_info(f"[WAKE] Heard: '{raw_text}'")

                matched_wake = fuzzy_match_wake(raw_text)

                if matched_wake:
                    # ── Cooldown: ignore rapid re-triggers ──
                    now_ts = time.time()
                    global LAST_WAKE_TIME
                    if now_ts - LAST_WAKE_TIME < WAKE_COOLDOWN:
                        log_info(f"[WAKE] Cooldown active — ignoring re-trigger for '{matched_wake}'")
                    else:
                        LAST_WAKE_TIME = now_ts
                        log_info(f"[WAKE] TRIGGER: '{raw_text}' matched '{matched_wake}'")
                        broadcast_sync({"type": "status", "text": "Triggered"})
                        cmd_part = ""
                        # Try to extract command after the wake word
                        for wake in all_wake_words:
                            if wake in raw_text:
                                parts = raw_text.split(wake, 1)
                                if len(parts) > 1:
                                    cmd_part = parts[-1].strip()
                                    break

                        if cmd_part and len(cmd_part) > 2:
                            log_info(f"[WAKE] Instant Command: '{cmd_part}'")
                            broadcast_sync({"type": "user_input", "text": f"(Wake) {cmd_part}"})
                            broadcast_sync({"type": "status", "text": "Processing..."})
                            # Run on_f2_pressed in a new thread to avoid blocking the wake word loop
                            threading.Thread(target=on_f2_pressed, args=(cmd_part,), daemon=True).start()
                            # Sleep to allow recording to start and prevent immediate re-trigger
                            time.sleep(1)
                        else:
                            log_info("[WAKE] Listen mode triggered")
                            broadcast_sync({"type": "status", "text": "Listening..."})
                            threading.Thread(target=on_f2_pressed, daemon=True).start()
                            # Sleep for the duration of the recording to prevent overlap
                            time.sleep(RECORD_SECONDS + 1)
                            broadcast_sync({"type": "status", "text": "Idle"})

            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                pass
        except sr.WaitTimeoutError:
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
            data = await websocket.receive_text()
            # Handle text messages sent from frontend chat input
            try:
                msg = json.loads(data)
                if msg.get("type") == "chat":
                    text = msg.get("text", "").strip()
                    if text:
                        broadcast_sync({"type": "user_input", "text": text})
                        broadcast_sync({"type": "status", "text": "Thinking..."})

                        # Use a proper async task for processing
                        async def handle_chat():
                            # process_command is sync, but we can run it in a thread
                            res = await asyncio.to_thread(process_command, text)
                            broadcast_sync({"type": "speak", "text": res})
                            broadcast_sync({"type": "status", "text": "Idle"})

                        asyncio.create_task(handle_chat())
            except Exception as e:
                log_info(f"[WS] Error processing message: {e}")

    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        log_info("[WS] Client disconnected.")


if __name__ == "__main__":
    import socket

    PORT = 8000

    # Check if port is already in use
    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    if is_port_in_use(PORT):
        log_info(f"[SERVER] ERROR: Port {PORT} is already in use!")
        log_info(f"[SERVER] Another instance of Risse may be running.")
        log_info(f"[SERVER] Close it first or run: taskkill /f /im python.exe")
        input("Press Enter to exit...")
        exit(1)

    log_info("=" * 50)
    log_info(f"[SERVER] Starting {CFG.get('character_name','Mizune')} backend on port {PORT}...")
    log_info(f"[SERVER] AI Model: {CFG.get('ai_model','gemini')}")
    log_info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
