"""File Organizer Agent for Mizune."""
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List


class FileOrganizerAgent:
    """Agent for automatic file organization."""

    FILE_TYPES = {
        "Documents": [".txt", ".pdf", ".doc", ".docx", ".md", ".rtf"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
        "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
        "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "Data": [".csv", ".json", ".xml", ".xlsx", ".xls"],
        "Code": [".py", ".js", ".java", ".cpp", ".c", ".h", ".html", ".css"]
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _get_category(self, filename: str) -> str:
        """Determine category for a file."""
        ext = os.path.splitext(filename)[1].lower()
        for category, extensions in self.FILE_TYPES.items():
            if ext in extensions:
                return category
        return "Other"

    def organize_folder(self, folder_path: str, strategy: str = "by_type") -> Dict[str, Any]:
        """Organize files in a folder."""
        if not os.path.exists(folder_path):
            return {"success": False, "error": "Folder not found"}

        files_moved = []
        errors = []

        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if not os.path.isfile(filepath):
                continue

            try:
                if strategy == "by_type":
                    category = self._get_category(filename)
                    dest_folder = os.path.join(folder_path, category)
                    os.makedirs(dest_folder, exist_ok=True)
                    dest_path = os.path.join(dest_folder, filename)
                    shutil.move(filepath, dest_path)
                    files_moved.append({"from": filepath, "to": dest_path})

                elif strategy == "by_date":
                    mtime = os.path.getmtime(filepath)
                    date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m")
                    dest_folder = os.path.join(folder_path, date_str)
                    os.makedirs(dest_folder, exist_ok=True)
                    dest_path = os.path.join(dest_folder, filename)
                    shutil.move(filepath, dest_path)
                    files_moved.append({"from": filepath, "to": dest_path})

            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return {
            "success": True,
            "files_moved": len(files_moved),
            "moved_details": files_moved[:10],
            "errors": errors
        }

    def sort_downloads(self) -> Dict[str, Any]:
        """Sort the user's Downloads folder."""
        downloads = os.path.expanduser("~/Downloads")
        return self.organize_folder(downloads, "by_type")

    def cleanup_duplicates(self, folder_path: str) -> Dict[str, Any]:
        """Find and report duplicate files."""
        if not os.path.exists(folder_path):
            return {"success": False, "error": "Folder not found"}

        size_map = {}
        duplicates = []

        for root, _, files in os.walk(folder_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    size = os.path.getsize(filepath)
                    if size in size_map:
                        duplicates.append({
                            "file1": size_map[size],
                            "file2": filepath,
                            "size": size
                        })
                    else:
                        size_map[size] = filepath
                except Exception:
                    continue

        return {
            "success": True,
            "duplicate_count": len(duplicates),
            "duplicates": duplicates[:20]
        }