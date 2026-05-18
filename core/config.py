"""Configuration management for Mizune AI."""
import json
import os
import logging
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "openrouter_api_key": "",
    "opencode_api_key": "",
    "groq_api_key": "",
    "murf_api_key": "",
    "ai_model": "gemini",
    "gemini_model": "gemini-2.0-flash",
    "openai_model": "gpt-4o",
    "anthropic_model": "claude-3-opus-20240229",
    "openrouter_model": "anthropic/claude-3-opus",
    "opencode_model": "default",
    "wake_words": ["mizune", "misune", "mizuna", "mizu", "missy", "darling", "baka"],
    "custom_wake_word": "",
    "wake_language": "en-IN",
    "wake_energy_threshold": 180,
    "wake_dynamic_energy": True,
    "wake_phrase_time_limit": 4.5,
    "wake_timeout": 6.0,
    "wake_adjust_noise_sec": 0.3,
    "mic_device_name": "",
    "mic_device_index": None,
    "voice_id": "ja-JP-NanamiNeural",
    "edge_tts_voice": "ja-JP-NanamiNeural",
    "voice_style": "Cheerful",
    "voice_rate": -2,
    "voice_pitch": 6,
    "memory_size": 30,
    "character_name": "Mizune",
    "personality": (
        "You are Mizune, Master's fierce and adorable anime AI companion. "
        "You speak English with a cute Japanese accent."
    ),
}


def load_config() -> dict:
    """Load configuration with validation and warnings."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except FileNotFoundError:
        logging.info("[CONFIG] No config.json found - using defaults")
        return DEFAULT_CONFIG.copy()
    except json.JSONDecodeError as e:
        logging.info(f"[CONFIG] Invalid JSON in config.json: {e} - using defaults")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        logging.info(f"[CONFIG] Failed to load config: {e} - using defaults")
        return DEFAULT_CONFIG.copy()

    config = {**DEFAULT_CONFIG, **user_config}
    _validate_config(config)
    return config


def _validate_config(config: dict) -> list[str]:
    """Validate config and return warnings for missing/invalid values."""
    warnings = []

    ai_model = config.get("ai_model", "gemini")
    api_key_map = {
        "gemini": "gemini_api_key",
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "opencode": "opencode_api_key",
    }

    if ai_model in api_key_map:
        key = api_key_map[ai_model]
        if not config.get(key):
            warnings.append(f"{key} is missing - {ai_model} will not work")

    system_settings = config.get("system_settings", {})
    required_settings = {
        "wake_key": str,
        "record_seconds": (int, float),
        "wake_cooldown": (int, float),
        "focus_minutes": int,
    }

    for key, expected in required_settings.items():
        if key not in system_settings:
            warnings.append(f"system_settings.{key} not configured")

    for warning in warnings:
        logging.warning(f"[CONFIG] {warning}")


def get_api_key(config: dict, model_type: str) -> Optional[str]:
    """Get API key for the given model type."""
    key_map = {
        "gemini": "gemini_api_key",
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "opencode": "opencode_api_key",
    }
    return config.get(key_map.get(model_type, ""))