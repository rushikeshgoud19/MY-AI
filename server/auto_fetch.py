import time
import logging
import threading
from typing import Dict, Any

from .config import log_info
from .integrations import integrations
from .memory_tree import memory_tree_db

logger = logging.getLogger("mizune.auto_fetch")

class AutoFetchEngine:
    """
    Background worker that fetches state from connected integrations (GitHub, Spotify, etc.)
    and injects it directly into the Memory Tree.
    Runs every 20 minutes to maintain context.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.interval_minutes = 20
        self._running = False
        
    def start(self):
        if not self.config.get("auto_fetch_enabled", True):
            return
            
        self._running = True
        log_info(f"[AUTO-FETCH] Background sync online. Polling every {self.interval_minutes} minutes.")
        threading.Thread(target=self._loop, daemon=True, name="AutoFetchThread").start()
        
    def _loop(self):
        while self._running:
            time.sleep(self.interval_minutes * 60)
            self._fetch_all()
            
    def _fetch_all(self):
        log_info("[AUTO-FETCH] Syncing connected integrations...")
        for provider in ["google", "github", "spotify"]:
            # Check if token exists
            if not integrations.load_token(provider):
                continue
                
            try:
                data = integrations.fetch_recent(provider)
                if data:
                    chunk_id = f"autofetch_{provider}_{int(time.time())}"
                    memory_tree_db.insert_chunk(
                        chunk_id=chunk_id,
                        source=f"integration_{provider}",
                        text=data,
                        token_count=len(data)//4,
                        metadata={"type": "auto_fetch", "provider": provider}
                    )
            except Exception as e:
                log_info(f"[AUTO-FETCH] Error syncing {provider}: {e}")

auto_fetch_engine = None

def init_auto_fetch(config: Dict[str, Any]):
    global auto_fetch_engine
    if not auto_fetch_engine:
        auto_fetch_engine = AutoFetchEngine(config)
        auto_fetch_engine.start()
