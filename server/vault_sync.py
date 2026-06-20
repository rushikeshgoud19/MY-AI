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
            
    def full_export(self):
        """Export all topics and skills to the Vault."""
        try:
            self._export_topics()
            self._export_skills()
            self._export_contacts()
            self._export_whatsapp()
            self._export_gmail()
            self._export_episodic()
            log_info("[VAULT SYNC] Full export completed.")
        except Exception as e:
            log_info(f"[VAULT SYNC] Full export failed: {e}")
            
    def _export_topics(self):
        cursor = memory_tree_db.db.cursor()
        cursor.execute("SELECT id, entity_name, entity_type, hotness, l2_summary, last_accessed FROM topics WHERE l2_summary IS NOT NULL")
        rows = cursor.fetchall()
        for row in rows:
            t_id, name, t_type, hotness, summary, last_acc = row
            safe_name = "".join([c if c.isalnum() else " " for c in name]).strip()
            filename = f"{safe_name}.md"
            folder = "Knowledge/Topics"
            if t_type == "person": folder = "Knowledge/People"
            
            filepath = os.path.join(self.vault_path, folder, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_acc))
            md_content = f"---\nid: topic_{t_id}\ntype: {t_type}\nhotness: {hotness}\nlast_accessed: {date_str}\n---\n\n# {name}\n\n[[_Index]]\n\n{summary}\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
    def _export_skills(self):
        cursor = memory_tree_db.db.cursor()
        cursor.execute("SELECT id, name, version, success_rate, markdown_body, updated_at FROM skills WHERE markdown_body IS NOT NULL")
        rows = cursor.fetchall()
        for row in rows:
            s_id, name, version, success_rate, body, updated_at = row
            safe_name = "".join([c if c.isalnum() else " " for c in name]).strip()
            filename = f"{safe_name}.md"
            filepath = os.path.join(self.vault_path, "Knowledge/Skills", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(updated_at))
            md_content = f"---\nid: skill_{s_id}\nversion: {version}\nsuccess_rate: {success_rate}\nupdated_at: {date_str}\n---\n\n# Skill: {name}\n\n[[_Index]]\n\n{body}\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)

    def _export_contacts(self):
        """Export contacts from cortex.db to Knowledge/People"""
        db_path = "cortex.db"
        if not os.path.exists(db_path): return
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name, phone, tier, relationship_score, message_count, notes FROM contacts WHERE name IS NOT NULL")
            for row in c.fetchall():
                name, phone, tier, rel, msgs, notes = row
                safe_name = "".join([ch if ch.isalnum() else " " for ch in name]).strip()
                if not safe_name: continue
                filepath = os.path.join(self.vault_path, "Knowledge/People", f"{safe_name}.md")
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                md = f"---\nphone: {phone}\ntier: {tier}\nrelationship: {rel}\n---\n\n# {name}\n\n[[_Index]] | [[Sources/WhatsApp/{safe_name} Chat|WhatsApp History]]\n\n**Messages:** {msgs}\n**Notes:** {notes}\n"
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(md)
        except Exception as e:
            log_info(f"Failed to export contacts: {e}")

    def _export_whatsapp(self):
        """Export WhatsApp messages grouped by chat."""
        if not os.path.exists("cortex.db"): return
        try:
            import sqlite3
            cdb = sqlite3.connect("cortex.db")
            cc = cdb.cursor()
            cc.execute("SELECT chat_jid, timestamp, sender_name, text FROM whatsapp_messages ORDER BY timestamp ASC")
            
            chats = {}
            chat_names = {}
            
            for wrow in cc.fetchall():
                cjid, ts, sender, txt = wrow
                if not cjid: continue
                if ts and txt:
                    sender = sender or "Unknown"
                    safe_sender = "".join([ch if ch.isalnum() else " " for ch in sender]).strip()
                    
                    if cjid not in chats:
                        chats[cjid] = []
                        chat_names[cjid] = set()
                        
                    chat_names[cjid].add(safe_sender)
                    
                    date_str = time.strftime('%Y-%m-%d', time.localtime(ts))
                    time_str = time.strftime('%H:%M:%S', time.localtime(ts))
                    chats[cjid].append(f"**[{date_str} {time_str}] {safe_sender}:** {txt}")
                    
            hub_path = os.path.join(self.vault_path, "Sources/WhatsApp", "WhatsApp Hub.md")
            os.makedirs(os.path.dirname(hub_path), exist_ok=True)
            hub_content = "# 📱 WhatsApp Hub\n\n[[_Index]]\n\n## Chats\n"
            
            for cjid, lines in chats.items():
                # Determine chat name: pick the first name that isn't 'Rushikesh Goud' or 'Mathew'
                # If only one name exists, use that.
                names = list(chat_names[cjid])
                other_names = [n for n in names if n and n not in ('Rushikesh Goud', 'Mathew', 'Unknown')]
                chat_name = other_names[0] if other_names else (names[0] if names else cjid)
                
                hub_content += f"- [[{chat_name} Chat]]\n"
                filepath = os.path.join(self.vault_path, "Sources/WhatsApp", f"{chat_name} Chat.md")
                
                header = f"# 💬 WhatsApp: {chat_name}\n\n[[WhatsApp Hub]] | [[Knowledge/People/{chat_name}|Contact: {chat_name}]]\n\n"
                content = "\n\n".join(lines)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(header + content + "\n")
                    
            with open(hub_path, 'w', encoding='utf-8') as f:
                f.write(hub_content)
        except Exception as e:
            log_info(f"[VAULT SYNC] WhatsApp export failed: {e}")

    def _export_gmail(self):
        """Export Gmail messages grouped by sender."""
        if not os.path.exists("cortex.db"): return
        try:
            import sqlite3
            cdb = sqlite3.connect("cortex.db")
            cc = cdb.cursor()
            try:
                cc.execute("SELECT timestamp, sender, subject, snippet, importance_score FROM gmail_messages ORDER BY timestamp ASC")
            except sqlite3.OperationalError:
                return # table doesn't exist yet
                
            emails = {}
            for row in cc.fetchall():
                ts, sender, subj, snip, imp = row
                if ts and sender:
                    safe_sender = "".join([ch if ch.isalnum() or ch in "@." else " " for ch in sender]).strip()
                    if safe_sender not in emails: emails[safe_sender] = []
                    
                    date_str = time.strftime('%Y-%m-%d', time.localtime(ts))
                    time_str = time.strftime('%H:%M:%S', time.localtime(ts))
                    emails[safe_sender].append(f"**[{date_str} {time_str}]** (Imp: {imp}/10)\n**Subj:** {subj}\n> {snip}\n")
                    
            hub_path = os.path.join(self.vault_path, "Sources/Gmail", "Gmail Hub.md")
            os.makedirs(os.path.dirname(hub_path), exist_ok=True)
            hub_content = "# 📧 Gmail Hub\n\n[[_Index]]\n\n## Senders\n"
            
            for sender, lines in emails.items():
                hub_content += f"- [[{sender} Emails]]\n"
                filepath = os.path.join(self.vault_path, "Sources/Gmail", f"{sender} Emails.md")
                
                header = f"# 📧 Emails: {sender}\n\n[[Gmail Hub]]\n\n"
                content = "\n\n".join(lines)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(header + content + "\n")
                    
            with open(hub_path, 'w', encoding='utf-8') as f:
                f.write(hub_content)
        except Exception as e:
            log_info(f"[VAULT SYNC] Gmail export failed: {e}")

    def _export_episodic(self):
        """Export raw episodic memories (conversation logs) into Daily notes."""
        cursor = memory_tree_db.db.cursor()
        # Get all episodic memories ordered by timestamp
        cursor.execute("SELECT timestamp, source, content FROM episodic ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        
        
        daily_logs = {}
        for row in rows:
            timestamp, source, content = row
            # Convert timestamp to YYYY-MM-DD
            date_str = time.strftime('%Y-%m-%d', time.localtime(timestamp))
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
            
            if date_str not in daily_logs:
                daily_logs[date_str] = []
                
            prefix = ""
            if source: prefix = f"**[{source.upper()}]** "
            elif content.startswith("MODEL:"): content = f"**[MIZUNE]** {content[6:]}"
            elif content.startswith("USER:"): content = f"**[MASTER]** {content[5:]}"
            
            
            daily_logs[date_str].append(f"[{time_str}] {prefix}{content}")
            
        # Legacy history fallback
        for legacy_db in [".data/mizune_memory.db", "data_collector/mizune_memory.db"]:
            if os.path.exists(legacy_db):
                try:
                    import sqlite3
                    ldb = sqlite3.connect(legacy_db)
                    lc = ldb.cursor()
                    # Check which table exists
                    tables = [r[0] for r in lc.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                    if "history" in tables:
                        lc.execute("SELECT timestamp, role, content FROM history ORDER BY timestamp ASC")
                        for lrow in lc.fetchall():
                            ts_str, role, content = lrow
                            if " " in str(ts_str):
                                date_str, time_str = str(ts_str).split(" ", 1)
                                if date_str not in daily_logs: daily_logs[date_str] = []
                                prefix = "**[MIZUNE]** " if role == "model" else "**[MASTER]** "
                                daily_logs[date_str].append(f"[{time_str}] {prefix}{content}")
                    if "conversation_log" in tables:
                        lc.execute("SELECT timestamp, role, content FROM conversation_log ORDER BY timestamp ASC")
                        for lrow in lc.fetchall():
                            ts_str, role, content = lrow
                            if " " in str(ts_str):
                                date_str, time_str = str(ts_str).split(" ", 1)
                                if date_str not in daily_logs: daily_logs[date_str] = []
                                prefix = "**[MIZUNE]** " if role == "model" else "**[MASTER]** "
                                daily_logs[date_str].append(f"[{time_str}] {prefix}{content}")
                except Exception as e:
                    log_info(f"[VAULT SYNC] Legacy history export failed for {legacy_db}: {e}")
            
        for date_str, lines in daily_logs.items():
            filepath = os.path.join(self.vault_path, "Daily", f"{date_str}.md")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            header = f"---\ndate: {date_str}\ntags: [daily_log, history]\n---\n\n# Daily Log: {date_str}\n\n[[_Index]] | [[Daily Log]]\n\n"
            content = "\n\n".join(lines)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(header + content + "\n")
                
        # Generate Central Daily Log Hub
        hub_path = os.path.join(self.vault_path, "Daily", "Daily Log.md")
        with open(hub_path, 'w', encoding='utf-8') as f:
            f.write("# 📅 Daily Logs Master Hub\n\n[[_Index]]\n\n")
            for d in sorted(daily_logs.keys(), reverse=True):
                f.write(f"- [[{d}]]\n")

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
        # Export all existing memories on startup
        threading.Thread(target=vault_sync.full_export, daemon=True).start()
