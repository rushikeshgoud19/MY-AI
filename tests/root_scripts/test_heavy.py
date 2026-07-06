import os
import sys
import asyncio
import threading

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.config import load_config
from server.processor import process_command
from server.agents import mizune_manager

config = load_config()
mizune_manager.initialize(config)

def dummy_broadcast(msg):
    pass

test_cases = [
    ("why do I need sleep?", "Expect LLM response, NOT 'I can help you with that...'"),
    ("I am playing a game look and tell me", "Expect vision context to be fed to LLM, returning natural response, NOT raw vision output"),
    ("open notepad", "Expect system agent to open notepad and return confirmation"),
    ("what is the current time", "Expect built-in time responder to answer immediately"),
    ("what is 25 * 4?", "Expect normal conversation fallback to LLM"),
    ("start watching", "Expect vision mode to activate and return greeting"),
    ("stop watching", "Expect vision mode to stop"),
    ("check my code", "Expect coding mode review to trigger"),
    ("pause monitoring", "Expect coding pause command to trigger"),
    ("tell me a joke about programming", "Expect normal LLM fallback")
]

def run_tests():
    print("=== RUNNING 10 HEAVY TEST CASES ===")
    for i, (query, expectation) in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"User Query: '{query}'")
        print(f"Expectation: {expectation}")
        try:
            # Run in a new thread to ensure no event loop is running in the thread, simulating fastapi to_thread
            result = [None]
            def target():
                result[0] = process_command(query, config, dummy_broadcast, session_id="test_session")
            
            t = threading.Thread(target=target)
            t.start()
            t.join()
            
            print(f"Mizune Output: {result[0]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    # Disable CameraAgent to prevent OpenCV spam
    if "camera" in mizune_manager.workers:
        del mizune_manager.workers["camera"]
    run_tests()
