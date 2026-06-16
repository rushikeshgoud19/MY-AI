import time
import logging
import threading
from typing import Dict, Any

from .config import log_info

logger = logging.getLogger("mizune.subconscious")

class SubconsciousEngine:
    """
    The background heartbeat of Mizune.
    Wakes up every few minutes to check integrations, memory, and time.
    Decides whether to SKIP, ACT silently, or ESCALATE (speak to user).
    """
    def __init__(self, config: Dict[str, Any], trigger_callback, processing_lock: threading.Lock):
        self.config = config
        self.trigger_callback = trigger_callback
        self.processing_lock = processing_lock
        
        # Minimum heartbeat is 3 mins to avoid API bans
        self.interval_minutes = max(3, config.get("proactive_interval_minutes", 5))
        self._running = False
        
    def start(self):
        if not self.config.get("proactive_enabled", True):
            log_info("[SUBCONSCIOUS] Background engine disabled in config.")
            return
            
        self._running = True
        log_info(f"[SUBCONSCIOUS] Engine online. Heartbeat every {self.interval_minutes} minutes.")
        threading.Thread(target=self._loop, daemon=True, name="SubconsciousThread").start()
        
    def _loop(self):
        while self._running:
            time.sleep(self.interval_minutes * 60)
            
            if self.processing_lock.locked():
                log_info("[SUBCONSCIOUS] Skipping heartbeat (Mizune is busy).")
                continue
                
            self._tick()
            
    def _build_situation_report(self) -> str:
        """
        Gathers basic stats to decide if waking up is necessary.
        """
        # In a real setup, this would ping auto_fetch for unread emails, check calendar, etc.
        # For now, we inject time and request the LLM to decide.
        report = []
        report.append(f"Current Time: {time.strftime('%I:%M %p, %A, %B %d')}")
        
        # Look for pending memories or background tasks
        from .memory_tree import memory_tree_db
        pending = memory_tree_db.get_queue_depth()
        if pending > 0:
            report.append(f"System State: {pending} memory chunks pending consolidation.")
            
        return "\\n".join(report)

    def _tick(self):
        log_info("[SUBCONSCIOUS] Heartbeat tick...")
        sitrep = self._build_situation_report()
        
        # We prompt the AI to evaluate the situation
        prompt = (
            f"[SYSTEM SUBCONSCIOUS TICK]\\n"
            f"You are running in the background. Master is not explicitly talking to you.\\n"
            f"SITUATION REPORT:\\n{sitrep}\\n\\n"
            f"DECISION MATRIX:\\n"
            f"1. If nothing requires attention, reply exactly with [SKIP].\\n"
            f"2. If you need to perform a silent background task (like using a tool to check emails or weather), reply with [ACT] and use the tool.\\n"
            f"3. If there is an urgent notification (meeting in 5 mins), reply with [ESCALATE] and use notify_master.\\n\\n"
            f"If you ACT or ESCALATE, you MUST fulfill the action immediately. If unsure, [SKIP]."
        )
        
        try:
            # We override the output so that if she returns SKIP, the processor drops it.
            # Processor already handles [SLEEP], we'll add [SKIP] to it in processor.py.
            self.trigger_callback(pre_text=prompt)
        except Exception as e:
            log_info(f"[SUBCONSCIOUS] Tick failed: {e}")

def start_proactive_agent(config: dict, trigger_callback, processing_lock: threading.Lock):
    """Legacy wrapper for backward compatibility."""
    engine = SubconsciousEngine(config, trigger_callback, processing_lock)
    engine.start()
