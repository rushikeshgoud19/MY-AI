import sqlite3
import json

conn = sqlite3.connect(".data/session_store.db")
cursor = conn.execute("SELECT session_id, role, content FROM session_messages WHERE content LIKE '%Matt%' OR content LIKE '%Mat%'")
for row in cursor.fetchall():
    print(row)
