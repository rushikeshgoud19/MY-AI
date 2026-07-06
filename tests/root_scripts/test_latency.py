import time
import datetime
import os
from server.ai import get_ai_response
from server.config import load_config

def main():
    print("Testing Latency...")
    config = load_config()
    print(f"Model: {config.get('ai_model')}")
    
    start = time.time()
    try:
        res, tools = get_ai_response("Mizune what time is it?", [], config)
        end = time.time()
        print(f"Time: {end - start:.2f}s")
        print(f"Response: {res}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
