import asyncio
from server.agents import mizune_manager
from server.config import load_config
import logging

logging.basicConfig(level=logging.INFO)
config = load_config()

# Initialize the manager with config (this should now load the planner)
mizune_manager.initialize(config)

async def test_planning():
    print("--- TESTING AUTONOMOUS PLANNING ---")
    response = await mizune_manager.execute("book a flight to tokyo", context={"screen_context": "Desktop"})
    print(f"\nResponse:\n{response}")

if __name__ == "__main__":
    asyncio.run(test_planning())
