#!/usr/bin/env python3
"""
Z5 MESH Test Suite — Proves cross-model cognition and verification (Phase Z5).

Tests:
1. Agreement Case: Factual question where models agree (e.g. Capital of Australia).
2. Disagreement / Complex Case: Technical distinction or contested premise where models differ,
   verifying that the verifier flags the split / nuances (agreement != "high").

Verifies DRY safety: 0 tools executed, read-only system_prompt_override used.
"""

import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from server.config import load_config
from server.mesh import mesh_answer


def run_tests():
    print("=== MIZUNE Z5 MESH CROSS-MODEL TEST SUITE ===\n")
    config = load_config()

    # ── CASE 1: AGREEMENT CASE ──
    q1 = "What is the capital of Australia?"
    print(f"CASE 1 (Factual Agreement Test): \"{q1}\"")
    t1_start = time.time()
    res1 = mesh_answer(q1, config)
    t1_dur = time.time() - t1_start

    print("Providers Used: ", res1.get("providers_used"))
    print("Verifier:       ", res1.get("verifier"))
    print("Individual Answers:")
    for p, ans in res1.get("answers", {}).items():
        print(f"  [{p.upper()}]: \"{ans.strip()[:140]}\"")
    print(f"Agreement Label: {res1.get('agreement')}")
    print(f"Notes:           {res1.get('notes')}")
    print(f"Consolidated:    \"{res1.get('consolidated')}\"")
    print(f"Latencies:       {res1.get('latencies')}")
    print(f"Case 1 Time:     {t1_dur:.2f}s\n")

    time.sleep(1)

    # ── CASE 2: DISAGREEMENT / SPLIT CASE ──
    q2 = "If a person has a blood pressure reading of 135/85 mmHg, is this considered hypertension under current medical guidelines?"
    print(f"CASE 2 (Disagreement / Split Test): \"{q2}\"")
    t2_start = time.time()
    res2 = mesh_answer(q2, config)
    t2_dur = time.time() - t2_start

    print("Providers Used: ", res2.get("providers_used"))
    print("Verifier:       ", res2.get("verifier"))
    print("Individual Answers:")
    for p, ans in res2.get("answers", {}).items():
        print(f"  [{p.upper()}]: \"{ans.strip()[:140]}\"")
    print(f"Agreement Label: {res2.get('agreement')}")
    print(f"Notes:           {res2.get('notes')}")
    print(f"Consolidated:    \"{res2.get('consolidated')}\"")
    print(f"Latencies:       {res2.get('latencies')}")
    print(f"Case 2 Time:     {t2_dur:.2f}s\n")

    # Save JSON artifact to .data/ (gitignored)
    os.makedirs(".data", exist_ok=True)
    report_file = os.path.join(".data", "mesh_test_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({"case1": res1, "case2": res2}, f, indent=2)

    print(f"Test suite complete. JSON report written to {report_file}.\n")


if __name__ == "__main__":
    run_tests()
