import sqlite3
import json
import hashlib
from datetime import datetime
import os

# Connect to old db
old_db_path = ".data/mizune_memory.db"
new_db_path = ".data/session_store.db"

if not os.path.exists(old_db_path):
    print("No old memory DB found.")
    exit(0)

if not os.path.exists(new_db_path):
    print("No new session DB found. Initializing...")
    from server.session_store import SessionStore
    SessionStore() # initialize tables

old_conn = sqlite3.connect(old_db_path)
new_conn = sqlite3.connect(new_db_path)

# Check if migration already done
try:
    c = new_conn.execute("SELECT COUNT(*) FROM session_messages WHERE session_id = 'migrated_main'")
    if c.fetchone()[0] > 0:
        print("Migration already performed.")
        exit(0)
except Exception as e:
    pass

print("Starting migration...")
cursor = old_conn.execute("SELECT timestamp, role, content FROM history ORDER BY id ASC")
rows = cursor.fetchall()

if not rows:
    print("No history to migrate.")
    exit(0)

print(f"Found {len(rows)} messages in old history.")

session_id = "main"

# Add dummy session if not exists
new_conn.execute("""
    INSERT OR IGNORE INTO sessions (session_id, platform, started_at, last_active, metadata)
    VALUES (?, ?, ?, ?, ?)
""", (session_id, 'desktop', datetime.now().timestamp(), datetime.now().timestamp(), '{}'))

turn_number = 1
for row in rows:
    ts, role, content = row
    # Convert TS string to float timestamp if possible
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        timestamp = dt.timestamp()
    except:
        timestamp = datetime.now().timestamp()
        
    msg_hash = hashlib.sha256(f"{role}:{content}:{timestamp}".encode()).hexdigest()[:16]
    token_count = len(content) // 4
    
    try:
        new_conn.execute("""
            INSERT INTO session_messages 
            (session_id, turn_number, role, content, timestamp, message_hash, metadata, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, turn_number, role, content, timestamp, msg_hash, '{}', token_count))
        turn_number += 1
    except sqlite3.IntegrityError:
        pass # duplicate

new_conn.commit()
print(f"Successfully migrated {turn_number - 1} messages into SessionStore under 'main' session.")
