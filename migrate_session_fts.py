import sqlite3

db_path = ".data/session_store.db"
conn = sqlite3.connect(db_path)

print("Adding FTS5 to session_store.db...")

conn.executescript("""
    CREATE VIRTUAL TABLE IF NOT EXISTS session_messages_fts USING fts5(
        content,
        content='session_messages',
        content_rowid='id'
    );
""")

# Check if populated
cursor = conn.execute("SELECT COUNT(*) FROM session_messages_fts")
if cursor.fetchone()[0] == 0:
    print("Populating FTS5 table with existing messages...")
    conn.execute("""
        INSERT INTO session_messages_fts (rowid, content)
        SELECT id, content FROM session_messages
    """)
    conn.commit()
    print("Population complete.")
else:
    print("FTS5 table already populated.")

# Triggers to keep FTS5 in sync
conn.executescript("""
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

print("FTS5 migration complete.")
