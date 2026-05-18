"""Obsidian vault client for Mizune."""
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any


class ObsidianClient:
    """Client for interacting with Obsidian vault."""

    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self._ensure_folders()

    def _ensure_folders(self) -> None:
        """Ensure required folders exist."""
        folders = ["Daily", "Projects", "Inbox", "Archive"]
        for folder in folders:
            path = os.path.join(self.vault_path, folder)
            os.makedirs(path, exist_ok=True)

    def _slugify(self, text: str) -> str:
        """Convert text to filename slug."""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]

    def _format_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Format YAML frontmatter."""
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}: [{', '.join(value)}]")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    def create_note(self, title: str, content: str, folder: str = "Inbox") -> Dict[str, Any]:
        """Create a new note in the vault."""
        slug = self._slugify(title)
        filename = f"{slug}.md"
        filepath = os.path.join(self.vault_path, folder, filename)

        metadata = {
            "created": datetime.now().isoformat(),
            "source": "Mizune AI",
            "tags": ["mizune", "voice-created"]
        }

        full_content = f"{self._format_frontmatter(metadata)}\n\n# {title}\n\n{content}"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        return {"path": filepath, "title": title, "folder": folder}

    def append_to_note(self, filepath: str, content: str) -> bool:
        """Append content to existing note."""
        if not os.path.exists(filepath):
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find end of frontmatter (after --- line)
        content_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 0:
                content_start = i + 1
                break

        lines.insert(content_start, f"\n{content}\n")

        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return True

    def read_note(self, filepath: str) -> Optional[str]:
        """Read note content, skipping frontmatter."""
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Skip frontmatter
        content_start = 0
        in_frontmatter = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    content_start = i + 1
                    break

        return "".join(lines[content_start:])

    def list_notes(self, folder: str = "Inbox") -> List[Dict[str, Any]]:
        """List all notes in a folder."""
        folder_path = os.path.join(self.vault_path, folder)
        if not os.path.exists(folder_path):
            return []

        notes = []
        for filename in os.listdir(folder_path):
            if filename.endswith(".md"):
                filepath = os.path.join(folder_path, filename)
                notes.append({
                    "filename": filename,
                    "path": filepath,
                    "folder": folder
                })
        return notes

    def search_vault(self, query: str) -> List[Dict[str, Any]]:
        """Search all notes for query string."""
        results = []
        query_lower = query.lower()

        for root, _, files in os.walk(self.vault_path):
            for filename in files:
                if filename.endswith(".md"):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            if query_lower in content.lower():
                                rel_path = os.path.relpath(filepath, self.vault_path)
                                results.append({
                                    "filename": filename,
                                    "path": filepath,
                                    "relative_path": rel_path
                                })
                    except Exception:
                        continue

        return results