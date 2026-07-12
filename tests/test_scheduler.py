import asyncio
import time
from server.processor import _scheduler_callback
from server.config import log_info

def test_callback():
    log_info("Starting test...")
    # Simulate the scheduler waking up
    _scheduler_callback("VIA_WHATSAPP: remind Master to drink water")
    
    # Wait to see if LLM generates a tool call and processor runs it
    time.sleep(20)

if __name__ == "__main__":
    test_callback()
