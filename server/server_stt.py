import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ptt-backend")

import json

# Try to load groq key from config.json
try:
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        if cfg.get("groq_api_key"):
            os.environ["GROQ_API_KEY"] = cfg.get("groq_api_key")
        os.environ["TRANSCRIPTION_BACKEND"] = "groq"
except Exception:
    pass

TRANSCRIPTION_BACKEND = "groq"
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL_NAME = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB safety cap
CHUNK_SIZE = 1024 * 1024

_local_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _local_model
    if TRANSCRIPTION_BACKEND == "local":
        try:
            from faster_whisper import WhisperModel
            import torch
            logger.info(f"Loading Faster-Whisper model '{WHISPER_MODEL_NAME}'...")
            compute_type = "float16" if torch.cuda.is_available() else "int8"
            _local_model = WhisperModel(WHISPER_MODEL_NAME, device="auto", compute_type=compute_type)
            logger.info("Faster-Whisper model loaded.")
        except ImportError:
            logger.error("openai-whisper is not installed. Please run: pip install openai-whisper")
    else:
        if not GROQ_API_KEY:
            logger.warning("TRANSCRIPTION_BACKEND=groq but GROQ_API_KEY is not set!")
        logger.info(f"Using Groq hosted Whisper API (model={GROQ_MODEL_NAME}).")
    yield

app = FastAPI(title="Push-to-Talk Transcription Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _transcribe_local(path: str) -> dict:
    if _local_model is None:
        raise HTTPException(status_code=503, detail="Whisper model is still loading, try again shortly.")
    # faster-whisper transcribe returns an iterator of segments
    segments, info = _local_model.transcribe(path, beam_size=5)
    text = " ".join([segment.text for segment in segments]).strip()
    return {"text": text, "language": info.language}

def _transcribe_groq(path: str) -> dict:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured on the server.")

    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY, timeout=5.0) # Reduced timeout for faster failover
    
    try:
        with open(path, "rb") as audio_fh:
            response = client.audio.transcriptions.create(
                file=audio_fh,
                model=GROQ_MODEL_NAME,
                # English hint: auto-detect frequently mis-hears Indian English
                # as other languages and returns garbage transcripts.
                language=os.environ.get("STT_LANGUAGE", "en"),
            )
        return {"text": (response.text or "").strip(), "language": "en"}
    except Exception as e:
        logger.warning(f"Groq STT failed: {e}. Falling back to faster-whisper.")
        # If Groq fails, instantly fall back to local faster-whisper
        return _transcribe_local(path)

@app.post("/api/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    suffix = os.path.splitext(audio_file.filename or "")[1] or ".m4a"
    tmp_path = None
    total_bytes = 0

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await audio_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file too large.")
                tmp.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received.")

        start = time.monotonic()
        if TRANSCRIPTION_BACKEND == "groq":
            result = _transcribe_groq(tmp_path)
        else:
            result = _transcribe_local(tmp_path)
        elapsed = time.monotonic() - start

        logger.info(
            "Transcribed %d bytes in %.2fs via '%s' -> %r",
            total_bytes, elapsed, TRANSCRIPTION_BACKEND, result["text"][:80],
        )

        return JSONResponse(
            {
                "text": result["text"],
                "language": result.get("language"),
                "duration_sec": round(elapsed, 2),
                "backend": TRANSCRIPTION_BACKEND,
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "backend": TRANSCRIPTION_BACKEND}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
