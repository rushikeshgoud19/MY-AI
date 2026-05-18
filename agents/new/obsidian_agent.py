"""Obsidian Agent for knowledge management."""
import os
from typing import Dict, Any, Optional
from obsidian.client import ObsidianClient


class ObsidianAgent:
    """Agent for Obsidian vault interactions."""

    def __init__(self, config: Dict[str, Any]):
        vault_path = config.get("obsidian_vault_path", "")
        if not vault_path or not os.path.exists(vault_path):
            self.client = None
            return
        self.client = ObsidianClient(vault_path)

    def create_note(self, title: str, content: str, folder: str = "Inbox") -> Dict[str, Any]:
        """Create a new note."""
        if not self.client:
            return {"success": False, "error": "Obsidian vault not configured"}

        try:
            result = self.client.create_note(title, content, folder)
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_to_daily(self, content: str) -> Dict[str, Any]:
        """Append to today's daily note."""
        if not self.client:
            return {"success": False, "error": "Obsidian vault not configured"}

        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}.md"
        daily_path = os.path.join(self.client.vault_path, "Daily", filename)

        if not os.path.exists(daily_path):
            self.client.create_note(f"Daily Note - {date_str}", "", "Daily")

        success = self.client.append_to_note(daily_path, content)
        return {"success": success, "path": daily_path}

    def search_notes(self, query: str) -> Dict[str, Any]:
        """Search vault for notes."""
        if not self.client:
            return {"success": False, "error": "Obsidian vault not configured", "results": []}

        results = self.client.search_vault(query)
        return {"success": True, "results": results}

    def list_folder(self, folder: str = "Inbox") -> Dict[str, Any]:
        """List notes in a folder."""
        if not self.client:
            return {"success": False, "error": "Obsidian vault not configured", "notes": []}

        notes = self.client.list_notes(folder)
        return {"success": True, "notes": notes}

    def read_note(self, filepath: str) -> Dict[str, Any]:
        """Read a note."""
        if not self.client:
            return {"success": False, "error": "Obsidian vault not configured"}

        content = self.client.read_note(filepath)
        if content is None:
            return {"success": False, "error": "Note not found"}

        return {"success": True, "content": content}