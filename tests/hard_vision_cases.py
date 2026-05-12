"""
Hard vision routing tests: SCREEN vs CAMERA.
Run: python tests/hard_vision_cases.py
"""
import re
import sys

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


def run_case(name: str, text: str, expected: str) -> bool:
    got = classify_vision(text)
    ok = got == expected
    status = "OK" if ok else "FAIL"
    print(f"{status} [{name}] '{text}' -> expected {expected}, got {got}")
    return ok


def main() -> int:
    cases = [
        ("HARD-01", "guess what i am doing", "SCREEN"),
        ("HARD-02", "look at my screen, not my face", "SCREEN"),
        ("HARD-03", "tell me what i am doing on my computer", "SCREEN"),
        ("HARD-04", "look at me, not my screen", "CAMERA"),
        ("HARD-05", "what do you see in front of you", "CAMERA"),
        ("HARD-06", "check my screen and tell me what is happening", "SCREEN"),
        ("HARD-07", "describe my room", "CAMERA"),
        ("HARD-08", "see my screen and guess what i am doing", "SCREEN"),
        ("HARD-09", "look at my face and tell me how i look", "CAMERA"),
        ("HARD-10", "what is on my monitor right now", "SCREEN"),
        ("HARD-11", "see what is on my screen, not the camera", "SCREEN"),
        ("HARD-12", "can you see me and how do i look", "CAMERA"),
        ("HARD-13", "look around and describe what you see", "CAMERA"),
        ("HARD-14", "what am i working on", "SCREEN"),
        ("HARD-15", "what am i doing on my pc", "SCREEN"),
        ("HARD-16", "look at my screen and guess what i am doing not look at me through camera", "SCREEN"),
    ]

    passed = 0
    for name, text, expected in cases:
        if run_case(name, text, expected):
            passed += 1

    total = len(cases)
    failed = total - passed
    print("\n=== HARD VISION RESULTS ===")
    print(f"Passed: {passed}/{total}")
    if failed:
        print(f"Failed: {failed}")
        return 1
    print("All hard vision cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
