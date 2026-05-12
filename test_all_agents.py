"""
Mizune Agent Routing Test Suite
================================
Tests ALL intent classification + server.py vision routing.
Run: python test_all_agents.py
"""
import re
import sys

# ─── Import the ManagerAgent classifier ───────────────────────────────────────
sys.path.insert(0, ".")
from agents.manager_agent import ManagerAgent
manager = ManagerAgent({})

# ─── Server.py Screen vs Camera Vision regex (copied from server.py) ──────────
def classify_vision(text: str) -> str:
    lower = text.lower().strip()
    
    # Screen Vision (checked FIRST)
    if re.search(
        r"\b(look at my screen|look at (the|my) screen|what('s| is) on (my |the )?screen|"
        r"what am i (doing|looking at|working on)|what am i doing on (my )?(pc|computer|screen|monitor)|"
        r"describe my screen|what's on my monitor|what is on my monitor|check my screen|"
        r"see my screen|guess what i am doing|tell me what i am doing|"
        r"see what('s| is) on (my )?screen|what('s| is) happening on (my )?screen)\b", lower):
        return "SCREEN"
    
    # Camera Vision
    if re.search(
        r"\b(what do you see|what can you see|look at me|how do i look|"
        r"what('s| is) on my camera|whats going on my camera|"
        r"describe what you see|what's around me|what's in front of you|"
        r"who is here|who is in front|describe my room|look around|"
        r"see me|can you see me|look at my face)\b", lower):
        return "CAMERA"
    
    return "NONE"


# ─── Test Runner ──────────────────────────────────────────────────────────────
passed = 0
failed = 0
failures = []

def test(test_name: str, input_text: str, expected: str, test_type: str = "intent"):
    global passed, failed
    
    if test_type == "intent":
        result = manager._classify_intent(input_text)
    elif test_type == "vision":
        result = classify_vision(input_text)
    else:
        result = "UNKNOWN"
    
    status = "✅" if result == expected else "❌"
    if result != expected:
        failed += 1
        failures.append((test_name, input_text, expected, result))
        print(f"  {status} [{test_name}] '{input_text}' → Expected: {expected}, Got: {result}")
    else:
        passed += 1
        print(f"  {status} [{test_name}] '{input_text}' → {result}")


print("=" * 80)
print("  MIZUNE AGENT ROUTING TEST SUITE")
print("  Testing ALL agents + vision routing")
print("=" * 80)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. SYSTEM AGENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 1. SYSTEM AGENT ─────────────────────────────────────────────────")
test("SYS-01", "open brave", "system")
test("SYS-02", "close discord", "system")
test("SYS-03", "launch vs code", "system")
test("SYS-04", "take a screenshot", "system")
test("SYS-05", "lock my pc", "system")
test("SYS-06", "volume up", "system")
test("SYS-07", "mute", "system")
test("SYS-08", "put the computer to sleep", "system")
test("SYS-09", "increase the brightness", "system")
test("SYS-10", "kill task manager", "system")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTONOMOUS AGENT (multi-step tasks)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 2. AUTONOMOUS AGENT ─────────────────────────────────────────────")
test("AUTO-01", "search for wireless earbuds on amazon", "autonomous")
test("AUTO-02", "book a flight to tokyo", "autonomous")
test("AUTO-03", "go to google maps and navigate to hyderabad", "autonomous")
test("AUTO-04", "open brave and search for python tutorials on youtube and play the first one", "autonomous")
test("AUTO-05", "search for jobs on linkedin and apply to the first three", "autonomous")
test("AUTO-06", "can you do it for me", "autonomous")
test("AUTO-07", "order food from swiggy", "autonomous")
test("AUTO-08", "open spotify and play lofi music in the background while i code", "autonomous")
test("AUTO-09", "buy me a new keyboard from amazon", "autonomous")
test("AUTO-10", "search for anime on crunchyroll and then save it to my watchlist", "autonomous")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. CODING AGENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 3. CODING AGENT ─────────────────────────────────────────────────")
test("CODE-01", "check my code", "coding")
test("CODE-02", "review the code please", "coding")
test("CODE-03", "is this code correct", "coding")
test("CODE-04", "make the code better baka", "coding")
test("CODE-05", "did i do it right", "coding")
test("CODE-06", "fix my code", "coding")
test("CODE-07", "debug this for me", "coding")
test("CODE-08", "what's wrong with my code", "coding")
test("CODE-09", "help me fix this bug", "coding")
test("CODE-10", "is it correct", "coding")
test("CODE-11", "did i do good", "coding")
test("CODE-12", "make this better", "coding")
test("CODE-13", "can you look at this", "coding")
test("CODE-14", "improve the code", "coding")
test("CODE-15", "any errors in the code", "coding")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. VISION AGENT (via manager_agent intent)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 4. VISION AGENT (Intent) ─────────────────────────────────────────")
test("VIS-01", "what's on my screen right now", "vision")
test("VIS-02", "can you see my screen", "vision")
test("VIS-03", "describe what's on the screen", "vision")
test("VIS-04", "what am i looking at on my screen", "vision")
test("VIS-05", "look at my screen and tell me", "vision")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. SCREEN vs CAMERA VISION (server.py routing)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 5. SCREEN vs CAMERA VISION (Server Routing) ─────────────────────")
# These MUST go to SCREEN
test("SCR-01", "look at my screen and guess what i am doing", "SCREEN", "vision")
test("SCR-02", "what am i doing", "SCREEN", "vision")
test("SCR-03", "tell me what i am doing", "SCREEN", "vision")
test("SCR-04", "what is on my screen", "SCREEN", "vision")
test("SCR-05", "what's on my screen right now", "SCREEN", "vision")
test("SCR-06", "describe my screen", "SCREEN", "vision")
test("SCR-07", "guess what i am doing", "SCREEN", "vision")
test("SCR-08", "what am i working on", "SCREEN", "vision")
test("SCR-09", "check my screen", "SCREEN", "vision")
test("SCR-10", "look at the screen and tell me what i am doing", "SCREEN", "vision")
test("SCR-11", "what's happening on my screen", "SCREEN", "vision")
test("SCR-12", "i said look at my screen and tell me what i am doing not look at me through camera", "SCREEN", "vision")

