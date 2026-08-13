import os
import json
import logging
from logging.handlers import RotatingFileHandler

__all__ = ["CONFIG_PATH", "DEFAULT_CONFIG", "load_config", "_validate_config", "log_info", "is_cloud_mode",
           "mizune_tz", "mizune_now"]

# ── Canonical clock ─────────────────────────────────────────────────────
# The VM runs in UTC but Master lives in IST; every user-facing time must go
# through these helpers or reminders/answers drift by 5h30m.
_TZ_CACHE = None

def mizune_tz():
    """Master's timezone (config key 'timezone', default Asia/Kolkata)."""
    global _TZ_CACHE
    if _TZ_CACHE is None:
        import datetime as _dt
        name = "Asia/Kolkata"
        try:
            name = load_config().get("timezone", name)
        except Exception:
            pass
        try:
            import zoneinfo
            _TZ_CACHE = zoneinfo.ZoneInfo(name)
        except Exception:
            # IST has no DST, so a fixed offset fallback is exact.
            _TZ_CACHE = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    return _TZ_CACHE

def mizune_now():
    """Timezone-aware 'now' in Master's timezone. Use for ALL user-facing time."""
    import datetime as _dt
    return _dt.datetime.now(mizune_tz())


def parse_mizune_ts(raw):
    """Parse a stored ISO timestamp into a tz-aware datetime in Master's timezone.

    Rows written before the tz-aware rule are naive; those are read AS Master's local
    time, which is what they were. Returns None when `raw` is missing or unparseable —
    callers must treat None as "unknown", never as "recent"."""
    if not raw:
        return None
    import datetime as _dt
    try:
        dt = _dt.datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=mizune_tz())
    return dt


def is_recent(raw, max_age_hours: float) -> bool:
    """True only if `raw` is a timestamp within the last `max_age_hours`.

    THE ANTI-FABRICATION GATE. A daily report that reads the newest row and assumes it
    is recent will narrate a 10-day-old row as this morning's news forever (2026-08-07:
    the night-shift report, the briefing self-review line, and the nightly bug report all
    had this bug). Unknown/unparseable timestamps return False — silence over a false
    report."""
    dt = parse_mizune_ts(raw)
    if dt is None:
        return False
    return (mizune_now() - dt).total_seconds() <= max_age_hours * 3600.0

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

_CLOUD_MODE_CACHE = None

def is_cloud_mode(config: dict = None) -> bool:
    """True when Mizune runs headless on a cloud server (no webcam, no desktop, no UI
    automation). Controlled by the MIZUNE_CLOUD env var (wins) or config['cloud_mode'].
    Env values '1','true','yes','on' (case-insensitive) enable it. Result is cached."""
    global _CLOUD_MODE_CACHE
    env = os.environ.get("MIZUNE_CLOUD")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    if config is not None and "cloud_mode" in config:
        return bool(config.get("cloud_mode"))
    if _CLOUD_MODE_CACHE is not None:
        return _CLOUD_MODE_CACHE
    try:
        cfg = load_config()
        _CLOUD_MODE_CACHE = bool(cfg.get("cloud_mode", False))
    except Exception:
        _CLOUD_MODE_CACHE = False
    return _CLOUD_MODE_CACHE
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
