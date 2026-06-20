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
from server.ai import get_ai_response
from server.skills import skill_manager

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
        log_info("[SKILL EVOLVER] Deep Research: Analyzing recent memory to find skill gaps...")
        try:
            cursor = self.memory.db.cursor()
            # Fetch last 50 conversational exchanges
            logs = cursor.execute("SELECT content FROM episodic ORDER BY timestamp DESC LIMIT 50").fetchall()
            if not logs: return
            
            chat_history = "\n".join([r[0] for r in logs])
            
            prompt = f"""
            Analyze this recent chat history between the Master and Mizune. 
            Identify if there are any specific tasks the Master asked Mizune to do that she failed at, struggled with, or couldn't do because she lacked a skill/tool.
            If you find a missing skill, write the Python code for a new Mizune Skill to solve it.
            
            A Mizune skill must be a single function named 'execute(*args, **kwargs)' that returns a string.
            Only return the raw python code. Do not include markdown blocks. Do not explain.
            If no new skill is needed, return 'NO_SKILL_NEEDED'.
            
            History:
            {chat_history}
            """
            
            resp = get_ai_response(prompt, provider="local").strip()
            
            if resp and "NO_SKILL_NEEDED" not in resp and "def execute" in resp:
                # We generated a new skill! Let's save it.
                skill_name = f"auto_skill_{int(time.time())}"
                code = resp.replace('```python', '').replace('```', '').strip()
                desc = f"Autonomously generated skill to address a gap found during deep evolution research."
                
                log_info(f"[SKILL EVOLVER] 🧬 EVOLUTION: Generated new skill '{skill_name}'!")
                # Distill the skill into the system (this creates the .py file in staging/active)
                skill_manager.create_skill(skill_name, desc, code, requires_approval=True)
                
        except Exception as e:
            log_info(f"[SKILL EVOLVER] Failed: {e}")

class BehaviorEvolver:
    def __init__(self, memory, emotion):
        self.memory = memory
        self.emotion = emotion
    async def evolve_greeting(self):
        log_info("[BEHAVIOR EVOLVER] Running LLM emotional synthesis...")
        try:
            cursor = self.memory.db.cursor()
            frustrations = cursor.execute("SELECT content FROM episodic WHERE content LIKE '%annoyed%' OR content LIKE '%frustrated%' LIMIT 10").fetchall()
            if frustrations:
                log_info("[BEHAVIOR EVOLVER] Found user frustration, adapting response templates...")
                # Insert a rule into memory to be more concise
                self.memory.insert_chunk(f"behavior_patch_{int(time.time())}", "rules", "The user was recently frustrated. Be extremely concise and apologetic.", 10, {})
        except Exception as e:
            pass

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
