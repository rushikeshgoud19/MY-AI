import os
import json
import logging
from logging.handlers import RotatingFileHandler

__all__ = ["CONFIG_PATH", "DEFAULT_CONFIG", "load_config", "_validate_config", "log_info"]

# Set up logging for the module
logger = logging.getLogger("mizune")
logger.setLevel(logging.INFO)

log_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server_debug.log")
file_handler = RotatingFileHandler(_LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

_ws_callback = None

def set_log_callback(cb):
    global _ws_callback
    _ws_callback = cb

def log_info(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(str(msg).encode('ascii', 'replace').decode('ascii'))
    logger.info(msg)
    if _ws_callback:
        # Prevent recursive logging loops if websocket fails
        try:
            _ws_callback(msg)
        except Exception:
            pass

# ─── Configuration & Defaults ────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

DEFAULT_CONFIG = {
    "character_name": "Mizune",
    "character_file": "",
    "character_color": "#a777e3",
    "ai_model": "nvidia",
    "gemini_api_key": "",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "openrouter_api_key": "",
    "openrouter_model": "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia_api_key": "",
    "groq_api_key": "",
    "opencode_api_key": "",
    "system_prompt": "You are {character_name}, an AI assistant. You are helpful, polite, and eager to assist.",
    "personality": "You are {character_name}, an AI assistant. You are helpful, polite, and eager to assist.",
    "elevenlabs_api_key": "",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Default Rachel voice
    "edge_tts_voice": "ja-JP-NanamiNeural",
    "wake_words": [
        "mizune",
        "misune",
        "mizuna",
        "mizu",
        "missy",
        "darling",
        "baka"
    ],
    "custom_wake_word": "",
    "wake_language": "en-IN",
    "wake_energy_threshold": 180,
    "wake_dynamic_energy": True,
    "wake_phrase_time_limit": 4.5,
    "wake_timeout": 6.0,
    "wake_adjust_noise_sec": 0.3,
    "wake_cooldown_sec": 3.0,
    "record_seconds": 6,
    "mic_device_index": None,
    "vision_mode_interval": 15,
    "memory_size": 30,
    "discord_webhook": "",
    "data_collection_enabled": False,
    "data_collection_interval_sec": 10,
    "data_collection_screen_scale": 1.0,
    "data_collection_capture_camera": True,
    "data_collection_use_time_features": True,
    "streamer_mode": False,
    "twitch_channel": "",
    "coding_monitor_interval": 30,
    "obsidian_vault_path": "",
    "proactive_enabled": True,
    "proactive_interval_minutes": 15
}

def _validate_config(cfg: dict) -> dict:
    """Ensure all default keys exist in config, filling in missing ones."""
    changed = False
    for key, val in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = val
            changed = True
    
    # Handle array types correctly
    if not isinstance(cfg.get("wake_words"), list):
        cfg["wake_words"] = DEFAULT_CONFIG["wake_words"]
        changed = True
        
    return changed

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                
            # Migrate any missing keys automatically
            if _validate_config(cfg):
                log_info("[CONFIG] Migrating config.json to include new default settings.")
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
                    
            return cfg
        except Exception as e:
            log_info(f"[CONFIG] Error loading config.json: {e}. Using defaults.")
            return DEFAULT_CONFIG.copy()
    else:
        log_info("[CONFIG] config.json not found. Creating default config.")
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()
