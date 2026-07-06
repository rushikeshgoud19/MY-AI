import os
import sys
from server.processor import process_command
from server.config import load_config
import time
import logging

logging.basicConfig(level=logging.ERROR)
config = load_config()

def broadcast_sync_fn(msg):
    pass # mock websocket

print("--- STARTING SESSION ---")
# Interaction 1: Give her a secret
response = process_command("Hey Mizune, my favorite color is crimson red and I love drinking matcha lattes. Remember this!", config, broadcast_sync_fn, session_id="main")
print(f"Mizune: {response}")

print("\n--- SIMULATING RESTART ---")
# To simulate a true restart, we will directly check the session_store db
# instead of relying on the in-memory variables.
from server.processor import global_session_store

# clear ram cache completely
global_session_store._ram_cache.clear()

# Interaction 2: Ask her about it (fetching from disk)
response = process_command("Hey Mizune, do you remember what my favorite color is and what I like to drink?", config, broadcast_sync_fn, session_id="main")
print(f"Mizune: {response}")

print("\n--- STATS ---")
print(global_session_store.get_stats())
