import os
import sqlite3
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class SessionMessage:
    role: str           # 'system', 'user', 'model', 'tool' (renamed 'assistant' to 'model' for Gemini compatibility)
    content: str
    timestamp: float
    message_hash: str   # SHA256 for dedup
    metadata: Dict      # {"tool_calls": [...], "emotion": "happy", "app": "vscode"}
    token_count: int

class SessionStore:
    """
    Disk-first conversation memory. Survives restarts. Loads in <10ms.
    """
    
    def __init__(self, db_path: str = ".data/session_store.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._connect_and_check()
        
        # RAM cache: only last 30 messages (hot path)
        self._ram_cache: Dict[str, List[SessionMessage]] = {}
        
    def _connect_and_check(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("integrity_check failed")
        except sqlite3.DatabaseError as e:
            from server.config import log_info
            log_info(f"[SESSION_STORE] Database corrupted ({e}). Auto-healing by recreating the DB.")
            if getattr(self, 'conn', None):
                try: self.conn.close()
                except: pass
            
            # Delete corrupted files
            for ext in ["", "-wal", "-shm"]:
                try:
                    p = self.db_path + ext
                    if os.path.exists(p):
                        os.remove(p)
                except Exception as de:
                    log_info(f"[SESSION_STORE] Failed to delete {p}: {de}")
                    
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        self.conn.execute("PRAGMA journal_mode=WAL")      # Fast concurrent reads
        self.conn.execute("PRAGMA synchronous=NORMAL")    # Speed over paranoia
        self.conn.execute("PRAGMA cache_size=-64000")     # 64MB page cache
        self._init_tables()
    
    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                platform TEXT,           -- 'desktop', 'whatsapp', 'telegram'
                started_at REAL,
                last_active REAL,
                context_window_used INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',  -- 'active', 'closed', 'crashed'
                metadata JSON
            );
            
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                turn_number INTEGER,
                role TEXT,
                content TEXT,
                timestamp REAL,
                message_hash TEXT UNIQUE,
                metadata JSON,
                token_count INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_msg_session ON session_messages(session_id, turn_number);
            CREATE INDEX IF NOT EXISTS idx_msg_time ON session_messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_session_active ON sessions(status) WHERE status = 'active';
            
            -- For quick "last conversation" lookup
            CREATE TABLE IF NOT EXISTS session_index (
                entity TEXT,
                session_id TEXT,
                last_message_time REAL,
                message_count INTEGER,
                PRIMARY KEY (entity, session_id)
            );
            
            CREATE VIRTUAL TABLE IF NOT EXISTS session_messages_fts USING fts5(
                content,
                content='session_messages',
                content_rowid='id'
            );
            
            CREATE TRIGGER IF NOT EXISTS session_messages_ai AFTER INSERT ON session_messages BEGIN
                INSERT INTO session_messages_fts (rowid, content) VALUES (new.id, new.content);
            END;
            
            CREATE TRIGGER IF NOT EXISTS session_messages_ad AFTER DELETE ON session_messages BEGIN
                INSERT INTO session_messages_fts (session_messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
            END;
            
            CREATE TRIGGER IF NOT EXISTS session_messages_au AFTER UPDATE ON session_messages BEGIN
                INSERT INTO session_messages_fts (session_messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
                INSERT INTO session_messages_fts (rowid, content) VALUES (new.id, new.content);
            END;
        """)
        self.conn.commit()
    
    def start_or_resume_session(self, session_id: str, platform: str = "desktop", metadata: Dict = None) -> str:
        """Start or resume a session."""
        cursor = self.conn.execute("SELECT session_id, metadata FROM sessions WHERE session_id = ?", (session_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Merge new metadata into existing
            existing_meta = json.loads(existing[1] or '{}')
            if metadata:
                existing_meta.update(metadata)
                
            self.conn.execute("""
                UPDATE sessions SET status = 'active', last_active = ?, metadata = ?
                WHERE session_id = ?
            """, (datetime.now().timestamp(), json.dumps(existing_meta), session_id))
        else:
            self.conn.execute("""
                INSERT INTO sessions (session_id, platform, started_at, last_active, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, platform, datetime.now().timestamp(), 
                  datetime.now().timestamp(), json.dumps(metadata or {})))
        
        self.conn.commit()
        if session_id not in self._ram_cache:
            self._load_hot_cache(session_id)
            
        return session_id
    
    def get_session_metadata(self, session_id: str) -> Dict:
        cursor = self.conn.execute("SELECT metadata FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return json.loads(row[0] or '{}') if row else {}

    def update_session_metadata(self, session_id: str, metadata: Dict):
        existing_meta = self.get_session_metadata(session_id)
        existing_meta.update(metadata)
        self.conn.execute("UPDATE sessions SET metadata = ? WHERE session_id = ?", (json.dumps(existing_meta), session_id))
        self.conn.commit()

    def _load_hot_cache(self, session_id: str, limit: int = 30):
        """Load last N messages into RAM for fast access."""
        cursor = self.conn.execute("""
            SELECT role, content, timestamp, message_hash, metadata, token_count
            FROM session_messages
            WHERE session_id = ?
            ORDER BY turn_number DESC
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        self._ram_cache[session_id] = [
            SessionMessage(
                role=r[0], content=r[1], timestamp=r[2],
                message_hash=r[3], metadata=json.loads(r[4] or '{}'),
                token_count=r[5]
            )
            for r in reversed(rows)  # Oldest first
        ]
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None, 
                   token_count: int = 0) -> SessionMessage:
        """Add a message. Writes to disk IMMEDIATELY. Updates RAM cache."""
        # Standardize 'assistant' to 'model' for Gemini
        if role == 'assistant': role = 'model'
            
        msg_hash = hashlib.sha256(f"{role}:{content}:{datetime.now().timestamp()}".encode()).hexdigest()[:16]
        now = datetime.now().timestamp()
        metadata = metadata or {}
        
        # Get next turn number
        cursor = self.conn.execute("""
            SELECT COALESCE(MAX(turn_number), 0) + 1 
            FROM session_messages WHERE session_id = ?
        """, (session_id,))
        turn_number = cursor.fetchone()[0]
        
        # Write to disk FIRST (durable)
        self.conn.execute("""
            INSERT INTO session_messages 
            (session_id, turn_number, role, content, timestamp, message_hash, metadata, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, turn_number, role, content, now, 
              msg_hash, json.dumps(metadata), token_count))
        
        # Update session metadata
        self.conn.execute("""
            UPDATE sessions SET last_active = ?, context_window_used = ?
            WHERE session_id = ?
        """, (now, self._get_total_tokens(session_id), session_id))
        
        self.conn.commit()
        
        # Update RAM cache
        msg = SessionMessage(
            role=role, content=content, timestamp=now,
            message_hash=msg_hash, metadata=metadata, token_count=token_count
        )
        if session_id not in self._ram_cache:
            self._ram_cache[session_id] = []
            
        self._ram_cache[session_id].append(msg)
        if len(self._ram_cache[session_id]) > 30:  # Keep only hot data
            self._ram_cache[session_id].pop(0)
        
        # Update entity index for cross-session recall
        self._index_entities(content, session_id, now)
        
        return msg
    
    def get_recent(self, session_id: str, limit: int = 30) -> List[Dict]:
        """Get recent messages. RAM-first, disk fallback."""
        if session_id not in self._ram_cache:
            self._load_hot_cache(session_id, limit=limit)
            
        cache = self._ram_cache.get(session_id, [])
        if len(cache) >= limit:
            return [{"role": m.role, "parts": [{"text": m.content}]} for m in cache[-limit:]]
        
        # Fallback: query disk (still fast with index)
        cursor = self.conn.execute("""
            SELECT role, content
            FROM session_messages
            WHERE session_id = ?
            ORDER BY turn_number DESC
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        # Return in chronological order
        return [{"role": r[0], "parts": [{"text": r[1]}]} for r in reversed(rows)]
    
    def get_full_history(self, session_id: str) -> List[Dict]:
        """Get complete conversation history. Always from disk."""
        cursor = self.conn.execute("""
            SELECT role, content
            FROM session_messages
            WHERE session_id = ?
            ORDER BY turn_number ASC
        """, (session_id,))
        
        return [{"role": r[0], "parts": [{"text": r[1]}]} for r in cursor.fetchall()]
    
    def search_across_sessions(self, query: str, limit: int = 5) -> List[Dict]:
        """Find messages from ANY past session mentioning 'query'."""
        stop_words = {'tell', 'me', 'what', 'u', 'you', 'about', 'him', 'her', 'it', 'the', 'a', 'an', 'is', 'was', 'mizune', 'do'}
        clean_words = [w for w in query.lower().split() if w not in stop_words and w.isalnum()]
        if not clean_words:
            return []
            
        fts_query = " OR ".join(clean_words)
        try:
            cursor = self.conn.execute("""
                SELECT m.session_id, m.role, m.content, m.timestamp, s.platform
                FROM session_messages_fts fts
                JOIN session_messages m ON fts.rowid = m.id
                JOIN sessions s ON m.session_id = s.session_id
                WHERE session_messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, limit))
        except sqlite3.OperationalError:
            # Fallback if FTS syntax fails
            conditions = " OR ".join(["m.content LIKE ?"] * len(clean_words))
            params = tuple(f"%{w}%" for w in clean_words) + (limit,)
            cursor = self.conn.execute(f"""
                SELECT m.session_id, m.role, m.content, m.timestamp, s.platform
                FROM session_messages m
                JOIN sessions s ON m.session_id = s.session_id
                WHERE {conditions}
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, params)
        
        return [
            {
                'session_id': r[0], 'role': r[1], 'content': r[2],
                'timestamp': r[3], 'platform': r[4]
            }
            for r in cursor.fetchall()
        ]
    
    def close_session(self, session_id: str, status: str = 'closed'):
        """Graceful shutdown. Mark session closed."""
        self.conn.execute("""
            UPDATE sessions SET status = ?, last_active = ?
            WHERE session_id = ?
        """, (status, datetime.now().timestamp(), session_id))
        self.conn.commit()
        if session_id in self._ram_cache:
            del self._ram_cache[session_id]
    
    def _get_total_tokens(self, session_id: str) -> int:
        cursor = self.conn.execute("""
            SELECT COALESCE(SUM(token_count), 0) 
            FROM session_messages 
            WHERE session_id = ?
        """, (session_id,))
        return cursor.fetchone()[0]
    
    def _index_entities(self, content: str, session_id: str, timestamp: float):
        """Extract key terms and index them for cross-session recall."""
        words = set(w.lower() for w in content.split() if len(w) > 4)
        for word in words:
            self.conn.execute("""
                INSERT INTO session_index (entity, session_id, last_message_time, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(entity, session_id) DO UPDATE SET
                last_message_time = excluded.last_message_time,
                message_count = session_index.message_count + 1
            """, (word, session_id, timestamp))
        self.conn.commit()
    
    def get_stats(self) -> Dict:
        cursor = self.conn.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM session_messages")
        total_messages = cursor.fetchone()[0]
        
        cursor = self.conn.execute("""
            SELECT session_id, platform, started_at, last_active, 
                   (SELECT COUNT(*) FROM session_messages WHERE session_id = s.session_id) as msg_count
            FROM sessions s
            WHERE status = 'active'
        """)
        active = cursor.fetchall()
        
        return {
            'total_sessions': total_sessions,
            'total_messages': total_messages,
            'active_sessions': len(active),
            'active_details': [
                {'id': r[0], 'platform': r[1], 'messages': r[4],
                 'duration_min': (r[3] - r[2]) / 60}
                for r in active
            ],
            'ram_cache_size': sum(len(c) for c in self._ram_cache.values())
        }
