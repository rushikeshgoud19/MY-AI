import os
import subprocess
import sounddevice as sd
import numpy as np
import wave
import io
import logging
import threading
import time
from datetime import datetime
from agents.base_agent import BaseAgent
from typing import Any, Optional, Dict, List

class MemoryAgent(BaseAgent):
    """
    Specialized Agent for session logging, transcription, and memory retrieval.
    Implements the 'Session Logger' workflow.
    """
    def __init__(self, config: dict):
        super().__init__(config)
        self.log("MemoryAgent initialized. Preparing to record Master's wisdom.")

        # Setup Paths
        self.desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        self.sessions_folder = os.path.join(self.desktop_path, "sessions")
        os.makedirs(self.sessions_folder, exist_ok=True)

        # Background loading state
        self.stt_model = None
        self.chroma_client = None
        self.collection = None
        self.embedding_fn = None
        
        # Start background load
        threading.Thread(target=self._init_heavy_models, daemon=True).start()

    def _init_heavy_models(self):
        try:
            self.log("Background loading ChromaDB and Whisper for MemoryAgent...")
            from faster_whisper import WhisperModel
            import chromadb
            from chromadb.utils import embedding_functions

            # Initialize Transcription Model (Small/Fast for local use)
            self.stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")

            # Initialize Vector Store for Memory
            self.chroma_client = chromadb.PersistentClient(path=os.path.join(os.path.dirname(__file__), "..", ".chroma_db"))
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.chroma_client.get_or_create_collection(
                name="mizune_memory",
                embedding_function=self.embedding_fn
            )
            self.log("MemoryAgent background models loaded successfully!")
        except Exception as e:
            self.log(f"Failed to load background models: {e}")

        # Session State - Thread-safe using Event
        self._logging_event = threading.Event()
        self._logging_event.clear()  # Not logging initially
        self.session_buffer: List[str] = []
        self.session_buffer_lock = threading.Lock()  # Protect buffer access
        self.logging_thread: Optional[threading.Thread] = None

    @property
    def is_logging(self) -> bool:
        return self._logging_event.is_set()

    @is_logging.setter
    def is_logging(self, value: bool):
        if value:
            self._logging_event.set()
        else:
            self._logging_event.clear()

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        self.log(f"Processing memory task: {task_input}")
        text = task_input.lower()

        if "start session logging" in text or "recording training" in text:
            return await self._start_session_logger()

        if "stop session logging" in text:
            return await self._stop_session_logger()

        if "summarize" in text or "what happened" in text:
            return await self._summarize_session()

        if "remember" in text or "save this" in text:
            return await self._save_to_memory(task_input)

        if "recall" in text or "do you remember" in text:
            # Extract the query part
            query = text.replace("recall", "").replace("do you remember", "").strip()
            return await self.query_memory(query)

        return "I remember everything you tell me, Master~! What would you like me to recall?"

    async def _start_session_logger(self) -> str:
        if self.is_logging:
            return "I'm already recording, Master! Everything is being noted~"

        self.log("Starting Session Logger pipeline...")
        self.is_logging = True
        self.session_buffer = []

        # Start background recording thread
        self.logging_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.logging_thread.start()

        return "Hai~! I'm now listening to your session and taking notes. I'll summarize everything for you later!"

    async def _stop_session_logger(self) -> str:
        self.is_logging = False
        if self.logging_thread:
            self.logging_thread.join(timeout=2)
        return "I've stopped the recording, Master. Your session is safely logged~"

    def _recording_loop(self):
        """Background thread that records audio in chunks and transcribes them."""
        self.log("Session recording loop active.")
        chunk_duration = 10  # Record in 10-second chunks for responsiveness
        fs = 16000  # Whisper expects 16kHz

        try:
            # Use event wait instead of polling is_logging flag
            while self._logging_event.is_set():
                try:
                    # Record chunk
                    recording = sd.rec(int(chunk_duration * fs), samplerate=fs, channels=1, dtype='float32')
                    sd.wait()

                    # Convert to the format Whisper expects (numpy array)
                    # faster-whisper can take numpy arrays directly
                    segments, _ = self.stt_model.transcribe(recording.flatten(), beam_size=5)
                    text = " ".join([s.text for s in segments]).strip()

                    if text:
                        self.log(f"Session Log: {text}")
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        # Thread-safe append to buffer
                        with self.session_buffer_lock:
                            self.session_buffer.append(f"[{timestamp}] {text}")

                except Exception as e:
                    self.log(f"Error in recording loop: {e}")
                    time.sleep(2)  # Cool down on error
        except Exception as e:
            self.log(f"Critical failure in recording loop: {e}")
        finally:
            self._logging_event.clear()

    async def _summarize_session(self) -> str:
        # Thread-safe buffer access
        with self.session_buffer_lock:
            buffer_copy = list(self.session_buffer)

        if not buffer_copy:
            return "I don't have any logs for the current session, Master. Maybe you haven't spoken much?"

        self.log("Summarizing current session...")
        full_transcript = "\n".join(buffer_copy)

        # For the summary, we'll use a simplified version that can be expanded
        # when the AI model call is integrated.
        summary_text = "# Session Summary\n\n" + full_transcript + "\n\n(Summary generated by Mizune AI)"

        # Save to sessions folder
        filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.sessions_folder, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary_text)
            return f"I've summarized the session and saved it to your Desktop in the 'sessions' folder as {filename}, Master!"
        except Exception as e:
            self.log(f"Error saving summary: {e}")
            return "I tried to save the summary, but something went wrong, Master... gomen ne~"

    async def _save_to_memory(self, text: str) -> str:
        try:
            timestamp = datetime.now().isoformat()
            doc_id = f"mem_{int(time.time() * 1000)}"

            self.collection.add(
                documents=[text],
                metadatas=[{"timestamp": timestamp}],
                ids=[doc_id]
            )
            return "Got it, Master! I've etched that into my memory forever~"
        except Exception as e:
            self.log(f"Error saving to memory: {e}")
            return "I had a little trouble remembering that, Master... could you say it again?"

    async def query_memory(self, query: str) -> str:
        try:
            if not query:
                return "What would you like me to recall, Master?"

            results = self.collection.query(
                query_texts=[query],
                n_results=3
            )

            docs = results.get("documents", [[]])[0]
            if not docs:
                return "Hmm... I searched my heart and mind, but I couldn't find anything about that, Master~"

            recalled_text = "\n".join([f"- {d}" for d in docs])
            return f"I remember this, Master!\n\n{recalled_text}"
        except Exception as e:
            self.log(f"Error querying memory: {e}")
            return "My memory is a bit fuzzy right now, Master... gomen ne~"
