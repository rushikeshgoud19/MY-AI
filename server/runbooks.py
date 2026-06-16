import json
import logging
from typing import List, Dict

from .config import log_info
from .memory import memory

class RunbookManager:
    """
    Manages Executable Runbooks (Skills).
    Allows recording a sequence of UI interactions and saving them to FTS5 
    so Mizune can execute them autonomously later.
    """
    def __init__(self):
        self.is_recording = False
        self.current_sequence: List[Dict] = []
        self.runbook_name = ""
        self.runbook_description = ""

    def start_recording(self, name: str, description: str):
        """Start tracking a new sequence."""
        self.is_recording = True
        self.current_sequence = []
        self.runbook_name = name
        self.runbook_description = description
        log_info(f"[RUNBOOK] Started recording skill: {name}")

    def log_action(self, action_type: str, target: str, value: str = ""):
        """Add an action to the current recording sequence."""
        if not self.is_recording:
            return
            
        step = {
            "action": action_type,
            "target": target,
            "value": value
        }
        self.current_sequence.append(step)
        log_info(f"[RUNBOOK] Recorded step: {step}")

    def save_recording(self) -> bool:
        """Commit the recorded sequence to the FTS5 skills database."""
        if not self.is_recording or not self.current_sequence:
            log_info("[RUNBOOK] Nothing to save.")
            self.is_recording = False
            return False
            
        payload = json.dumps(self.current_sequence)
        try:
            if memory.db:
                cursor = memory.db.cursor()
                cursor.execute(
                    "INSERT INTO skills_fts (name, description, code_payload) VALUES (?, ?, ?)",
                    (self.runbook_name, self.runbook_description, payload)
                )
                memory.db.commit()
                log_info(f"[RUNBOOK] Saved skill '{self.runbook_name}' to FTS5 memory.")
                
            self.is_recording = False
            self.current_sequence = []
            return True
        except Exception as e:
            log_info(f"[RUNBOOK] Error saving skill: {e}")
            self.is_recording = False
            return False

    def retrieve_skill(self, keyword: str) -> str:
        """Search the FTS5 database for a skill by keyword."""
        try:
            if not memory.db:
                return "Memory database offline."
                
            cursor = memory.db.cursor()
            # FTS5 Match query
            cursor.execute(
                "SELECT name, description, code_payload FROM skills_fts WHERE skills_fts MATCH ? ORDER BY rank LIMIT 1", 
                (keyword,)
            )
            row = cursor.fetchone()
            if row:
                name, desc, payload = row
                return f"Found Skill: {name}\nDescription: {desc}\nPayload: {payload}"
            return "No matching skill found."
        except Exception as e:
            log_info(f"[RUNBOOK] Error retrieving skill: {e}")
            return f"Error searching memory: {str(e)}"

# Global singleton
runbook_manager = RunbookManager()
