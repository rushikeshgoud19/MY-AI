import time
import sqlite3
import threading
import logging
from typing import List, Dict
import json

from .config import log_info

class CuratorAgent:
    """
    Background worker that runs periodically to consolidate memory,
    deduplicate facts, and optimize the FTS5 search index.
    """
    
    def __init__(self, memory_system):
        self.memory = memory_system
        self._stop_event = threading.Event()
        self._thread = None
        self.interval_minutes = 60 # Run every hour by default

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            log_info("[CURATOR] CuratorAgent background consolidation started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop_event.is_set():
            # Wait for interval
            for _ in range(self.interval_minutes * 60):
                if self._stop_event.is_set():
                    return
                time.sleep(1)
            
            self._run_consolidation()

    def _run_consolidation(self):
        """Perform FTS5 optimization and deduplication."""
        log_info("[CURATOR] Running memory consolidation...")
        try:
            if not self.memory.db:
                return
                
            cursor = self.memory.db.cursor()
            
            # 1. Clean up old short-term history (> 2 days old)
            cursor.execute("DELETE FROM history WHERE timestamp < datetime('now', '-2 days')")
            
            # 2. Optimize FTS5 table
            cursor.execute("INSERT INTO memory_fts(memory_fts) VALUES('optimize')")
            
            self.memory.db.commit()
            log_info("[CURATOR] Consolidation complete.")
        except Exception as e:
            log_info(f"[CURATOR] Consolidation error: {e}")

curator_agent = None

def init_curator(memory_system):
    global curator_agent
    curator_agent = CuratorAgent(memory_system)
    curator_agent.start()
    return curator_agent
