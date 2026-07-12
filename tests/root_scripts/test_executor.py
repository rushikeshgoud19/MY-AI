import asyncio
from agents.action_executor_agent import ActionExecutorAgent
from server.config import load_config
import logging
import json

logging.basicConfig(level=logging.INFO)
config = load_config()

executor = ActionExecutorAgent(config)

async def run_tests():
    print("--- TESTING ACTION EXECUTOR ---")
    # Test 1: Write a file
    step_write = {
        "action": "write_file",
        "params": {
            "path": "test_output.txt",
            "content": "Hello World from Mizune!"
        }
    }
    res = await executor.execute(json.dumps(step_write))
    print(f"Write File Result: {res}")

    # Test 2: Run a terminal command
    step_cmd = {
        "action": "run_terminal_command",
        "params": {
            "command": "type test_output.txt"
        }
    }
    res2 = await executor.execute(json.dumps(step_cmd))
    print(f"Run Command Result: {res2}")

if __name__ == "__main__":
    asyncio.run(run_tests())
