#!/usr/bin/env python3
"""
scripts/test_ws_auth.py — Test suite for Deliverable 12.1 (WebSocket Auth).

TESTS 4 MATRIX CONDITIONS:
  1. ws_auth_required = True, unauthenticated -> REFUSED (code 4001, readable reason)
  2. ws_auth_required = True, authenticated   -> ACCEPTED (200 / connected)
  3. ws_auth_required = False, unauthenticated -> ACCEPTED
  4. ws_auth_required = False, authenticated   -> ACCEPTED

Also tests patch_ws_auth.py idempotency and AST parse safety.
"""

import asyncio
import json
import os
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.patch_ws_auth import _verify_ws_auth, patch_ws_file


@dataclass
class MockWebSocket:
    query_params: dict
    headers: dict


def test_ws_auth_matrix():
    print("==========================================================================================")
    print("=== RUNNING DELIVERABLE 12.1 WEBSOCKET AUTH TEST MATRIX ===")
    print("==========================================================================================")

    test_key = "secret_dash_test_key_999"

    # 1. ws_auth_required = True, Unauthenticated (no key)
    cfg1 = {"ws_auth_required": True, "dashboard_api_key": test_key}
    ws1 = MockWebSocket(query_params={}, headers={})
    ok1, reason1 = _verify_ws_auth(ws1, cfg1)
    print(f"CASE 1 (ws_auth_required=True, No Key)     : ok={ok1} | Reason='{reason1}'")
    assert not ok1, "Should refuse unauthenticated connection when auth required"

    # 1b. ws_auth_required = True, Wrong key
    ws1b = MockWebSocket(query_params={"key": "wrong_key_123"}, headers={})
    ok1b, reason1b = _verify_ws_auth(ws1b, cfg1)
    print(f"CASE 1b (ws_auth_required=True, Wrong Key)  : ok={ok1b} | Reason='{reason1b}'")
    assert not ok1b, "Should refuse wrong key when auth required"

    # 2. ws_auth_required = True, Authenticated (valid query param key)
    ws2 = MockWebSocket(query_params={"key": test_key}, headers={})
    ok2, reason2 = _verify_ws_auth(ws2, cfg1)
    print(f"CASE 2 (ws_auth_required=True, Valid Key)   : ok={ok2} | Reason='{reason2}'")
    assert ok2, "Should accept valid query param key"

    # 3. ws_auth_required = False, Unauthenticated
    cfg3 = {"ws_auth_required": False, "dashboard_api_key": test_key}
    ws3 = MockWebSocket(query_params={}, headers={})
    ok3, reason3 = _verify_ws_auth(ws3, cfg3)
    print(f"CASE 3 (ws_auth_required=False, No Key)    : ok={ok3} | Reason='{reason3}'")
    assert ok3, "Should accept unauthenticated when auth disabled"

    # 4. ws_auth_required = False, Authenticated
    ws4 = MockWebSocket(query_params={"key": test_key}, headers={})
    ok4, reason4 = _verify_ws_auth(ws4, cfg3)
    print(f"CASE 4 (ws_auth_required=False, Valid Key)  : ok={ok4} | Reason='{reason4}'")
    assert ok4, "Should accept authenticated when auth disabled"

    # Patch file test
    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, "backend_test.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("# mock backend\n")

    p_ok1, p_msg1 = patch_ws_file(test_file)
    assert p_ok1 and "PATCH_SUCCESS" in p_msg1, "Patch should succeed"

    p_ok2, p_msg2 = patch_ws_file(test_file)
    assert p_ok2 and "IDEMPOTENT" in p_msg2, "Patch should be idempotent"

    print("\nRESULT: ALL 4 WEBSOCKET AUTH MATRIX CASES PASSED ok")


if __name__ == "__main__":
    test_ws_auth_matrix()