# These MUST go to CAMERA
test("CAM-01", "look at me", "CAMERA", "vision")
test("CAM-02", "how do i look", "CAMERA", "vision")
test("CAM-03", "can you see me", "CAMERA", "vision")
test("CAM-04", "describe my room", "CAMERA", "vision")
test("CAM-05", "who is in front of you", "CAMERA", "vision")
test("CAM-06", "look at my face", "CAMERA", "vision")
test("CAM-07", "what's around me", "CAMERA", "vision")
test("CAM-08", "look around", "CAMERA", "vision")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. RESEARCH AGENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 6. RESEARCH AGENT ───────────────────────────────────────────────")
test("RES-01", "what is quantum computing", "research")
test("RES-02", "who is elon musk", "research")
test("RES-03", "tell me about black holes", "research")
test("RES-04", "how does blockchain work", "research")
test("RES-05", "search for python tutorials", "research")
test("RES-06", "look up the weather api documentation", "research")
test("RES-07", "best anime of 2025", "research")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. ENTERTAINMENT AGENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 7. ENTERTAINMENT AGENT ──────────────────────────────────────────")
test("ENT-01", "play some music", "entertainment")
test("ENT-02", "sing a song for me", "entertainment")
test("ENT-03", "recommend me an anime", "entertainment")
test("ENT-04", "what anime should i watch", "entertainment")
test("ENT-05", "put on some tunes", "entertainment")
test("ENT-06", "i want to watch something", "entertainment")
test("ENT-07", "play something", "entertainment")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. WRITING AGENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 8. WRITING AGENT ────────────────────────────────────────────────")
test("WRT-01", "take a note", "writing")
test("WRT-02", "write this down", "writing")
test("WRT-03", "remember this for me", "writing")
test("WRT-04", "note this please", "writing")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. CONVERSATION (Fallback - general chat)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 9. CONVERSATION (Fallback) ──────────────────────────────────────")
test("CONV-01", "hey mizune", "conversation")
test("CONV-02", "how are you", "conversation")
test("CONV-03", "baka", "conversation")
test("CONV-04", "i love you mizune", "conversation")
test("CONV-05", "good morning", "conversation")
test("CONV-06", "tell me a joke", "conversation")
test("CONV-07", "you are so cute", "conversation")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. EDGE CASES — Previously broken inputs
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── 10. EDGE CASES (Previously Broken) ──────────────────────────────")
test("EDGE-01", "make the code better baka", "coding")
test("EDGE-02", "did i good mizune? with the coding question", "coding")
test("EDGE-03", "this question did i do it correct can u make this code better?", "coding")
test("EDGE-04", "hey look at my screen and guess what i am doing", "SCREEN", "vision")
test("EDGE-05", "i said look at my screen not through camera", "SCREEN", "vision")
test("EDGE-06", "mizune how are you", "conversation")

# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
total = passed + failed
print(f"  RESULTS: {passed}/{total} passed ({failed} failed)")

if failures:
    print(f"\n  ❌ FAILURES:")
    for name, text, expected, got in failures:
        print(f"     [{name}] '{text}'")
        print(f"       Expected: {expected} → Got: {got}")

if failed == 0:
    print("  🎉 ALL TESTS PASSED! Mizune's brain is bulletproof!")
else:
    print(f"\n  ⚠️  {failed} test(s) need fixing before deployment.")

print("=" * 80)
sys.exit(1 if failed else 0)
