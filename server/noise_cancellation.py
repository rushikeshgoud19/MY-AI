import numpy as np
from .config import log_info

# Global model state
_df_model = None
_df_state = None
# Init is attempted ONCE per process. Without this guard the VM (torch deliberately
# blocked) re-attempted on every audio session and spammed a full traceback 52x in the
# logs. Cache the outcome and never retry.
_init_done = False
_init_result = False

def init_noise_cancellation():
    """Initializes the DeepFilterNet AI model into memory for zero-latency cleaning.
    Runs at most once per process; subsequent calls return the cached result."""
    global _df_model, _df_state, _init_done, _init_result
    if _init_done:
        return _init_result
    _init_done = True
    try:
        # DeepFilterNet is incompatible with newer Torchaudio. We monkeypatch the missing type hint module so it loads perfectly.
        import sys
        import torchaudio
        if not hasattr(torchaudio, 'backend'):
            import types
            torchaudio.backend = types.ModuleType('torchaudio.backend')
            torchaudio.backend.common = types.ModuleType('torchaudio.backend.common')
            class AudioMetaData: pass
            torchaudio.backend.common.AudioMetaData = AudioMetaData
            sys.modules['torchaudio.backend'] = torchaudio.backend
            sys.modules['torchaudio.backend.common'] = torchaudio.backend.common
            
        from df.enhance import init_df
        log_info("[AUDIO] Initializing DeepFilterNet AI Model...")
        _df_model, _df_state, _ = init_df()
        log_info("[AUDIO] DeepFilterNet loaded successfully!")
        _init_result = True
        return True
    except ImportError as e:
        # EXPECTED on the VM: torch is deliberately blocked (898MB box) → torchaudio import
        # raises. This is not an error, so log ONE clean line and never dump a traceback.
        msg = str(e)
        if 'torch' in msg.lower():
            log_info("[AUDIO] DeepFilterNet disabled (torch blocked on this host) — noise cancellation off, using raw audio.")
        else:
            log_info(f"[AUDIO] DeepFilterNet missing dependency: {msg}. Noise cancellation disabled.")
        _init_result = False
        return False
    except Exception as e:
        log_info(f"[AUDIO] DeepFilterNet failed to initialize: {e}")
        import traceback
        log_info(f"[AUDIO] DeepFilterNet Trace: {traceback.format_exc()}")
        _init_result = False
        return False

def clean_audio(audio_bytes: bytes, sample_rate: int) -> bytes:
    """Takes raw noisy PCM audio bytes and returns crystal clear speech bytes."""
    if not _df_model or not _df_state:
        return audio_bytes # Fallback to original audio if model failed to load
        
    try:
        from df.enhance import enhance
        import torch
        import torchaudio
        
        # Convert raw bytes (int16 PCM) to tensor
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_np).unsqueeze(0) # Shape: [1, seq_len]
        
        # DeepFilterNet expects the sample rate to match _df_state.sr() (which is usually 48000).
        model_sr = _df_state.sr()
        
        # Resample if needed
        if sample_rate != model_sr:
            audio_tensor = torchaudio.functional.resample(audio_tensor, orig_freq=sample_rate, new_freq=model_sr)
            
        # Run AI Enhancement (This deletes fans, keyboard typing, and background static)
        enhanced_tensor = enhance(_df_model, _df_state, audio_tensor)
        
        # Resample back to original
        if sample_rate != model_sr:
            enhanced_tensor = torchaudio.functional.resample(enhanced_tensor, orig_freq=model_sr, new_freq=sample_rate)
            
        # Convert back to raw int16 PCM bytes
        enhanced_np = (enhanced_tensor.squeeze().cpu().numpy() * 32768.0).astype(np.int16)
        return enhanced_np.tobytes()
        
    except Exception as e:
        log_info(f"[AUDIO] DeepFilterNet processing error: {e}")
        return audio_bytes # Return original if failed
