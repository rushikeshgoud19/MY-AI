import sys
import os

# Ensure the server module can be imported
sys.path.append(os.path.abspath('.'))

from server.model_router import get_model_router

config = {
    "nvidia_api_key": "dummy_nvidia_key",
    "openrouter_api_key": "dummy_openrouter_key",
    "gemini_api_key": "dummy_gemini_key",
    "openai_api_key": "dummy_openai_key"
}

router = get_model_router(config)

test_cases = [
    # Normal conversation
    ("Hey Mizune, how are you doing today?", "conversation"),
    ("What do you think about anime?", "conversation"),
    ("Mizune baka", "conversation"),
    ("wassup my woman", "conversation"),
    
    # Complex Tasks
    ("open youtube in brave", "task"),
    ("search the web for the latest ai news", "research"),
    ("write a python script to sort a list", "coding"),
    ("research lead generation tools", "research"),
    ("launch notepad", "task"),
    ("create a new skill", "autonomous"),
    
    # Vision
    ("what is on my screen?", "conversation")
]

print("=== MIZUNE ROUTING TEST RESULTS ===")
for text, intent in test_cases:
    model = router.route(text, context=[], hints={"intent": intent})
    
    # Check if we should override for vision
    if "VISION" in text.upper() or "SCREEN" in text.upper() or "CAMERA" in text.upper():
        if "screen" in text.lower(): 
            # Our router currently looks for "VISION" or "CAMERA"
            pass
            
    print(f"Prompt: '{text}'")
    print(f"Intent: {intent}")
    print(f"Routed to: {model.upper()}")
    print("-" * 30)
