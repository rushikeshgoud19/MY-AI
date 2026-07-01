import asyncio
import json
import logging
import os

from agents.traceroot_analyst_agent import TracerootAnalystAgent

# Set up simple console logging to see the fallback warning
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    print("=== Testing TracerootAnalystAgent Fallback ===")
    
    # Initialize the agent
    with open('config.json', 'r') as f:
        cfg = json.load(f)
    agent = TracerootAnalystAgent(cfg)
    
    # 1. Sabotage the Gemini client to force a failure
    print("\n[Test] Sabotaging the Gemini API key...")
    from google import genai
    agent.client = genai.Client(api_key="FAKE_INVALID_KEY_TO_FORCE_ERROR")
    
    # 2. Run the agent
    print("[Test] Asking the agent a question...")
    result = await agent.run({"question": "What is the average latency of the Vision Agent today?"})
    
    # 3. Print the results
    print("\n=== Result ===")
    print(json.dumps(result, indent=2))
    
    if result.get("status") == "success":
        print("\n✅ SUCCESS: The fallback mechanism caught the Gemini error and successfully used the NVIDIA API!")
    else:
        print("\n❌ FAILED: The fallback did not work.")

if __name__ == "__main__":
    asyncio.run(main())
