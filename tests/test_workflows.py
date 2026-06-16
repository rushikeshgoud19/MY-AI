import sys
import os
import json
import time

# Add root directory to python path so we can import server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.ai import get_ai_response

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

TEST_CASES = [
    {
        "name": "Social Workflow",
        "prompt": "Mizune, open whatsapp web and message Sarthak Lanjava while opening youtube on brave and play pinklips.",
        "expected_actions_min": 2,
    },
    {
        "name": "Dev Workflow",
        "prompt": "I'm about to code. Close Steam, open VS Code, open Spotify, and start a 25-minute focus mode.",
        "expected_actions_min": 3,
    },
    {
        "name": "Productivity Flow",
        "prompt": "Take a note that says 'Buy milk tomorrow', then open Discord and close Chrome.",
        "expected_actions_min": 3,
    },
    {
        "name": "Research Start",
        "prompt": "Open edge, open chatgpt, and close discord so I can focus on my homework.",
        "expected_actions_min": 3,
    },
    {
        "name": "Gaming Setup",
        "prompt": "Close VS Code, open Steam, open Discord, and open Spotify to play some hype music.",
        "expected_actions_min": 4,
    },
    {
        "name": "Anime Time",
        "prompt": "Take a note saying 'Watched episode 5', close brave, open crunchyroll, and open discord.",
        "expected_actions_min": 4,
    },
    {
        "name": "Quick Twin Commands",
        "prompt": "Open word and open excel, I need to do some office work.",
        "expected_actions_min": 2,
    },
    {
        "name": "Focus Mode Activation",
        "prompt": "Close youtube, close twitter, close instagram, and open vscode.",
        "expected_actions_min": 4,
    },
    {
        "name": "Meeting Prep",
        "prompt": "Open Microsoft Teams, close Spotify, and take a note saying 'Meeting started at 10 AM'.",
        "expected_actions_min": 3,
    },
    {
        "name": "Random Chaos",
        "prompt": "Open calculator, open notepad, open paint, and open task manager.",
        "expected_actions_min": 4,
    }
]

def run_tests():
    config = load_config()
    print("==================================================")
    print("MIZUNE BRAIN STRESS TEST: Multi-Action Workflow")
    print("==================================================\n")
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_CASES):
        print(f"[{i+1}/{len(TEST_CASES)}] Testing: {test['name']}")
        print(f"   Prompt: '{test['prompt']}'")
        
        try:
            # We don't need history for this test, just the prompt
            text, tools = get_ai_response(test['prompt'], [], config)
            
            print(f"   Mizune Says: '{text}'")
            print(f"   Tools Parsed: {len(tools)}")
            
            for tool in tools:
                print(f"      - {tool.get('name')}: {tool.get('args')}")
                
            if len(tools) >= test['expected_actions_min']:
                print("   [PASS]")
                passed += 1
            else:
                print(f"   [FAIL] (Expected at least {test['expected_actions_min']} actions, got {len(tools)})")
                failed += 1
                
        except Exception as e:
            print(f"   [ERROR]: {e}")
            failed += 1
            
        print("-" * 50)
        time.sleep(1.5) # Anti-rate limit delay
        
    print("\n==================================================")
    print(f"STRESS TEST RESULTS: {passed} PASSED | {failed} FAILED")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
