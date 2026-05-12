import json
import asyncio
from agents.action_executor_agent import ActionExecutorAgent

async def test_gitlab_connection():
    # Load config
    with open("config.json", "r") as f:
        config = json.load(f)
    
    executor = ActionExecutorAgent(config)
    
    print("🚀 Testing Mizune's connection to GitLab...")
    
    # We will try to list issues for a specific project if you have one, 
    # but for a generic test, let's just check if the library is working.
    
    # Example: List projects (we'll use a generic operation to see if the token works)
    # Since we only implemented specific ops, let's try 'list_issues' on a project.
    # Note: You'll need to replace 'your-username/your-project' with a real one.
    
    test_params = {
        "operation": "list_issues",
        "project": "rushikeshgoud19/MY-AI" # Using your repo name from metadata
    }
    
    result = await executor._action_gitlab_action(test_params, {})
    
    if result["success"]:
        print("✅ SUCCESS! Mizune successfully talked to GitLab.")
        print(f"Message: {result.get('message')}")
        if "issues" in result:
            print(f"Issues found: {result['issues']}")
    else:
        print("❌ FAILED.")
        print(f"Error: {result.get('error')}")
        
    print("\nNext step: Try asking Mizune out loud: 'Mizune, check my GitLab issues!'")

if __name__ == "__main__":
    asyncio.run(test_gitlab_connection())
