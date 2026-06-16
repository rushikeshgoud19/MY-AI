from server.processor import process_command
from server.config import load_config
from server.memory import memory
import logging
import asyncio

logging.basicConfig(level=logging.ERROR)
config = load_config()

# Inject fact
print("Injecting fact...")
memory.store_longterm("Mathew works as a carer for a person with disabilities at Uloba, acting as a friend and assistant.")

# Test retrieval manually
print("Testing manual recall...")
print(memory.recall_longterm("mathew works", n_results=1))

def sync_fn(msg): pass

print("--- TESTING CROSS-SESSION MEMORY RECALL ---")
response = process_command("yoo do u know mathew and where he works?", config, sync_fn, "desktop")
print(f"Mizune: {response}")
