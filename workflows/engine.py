"""Workflow Engine for Mizune."""
import json
import os
import threading
import time
from typing import Dict, Any, List, Optional

try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False
    schedule = None


class WorkflowEngine:
    """Engine for managing automated workflows."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.workflows_dir = config.get("workflows_dir", os.path.expanduser("~/.mizune/workflows"))
        self.workflows: Dict[str, Dict] = {}
        self.running = False
        self._scheduler_thread = None

        os.makedirs(self.workflows_dir, exist_ok=True)
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Load all workflow definitions."""
        if not os.path.exists(self.workflows_dir):
            return

        for filename in os.listdir(self.workflows_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.workflows_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        workflow = json.load(f)
                        name = workflow.get('name', filename[:-5])
                        self.workflows[name] = workflow
                except Exception as e:
                    print(f"Failed to load workflow {filename}: {e}")

    def add_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new workflow."""
        name = workflow.get('name', 'unnamed')
        self.workflows[name] = workflow

        # Save to file
        filepath = os.path.join(self.workflows_dir, f"{name}.json")
        with open(filepath, 'w') as f:
            json.dump(workflow, f, indent=2)

        return {"success": True, "name": name}

    def remove_workflow(self, name: str) -> Dict[str, Any]:
        """Remove a workflow."""
        if name not in self.workflows:
            return {"success": False, "error": "Workflow not found"}

        del self.workflows[name]

        filepath = os.path.join(self.workflows_dir, f"{name}.json")
        if os.path.exists(filepath):
            os.remove(filepath)

        return {"success": True}

    def list_workflows(self) -> Dict[str, Any]:
        """List all workflows."""
        return {
            "success": True,
            "workflows": [
                {
                    "name": name,
                    "trigger": w.get("trigger", {}),
                    "actions_count": len(w.get("actions", []))
                }
                for name, w in self.workflows.items()
            ]
        }

    def execute_workflow(self, name: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a workflow manually."""
        if name not in self.workflows:
            return {"success": False, "error": "Workflow not found"}

        workflow = self.workflows[name]
        actions = workflow.get("actions", [])

        results = []
        for action in actions:
            result = self._execute_action(action, context or {})
            results.append(result)

        return {
            "success": True,
            "workflow": name,
            "results": results
        }

    def _execute_action(self, action: Dict[str, Any], context: Dict) -> Dict[str, Any]:
        """Execute a single action."""
        action_type = action.get("type", "")

        if action_type == "note":
            return {"type": "note", "content": action.get("content", "")}

        elif action_type == "search":
            return {"type": "search", "query": action.get("query", "")}

        elif action_type == "speak":
            return {"type": "speak", "text": action.get("text", "")}

        elif action_type == "command":
            return {"type": "command", "command": action.get("command", "")}

        else:
            return {"type": "unknown", "error": f"Unknown action type: {action_type}"}

    def start_scheduler(self) -> None:
        """Start the workflow scheduler."""
        if self.running:
            return

        self.running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        """Stop the workflow scheduler."""
        self.running = False

    def _run_scheduler(self) -> None:
        """Run the scheduler loop."""
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def schedule_workflow(self, name: str, schedule_str: str) -> Dict[str, Any]:
        """Schedule a workflow to run at intervals."""
        if name not in self.workflows:
            return {"success": False, "error": "Workflow not found"}

        try:
            if schedule_str.startswith("every"):
                # e.g., "every 30 minutes"
                interval = schedule_str.split()[1]
                if "minute" in interval:
                    mins = int(interval.split()[0])
                    schedule.every(mins).minutes.do(lambda: self.execute_workflow(name))
                elif "hour" in interval:
                    hours = int(interval.split()[0])
                    schedule.every(hours).hours.do(lambda: self.execute_workflow(name))
                elif "day" in interval:
                    schedule.every().day.do(lambda: self.execute_workflow(name))

            return {"success": True, "scheduled": schedule_str}
        except Exception as e:
            return {"success": False, "error": str(e)}


def create_example_workflow() -> Dict[str, Any]:
    """Create an example workflow."""
    return {
        "name": "Morning Summary",
        "description": "Summary of tasks at start of day",
        "trigger": {
            "type": "scheduled",
            "schedule": "every day at 9am"
        },
        "actions": [
            {
                "type": "search",
                "query": "tasks due today"
            },
            {
                "type": "speak",
                "text": "You have X tasks due today"
            }
        ]
    }