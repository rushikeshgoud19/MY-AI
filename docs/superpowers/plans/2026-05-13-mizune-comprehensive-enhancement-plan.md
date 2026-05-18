# Mizune Comprehensive Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Obsidian integration, 6 new specialized agents, workflow system, and learning engine for Mizune OS while maintaining existing stable core.

**Architecture:** Hybrid approach - keep existing server.py/agents/core stable, create new parallel services under new directories (agents/new/, workflows/, learning/, obsidian/). Each new component is a self-contained module that integrates via well-defined interfaces.

**Tech Stack:** Python (FastAPI, asyncio), ChromaDB (memory), pandas/matplotlib (data analysis), markdown parsing, filesystem I/O, cron scheduling.

---

## File Structure Overview

### New Directories (Create)
- `agents/new/` - New agent modules (obsidian, data_analysis, research, file_organizer, code_review, project_manager)
- `workflows/` - Workflow engine and definitions
- `learning/` - User learning engine
- `obsidian/` - Obsidian integration utilities

### Modify Existing
- `config.json` - Add obsidian_vault_path, workflow settings, learning settings
- `server.py` - Register new agents in AGENTS dict, add intent routing for new commands
- `agents/manager_agent.py` - Add intent routing for new agent commands
- `core/__init__.py` - Export new modules

---

## Phase 1: Foundation (Obsidian Integration)

### Task 1: Obsidian Configuration

**Files:**
- Modify: `config.json`
- Create: `tests/test_obsidian_config.py`

- [ ] **Step 1: Write failing test for obsidian config**

```python
def test_obsidian_config_loaded():
    from core.config import load_config
    cfg = load_config()
    assert "obsidian_vault_path" in cfg
    assert cfg.get("obsidian_vault_path") != ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_obsidian_config.py -v
```
Expected: FAIL - KeyError or assertion error

- [ ] **Step 3: Add obsidian config to DEFAULT_CONFIG in server.py**

```python
# In DEFAULT_CONFIG dict (around line 58), add:
"obsidian_vault_path": "",
"obsidian_default_folder": "Inbox",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_obsidian_config.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.json server.py tests/test_obsidian_config.py
git commit -m "feat: add obsidian configuration to defaults"
```

---

### Task 2: Create Obsidian Utility Module

**Files:**
- Create: `obsidian/client.py`
- Create: `tests/test_obsidian_client.py`

- [ ] **Step 1: Write failing test for obsidian client**

```python
import os
import tempfile

def test_create_note():
    from obsidian.client import ObsidianClient
    
    with tempfile.TemporaryDirectory() as tmpdir:
        client = ObsidianClient(tmpdir)
        result = client.create_note("Test Note", "This is test content", "Inbox")
        
        assert os.path.exists(result["path"])
        assert "Test Note" in open(result["path"]).read()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_obsidian_client.py -v
```
Expected: FAIL - ModuleNotFoundError: No module named 'obsidian'

- [ ] **Step 3: Create obsidian/client.py**

```python
"""Obsidian vault client for Mizune."""
import os
import json
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
        import re
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_obsidian_client.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add obsidian/client.py tests/test_obsidian_client.py
git commit -m "feat: add obsidian client for vault operations"
```

---

### Task 3: Create ObsidianAgent

**Files:**
- Create: `agents/new/obsidian_agent.py`
- Create: `tests/test_obsidian_agent.py`

- [ ] **Step 1: Write failing test for ObsidianAgent**

```python
def test_obsidian_agent_create_note():
    from agents.new.obsidian_agent import ObsidianAgent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = ObsidianAgent({"obsidian_vault_path": tmpdir})
        result = agent.create_note("Meeting Notes", "Discussed project timeline")
        
        assert result["success"] is True
        assert "path" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_obsidian_agent.py -v
```
Expected: FAIL - No module named 'agents.new'

- [ ] **Step 3: Create agents/new/__init__.py**

```python
"""New agents for Mizune."""
```

- [ ] **Step 4: Create agents/new/obsidian_agent.py**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_obsidian_agent.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agents/new/ tests/test_obsidian_agent.py
git commit -m "feat: add ObsidianAgent for knowledge management"
```

---

## Phase 2: New Agents (Data Analysis, File Organizer, Project Manager)

### Task 4: DataAnalysisAgent

**Files:**
- Create: `agents/new/data_analysis_agent.py`
- Create: `tests/test_data_analysis_agent.py`

- [ ] **Step 1: Write failing test**

```python
import pandas as pd
import tempfile
import os

def test_analyze_csv():
    from agents.new.data_analysis_agent import DataAnalysisAgent
    
    # Create test CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("name,age,salary\n")
        f.write("Alice,30,50000\n")
        f.write("Bob,25,45000\n")
        f.write("Charlie,35,60000\n")
        tmpfile = f.name
    
    try:
        agent = DataAnalysisAgent({})
        result = agent.analyze_csv(tmpfile)
        
        assert result["success"] is True
        assert "statistics" in result
        assert result["statistics"]["row_count"] == 3
    finally:
        os.unlink(tmpfile)
```

- [ ] **Step 2: Run test - expect failure**

```bash
python -m pytest tests/test_data_analysis_agent.py -v
```
Expected: FAIL - No module 'agents.new'

- [ ] **Step 3: Create agents/new/data_analysis_agent.py**

```python
"""Data Analysis Agent for Mizune."""
import os
import pandas as pd
from typing import Dict, Any, Optional


