import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from server.memory_tree import memory_tree_db
from server.config import log_info

@dataclass
class EmotionalState:
    valence: float = 0.0        # -1 (miserable) to +1 (ecstatic)
    arousal: float = 0.2        # -1 (asleep) to +1 (panicked)
    dominance: float = 0.0      # -1 (helpless) to +1 (in control)
    trust: float = 0.5          # 0 (stranger) to 1 (confidant)
    familiarity: float = 0.0    # 0 (new) to 1 (intimate)
    curiosity: float = 0.5      # 0 (bored) to 1 (fascinated)
    confidence: float = 0.5     # 0 (uncertain) to 1 (certain)
    concern: float = 0.0        # 0 (fine) to 1 (worried about user)
    protectiveness: float = 0.0 # 0 (neutral) to 1 (mother hen)
    
    def to_dict(self) -> dict:
        return {
            "valence": self.valence, "arousal": self.arousal, "dominance": self.dominance,
            "trust": self.trust, "familiarity": self.familiarity, "curiosity": self.curiosity,
            "confidence": self.confidence, "concern": self.concern, "protectiveness": self.protectiveness
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_prompt_modifier(self) -> str:
        modifiers = []
        if self.valence > 0.5:
            modifiers.append("You are cheerful and optimistic.")
        elif self.valence < -0.3:
            modifiers.append("You are subdued and careful with your words.")
        if self.trust > 0.8:
            modifiers.append("You speak openly and share your reasoning freely.")
        elif self.trust < 0.3:
            modifiers.append("You are cautious and verify facts carefully.")
        if self.concern > 0.6:
            modifiers.append("You check on the user's wellbeing and offer support.")
        if self.curiosity > 0.7:
            modifiers.append("You ask probing questions and explore alternatives.")
        return " ".join(modifiers) if modifiers else "You are neutral and helpful."
    
    def to_vrm_expression(self) -> dict:
        """Map emotion to V-Tuber blendshapes"""
        blendshapes = {}
        if self.valence > 0.3:
            blendshapes['happy'] = min(1.0, self.valence)
        elif self.valence < -0.3:
            blendshapes['sad'] = min(1.0, abs(self.valence))
        if self.arousal > 0.5:
            blendshapes['surprised'] = min(1.0, self.arousal)
        if self.trust > 0.7:
            blendshapes['relaxed'] = (self.trust - 0.7) / 0.3
        if self.concern > 0.5:
            blendshapes['worried'] = (self.concern - 0.5) / 0.5
        if self.curiosity > 0.6:
            blendshapes['interested'] = (self.curiosity - 0.6) / 0.4
        return {
            'blendshapes': blendshapes,
            'blink_rate': 0.15 if self.arousal < 0 else 0.25,
            'breathing_rate': 0.1 + (self.arousal * 0.1)
        }

class EmotionalMemory:
    def __init__(self, db):
        self.db = db
    
    def record_interaction(self, session_id: str, user_input: str, mizune_response: str, 
                          detected_emotion: str, task_outcome: str, duration: float):
        if not self.db.db: return
        try:
            impact = self._calculate_impact(detected_emotion, task_outcome, duration)
            entities = self._extract_entities(user_input, mizune_response)
            
            cursor = self.db.db.cursor()
            cursor.execute("""
                INSERT INTO emotional_memory 
                (session_id, user_input, mizune_response, detected_emotion, task_outcome, impact_score, entities, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user_input, mizune_response, detected_emotion, task_outcome, impact, json.dumps(entities), duration))
            
            for entity in entities:
                self._update_connection_strength(entity, impact)
                
            self.db.db.commit()
        except Exception as e:
            log_info(f"[EMOTION ENGINE] Failed to record interaction: {e}")
    
    def _calculate_impact(self, emotion: str, outcome: str, duration: float) -> float:
        base = 0.0
        outcome_map = {'success': 0.5, 'failure': -0.3, 'abandoned': -0.1, 'ongoing': 0.1}
        base += outcome_map.get(outcome, 0.0)
        emotion_map = {'joy': 0.3, 'gratitude': 0.4, 'excitement': 0.3, 'frustration': -0.4, 'anger': -0.5}
        base += emotion_map.get(emotion, 0.0)
        base += min(duration / 3600, 1.0) * 0.2
        return max(-1.0, min(1.0, base))
    
    def _update_connection_strength(self, entity: str, impact: float):
        DECAY = 0.95
        cursor = self.db.db.cursor()
        row = cursor.execute("SELECT strength, last_updated FROM connection_strength WHERE entity = ?", (entity,)).fetchone()
        
        if row:
            old_strength, last_updated = row
            days_passed = (time.time() - last_updated) / 86400
            decayed = old_strength * (DECAY ** days_passed)
            new_strength = decayed + impact * (1 - decayed) * 0.3
        else:
            new_strength = max(0.0, impact * 0.5)
        
        cursor.execute("""
            INSERT INTO connection_strength (entity, strength, last_updated, interaction_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(entity) DO UPDATE SET
                strength = excluded.strength,
                last_updated = excluded.last_updated,
                interaction_count = interaction_count + 1
        """, (entity, max(0.0, min(1.0, new_strength)), time.time()))

    def _extract_entities(self, text_in: str, text_out: str) -> List[str]:
        # Minimal extraction for now
        words = (text_in + " " + text_out).split()
        return [w for w in words if len(w) > 5][:3]
        
    def prime_emotion(self, user_input: str, current_state: EmotionalState) -> EmotionalState:
        """Modifies current emotion based on incoming text."""
        # A simple keyword based modulation to prove the architecture
        if any(w in user_input.lower() for w in ['sad', 'bad', 'failed', 'cry']):
            current_state.valence -= 0.2
            current_state.concern += 0.3
        elif any(w in user_input.lower() for w in ['good', 'yay', 'happy', 'thanks', 'awesome']):
            current_state.valence += 0.3
        return current_state

# Global instances
global_emotion_state = EmotionalState()
emotional_memory = EmotionalMemory(memory_tree_db)
