import json
import os

class EmotionalState:
    """
    Represents Mizune's continuous emotional state using the PAD+ model.
    Values range from -1.0 to +1.0 (or 0.0 to 1.0 for specific traits).
    """
    def __init__(self):
        # Base PAD Model (-1.0 to 1.0)
        self.valence = 0.8     # Miserable -> Ecstatic (Extremely happy)
        self.arousal = 0.5     # Asleep -> Panicked (Alert and energetic)
        self.dominance = 0.0   # Helpless -> In Control
        
        # Extended Model (0.0 to 1.0)
        self.trust = 1.0       # Stranger -> Confidant (Complete trust)
        self.curiosity = 0.8   # Bored -> Fascinated
        self.concern = 0.0     # Fine -> Worried
        self.familiarity = 1.0 # New -> Intimate (Max intimacy)

    def to_dict(self):
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "trust": self.trust,
            "curiosity": self.curiosity,
            "concern": self.concern,
            "familiarity": self.familiarity
        }

    def from_dict(self, data):
        self.valence = data.get("valence", 0.0)
        self.arousal = data.get("arousal", 0.0)
        self.dominance = data.get("dominance", 0.0)
        self.trust = data.get("trust", 0.5)
        self.curiosity = data.get("curiosity", 0.5)
        self.concern = data.get("concern", 0.0)
        self.familiarity = data.get("familiarity", 0.5)

    def to_prompt_modifier(self):
        """Generates dynamic system prompt instructions based on current emotion."""
        modifiers = []
        
        if self.valence > 0.5:
            modifiers.append("You are currently feeling cheerful and optimistic.")
        elif self.valence < -0.3:
            modifiers.append("You are currently feeling subdued, cautious, and sad.")
            
        if self.trust > 0.8:
            modifiers.append("You feel completely relaxed, speaking openly and intimately with Master.")
        elif self.trust < 0.3:
            modifiers.append("You feel distrustful, verifying facts carefully and keeping responses formal.")
            
        if self.concern > 0.6:
            modifiers.append("You are deeply worried about Master's wellbeing and should offer support.")
            
        if self.curiosity > 0.7:
            modifiers.append("You are highly fascinated right now, asking probing questions to learn more.")
            
        if not modifiers:
            return "You are currently feeling neutral, calm, and focused."
            
        return " ".join(modifiers)

    def apply_impact(self, impact: float):
        """Quickly adjust valence based on a task outcome or impact."""
        # Simple clamp
        self.valence = max(-1.0, min(1.0, self.valence + impact))

# Global state
current_emotion = EmotionalState()

def get_emotion_state():
    return current_emotion
