#!/usr/bin/env python3
"""
scripts/patch_model_api.py — Self-contained patch script for VM's backend_main.py (Task Pack 11.2).

Inserts GET /api/models and POST /api/model endpoints into backend_main.py.

AUTH REQUIREMENT FOR POST /api/model:
  Compares X-Mizune-Key header against config["dashboard_api_key"].
  FAILS CLOSED with 401 when header is missing/invalid OR config dashboard_api_key is unset.

IDEMPOTENCE & SAFETY:
  - If routes already exist, skips without duplicating.
  - Validates output using ast.parse() before writing file.
"""

import ast
import os
import sys

PATCH_MARKER = "# --- TASK PACK 11: MODEL SELECTOR ENDPOINTS ---"

ROUTES_CODE = '''

# --- TASK PACK 11: MODEL SELECTOR ENDPOINTS ---
@app.get("/api/models")
async def get_model_catalog_endpoint():
    """GET /api/models — List all providers, model health, and reliability (NO SECRETS)."""
    try:
        from server.config import load_config
        from server.model_catalog import list_models
        cfg = load_config()
        models = list_models(cfg)
        curr = next((m for m in models if m.get("is_current")), models[0] if models else {})
        return {"models": models, "current": curr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/model")
async def set_model_endpoint(request: Request):
    """POST /api/model — Update active LLM provider/model.
    AUTH REQUIRED: Fail closed 401 if X-Mizune-Key != dashboard_api_key or if dashboard_api_key is unset.
    """
    from server.config import load_config, save_config
    from server.model_catalog import list_models
    cfg = load_config()

    # Security Authentication Check (Fail closed)
    dash_key = cfg.get("dashboard_api_key", "").strip()
    req_key = request.headers.get("X-Mizune-Key", "").strip()

    if not dash_key or not req_key or req_key != dash_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing X-Mizune-Key header")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    provider = body.get("provider", "").strip().lower()
    model = body.get("model", "").strip()

    if not provider:
        raise HTTPException(status_code=400, detail="Missing required field 'provider'")

    catalog = list_models(cfg)
    valid_providers = {m["provider"]: m for m in catalog}

    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'. Valid providers: {list(valid_providers.keys())}")

    # Update config
    cfg["ai_model"] = provider
    if model:
        cfg[f"{provider}_model"] = model

    save_config(cfg)
    updated_catalog = list_models(cfg)
    new_curr = next((m for m in updated_catalog if m.get("is_current")), {})
    return {"status": "ok", "message": f"Active provider set to '{provider}'", "current": new_curr}
# --- END TASK PACK 11: MODEL SELECTOR ENDPOINTS ---
'''


def patch_file(target_path: str) -> tuple:
    """Patch target python file with model selector routes safely.
    Returns (success: bool, message: str).
    """
    if not os.path.exists(target_path):
        return False, f"Target file does not exist: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for idempotency
    if PATCH_MARKER in content or "/api/models" in content:
        return True, "IDEMPOTENT: Target file already contains model selector endpoints."

    patched_content = content + ROUTES_CODE

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
        print("Usage: python scripts/patch_model_api.py <path_to_backend_main.py>")
        sys.exit(1)

    target = sys.argv[1]
    ok, msg = patch_file(target)
    print(msg)
    if not ok:
        sys.exit(1)
