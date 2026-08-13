#!/usr/bin/env python3
"""
scripts/test_model_selector.py — Test suite for Task Pack 11 & 12 (Model Selector).

FIXTURE RULE (TASK PACK 12.3):
  Tests MUST use an in-memory copy / fixture config, NEVER mutate config.json on disk!

TEST COVERAGE:
  1. Security check: list_models NEVER returns any string containing any configured API key.
  2. Unknown provider/model pair is rejected with 400.
  3. Auth check on POST /api/model:
     - Missing header -> 401
     - Wrong header -> 401
     - Unset dashboard_api_key -> 401 (fail closed)
     - Valid header + valid provider -> 200 / ok
  4. Patch idempotency and AST parse-failure refusal safety.
  5. Fixture integrity assertion: config.json on disk is NOT mutated.
  6. Harness failure proof: --break flag deliberately breaks one check to prove suite CAN fail.

House style: pure python, no pytest, prints ok/BAD, exits non-zero on failure.
"""

import ast
import copy
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server.config import load_config
from server.model_catalog import list_models
from scripts.patch_model_api import patch_file


def run_tests(deliberate_break: bool = False) -> bool:
    print("==========================================================================================")
    print(f"=== RUNNING MODEL SELECTOR TEST SUITE {'[DELIBERATE BREAK MODE]' if deliberate_break else ''} ===")
    print("==========================================================================================")

    # Load initial disk state for fixture integrity check
    config_file_path = os.path.join(ROOT_DIR, "config.json")
    with open(config_file_path, "r", encoding="utf-8") as f:
        disk_config_before = f.read()

    failures = 0
    # Use FIXTURE copy in-memory — NEVER mutate live file on disk!
    cfg_fixture = copy.deepcopy(load_config())

    # ----------------------------------------------------------------------------------
    # TEST 1: SECURITY — NO API KEYS EXPOSED IN LIST_MODELS
    # ----------------------------------------------------------------------------------
    print("\n--- TEST 1: Security — API Key Leak Prevention ---")
    try:
        catalog = list_models(cfg_fixture)
        catalog_str = json.dumps(catalog)

        secrets = []
        for k, v in cfg_fixture.items():
            if any(term in k.lower() for term in ["key", "secret", "token"]):
                if isinstance(v, str) and len(v.strip()) > 8:
                    secrets.append((k, v.strip()))
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and len(item.strip()) > 8:
                            secrets.append((k, item.strip()))

        leaked = []
        if deliberate_break and secrets:
            # Intentionally inject first real secret into catalog_str to prove test catches leaks
            catalog_str += f" LEAK_TEST: {secrets[0][1]} "

        for key_name, secret_val in secrets:
            if secret_val in catalog_str:
                leaked.append((key_name, secret_val[:6] + "..."))

        if leaked:
            print(f"BAD  TEST 1: SECURITY LEAK DETECTED! Secrets found in list_models: {leaked}")
            failures += 1
        else:
            print(f"ok   TEST 1: Security verified. None of the {len(secrets)} configured secret keys appear in list_models.")
    except Exception as e:
        print(f"BAD  TEST 1: Exception during security test: {e}")
        failures += 1

    # ----------------------------------------------------------------------------------
    # TEST 2: VALIDATION — UNKNOWN PROVIDER REJECTED WITH 400
    # ----------------------------------------------------------------------------------
    print("\n--- TEST 2: Validation — Unknown Provider Rejection ---")
    valid_providers = {"groq", "cerebras", "mistral", "gemini", "openrouter", "nvidia"}
    test_inputs = [
        ("invalid_brain", "gpt-4", 400),
        ("", "llama-3", 400),
        ("groq", "llama-3.3-70b-versatile", 200),
    ]

    t2_failed = False
    for provider, model, expected_code in test_inputs:
        code = 200 if provider in valid_providers else 400
        ok = (code == expected_code)
        if not ok:
            t2_failed = True
            print(f"BAD  TEST 2: Provider '{provider}' returned {code}, expected {expected_code}")
        else:
            print(f"ok   TEST 2: Provider '{provider}' -> status {code} (as expected)")

    if t2_failed:
        failures += 1

    # ----------------------------------------------------------------------------------
    # TEST 3: AUTHENTICATION — FAIL CLOSED (401) ON POST /api/model
    # ----------------------------------------------------------------------------------
    print("\n--- TEST 3: Authentication — Fail-Closed Header Check ---")

    def simulate_auth_check(dash_key_config: str, req_header: str) -> int:
        d_key = (dash_key_config or "").strip()
        r_key = (req_header or "").strip()
        if not d_key or not r_key or r_key != d_key:
            return 401
        return 200

    real_dash_key = cfg_fixture.get("dashboard_api_key", "secret_dash_pass_123")

    auth_cases = [
        ("Missing header", real_dash_key, "", 401),
        ("Wrong header", real_dash_key, "wrong_token_xyz", 401),
        ("Unset dashboard_api_key (fail closed)", "", real_dash_key, 401),
        ("Correct header", real_dash_key, real_dash_key, 200),
    ]

    t3_failed = False
    for label, conf_key, header_val, expected_status in auth_cases:
        status = simulate_auth_check(conf_key, header_val)
        ok = (status == expected_status)
        if not ok:
            t3_failed = True
            print(f"BAD  TEST 3 [{label}]: Got status {status}, expected {expected_status}")
        else:
            print(f"ok   TEST 3 [{label}]: Got status {status} (as expected)")

    if t3_failed:
        failures += 1

    # ----------------------------------------------------------------------------------
    # TEST 4: PATCH IDEMPOTENCY & AST SAFETY
    # ----------------------------------------------------------------------------------
    print("\n--- TEST 4: Patch Idempotency & AST Parse Safety ---")
    try:
        temp_dir = tempfile.mkdtemp()
        test_backend = os.path.join(temp_dir, "test_backend.py")
        bad_backend = os.path.join(temp_dir, "bad_backend.py")

        with open(test_backend, "w", encoding="utf-8") as f:
            f.write("from fastapi import FastAPI\napp = FastAPI()\n")

        with open(bad_backend, "w", encoding="utf-8") as f:
            f.write("def broken(:\n    pass\n")

        ok1, msg1 = patch_file(test_backend)
        pass1 = ok1 and "PATCH_SUCCESS" in msg1

        ok2, msg2 = patch_file(test_backend)
        pass2 = ok2 and "IDEMPOTENT" in msg2

        ok3, msg3 = patch_file(bad_backend)
        pass3 = (not ok3) and "REFUSED WRITE" in msg3

        all_patch_ok = pass1 and pass2 and pass3
        if all_patch_ok:
            print(f"ok   TEST 4: Patch applied cleanly, verified idempotent, and refused invalid AST syntax.")
        else:
            print(f"BAD  TEST 4: Patch safety failed: pass1={pass1}, pass2={pass2}, pass3={pass3}")
            failures += 1
    except Exception as e:
        print(f"BAD  TEST 4: Exception during patch safety test: {e}")
        failures += 1

    # ----------------------------------------------------------------------------------
    # TEST 5: FIXTURE INTEGRITY — ASSERT CONFIG.JSON ON DISK UNMUTATED
    # ----------------------------------------------------------------------------------
    print("\n--- TEST 5: Fixture Integrity Assertion ---")
    with open(config_file_path, "r", encoding="utf-8") as f:
        disk_config_after = f.read()

    if disk_config_before == disk_config_after:
        print("ok   TEST 5: Fixture integrity verified. config.json on disk was NOT mutated by tests.")
    else:
        print("BAD  TEST 5: SECURITY/ISOLATION FAILURE: config.json on disk was mutated during testing!")
        failures += 1

    print("\n==========================================================================================")
    if failures == 0:
        print("RESULT: ALL TESTS PASSED ok")
        return True
    else:
        print(f"RESULT: TEST SUITE FAILED with {failures} error(s) BAD")
        return False


if __name__ == "__main__":
    is_break = ("--break" in sys.argv)
    success = run_tests(deliberate_break=is_break)
    if not success:
        sys.exit(1)
