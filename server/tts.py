"""
Text-to-Speech (TTS) module for Mizune AI using Edge TTS.
"""
import os
import re
import hashlib
import logging

__all__ = ["generate_tts", "clean_text_for_tts"]


from .config import log_info

logger = logging.getLogger("mizune.tts")

_TTS_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tts_cache")
os.makedirs(_TTS_CACHE_DIR, exist_ok=True)

def clean_text_for_tts(text: str) -> str:
    """Clean text for the Japanese TTS engine to prevent it from spelling out acronyms or weird sounds."""
    tts_text = text.strip()
    if not tts_text:
        return ""
        
    # Remove all tildes, asterisks, brackets, backticks, double quotes, and weird math symbols
    tts_text = re.sub(r'[\~\|\*\<\>\[\]\(\)\{\}\"\`_]', '', tts_text)
    # Remove single quotes ONLY if they are at the start/end of words (keeps I'm, don't, etc intact)
    tts_text = re.sub(r"(?<!\w)'|'(?!\w)", "", tts_text)
    # Reduce multiple punctuation marks to a single one (e.g., !!! -> !)
    tts_text = re.sub(r'!+', '!', tts_text)
    tts_text = re.sub(r'\?+', '?', tts_text)
    tts_text = re.sub(r'\.+', '.', tts_text)
    
    # Fix broken syllables
    tts_text = re.sub(r'\b(hmph|mph)\b', 'humph', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\bne\b\??', 'neh', tts_text, flags=re.IGNORECASE)
    
    # Map actions and English expressions to cute phonetic sounds for the Japanese voice
    tts_text = re.sub(r'\bgiggles?\b', 'fufufu', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\b(aww|awww+)\b', 'waa', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\b(ah|ahh+)\b', 'aa', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\b(oh|ohh+)\b', 'ooh', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\bsighs?\b', 'haah', tts_text, flags=re.IGNORECASE)
    tts_text = re.sub(r'\b(hmm|hmmm+)\b', 'nnn', tts_text, flags=re.IGNORECASE)

    # ── Expand English contractions for Japanese TTS engine ──
    # The Japanese voice reads contractions character-by-character, producing garbled output
    contraction_map = {
        r"\bshouldn't\b": "should not",
        r"\bcan't\b": "cannot",
        r"\bwon't\b": "will not",
        r"\bdon't\b": "do not",
        r"\bdoesn't\b": "does not",
        r"\bdidn't\b": "did not",
        r"\bisn't\b": "is not",
        r"\baren't\b": "are not",
        r"\bwasn't\b": "was not",
        r"\bweren't\b": "were not",
        r"\bhasn't\b": "has not",
        r"\bhaven't\b": "have not",
        r"\bhadn't\b": "had not",
        r"\bcouldn't\b": "could not",
        r"\bwouldn't\b": "would not",
        r"\bmustn't\b": "must not",
        r"\bI'm\b": "I am",
        r"\bI've\b": "I have",
        r"\bI'll\b": "I will",
        r"\bI'd\b": "I would",
        r"\byou're\b": "you are",
        r"\byou've\b": "you have",
        r"\byou'll\b": "you will",
        r"\byou'd\b": "you would",
        r"\bhe's\b": "he is",
        r"\bshe's\b": "she is",
        r"\bit's\b": "it is",
        r"\bwe're\b": "we are",
        r"\bwe've\b": "we have",
        r"\bwe'll\b": "we will",
        r"\bthey're\b": "they are",
        r"\bthey've\b": "they have",
        r"\bthey'll\b": "they will",
        r"\bthere's\b": "there is",
        r"\bthat's\b": "that is",
        r"\bwhat's\b": "what is",
        r"\bwho's\b": "who is",
        r"\blet's\b": "let us",
        r"\bhere's\b": "here is",
        r"\bhow's\b": "how is",
        r"\bwhere's\b": "where is",
        r"\bain't\b": "is not",
    }
    for pattern, replacement in contraction_map.items():
        tts_text = re.sub(pattern, replacement, tts_text, flags=re.IGNORECASE)
        
    return tts_text

from server.tracing import observe, update_current_span
# capture_input=False: `config` holds live API keys — keep them out of TraceRoot.
@observe(name="media.generate", type="agent", capture_input=False)
async def generate_tts(text: str, config: dict) -> bytes:
    """Generate speech from text using edge-tts (free Microsoft Neural voices) and return audio bytes."""
    update_current_span(metadata={"text_preview": text[:50]})
    tts_text = clean_text_for_tts(text)
    if not tts_text:
        return b""

    # Voice selection — ja-JP-NanamiNeural = sweet Japanese idol voice (like Ai Hoshino)
    voice = config.get("edge_tts_voice", "ja-JP-NanamiNeural")

    # Check cache first
    cache_key = hashlib.md5(f"{voice}:{tts_text}".encode()).hexdigest()
    cache_path = os.path.join(_TTS_CACHE_DIR, f"{cache_key}.mp3")

    if os.path.exists(cache_path):
        log_info(f"[TTS] Cache hit for: {tts_text[:40]}...")
        with open(cache_path, "rb") as f:
            return f.read()

    # Generate with edge-tts
    try:
        import edge_tts

        communicate = edge_tts.Communicate(tts_text, voice, rate="+0%", pitch="+10Hz")
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if audio_bytes:
            # Cache for future use
            with open(cache_path, "wb") as f:
                f.write(audio_bytes)
            log_info(f"[TTS] Edge-TTS generated ({len(audio_bytes)} bytes): {text[:40]}...")
            return audio_bytes
        else:
            log_info("[TTS] Edge-TTS returned empty audio")
            return b""

    except ImportError:
        log_info("[TTS] edge-tts not installed. Run: pip install edge-tts")
        return b""
    except Exception as e:
        log_info(f"[TTS] Edge-TTS error: {e}")
        return b""
