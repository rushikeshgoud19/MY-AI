"""Audio handling for Mizune AI - recording, speech recognition."""
import io
import logging
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import speech_recognition as sr
from scipy.signal import resample


log_info = logging.info

SAMPLE_RATE = 44100
RECORD_SECONDS = 6


def get_default_sample_rate() -> int:
    """Get the default sample rate for audio recording."""
    try:
        return int(sd.query_devices(sd.default.device[0], 'input')['default_samplerate'])
    except Exception as e:
        log_info(f"[SERVER] Could not query default device: {e}")
        return 44100


def resolve_mic_device_index(config_index: Optional[int] = None, config_name: str = "") -> Optional[int]:
    """Resolve the microphone device index from config."""
    if config_index is not None:
        try:
            return int(config_index)
        except (TypeError, ValueError):
            return None

    if config_name:
        config_name = config_name.lower().strip()
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev['max_input_channels'] > 0:
                    dev_name = str(dev.get("name", "")).lower()
                    if config_name in dev_name:
                        return idx
        except Exception as e:
            log_info(f"[MIC] Error resolving device: {e}")

    return None


def record_audio(seconds: float = RECORD_SECONDS, sample_rate: int = SAMPLE_RATE) -> Tuple[bytes, int]:
    """Record audio from microphone."""
    try:
        audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        audio_bytes = audio.tobytes()
        return audio_bytes, sample_rate
    except Exception as e:
        log_info(f"[AUDIO] Recording failed: {e}")
        return b"", sample_rate


def normalize_audio(audio_data: bytes, target_sample_rate: int = 16000) -> bytes:
    """Normalize audio to target sample rate."""
    try:
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) > 0:
            samples = len(audio_array)
            target_samples = int(samples * target_sample_rate / SAMPLE_RATE)
            resampled = resample(audio_array.astype(np.float64), target_samples)
            resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
            return resampled.tobytes()
    except Exception as e:
        log_info(f"[AUDIO] Normalization failed: {e}")
    return audio_data


def detect_energy_level(audio_data: bytes) -> int:
    """Detect the energy level of audio."""
    try:
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        return int(np.max(np.abs(audio_array)))
    except Exception:
        return 0


class SpeechRecognizer:
    """Wrapper for speech recognition."""

    def __init__(self):
        self.recognizer = sr.Recognizer()

    def recognize_speech(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        """Recognize speech from audio data."""
        try:
            audio_io = io.BytesIO(audio_data)
            with sr.AudioFile(audio_io) as source:
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            log_info(f"[STT] Recognition error: {e}")
            return None
        except Exception as e:
            log_info(f"[STT] Error: {e}")
            return None


_recognizer: Optional[SpeechRecognizer] = None


def get_recognizer() -> SpeechRecognizer:
    """Get or create the speech recognizer."""
    global _recognizer
    if _recognizer is None:
        _recognizer = SpeechRecognizer()
    return _recognizer