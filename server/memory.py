import os
import sqlite3
import json
from typing import List, Dict

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from .config import log_info
import uuid
from .memory_tree import memory_tree_db

__all__ = ["MemorySystem"]

class MemorySystem:
    def __init__(self, data_dir: str = ".data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.sqlite_path = os.path.join(self.data_dir, "mizune_memory.db")
        self.chroma_dir = os.path.join(self.data_dir, "chroma_db")
        
        self.db = None
        self.chroma_client = None
        self.collection = None
        
        self._init_sqlite()
        self._init_chroma()
        
    def _init_sqlite(self):
        try:
            self.db = sqlite3.connect(self.sqlite_path, check_same_thread=False)
            cursor = self.db.cursor()
            
            # Key-value store for preferences
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Short-term conversation history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    role TEXT,
                    content TEXT
                )
            ''')
            
            # FTS5 Virtual Table for fast long-term memory retrieval
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content,
                    tags,
                    timestamp UNINDEXED
                )
            ''')
            
            # FTS5 Virtual Table for Skill Documents (Executable runbooks)
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    name,
                    description,
                    code_payload
                )
            ''')
            self.db.commit()
            log_info("[MEMORY] SQLite initialized.")
        except Exception as e:
            log_info(f"[MEMORY] Error initializing SQLite: {e}")
            
    def _init_chroma(self):
        if not CHROMA_AVAILABLE:
            log_info("[MEMORY] ChromaDB not installed. Semantic memory disabled.")
            return
            
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_dir)
            self.collection = self.chroma_client.get_or_create_collection(name="mizune_longterm")
            log_info("[MEMORY] ChromaDB initialized.")
        except Exception as e:
            log_info(f"[MEMORY] Error initializing ChromaDB: {e}")
            
    def store_preference(self, key: str, value: str):
        if not self.db: return
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO preferences (key, value) VALUES (?, ?)", (key, value))
        self.db.commit()
        
    def get_preference(self, key: str, default: str = "") -> str:
        if not self.db: return default
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default
        
    def add_to_history(self, role: str, content: str, emotion: str = "neutral", mode: str = "conversation"):
        if not self.db: return
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO history (role, content) VALUES (?, ?)", (role, content))
        self.db.commit()
        
        # Flashbulb Memory Logic
        priority = 0.0
        if emotion in ["happy", "sad", "angry", "surprised", "excited"]:
            priority = 0.8
        elif emotion in ["worried", "blush", "interested"]:
            priority = 0.5
            
        # Route to Memory Tree
        chunk_id = f"chk_{uuid.uuid4().hex[:8]}"
        # Estimate tokens roughly
        token_count = len(content) // 4
        memory_tree_db.insert_chunk(
            chunk_id=chunk_id,
            source_id="chat",
            content=f"{role.upper()}: {content}",
            token_count=token_count,
            metadata={"role": role, "emotion": emotion, "mode": mode, "priority": priority}
        )
        

        
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, str]]:
        if not self.db: return []
        cursor = self.db.cursor()
        cursor.execute("SELECT role, content FROM history ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        # Return in chronological order
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        
    def store_longterm(self, text: str, metadata: dict = None):
        doc_id = f"mem_{os.urandom(8).hex()}"
        
        # 1. Route to ChromaDB
        if self.collection:
            try:
                self.collection.add(
                    documents=[text],
                    metadatas=[metadata or {"type": "memory"}],
                    ids=[doc_id]
                )
                log_info(f"[MEMORY] Stored semantic memory: {text[:30]}...")
            except Exception as e:
                log_info(f"[MEMORY] Error storing longterm memory: {e}")
                
        # 2. Route to Memory Tree
        chunk_id = f"chk_{uuid.uuid4().hex[:8]}"
        token_count = len(text) // 4
        memory_tree_db.insert_chunk(
            chunk_id=chunk_id,
            source_id="longterm_explicit",
            content=text,
            token_count=token_count,
            metadata=metadata
        )
        

            
    def recall_longterm(self, query: str, n_results: int = 3) -> List[str]:
        if not self.collection: return []
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            if results and 'documents' in results and len(results['documents']) > 0:
                return results['documents'][0]
            return []
        except Exception as e:
            log_info(f"[MEMORY] Error recalling memory: {e}")
            return []
            
    def export_to_markdown(self, filepath: str):
        """Export all databases (SQLite preferences, chat logs, root archives) and ChromaDB memories to Obsidian"""
        try:
            # 1. Fetch preferences
            preferences = []
            if self.db:
                try:
                    cursor = self.db.cursor()
                    cursor.execute("SELECT key, value FROM preferences ORDER BY key")
                    preferences = cursor.fetchall()
                except Exception as e:
                    log_info(f"[MEMORY] Error fetching preferences: {e}")

            # 2. Fetch short-term history
            history = []
            if self.db:
                try:
                    cursor = self.db.cursor()
                    cursor.execute("SELECT timestamp, role, content FROM history ORDER BY timestamp DESC")
                    history = cursor.fetchall()
                except Exception as e:
                    log_info(f"[MEMORY] Error fetching history: {e}")

            # 3. Fetch full active conversation log (from data_collector database)
            conversation_log = []
            telemetry_db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "data_collector", 
                "mizune_memory.db"
            )
            if os.path.exists(telemetry_db_path):
                try:
                    conn = sqlite3.connect(telemetry_db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT timestamp, role, content, emotion, context_mode FROM conversation_log ORDER BY timestamp DESC")
                    conversation_log = cursor.fetchall()
                    conn.close()
                except Exception as e:
                    log_info(f"[MEMORY] Error fetching conversation log: {e}")

            # 4. Fetch root conversation archive (mizune_conversations.db)
            root_conversations = []
            root_db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "mizune_conversations.db"
            )
            if os.path.exists(root_db_path):
                try:
                    conn = sqlite3.connect(root_db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT timestamp, role, text, emotion, mode FROM conversations ORDER BY timestamp DESC")
                    root_conversations = cursor.fetchall()
                    conn.close()
                except Exception as e:
                    log_info(f"[MEMORY] Error fetching root conversations: {e}")

            # 5. Fetch semantic memories (ChromaDB)
            docs = []
            metas = []
            if self.collection:
                try:
                    results = self.collection.get()
                    docs = results.get('documents', [])
                    metas = results.get('metadatas', [])
                except Exception as e:
                    log_info(f"[MEMORY] Error fetching semantic memories: {e}")

            # 6. Fetch Self-Learned Skills
            learned_skills_md = "*No self-learned skills loaded yet.*"
            try:
                from server.skills import skill_manager
                learned_skills_md = skill_manager.get_skill_descriptions()
            except Exception as e:
                log_info(f"[MEMORY] Error fetching skills: {e}")

            # 7. Write to Markdown file
            from datetime import datetime
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# 🌐 Mizune Complete AI Database\n\n")
                f.write(f"**Exported On:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("This file contains the complete export of Mizune's SQLite databases (preferences, conversation logs, telemetry archives), ChromaDB semantic memory, and Self-Learned Skills.\n\n")
                f.write("---\n\n")

                # Self-Learned Skills
                f.write("## 🛠️ Self-Learned Skills\n")
                f.write("*These are autonomous tools and behaviors acquired by the AI.*\n\n")
                f.write(learned_skills_md + "\n")
                f.write("\n---\n\n")

                # Preferences
                f.write("## ⚙️ User Preferences & Configurations\n")
                f.write("*Saved key-value preferences used by the companion.*\n\n")
                if preferences:
                    f.write("| Preference Key | Value |\n")
                    f.write("|---|---|\n")
                    for key, val in preferences:
                        f.write(f"| {key} | {val} |\n")
                else:
                    f.write("_No preferences configured yet._\n")
                f.write("\n---\n\n")

                # Semantic Memories
                f.write("## 🧠 Long-Term Semantic Memories (ChromaDB)\n")
                f.write("*Vector embeddings database for deep contextual recall.*\n\n")
                if docs:
                    for i, doc in enumerate(docs):
                        meta = metas[i] if i < len(metas) else {}
                        f.write(f"### Memory Item {i+1}\n")
                        f.write(f"**Metadata:** {json.dumps(meta)}\n\n")
                        f.write(f"{doc}\n\n")
                        f.write("---\n\n")
                else:
                    f.write("_No semantic memories saved yet._\n\n---\n\n")

                # Active Session Logs
                f.write("## 💬 Active Conversation Logs\n")
                f.write("*All chat turns recorded during current/recent sessions.*\n\n")
                if conversation_log:
                    for ts, role, content, emotion, mode in conversation_log:
                        content_str = content.strip().replace("\n", "\n> ")
                        f.write(f"### **{role.upper()}** — *{ts}*\n")
                        f.write(f"- **Emotion**: `{emotion}` | **Mode**: `{mode}`\n")
                        f.write(f"> {content_str}\n\n")
                else:
                    f.write("_No active conversation logs found._\n")
                f.write("\n---\n\n")

                # Root Conversation Archive
                f.write("## 🏛️ Historical Conversations Archive\n")
                f.write("*Archived conversation history from the main SQLite DB.*\n\n")
                if root_conversations:
                    for ts_val, role, text, emotion, mode in root_conversations:
                        try:
                            ts_str = datetime.fromtimestamp(ts_val).strftime('%Y-%m-%d %H:%M:%S')
                        except Exception:
                            ts_str = str(ts_val)
                        text_str = text.strip().replace("\n", "\n> ")
                        f.write(f"### **{role.upper()}** — *{ts_str}*\n")
                        f.write(f"- **Emotion**: `{emotion}` | **Mode**: `{mode}`\n")
                        f.write(f"> {text_str}\n\n")
                else:
                    f.write("_No archived history found._\n")
                f.write("\n---\n\n")

                # Short-term Memory Queue
                f.write("## ⏱️ Local Short-Term History\n")
                f.write("*Temporary memory queue.*\n\n")
                if history:
                    f.write("| Timestamp | Role | Content |\n")
                    f.write("|---|---|---|\n")
                    for ts, role, content in history:
                        f.write(f"| {ts} | {role} | {content.strip().replace('|', 'I')} |\n")
                else:
                    f.write("_Short term history queue is empty._\n")
                f.write("\n")

            log_info(f"[MEMORY] Exported all database contents to {filepath}")
        except Exception as e:
            log_info(f"[MEMORY] Error exporting memories: {e}")

# Global memory instance
memory = MemorySystem()
