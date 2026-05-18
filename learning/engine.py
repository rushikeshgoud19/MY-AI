"""Learning Engine for Mizune."""
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict


class LearningEngine:
    """Engine for learning user preferences and patterns."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.learning_file = config.get("learning_file", os.path.expanduser("~/.mizune/learning.json"))
        self._load_learning_data()

    def _load_learning_data(self) -> None:
        """Load learning data from file."""
        if os.path.exists(self.learning_file):
            try:
                with open(self.learning_file, 'r') as f:
                    data = json.load(f)
                    self.command_history = data.get("command_history", [])
                    self.app_preferences = data.get("app_preferences", {})
                    self.time_patterns = data.get("time_patterns", {})
                    self.conversation_context = data.get("conversation_context", {})
            except Exception:
                pass

        # Initialize defaults
        self.command_history = self.command_history if hasattr(self, 'command_history') else []
        self.app_preferences = self.app_preferences if hasattr(self, 'app_preferences') else {}
        self.time_patterns = self.time_patterns if hasattr(self, 'time_patterns') else {}
        self.conversation_context = self.conversation_context if hasattr(self, 'conversation_context') else {}

    def _save_learning_data(self) -> None:
        """Save learning data to file."""
        os.makedirs(os.path.dirname(self.learning_file), exist_ok=True)
        data = {
            "command_history": self.command_history[-100:],  # Keep last 100
            "app_preferences": self.app_preferences,
            "time_patterns": self.time_patterns,
            "conversation_context": self.conversation_context
        }
        with open(self.learning_file, 'w') as f:
            json.dump(data, f, indent=2)

    def record_command(self, command: str) -> None:
        """Record a command for pattern learning."""
        timestamp = datetime.now()

        # Add to history
        self.command_history.append({
            "command": command.lower().strip(),
            "timestamp": timestamp.isoformat(),
            "hour": timestamp.hour,
            "day_of_week": timestamp.strftime("%A")
        })

        self._save_learning_data()

    def get_command_suggestions(self) -> List[str]:
        """Get command suggestions based on history."""
        if not self.command_history:
            return []

        # Get recent commands
        recent = [c["command"] for c in self.command_history[-20:]]
        suggestions = list(set(recent))[:5]
        return suggestions

    def learn_app_preference(self, action: str, app: str) -> None:
        """Learn user preference for an app."""
        if action not in self.app_preferences:
            self.app_preferences[action] = {}

        if app not in self.app_preferences[action]:
            self.app_preferences[action][app] = 0

        self.app_preferences[action][app] += 1
        self._save_learning_data()

    def get_preferred_app(self, action: str) -> Optional[str]:
        """Get user's preferred app for an action."""
        if action not in self.app_preferences:
            return None

        app_counts = self.app_preferences[action]
        if not app_counts:
            return None

        # Return most used app
        return max(app_counts.keys(), key=lambda k: app_counts[k])

    def record_time_pattern(self, hour: int, activity: str) -> None:
        """Record time-based activity pattern."""
        if hour not in self.time_patterns:
            self.time_patterns[hour] = defaultdict(int)

        self.time_patterns[hour][activity] += 1
        self._save_learning_data()

    def get_peak_activity_hours(self) -> List[int]:
        """Get hours when user is most active."""
        if not self.time_patterns:
            return []

        hour_counts = {hour: sum(activities.values()) for hour, activities in self.time_patterns.items()}
        sorted_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)
        return sorted_hours[:3]

    def update_context(self, key: str, value: Any) -> None:
        """Update conversation context."""
        self.conversation_context[key] = {
            "value": value,
            "updated": datetime.now().isoformat()
        }
        self._save_learning_data()

    def get_context(self, key: str) -> Optional[Any]:
        """Get conversation context."""
        if key in self.conversation_context:
            return self.conversation_context[key].get("value")
        return None

    def clear_learning(self) -> Dict[str, Any]:
        """Clear all learning data."""
        self.command_history = []
        self.app_preferences = {}
        self.time_patterns = {}
        self.conversation_context = {}
        self._save_learning_data()
        return {"success": True}

    def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        return {
            "commands_recorded": len(self.command_history),
            "app_preferences_count": len(self.app_preferences),
            "time_patterns_hours": len(self.time_patterns),
            "context_entries": len(self.conversation_context)
        }