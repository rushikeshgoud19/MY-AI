import os
import json
import logging
from server.ai import get_ai_response
from server.config import load_config

# Configure logging to see the fallback messages
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def run_test():
    print("=== TESTING AI FALLBACK CHAIN ===")
    config = load_config()
    
    # 1. Test Groq (Primary)
    print("\n[TEST 1] Normal Groq Request (Should succeed if you have quota)")
    try:
        res, tools = get_ai_response("Say 'Groq is working'", [], config)
        print(f"Result: {res[:100]}")
    except Exception as e:
        print(f"Failed: {e}")
        
    # 2. Test Fallback (Force Groq to fail)
    print("\n[TEST 2] Force Groq to fail (Should fall back to Gemini)")
    original_groq = config.get("groq_api_key")
    config["groq_api_key"] = "gsk_invalid_key_to_force_failure" # This will cause an auth error
    try:
        res, tools = get_ai_response("Say 'Gemini Fallback is working'", [], config)
        print(f"Result: {res[:100]}")
    except Exception as e:
        print(f"Failed: {e}")
        
    # 3. Test Double Fallback (Force Groq AND Gemini to fail)
    print("\n[TEST 3] Force Groq AND Gemini to fail (Should fall back to Nvidia NIM)")
    original_gemini = config.get("gemini_api_key")
    config["gemini_api_key"] = "invalid_gemini_key_to_force_failure"
    try:
        res, tools = get_ai_response("Say 'Nvidia Fallback is working'", [], config)
        print(f"Result: {res[:100]}")
    except Exception as e:
        print(f"Failed: {e}")

    # Restore config
    config["groq_api_key"] = original_groq
    config["gemini_api_key"] = original_gemini
    print("\n=== TESTS COMPLETE ===")

if __name__ == "__main__":
    run_test()
