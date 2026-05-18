"""Core modules for Mizune AI."""

from .config import load_config, DEFAULT_CONFIG
from .llm_service import LLMService
from .actions import open_app, close_app, lock_pc, sleep_pc, search_web
from .emotion import detect_emotion, apply_emotion_response, get_tts_settings_for_emotion
from .audio import record_audio, normalize_audio, detect_energy_level, get_recognizer


def get_ai_response(text: str, history: list = None, system_prompt_override: str = None, cfg: dict = None) -> str:
    """Wrapper for LLMService.get_ai_response."""
    if history is None:
        history = []
    if cfg is None:
        from . import config as cfg_module
        cfg = cfg_module.load_config()
    return LLMService.get_ai_response(text, history, system_prompt_override, cfg)


__all__ = [
    "load_config",
    "DEFAULT_CONFIG",
    "get_ai_response",
    "LLMService",
    "open_app",
    "close_app",
    "lock_pc",
    "sleep_pc",
    "search_web",
    "detect_emotion",
    "apply_emotion_response",
    "get_tts_settings_for_emotion",
    "record_audio",
    "normalize_audio",
    "detect_energy_level",
    "get_recognizer",
]