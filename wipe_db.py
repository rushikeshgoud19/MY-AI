import sqlite3
import os

db_path = '/home/azureuser/mizune_sessions.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    conn.commit()
    print("Messages deleted.")
else:
    print("DB not found.")
