"""
Audio processing module for Mizune AI (Microphone, STT, Wake Word).
"""
import time
import re
import threading
import speech_recognition as sr
import logging
from typing import Optional

__all__ = ["listen_to_microphone", "listen_for_wake_word", "is_active_listening", "LAST_WAKE_TIME", "play_audio_bytes"]


from .config import log_info

logger = logging.getLogger("mizune.audio")

# Global audio state
is_active_listening = False
_recording_lock = threading.Lock()
LAST_WAKE_TIME = 0.0
MANUAL_WAKE_TRIGGER = threading.Event()

# Initialize speech recognizer
recognizer = sr.Recognizer()

# Attempt to load Whisper for fallback STT
HAS_WHISPER = False
WHISPER_MODEL = None

def _init_whisper_bg():
    global HAS_WHISPER, WHISPER_MODEL
    try:
        from faster_whisper import WhisperModel
        import os
        import torch
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        model_size = "tiny.en"
        compute_type = "float16" if torch.cuda.is_available() else "int8"
        WHISPER_MODEL = WhisperModel(model_size, device="auto", compute_type=compute_type)
        HAS_WHISPER = True
        log_info("[AUDIO] Faster-Whisper loaded successfully for offline fallback.")
    except Exception as e:
        log_info(f"[AUDIO] Faster-Whisper not available: {e}")

threading.Thread(target=_init_whisper_bg, daemon=True).start()

