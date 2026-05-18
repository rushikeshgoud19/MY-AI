"""Project Manager Agent for Mizune."""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional


class ProjectManagerAgent:
    """Agent for task and project management."""

    def __init__(self, config: Dict[str, Any]):
        self.tasks_file = config.get("tasks_file", os.path.expanduser("~/.mizune/tasks.json"))
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure tasks file exists."""
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, "w") as f:
                json.dump({"tasks": [], "projects": []}, f)

    def _load_tasks(self) -> Dict[str, Any]:
        """Load tasks from file."""
        with open(self.tasks_file, "r") as f:
            return json.load(f)

    def _save_tasks(self, data: Dict[str, Any]) -> None:
        """Save tasks to file."""
        with open(self.tasks_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_task(self, title: str, due_date: Optional[str] = None, project: Optional[str] = None) -> Dict[str, Any]:
        """Add a new task."""
        data = self._load_tasks()

        task = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "status": "pending",
            "created": datetime.now().isoformat(),
            "due_date": due_date,
            "project": project
        }

        data["tasks"].append(task)
        self._save_tasks(data)

        return {"success": True, "task": task}

    def list_tasks(self, status: Optional[str] = None, project: Optional[str] = None) -> Dict[str, Any]:
        """List tasks with optional filtering."""
        data = self._load_tasks()
        tasks = data.get("tasks", [])

        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        if project:
            tasks = [t for t in tasks if t.get("project") == project]

        return {"success": True, "tasks": tasks, "count": len(tasks)}

    def update_task(self, task_id: str, status: str) -> Dict[str, Any]:
        """Update task status."""
        data = self._load_tasks()

        for task in data["tasks"]:
            if task.get("id") == task_id:
                task["status"] = status
                task["updated"] = datetime.now().isoformat()
                self._save_tasks(data)
                return {"success": True, "task": task}

        return {"success": False, "error": "Task not found"}

    def get_progress(self, project: Optional[str] = None) -> Dict[str, Any]:
        """Get progress summary."""
        data = self._load_tasks()
        tasks = data.get("tasks", [])

        if project:
            tasks = [t for t in tasks if t.get("project") == project]

        total = len(tasks)
        completed = len([t for t in tasks if t.get("status") == "completed"])
        pending = len([t for t in tasks if t.get("status") == "pending"])

        return {
            "success": True,
            "total": total,
            "completed": completed,
            "pending": pending,
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        data = self._load_tasks()
        original_count = len(data["tasks"])

        data["tasks"] = [t for t in data["tasks"] if t.get("id") != task_id]

        if len(data["tasks"]) == original_count:
            return {"success": False, "error": "Task not found"}

        self._save_tasks(data)
        return {"success": True}