from server.processor import process_command
from server.config import load_config
import logging

logging.basicConfig(level=logging.ERROR)
config = load_config()

def broadcast_sync_fn(msg):
    pass

print("--- ASKING MIZUNE WHO IS MATT ---")
response = process_command("Mizune who is Matt?", config, broadcast_sync_fn, session_id="main")
print(f"Mizune: {response}")
