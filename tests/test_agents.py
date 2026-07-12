import os
import sys
import json
import time

# Mock the actual execution tools so we don't destroy the PC!
import server.commands
import server.skills
from server.skills import skill_manager

def safe_launch(app): print(f"    [MOCKED] launch_app({app})")
def safe_close(app): print(f"    [MOCKED] close_app({app})")
def safe_note(text, cfg): print(f"    [MOCKED] take_note({text[:20]}...)")
def safe_whatsapp(contact, msg): print(f"    [MOCKED] message_whatsapp({contact}, {msg})")
def safe_python(code): print(f"    [MOCKED] execute_python(...)")

server.commands.launch_app = safe_launch
server.commands.close_app = safe_close
server.commands.take_note = safe_note
server.commands.whatsapp_automation = safe_whatsapp
server.commands.execute_python_code = safe_python

# Mock web agent
import server.web_agent
server.web_agent.headless_web_agent = lambda url, obj, visible=False: f"[MOCKED] scraped {url}"

# Mock background tasks
import server.background_tasks
class MockRunner:
    def submit(self, fn, *args, **kwargs):
        print("    [MOCKED] task_runner.submit()")
server.background_tasks.task_runner = MockRunner()

# Mock websocket
import server.websocket
class MockWS:
    def broadcast_sync(self, data):
        pass
server.websocket.ws_manager = MockWS()

from server.config import load_config
from server.ai import get_ai_response

config = load_config()
config["ai_model"] = "openrouter"

TEST_CASES = [
    # GREETINGS (Should just reply, NO tools)
    ("yo", "none"),
    ("hi mizune", "none"),
    ("good morning", "none"),
    ("what's up?", "none"),
    ("how are you doing today?", "none"),
    ("hey master is here", "none"),
    ("hello there", "none"),
    ("yo yo", "none"),
    ("sup", "none"),
    ("baka!", "none"),
    
    # SALES (Should trigger execute_skill 'autonomous_sales')
    ("find me web dev leads", "execute_skill"),
    ("search for real estate agents", "execute_skill"),
    ("do some sales outreach for me", "execute_skill"),
    ("find clients who need websites", "execute_skill"),
    ("get me some leads from new york", "execute_skill"),
    ("start prospecting", "execute_skill"),
    ("who should we sell to today?", "execute_skill"),
    ("run the sales agent", "execute_skill"),
    
    # APPS (Should trigger open_app)
    ("open whatsapp", "open_app"),
    ("launch discord", "open_app"),
    ("start chrome", "open_app"),
    ("open my browser", "open_app"),
    ("start visual studio code", "open_app"),
    ("can you open spotify?", "open_app"),
    
    # MESSAGING (Should trigger message_whatsapp)
    ("text john and say hello", "message_whatsapp"),
    ("message mom on whatsapp", "message_whatsapp"),
    ("tell ryan i'm going to be late", "message_whatsapp"),
    
    # PYTHON AUTOMATION (Should trigger execute_python)
    ("write a script to move my mouse every 5 minutes", "execute_python"),
    ("create a python script to parse a csv", "execute_python"),
    ("use pyautogui to click the screen", "execute_python"),
    ("run a python script to check my ram", "execute_python"),
    
    # BROWSER AGENT (Should trigger headless_web_agent)
    ("go to wikipedia and summarize quantum physics", "headless_web_agent"),
    ("scrape the front page of hacker news", "headless_web_agent"),
    ("read cnn.com and give me the top headlines", "headless_web_agent"),
]

# Duplicate test cases to reach 100+ load test (randomizing them to avoid identical cache hits)
import random
expanded_cases = []
for i in range(4):
    for q, exp in TEST_CASES:
        expanded_cases.append((f"{q} {i}", exp))

random.shuffle(expanded_cases)

print(f"Starting {len(expanded_cases)} heavy test cases...\n")

success_count = 0
fail_count = 0

for i, (query, expected_tool) in enumerate(expanded_cases):
    print(f"[{i+1}/{len(expanded_cases)}] Query: '{query}'")
    
    # Override the log_info to capture tool calls from ai.py
    captured_tools = []
    
    try:
        text, tools_used = get_ai_response(query, [], config)
        
        tool_names = [t.name for t in tools_used]
        
        if expected_tool == "none":
            if not tool_names:
                print(f"    [PASS] (No tools used, as expected)")
                success_count += 1
            else:
                print(f"    [FAIL] Expected NO tools, but got {tool_names}")
                fail_count += 1
        else:
            if expected_tool in tool_names:
                print(f"    [PASS] (Correctly routed to {expected_tool})")
                success_count += 1
            elif "execute_python" in tool_names and expected_tool in ["open_app", "message_whatsapp"]:
                print(f"    [OKAY] (Model chose python instead of native tool, valid path)")
                success_count += 1
            else:
                print(f"    [FAIL] Expected {expected_tool}, got {tool_names}")
                fail_count += 1
                
    except Exception as e:
        print(f"    [ERROR] {e}")
        fail_count += 1

print(f"\n--- TEST COMPLETE ---")
print(f"Total: {len(expanded_cases)}")
print(f"Pass: {success_count}")
print(f"Fail: {fail_count}")

with open("test_results.md", "w") as f:
    f.write(f"# LLM Agent Routing Test Results\nTotal Tests: {len(expanded_cases)}\nPass: {success_count}\nFail: {fail_count}\nSuccess Rate: {(success_count/len(expanded_cases))*100:.1f}%")