def listen_to_microphone(config: dict, broadcast_sync_fn) -> Optional[str]:
    """Capture audio from microphone and transcribe using STT services."""
    global is_active_listening
    if not _recording_lock.acquire(blocking=False):
        log_info("[MIC] Already recording, skipping...")
        return None

    mic_device_index = config.get("mic_device_index")
    
    try:
        log_info("[MIC] Starting recording...")
        broadcast_sync_fn({"type": "status", "text": "Listening..."})
        is_active_listening = True

        with sr.Microphone(device_index=mic_device_index) if mic_device_index is not None else sr.Microphone() as source:
            # Re-enable dynamic thresholding so the mic auto-calibrates to the fan noise 
            # and knows exactly when you stop talking, instead of hanging for 15 seconds!
            recognizer.dynamic_energy_threshold = True
            
            # Quick ambient noise calibration to stabilize the mic
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            log_info("[MIC] Ready and listening for speech...")
            audio = recognizer.listen(source, timeout=config.get("wake_timeout", 6.0), phrase_time_limit=15.0)

        # Check volume gate to prevent Groq from hallucinating on pure silence
        import numpy as np
        raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
        
        # --- AI NOISE CANCELLATION ---
        # Completely removes fans, AC, and keyboard clacking
        from server.noise_cancellation import clean_audio
        raw_data = clean_audio(raw_data, sample_rate=16000)
        
        audio_np = np.frombuffer(raw_data, dtype=np.int16)
        volume_rms = np.sqrt(np.mean(audio_np.astype(np.float32)**2))
        
        if volume_rms < 150: # Lowered gate since noise is removed
            log_info(f"[MIC] Audio dropped (Volume {volume_rms:.1f} < 150 RMS). No speech detected.")
            return None

        # --- SILERO VAD (Voice Activity Detection) ---
        try:
            from silero_vad import load_silero_vad, get_speech_timestamps
            import torch
            
            # Load VAD model (cached internally)
            if not hasattr(listen_to_microphone, "vad_model"):
                listen_to_microphone.vad_model = load_silero_vad()
            
            audio_tensor = torch.from_numpy(audio_np.astype(np.float32) / 32768.0)
            speech_timestamps = get_speech_timestamps(audio_tensor, listen_to_microphone.vad_model, sampling_rate=16000, min_speech_duration_ms=250)
            
            if not speech_timestamps:
                log_info("[MIC] VAD rejected audio (No human vocal cords detected).")
                return None
        except Exception as e:
            log_info(f"[MIC] VAD skipped/Error: {e}")

        # Re-pack the cleaned audio back into speech_recognition AudioData
        cleaned_audio = sr.AudioData(raw_data, 16000, 2)

        log_info("[MIC] Recording finished. Processing...")
        broadcast_sync_fn({"type": "status", "text": "Processing..."})

        # ── Primary attempt: Groq STT ──
        groq_api_key = config.get("groq_api_key")
        if groq_api_key and len(groq_api_key) > 5:
            try:
                import requests
                log_info("[MIC] Trying Groq STT...")
                wav_data = cleaned_audio.get_wav_data(convert_rate=16000, convert_width=2)
                files = {'file': ('audio.wav', wav_data, 'audio/wav')}
                data = {
                    'model': 'whisper-large-v3', 
                    'language': 'en', 
                    'temperature': '0.0',
                    'prompt': 'mizune, misune, anime, song, baka, goshujin-sama, master, kawaii, sugoi'
                }
                headers = {'Authorization': f'Bearer {groq_api_key}'}
                response = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", files=files, data=data, headers=headers, timeout=7)
                if response.status_code == 200:
                    text = response.json().get('text', '').strip()
                    if text:
                        # Whisper often hallucinates these exact strings when fed pure silence or static noise
                        hallucinations = [
                            "thank you.", "thank you", "thanks.", "you're welcome.", "bye.", "amém", "amen.", "thank you!", 
                            "good.", "good", "akiaki is isumaa!", "akiaki is isumaa", "thanks for watching!", "thanks for watching",
                            "subscribe!", "please subscribe", "subscribe to my channel", "bye bye", "ahem", "music", "...",
                            "watching!", "you", "no", "yes", "my contact", "website", "tamil mp3", "somnath destination",
                            "thank you for watching!", "thank you for watching.", "thank you for watching", "bye"
                        ]
                        
                        clean_lower = text.lower().strip()
                        if clean_lower in hallucinations or len(clean_lower.replace(".", "").strip()) <= 2:
                            log_info(f"[MIC] Ignored Whisper static hallucination: '{text}'")
                            return None
                        log_info(f"[MIC] Groq Recognized: '{text}'")
                        broadcast_sync_fn({"type": "user_input", "text": text})
                        return text
                else:
                    log_info(f"[MIC] Groq STT error: {response.status_code} {response.text}")
            except Exception as e:
                log_info(f"[MIC] Groq STT exception: {e}")

        # ── Secondary attempt: Google STT ──
        try:
            text = recognizer.recognize_google(audio, language="en-IN")
            log_info(f"[MIC] Google Recognized: '{text}'")
            broadcast_sync_fn({"type": "user_input", "text": text})
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
                    broadcast_sync_fn({"type": "user_input", "text": text})
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

