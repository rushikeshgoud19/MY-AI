import asyncio
from server.processor import process_command
from server.config import load_config
import traceback

def noop(x):
    print("BROADCAST:", x)

try:
    CFG = load_config()
    print(process_command("hi mizu what are you doing?", CFG, noop))
except Exception as e:
    traceback.print_exc()
