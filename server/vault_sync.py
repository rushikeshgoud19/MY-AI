import os
import time
import threading
import logging
from typing import Dict, Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from .memory_tree import memory_tree_db
from .config import log_info

logger = logging.getLogger("mizune.vault_sync")

class VaultSyncHandler(FileSystemEventHandler if HAS_WATCHDOG else object):
    def __init__(self, sync_manager):
        self.sync = sync_manager
        
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return
        self.sync.handle_file_change(event.src_path)

class VaultSync:
    """
    Bidirectional sync between the Memory Tree SQLite DB and the Obsidian Markdown Vault.
    """
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.memories_dir = os.path.join(self.vault_path, "Memories")
        self.observer = None
        self._last_sync_times = {} # prevent echo loops
        
        if not os.path.exists(self.memories_dir):
            try:
                os.makedirs(self.memories_dir)
            except Exception:
                pass
                
    def start(self):
        if not HAS_WATCHDOG:
            log_info("[VAULT SYNC] Watchdog not installed. Vault sync disabled.")
            return
            
        if not os.path.exists(self.memories_dir):
            return
            
        self.observer = Observer()
        handler = VaultSyncHandler(self)
        self.observer.schedule(handler, self.memories_dir, recursive=False)
        self.observer.start()
        log_info(f"[VAULT SYNC] Watching for edits in {self.memories_dir}")
        
    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
    def export_summary(self, summary_id: str):
        """Export a sealed summary from the DB to the Vault as Markdown."""
        if not os.path.exists(self.memories_dir): return
        
        try:
            cursor = memory_tree_db.db.cursor()
            cursor.execute("SELECT id, tree_type, tree_id, level, content, created_at FROM summaries WHERE id = ?", (summary_id,))
            row = cursor.fetchone()
            if not row: return
            
            s_id, t_type, t_id, level, content, created_at = row
            
            # Sanitize filename
            safe_name = "".join([c if c.isalnum() else "_" for c in t_id])
            filename = f"L{level}_{t_type}_{safe_name}_{s_id}.md"
            filepath = os.path.join(self.memories_dir, filename)
            
            # Format as Markdown with YAML frontmatter
            date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))
            md_content = f"---\\nid: {s_id}\\ntype: {t_type}\\ntopic: {t_id}\\nlevel: {level}\\ndate: {date_str}\\n---\\n\\n# Memory: {t_id} (Level {level})\\n\\n{content}\\n"
            
            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            # Record sync time to prevent echo
            self._last_sync_times[filepath] = os.path.getmtime(filepath)
            log_info(f"[VAULT SYNC] Exported {s_id} to Vault.")
            
        except Exception as e:
            log_info(f"[VAULT SYNC] Export failed: {e}")

    def handle_file_change(self, filepath: str):
        """Called by watchdog when user edits a memory file in Obsidian."""
        try:
            mtime = os.path.getmtime(filepath)
            # Debounce and prevent echo from our own exports
            if filepath in self._last_sync_times and (mtime - self._last_sync_times[filepath]) < 2.0:
                return
                
            self._last_sync_times[filepath] = mtime
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract ID from frontmatter
            import re
            match = re.search(r'^id:\s*(sum_[a-f0-9]+)', content, re.MULTILINE)
            if not match: return
            
            summary_id = match.group(1)
            
            # Extract actual text (strip frontmatter and title)
            text_body = re.sub(r'^---.*?---\\n+', '', content, flags=re.DOTALL)
            text_body = re.sub(r'^# .*?\\n+', '', text_body).strip()
            
            if not text_body: return
            
            # Update DB
            cursor = memory_tree_db.db.cursor()
            cursor.execute("UPDATE summaries SET content = ? WHERE id = ?", (text_body, summary_id))
            memory_tree_db.db.commit()
            
            log_info(f"[VAULT SYNC] Ingested user edits for {summary_id} from Vault.")
            
        except Exception as e:
            log_info(f"[VAULT SYNC] File ingestion failed: {e}")

# Global instance will be initialized with config
vault_sync = None

def init_vault_sync(config):
    global vault_sync
    vault_path = config.get("obsidian_vault_path")
    if vault_path:
        vault_sync = VaultSync(vault_path)
        vault_sync.start()
