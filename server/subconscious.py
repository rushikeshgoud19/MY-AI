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
        
        # Minimum heartbeat is 3 mins to avoid API bans.
        # Default raised to 15: traces showed ticks were 90% of all LLM traffic
        # (8.3k input tokens each, answered "[SKIP]"), starving user requests
        # of Groq/Gemini quota and forcing them onto slow fallback providers.
        self.interval_minutes = max(3, config.get("proactive_interval_minutes", 15))
        self._running = False
        # Usefulness gate (P.2): don't re-ping about the SAME situation within the
        # cooldown, and stay quiet during Master's night unless it looks urgent.
        self._last_sitrep_hash = None
        self._last_sitrep_time = 0.0
        self.repeat_cooldown_s = int(config.get("proactive_repeat_cooldown_minutes", 120)) * 60
        
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
            
    def _build_situation_report(self) -> list:
        """Gather actionable items. Returns a LIST — empty means nothing needs the LLM."""
        items = []

        # Pending memory consolidation is handled by the memory worker on its own;
        # it only matters here if the queue is badly backed up.
        try:
            from .memory_tree import memory_tree_db
            pending = memory_tree_db.get_queue_depth()
            if pending > 25:
                # Bucketed, NOT the raw count. The novelty gate in _tick hashes these
                # strings to decide "same situation as last time, stay quiet" — and the
                # raw depth changes between almost every tick, so the hash never matched
                # and the cooldown never once suppressed anything. She re-reported the
                # same backlog every 15 minutes forever, which is most of "she speaks
                # unprompted". A backlog is the situation; its exact depth is not.
                bucket = "large" if pending > 200 else "moderate" if pending > 75 else "small"
                items.append(
                    f"System State: {bucket} backlog of memory chunks pending consolidation."
                )
        except Exception:
            pass

        # Scheduled tasks due soon — NOT WIRED.
        #
        # `CronManager` (server/scheduler.py) has no `peek_due_soon`, so the getattr
        # fallback fired on every tick and `due` was always []. This branch has never
        # once contributed an item; the memory backlog above is the only thing that has
        # ever populated a situation report. Left visible rather than deleted because
        # the intent is sound, but implementing it now would give her a NEW reason to
        # wake the LLM while "she speaks unprompted" is still the open complaint — so it
        # is a deliberate choice, not an oversight.
        if not hasattr(self, "_warned_no_peek"):
            self._warned_no_peek = True
            from .processor import global_cron_manager
            if not hasattr(global_cron_manager, "peek_due_soon"):
                log_info("[SUBCONSCIOUS] CronManager has no peek_due_soon() — "
                         "scheduled-task awareness is inert by design (see comment).")

        return items

    def _tick(self):
        # Deterministic gate: if nothing is actionable, DON'T wake the LLM at all.
        # Traces showed each idle tick cost ~8,300 input tokens to produce "[SKIP]" —
        # that burned ~90% of provider quota and slowed real user replies to a crawl.
        items = self._build_situation_report()
        if not items:
            log_info("[SUBCONSCIOUS] Tick: nothing actionable, skipping LLM entirely.")
            return

        # ── Usefulness gate (P.2) ──
        # Novelty: identical situation as the last handled tick → suppress (no repeat pings).
        import hashlib
        sitrep_hash = hashlib.md5("|".join(sorted(items)).encode()).hexdigest()
        now = time.time()
        if sitrep_hash == self._last_sitrep_hash and (now - self._last_sitrep_time) < self.repeat_cooldown_s:
            log_info("[SUBCONSCIOUS] Tick: same situation as last tick (cooldown active), suppressing.")
            return

        # Timing: quiet hours in Master's timezone 23:00-08:00 —
        # only wake the LLM if an item looks genuinely urgent.
        from .config import mizune_now
        ist = mizune_now()
        if (ist.hour >= 23 or ist.hour < 8):
            blob = " ".join(items).lower()
            if not any(kw in blob for kw in ("urgent", "meeting", "due", "emergency", "critical", "alarm")):
                log_info("[SUBCONSCIOUS] Tick: quiet hours (IST) and nothing urgent, suppressing.")
                return

        # Record BEFORE invoking the LLM so even an [ACT] outcome counts as handled.
        self._last_sitrep_hash = sitrep_hash
        self._last_sitrep_time = now

        log_info(f"[SUBCONSCIOUS] Heartbeat tick with {len(items)} actionable item(s)...")
        sitrep = "\n".join([f"Current Time: {mizune_now().strftime('%I:%M %p, %A, %B %d')}"] + items)

        prompt = (
            f"[SYSTEM SUBCONSCIOUS TICK]\n"
            f"You are running in the background. Master is not explicitly talking to you.\n"
            f"SITUATION REPORT:\n{sitrep}\n\n"
            f"DECISION MATRIX:\n"
            f"1. If nothing requires attention, reply exactly with [SKIP].\n"
            f"2. If you need to perform a silent background task (like using a tool to check emails or weather), reply with [ACT] and use the tool.\n"
            f"3. If there is highly important information, a finished task, or an urgent notification (e.g. meeting in 5 mins), reply with [ESCALATE] and speak to Master directly!\n\n"
            f"USEFULNESS BAR for [ESCALATE]: the message must be TIMELY (matters right now), NOVEL (you haven't told Master this already), and ACTIONABLE (Master can/should do something). "
            f"If Master would not thank you for the interruption, it fails the bar — [SKIP]. "
            f"If you ACT or ESCALATE, you MUST fulfill the action immediately. If unsure or if it's low priority, [SKIP]."
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
