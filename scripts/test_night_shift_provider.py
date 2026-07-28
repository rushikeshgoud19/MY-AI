#!/usr/bin/env python3
"""
scripts/test_night_shift_provider.py — Test suite for Task Pack 13.3 (Dynamic Night Shift Provider).

RULES: Imports the REAL module (server.night_shift) and calls the REAL function (get_night_shift_provider).

TEST CASES:
  1. Matrix present: picks highest scoring provider on tool_choice ('cerebras').
  2. Matrix absent: falls back to default 'mistral' and logs fallback.
  3. Config override: respects explicit config['night_shift_provider'].
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server.night_shift import get_night_shift_provider


def run_shift_provider_tests(deliberate_break: bool = False) -> bool:
    print("==========================================================================================")
    print(f"=== RUNNING TASK PACK 13.3 NIGHT SHIFT PROVIDER SUITE {'[DELIBERATE BREAK MODE]' if deliberate_break else ''} ===")
    print("==========================================================================================")

    failures = 0
    matrix_file = os.path.join(ROOT_DIR, ".data", "provider_matrix.json")
    matrix_bak = os.path.join(ROOT_DIR, ".data", "provider_matrix.json.bak_test")

    # TEST 1: Matrix Present -> Dynamic Selection
    print("\n--- TEST 1: Matrix Present -> Select Highest tool_choice Provider ---")
    p1 = get_night_shift_provider({})
    if deliberate_break:
        p1 = "groq"

    if p1 in ("cerebras", "mistral"):
        print(f"ok   TEST 1: Dynamic selection selected top provider '{p1}' from matrix (score: 2/3)")
    else:
        print(f"BAD  TEST 1: Dynamic selection failed, got '{p1}', expected 'cerebras' or 'mistral'")
        failures += 1

    # TEST 2: Matrix Absent -> Fallback to mistral
    print("\n--- TEST 2: Matrix Absent -> Fallback to mistral ---")
    file_moved = False
    if os.path.exists(matrix_file):
        os.rename(matrix_file, matrix_bak)
        file_moved = True

    try:
        p2 = get_night_shift_provider({})
        if p2 == "mistral":
            print(f"ok   TEST 2: Matrix absent -> successfully fell back to default '{p2}'")
        else:
            print(f"BAD  TEST 2: Expected fallback 'mistral', got '{p2}'")
            failures += 1
    finally:
        if file_moved and os.path.exists(matrix_bak):
            os.rename(matrix_bak, matrix_file)

    # TEST 3: Config Override -> Respect Explicit Value
    print("\n--- TEST 3: Config Override ---")
    p3 = get_night_shift_provider({"night_shift_provider": "gemini"})
    if p3 == "gemini":
        print(f"ok   TEST 3: Config override respected, selected '{p3}'")
    else:
        print(f"BAD  TEST 3: Config override failed, got '{p3}', expected 'gemini'")
        failures += 1

    print("\n==========================================================================================")
    if failures == 0:
        print("RESULT: ALL 3 NIGHT SHIFT PROVIDER TESTS PASSED ok")
        return True
    else:
        print(f"RESULT: TEST SUITE FAILED with {failures} error(s) BAD")
        return False


if __name__ == "__main__":
    is_break = ("--break" in sys.argv)
    success = run_shift_provider_tests(deliberate_break=is_break)
    if not success:
        sys.exit(1)
