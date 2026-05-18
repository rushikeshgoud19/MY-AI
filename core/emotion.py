"""Emotion detection for Mizune AI."""
import re
from typing import Optional


EMOTION_PATTERNS = {
    "shy": [
        r"\b(love you|marry|kiss|hug|cuddle|hold hands|date me|be mine|my wife|waifu|i love)\b"
    ],
    "blush": [
        r"\b(good girl|cute|pretty|beautiful|amazing job|well done|proud of you|best girl|kawaii|adorable|perfect|gorgeous|sweetie|you'?re the best|my girl|precious)\b"
    ],
    "excited": [
        r"\b(woohoo|yay|wow|awesome|amazing|fantastic|incredible|love it|so cool|epic|let's go|can't wait|super excited)\b"
    ],
    "happy": [
        r"\b(happy|glad|pleased|joy|delighted|thrilled|smile|grin|fun|laugh|enjoy|content)\b"
    ],
    "sad": [
        r"\b(sad|sorry|unfortunately|oh no|miss|lonely|miss you|feel bad|upset|depressed|tears|cry)\b"
    ],
    "angry": [
        r"\b(angry|mad|furious|annoyed|irritated|frustrated|hate|stupid|dumb|idiot|worst|terrible)\b"
    ],
    "surprise": [
        r"\b(woah|whoa|wait what|what|seriously|oh my|unbelievable|shocked|wait|unexpected)\b"
    ],
    "thinking": [
        r"\b(hmm|hm|let me think|consider|maybe|perhaps|possibly|not sure|need to think)\b"
    ],
}


def detect_emotion(text: str) -> str:
    """Detect emotion from text.

    Args:
        text: Input text to analyze

    Returns:
        Emotion label (e.g., "happy", "blush", "angry") or "neutral"
    """
    if not text:
        return "neutral"

    text_lower = text.lower()

    for emotion, patterns in EMOTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return emotion

    return "neutral"


def apply_emotion_response(response: str, emotion: str) -> str:
    """Add emotion tag to response if emotion detected."""
    if emotion != "neutral" and not response.startswith("[EMOTION:"):
        return f"[EMOTION: {emotion}] {response}"
    return response


EMOTION_TTS_SETTINGS = {
    "happy": {"rate": 0, "pitch": 0},
    "sad": {"rate": -2, "pitch": -2},
    "angry": {"rate": 2, "pitch": 3},
    "excited": {"rate": 3, "pitch": 2},
    "blush": {"rate": -1, "pitch": 1},
    "shy": {"rate": -2, "pitch": 0},
    "surprise": {"rate": 1, "pitch": 2},
    "neutral": {"rate": 0, "pitch": 0},
}


def get_tts_settings_for_emotion(emotion: str) -> dict:
    """Get TTS settings for a given emotion."""
    return EMOTION_TTS_SETTINGS.get(emotion, EMOTION_TTS_SETTINGS["neutral"])