def listen_for_wake_word(config: dict, on_wake_trigger_fn, broadcast_sync_fn):
    """Background loop that continuously listens for wake words."""
    mic_device_index = config.get("mic_device_index")

    # Build wake word list from config + verified phonetic variants ONLY
    wake_words = list(config.get("wake_words", ["mizune", "misune", "mizuna", "mizu", "missy", "darling", "baka"]))
    custom = config.get("custom_wake_word", "").strip().lower()
    if custom and custom not in wake_words:
        wake_words.insert(0, custom)

    # CLEANED: Only verified Google STT mishearings — no random words
    PHONETIC_VARIANTS = [
        "mizune", "misune", "mizuna", "mizu", "missy", "mizun", "mezune",
        "mizuney", "mizunee", "mizzy", "mizuki", "mitsune", "mizone", "mizoon",
        "my zone", "museum",
        "darling", "baka", "baat", "bata", "baca", "bark", "maca", "dhaka"
    ]
    all_wake_words = list(set(wake_words + PHONETIC_VARIANTS))
    log_info(f"[WAKE] Wake words ({len(all_wake_words)}): {wake_words[:8]}... + phonetic variants")

    def levenshtein(a: str, b: str) -> int:
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
        clean_text = re.sub(r'[^\w\s]', '', heard_text)
        words = clean_text.split()

        # 1. Exact word match (Highest Priority)
        for word in words:
            if word in all_wake_words:
                return word

        # 2. Contains match
        for wake in all_wake_words:
            if len(wake) >= 4 and wake in clean_text:  # only check >=4 char wake words
                return wake

        # 3. Levenshtein fuzzy match (Catch mispronunciations)
        for word in words:
            for wake in all_wake_words:
                if len(wake) >= 4:
                    dist = levenshtein(word, wake)
                    # Allow 1 typo for 4-5 letter words, 2 typos for 6+ letter words
                    threshold = 1 if len(wake) <= 5 else 2
                    if dist <= threshold:
                        return wake

        return None

    _wake_fail_count = 0

    wake_language = config.get("wake_language", "en-IN")
    wake_energy_threshold = int(config.get("wake_energy_threshold", 180))
    wake_phrase_time_limit = float(config.get("wake_phrase_time_limit", 2.5)) # Decreased from 15.0s to stop blocking F2 trigger
    wake_timeout = 1.0 # Lowered to 1.0 to quickly release mic for F2
    wake_adjust_noise_sec = float(config.get("wake_adjust_noise_sec", 0.3))
    wake_cooldown = float(config.get("wake_cooldown_sec", 3.0))

    while True:
        if MANUAL_WAKE_TRIGGER.is_set():
            MANUAL_WAKE_TRIGGER.clear()
            log_info("[WAKE] Manual trigger activated (F2)!")
            broadcast_sync_fn({"type": "stop_audio"})
            broadcast_sync_fn({"type": "status", "text": "Triggered"})
            on_wake_trigger_fn(None)
            # Clear it again in case F2 was mashed repeatedly while we were recording
            MANUAL_WAKE_TRIGGER.clear()
            continue

        # CRITICAL: Only listen for wake word if no one is currently recording a command
        if is_active_listening:
            time.sleep(0.5)
            continue
        try:
            with sr.Microphone(device_index=mic_device_index) if mic_device_index is not None else sr.Microphone() as source:
                # Disable dynamic thresholding which mutes quiet voices / causes early cutoffs
                recognizer.dynamic_energy_threshold = False
                # Increase pause threshold so she doesn't stop listening if you take a breath (default is 0.8)
                recognizer.pause_threshold = 1.8
                recognizer.energy_threshold = wake_energy_threshold

                if wake_adjust_noise_sec > 0:
                    recognizer.adjust_for_ambient_noise(source, duration=wake_adjust_noise_sec)

                audio = recognizer.listen(
                    source,
                    timeout=wake_timeout,
                    phrase_time_limit=wake_phrase_time_limit,
                )

            _wake_fail_count = 0  # Reset on successful audio capture

            try:
                # ── BIOMETRIC FINGERPRINT MATCHING ──
                import os
                import numpy as np
                
                profile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mizune_voice_profile.npy")
                biometric_triggered = False
                
                if os.path.exists(profile_path):
                    try:
                        from python_speech_features import mfcc
                        from fastdtw import fastdtw
                        from scipy.spatial.distance import euclidean
                        
                        templates = np.load(profile_path, allow_pickle=True)
                        
                        raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                        audio_np = np.frombuffer(raw_data, dtype=np.int16)
                        
                        # Calculate RMS volume to filter out pure silence/static
                        volume_rms = np.sqrt(np.mean(audio_np.astype(np.float32)**2))
                        
                        # Only process if audio is sufficiently long (at least 0.5 sec) and loud enough (> 1000 RMS)
                        # We raised this to 1000 to completely block the fan noise from tricking the biometric lock.
                        if len(audio_np) > 8000 and volume_rms > 1000:
                            test_mfcc = mfcc(audio_np, samplerate=16000, numcep=13, nfft=512)
                            
                            min_dist = float('inf')
                            for template in templates:
                                dist, path = fastdtw(test_mfcc, template, dist=euclidean)
                                normalized_dist = dist / len(path)
                                if normalized_dist < min_dist:
                                    min_dist = normalized_dist
                                    
                            log_info(f"[WAKE] Biometric Distance: {min_dist:.2f} (Vol: {volume_rms:.1f})")
                            
                            # Load custom threshold from auto-calibration config
                            dtw_threshold = 85.0
                            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "biometric_config.json")
                            if os.path.exists(config_path):
                                try:
                                    import json
                                    with open(config_path, "r") as f:
                                        bioconf = json.load(f)
                                        dtw_threshold = bioconf.get("dtw_threshold", 85.0)
                                except Exception:
                                    pass
                                    
                            log_info(f"[WAKE] Target threshold is < {dtw_threshold:.2f}")
                            
                            if min_dist < dtw_threshold:
                                log_info(f"[WAKE] BIOMETRIC MATCH ACCEPTED! (Dist: {min_dist:.2f}) - TEMPORARILY DISABLED TO PREVENT FALSE ALARMS")
                                # biometric_triggered = True
                                # matched_wake = "mizune (biometric)"
                    except Exception as e:
                        log_info(f"[WAKE] Biometric matching error: {e}")
                
                if not biometric_triggered:
                    # ── FALLBACK TO TEXT STT ──
                    raw_text = recognizer.recognize_google(audio, language=wake_language).lower()

                    if len(raw_text.strip()) < 3:
                        continue

                    log_info(f"[WAKE] Heard: '{raw_text}'")
                    matched_wake = fuzzy_match_wake(raw_text)

                if matched_wake:
                    # ── Cooldown ──
                    now_ts = time.time()
                    global LAST_WAKE_TIME
                    if now_ts - LAST_WAKE_TIME < wake_cooldown:
                        log_info(f"[WAKE] Cooldown active — ignoring re-trigger")
                    else:
                        LAST_WAKE_TIME = now_ts
                        log_info(f"[WAKE] TRIGGER: Matched '{matched_wake}'")
                        broadcast_sync_fn({"type": "stop_audio"})
                        broadcast_sync_fn({"type": "status", "text": "Triggered"})
                        
                        # If biometric triggered, we don't have a cmd_part from raw_text. We just wake up.
                        cmd_part = ""
                        if not biometric_triggered:
                            for wake in all_wake_words:
                                if wake in raw_text:
                                    parts = raw_text.split(wake, 1)
                                    if len(parts) > 1:
                                        cmd_part = parts[-1].strip()
                                        break

                        on_wake_trigger_fn(cmd_part if (cmd_part and len(cmd_part) > 2) else None)

            except sr.UnknownValueError:
                pass  # Google couldn't understand — normal, keep listening
            except sr.RequestError as e:
                log_info(f"[WAKE] Google STT request error: {e}")
                time.sleep(2)
        except sr.WaitTimeoutError:
            _wake_fail_count += 1
            if _wake_fail_count % 30 == 0:
                log_info(f"[WAKE] Still listening... ({_wake_fail_count} silent cycles)")
        except OSError as e:
            log_info(f"[WAKE] Microphone error: {e} — retrying in 3s")
            time.sleep(3)
        except Exception as e:
            log_info(f"[WAKE] Error: {e}")
            if "PyAudio" in str(e):
                log_info("[WAKE] PyAudio is missing. Disabling wake word listener permanently on this machine.")
                break
            time.sleep(1)

def play_audio_bytes(audio_bytes: bytes):
    """Play raw mp3 audio bytes locally using pygame.mixer."""
    if not audio_bytes:
        return
    try:
        import pygame
        import io
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(io.BytesIO(audio_bytes))
        pygame.mixer.music.play()
    except ImportError:
        log_info("[AUDIO] Pygame not installed. Cannot play TTS.")
    except Exception as e:
        log_info(f"[AUDIO] Failed to play TTS: {e}")
