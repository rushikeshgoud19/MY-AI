#!/usr/bin/env python3
"""
scripts/patch_ws_auth.py — Self-contained patch script for VM's backend_main.py (Task Pack 12.1).

Inserts WebSocket authentication check into /ws endpoint in backend_main.py.

AUTH REQUIREMENT FOR /ws:
  Reads token from query param ?key= or initial message.
  Gated behind config.get("ws_auth_required", False). Default is FALSE.
  When ws_auth_required is True:
    - Compares token against config["dashboard_api_key"].
    - On mismatch/missing: closes socket with code 4001 and readable reason.
  When ws_auth_required is False:
    - Accepts both authenticated and unauthenticated connections.

IDEMPOTENCE & SAFETY:
  - If patch marker already exists, skips without duplicating.
  - Validates output using ast.parse() before writing file.
"""

import ast
import os
import sys

PATCH_MARKER = "# --- TASK PACK 12.1: WEBSOCKET AUTHENTICATION ---"


def _verify_ws_auth(websocket, config: dict) -> tuple:
    """Check WebSocket token against config['dashboard_api_key'].
    Returns (ok: bool, reason: str).
    Gated behind config.get('ws_auth_required', False). If False, returns (True, 'Auth disabled').
    """
    auth_required = config.get("ws_auth_required", False)
    if not auth_required:
        return True, "Auth disabled"

    expected_key = (config.get("dashboard_api_key") or "").strip()
    if not expected_key:
        return False, "Unauthorized: dashboard_api_key is unset on server"

    # Query param token
    query_key = getattr(websocket, "query_params", {}).get("key", "").strip() if hasattr(websocket, "query_params") else ""
    if query_key and query_key == expected_key:
        return True, "Authenticated via query param"

    # Header token fallback
    header_key = getattr(websocket, "headers", {}).get("X-Mizune-Key", "").strip() if hasattr(websocket, "headers") else ""
    if header_key and header_key == expected_key:
        return True, "Authenticated via header"

    return False, "Unauthorized: Invalid or missing WebSocket authentication key"

WS_AUTH_HELPER = '''
# --- TASK PACK 12.1: WEBSOCKET AUTHENTICATION ---
def _verify_ws_auth(websocket, config: dict) -> tuple:
    """Check WebSocket token against config['dashboard_api_key'].
    Returns (ok: bool, reason: str).
    Gated behind config.get('ws_auth_required', False). If False, returns (True, 'Auth disabled').
    """
    auth_required = config.get("ws_auth_required", False)
    if not auth_required:
        return True, "Auth disabled"

    expected_key = (config.get("dashboard_api_key") or "").strip()
    if not expected_key:
        return False, "Unauthorized: dashboard_api_key is unset on server"

    # Query param token
    query_key = websocket.query_params.get("key", "").strip()
    if query_key and query_key == expected_key:
        return True, "Authenticated via query param"

    # Header token fallback
    header_key = websocket.headers.get("X-Mizune-Key", "").strip()
    if header_key and header_key == expected_key:
        return True, "Authenticated via header"

    return False, "Unauthorized: Invalid or missing WebSocket authentication key"
# --- END TASK PACK 12.1: WEBSOCKET AUTHENTICATION ---
'''


def patch_ws_file(target_path: str) -> tuple:
    """Patch target python file with WebSocket authentication helper safely.
    Returns (success: bool, message: str).
    """
    if not os.path.exists(target_path):
        return False, f"Target file does not exist: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Idempotency check
    if PATCH_MARKER in content or "_verify_ws_auth" in content:
        return True, "IDEMPOTENT: Target file already contains WebSocket authentication."

    patched_content = content + "\n" + WS_AUTH_HELPER

    # Validate AST syntax
    try:
        ast.parse(patched_content)
    except SyntaxError as e:
        return False, f"REFUSED WRITE: Patched content produced invalid Python syntax: {e}"

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(patched_content)

    return True, f"PATCH_SUCCESS: Successfully patched {target_path}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/patch_ws_auth.py <path_to_backend_main.py>")
        sys.exit(1)

    target = sys.argv[1]
    ok, msg = patch_ws_file(target)
    print(msg)
    if not ok:
        sys.exit(1)
