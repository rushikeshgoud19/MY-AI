"""
Mizune Conversation Database — SQLite persistence for conversation history.
Saves all user/model exchanges so CHRONICLE survives server restarts.
"""

import os
import sqlite3
import time
import logging
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mizune_conversations.db")

log = logging.getLogger("ConversationDB")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
    return conn


def init_db():
    """Create the conversations table if it doesn't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            emotion TEXT DEFAULT 'neutral',
            mode TEXT DEFAULT 'conversation'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)
    """)
    conn.commit()
    conn.close()
    log.info(f"[DB] Conversation database initialized at {DB_PATH}")


def save_turn(role: str, text: str, emotion: str = "neutral", mode: str = "conversation"):
    """Save a single conversation turn (user or model)."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO conversations (timestamp, role, text, emotion, mode) VALUES (?, ?, ?, ?, ?)",
            (time.time(), role, text, emotion, mode)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"[DB] Failed to save turn: {e}")


def load_recent_turns(n: int = 30) -> List[Dict]:
    """Load the last N conversation turns, formatted for CHRONICLE."""
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT role, text FROM conversations ORDER BY id DESC LIMIT ?",
            (n,)
        )
        rows = cursor.fetchall()
        conn.close()

        # Reverse to chronological order
        turns = []
        for role, text in reversed(rows):
            turns.append({"role": role, "parts": [{"text": text}]})
        return turns
    except Exception as e:
        log.error(f"[DB] Failed to load turns: {e}")
        return []


def get_turn_count() -> int:
    """Get total number of stored conversation turns."""
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


# Initialize on import
init_db()
