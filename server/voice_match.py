"""Voice Match — Google-Assistant-style speaker verification for the wake word.

Master enrolls by saying "Baka Mizune" 3x (app Settings -> Calibrate voice).
Each sample becomes an MFCC fingerprint; verification cosine-matches a new
utterance against the enrolled set. Same technique as record_biometric.py,
shared for the HTTP endpoints. Audio in/out is 16kHz mono 16-bit WAV.
"""
import io
import os
import wave

import numpy as np

PROFILE_PATH = os.path.join(".data", "voice_profile.npy")
# Cosine similarity against the closest enrolled sample. MFCC-mean prints are
# coarse: same-speaker ~0.95+, different-speaker typically <0.85.
MATCH_THRESHOLD = 0.90
MIN_SAMPLES = 3


def _wav_to_pcm16(data: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("expected 16-bit PCM WAV")
        frames = w.readframes(w.getnframes())
        pcm = np.frombuffer(frames, dtype=np.int16)
        if w.getnchannels() > 1:
            pcm = pcm[:: w.getnchannels()]
        if w.getframerate() != 16000:
            # Cheap linear resample — fingerprints tolerate it fine.
            ratio = 16000 / w.getframerate()
            idx = np.clip((np.arange(int(len(pcm) * ratio)) / ratio).astype(int), 0, len(pcm) - 1)
            pcm = pcm[idx]
    return pcm


def fingerprint(wav_bytes: bytes) -> np.ndarray:
    from python_speech_features import mfcc
    pcm = _wav_to_pcm16(wav_bytes)
    if len(pcm) < 1600:  # <0.1s of audio
        raise ValueError("audio too short")
    feat = mfcc(pcm, samplerate=16000, numcep=13, nfft=512)
    vec = feat.mean(axis=0)
    return vec / (np.linalg.norm(vec) + 1e-9)


def _load_profile() -> np.ndarray:
    if os.path.exists(PROFILE_PATH):
        return np.load(PROFILE_PATH)
    return np.empty((0, 13))


def enroll(wav_bytes: bytes) -> dict:
    vec = fingerprint(wav_bytes)
    profile = np.vstack([_load_profile(), vec])
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    np.save(PROFILE_PATH, profile)
    return {"samples": len(profile), "enrolled": len(profile) >= MIN_SAMPLES}


def reset() -> dict:
    if os.path.exists(PROFILE_PATH):
        os.remove(PROFILE_PATH)
    return {"samples": 0, "enrolled": False}


def status() -> dict:
    n = len(_load_profile())
    return {"samples": int(n), "enrolled": n >= MIN_SAMPLES}


def verify(wav_bytes: bytes) -> dict:
    """Returns match/score. If not enrolled yet, matches EVERYONE (open mode)
    so the wake word keeps working before calibration."""
    profile = _load_profile()
    if len(profile) < MIN_SAMPLES:
        return {"match": True, "score": 1.0, "enrolled": False}
    vec = fingerprint(wav_bytes)
    score = float(np.max(profile @ vec))
    return {"match": score >= MATCH_THRESHOLD, "score": round(score, 4), "enrolled": True}
