import asyncio
import time
import uuid
import threading
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass, field
from typing import List, Dict, Any

from server.config import log_info
from server.memory_tree import memory_tree_db
from server.afk_detector import afk_detector
from server.evolution_budget import evolution_budget
from server.emotion_engine import global_emotion_state

def generate_id():
    return uuid.uuid4().hex[:8]

@dataclass
class EvolutionHypothesis:
    id: str
    level: int
    target: str
    current_state: str
    proposed_change: str
    motivation: str
    expected_improvement: str
    risk_level: float
    expected_improvement_delta: float = 0.3
    validation_strategy: str = ""
    rollback_strategy: str = ""
    blast_radius: List[str] = field(default_factory=list)

class SkillEvolver:
    def __init__(self, memory, evolution):
        self.memory = memory
        self.evolution = evolution
    async def evolve(self):
        log_info("[SKILL EVOLVER] Checking skills for optimization...")
        # Placeholder logic for the DB calls
        pass

class BehaviorEvolver:
    def __init__(self, memory, emotion):
        self.memory = memory
        self.emotion = emotion
    async def evolve_greeting(self):
        log_info("[BEHAVIOR EVOLVER] Analyzing greetings...")

class ArchitectureEvolver:
    def __init__(self, memory):
        self.memory = memory

    async def evolve(self):
        log_info("[ARCHITECTURE EVOLVER] Looking for core bottlenecks...")
        # Example hypothesis generation
        hypothesis = EvolutionHypothesis(
            id=generate_id(),
            level=3,
            target="architecture:module:file_format_converter",
            current_state="No central conversion logic.",
            proposed_change="Add FileFormatConverter class to simplify PDF to TXT.",
            motivation="I noticed we spend a lot of time converting files manually.",
            expected_improvement="Reduce conversion time by 70%",
            risk_level=0.4,
            rollback_strategy="Delete FileFormatConverter and revert imports."
        )
        await self._request_approval(hypothesis)

    async def _request_approval(self, hypothesis: EvolutionHypothesis):
        log_info(f"[ARCHITECTURE] Requesting mandatory approval for {hypothesis.target}")
        
        # We need a tkinter popup
        def show_popup():
            root = tk.Tk()
            root.withdraw() # Hide the main window
            root.attributes('-topmost', True) # Bring to front
            
            msg = f"""🧬 MIZUNE WANTS TO EVOLVE HER CODE 🧬

Target: {hypothesis.target}

What: {hypothesis.proposed_change}
Why: {hypothesis.motivation}
Expected: {hypothesis.expected_improvement}

Risk Level: {hypothesis.risk_level:.0%}
Rollback: {hypothesis.rollback_strategy}

Do you approve this Architecture Patch?"""
            
            result = messagebox.askyesnocancel("Mizune Level 3 Evolution", msg, parent=root)
            root.destroy()
            return result

        # Run UI on a separate thread but wait for result
        result_container = []
        def ui_thread():
            res = show_popup()
            result_container.append(res)
            
        t = threading.Thread(target=ui_thread)
        t.start()
        
        while t.is_alive():
            await asyncio.sleep(0.5)
            
        res = result_container[0] if result_container else None
        
        if res is True:
            log_info(f"[ARCHITECTURE] User APPROVED patch {hypothesis.target}")
            # apply patch...
        elif res is False:
            log_info(f"[ARCHITECTURE] User REJECTED patch {hypothesis.target}")
        else:
            log_info(f"[ARCHITECTURE] User SNOOZED patch {hypothesis.target}")

class MetaEvolver:
    def __init__(self, evolution_engine):
        self.evolution = evolution_engine
    async def evolve(self):
        if not afk_detector.is_afk():
            return
        log_info("[META EVOLVER] Analyzing evolution success rate...")

class EvolutionEngine:
    def __init__(self):
        self.last_evolution_time = 0
        self.evolution_cooldown = 4 * 3600  # 4 hours
        self.paused = False
        self.generation = 0
        self.running = False
        
        self.skill_evolver = SkillEvolver(memory_tree_db, self)
        self.behavior_evolver = BehaviorEvolver(memory_tree_db, global_emotion_state)
        self.architecture_evolver = ArchitectureEvolver(memory_tree_db)
        self.meta_evolver = MetaEvolver(self)

    def get_status(self) -> Dict[str, Any]:
        return {
            "paused": self.paused,
            "budget_spent": evolution_budget.get_spend_today(),
            "budget_limit": evolution_budget.daily_limit_dollars,
            "time_since_last_evolve": time.time() - self.last_evolution_time,
            "generation": self.generation
        }

    def _observe_sql_only(self) -> List[dict]:
        """Token-free observation."""
        observations = []
        try:
            cursor = memory_tree_db.db.cursor()
            frustration = cursor.execute("SELECT COUNT(*) FROM emotional_memory WHERE detected_emotion IN ('frustration','anger','confusion') AND timestamp > ?", (time.time() - 86400,)).fetchone()
            if frustration and frustration[0] >= 5:
                observations.append({'type': 'user_frustration', 'target': 'behavior:interaction_style', 'severity': 'critical'})
        except Exception as e:
            log_info(f"[EVOLUTION] Observe error: {e}")
        return observations

    async def _run_evolution_cycle(self):
        if self.running: return
        self.running = True
        
        try:
            log_info(f"[EVOLUTION] Starting Cycle {self.generation}")
            
            # PHASE 1: OBSERVE
            observations = self._observe_sql_only()
            
            # PHASE 2/3/4/5: Level-Specific Evolvers
            await self.skill_evolver.evolve()
            await self.behavior_evolver.evolve_greeting()
            
            # Architecture (Level 3) requires approval
            await self.architecture_evolver.evolve()
            
            # PHASE 8: Meta-Evolve
            if self.generation % 10 == 0 and afk_detector.is_afk():
                await self.meta_evolver.evolve()
                
            self.generation += 1
            self.last_evolution_time = time.time()
            log_info("[EVOLUTION] Cycle Complete.")
        finally:
            self.running = False

    async def evolution_loop(self):
        log_info("[EVOLUTION] Engine v3.0 started in background.")
        while True:
            await asyncio.sleep(30)
            
            if self.paused:
                continue

            if not afk_detector.is_afk():
                continue

            if (time.time() - self.last_evolution_time) < self.evolution_cooldown:
                continue

            if not evolution_budget.can_evolve():
                continue

            try:
                await self._run_evolution_cycle()
            except Exception as e:
                log_info(f"[EVOLUTION] Cycle failed: {e}")

evolution_engine = EvolutionEngine()

def _start_evolution_bg():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(evolution_engine.evolution_loop())

threading.Thread(target=_start_evolution_bg, daemon=True).start()