class DataAnalysisAgent:
    """Agent for analyzing data files."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def _get_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate basic statistics."""
        stats = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "numeric_columns": [],
            "categorical_columns": []
        }
        
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                stats["numeric_columns"].append(col)
                stats[f"{col}_mean"] = float(df[col].mean())
                stats[f"{col}_min"] = float(df[col].min())
                stats[f"{col}_max"] = float(df[col].max())
            else:
                stats["categorical_columns"].append(col)
        
        return stats
    
    def analyze_csv(self, file_path: str) -> Dict[str, Any]:
        """Analyze a CSV file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        
        try:
            df = pd.read_csv(file_path)
            stats = self._get_statistics(df)
            
            return {
                "success": True,
                "file_path": file_path,
                "statistics": stats,
                "preview": df.head(5).to_dict(orient="records")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_excel(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Analyze an Excel file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            stats = self._get_statistics(df)
            
            return {
                "success": True,
                "file_path": file_path,
                "statistics": stats,
                "preview": df.head(5).to_dict(orient="records")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate natural language summary."""
        if not data.get("success"):
            return f"Error: {data.get('error', 'Unknown error')}"
        
        stats = data.get("statistics", {})
        row_count = stats.get("row_count", 0)
        col_count = stats.get("column_count", 0)
        cols = stats.get("columns", [])
        
        summary = f"This dataset contains {row_count} rows and {col_count} columns. "
        summary += f"The columns are: {', '.join(cols[:5])}"
        if len(cols) > 5:
            summary += f" and {len(cols) - 5} more."
        
        numeric_cols = stats.get("numeric_columns", [])
        if numeric_cols:
            summary += " For numeric columns: "
            for col in numeric_cols[:3]:
                mean = stats.get(f"{col}_mean", 0)
                summary += f"{col} has an average of {mean:.2f}. "
        
        return summary
```

- [ ] **Step 4: Run test - expect pass**

```bash
python -m pytest tests/test_data_analysis_agent.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/new/data_analysis_agent.py tests/test_data_analysis_agent.py
git commit -m "feat: add DataAnalysisAgent for CSV/Excel analysis"
```

---

### Task 5: FileOrganizerAgent

**Files:**
- Create: `agents/new/file_organizer_agent.py`
- Create: `tests/test_file_organizer_agent.py`

- [ ] **Step 1: Write failing test**

```python
import tempfile
import os

def test_organize_folder():
    from agents.new.file_organizer_agent import FileOrganizerAgent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        open(os.path.join(tmpdir, "doc1.txt"), "w").close()
        open(os.path.join(tmpdir, "image1.jpg"), "w").close()
        open(os.path.join(tmpdir, "data.csv"), "w").close()
        
        agent = FileOrganizerAgent({})
        result = agent.organize_folder(tmpdir, "by_type")
        
        assert result["success"] is True
        assert result["files_moved"] >= 3
```

- [ ] **Step 2: Run test - expect failure**

```bash
python -m pytest tests/test_file_organizer_agent.py -v
```
Expected: FAIL

- [ ] **Step 3: Create agents/new/file_organizer_agent.py**

```python
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
```

- [ ] **Step 4: Run test - expect pass**

```bash
python -m pytest tests/test_file_organizer_agent.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/new/file_organizer_agent.py tests/test_file_organizer_agent.py
git commit -m "feat: add FileOrganizerAgent for automatic file management"
```

---

### Task 6: ProjectManagerAgent

**Files:**
- Create: `agents/new/project_manager_agent.py`
- Create: `tests/test_project_manager_agent.py`

- [ ] **Step 1: Write failing test**

```python
import tempfile
import json
import os

def test_add_task():
    from agents.new.project_manager_agent import ProjectManagerAgent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"tasks_file": os.path.join(tmpdir, "tasks.json")}
        agent = ProjectManagerAgent(config)
        
        result = agent.add_task("Review PR", "2026-05-20", "Mizune")
        
        assert result["success"] is True
        assert result["task"]["title"] == "Review PR"
```

- [ ] **Step 2: Run test - expect failure**

```bash
python -m pytest tests/test_project_manager_agent.py -v
```
Expected: FAIL

- [ ] **Step 3: Create agents/new/project_manager_agent.py**

```python
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
```

- [ ] **Step 4: Run test - expect pass**

```bash
python -m pytest tests/test_project_manager_agent.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/new/project_manager_agent.py tests/test_project_manager_agent.py
git commit -m "feat: add ProjectManagerAgent for task tracking"
```

---

## Phase 3: Advanced Agents (Research, Code Review)

### Task 7: ResearchAgent

**Files:**
- Create: `agents/new/research_agent.py`
- Create: `tests/test_research_agent.py`

### Task 8: CodeReviewAgent

**Files:**
- Create: `agents/new/code_review_agent.py`
- Create: `tests/test_code_review_agent.py`

---

## Phase 4: Workflow System

### Task 9: Workflow Engine

**Files:**
- Create: `workflows/engine.py`
- Create: `tests/test_workflow_engine.py`

---

## Phase 5: Learning System

### Task 10: Learning Engine

**Files:**
- Create: `learning/engine.py`
- Create: `tests/test_learning_engine.py`

---

## Verification

After all tasks complete:
- [ ] Run all new tests: `python -m pytest tests/test_obsidian*.py tests/test_data*.py tests/test_file*.py tests/test_project*.py -v`
- [ ] Verify server.py loads: `python -c "import server; print('OK')"`
- [ ] Verify new agents can be imported: `from agents.new.obsidian_agent import ObsidianAgent`

---

## Plan Complete

**Execution choice:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?