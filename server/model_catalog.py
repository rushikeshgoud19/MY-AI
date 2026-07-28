#!/usr/bin/env python3
"""
server/model_catalog.py — Model catalog & availability tracker (Task Pack 11.1).

NO LLM IN THIS FILE.
Collects usable providers/models, tests key availability, reads tool_reliability
from .data/provider_matrix.json, and caches results to .data/model_catalog.json.

SECURITY GUARANTEE: NEVER RETURN OR SERIALIZE API KEYS OR SECRETS.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

PROVIDER_SPECS = {
    "groq": {
        "key_name": "groq_api_key",
        "model_cfg": "groq_model",
        "default_model": "llama-3.3-70b-versatile",
        "models_url": "https://api.groq.com/openai/v1/models",
    },
    "cerebras": {
        "key_name": "cerebras_api_key",
        "model_cfg": "cerebras_model",
        "default_model": "gpt-oss-120b",
        "models_url": "https://api.cerebras.ai/v1/models",
    },
    "mistral": {
        "key_name": "mistral_api_key",
        "model_cfg": "mistral_model",
        "default_model": "mistral-medium-2508",
        "models_url": "https://api.mistral.ai/v1/models",
    },
    "gemini": {
        "key_name": "gemini_api_key",
        "model_cfg": "gemini_model",
        "default_model": "gemini-2.5-flash",
        "models_url": None,
    },
    "openrouter": {
        "key_name": "openrouter_api_key",
        "model_cfg": "openrouter_model",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models_url": "https://openrouter.ai/api/v1/models",
    },
    "nvidia": {
        "key_name": "nvidia_api_key",
        "model_cfg": "nvidia_model",
        "default_model": "meta/llama-3.1-70b-instruct",
        "models_url": None,
    },
}


def _get_first_key(config: dict, key_name: str) -> str:
    """Extract a single API key string from config value (string or list)."""
    val = config.get(key_name)
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, list):
        for k in val:
            if isinstance(k, str) and k.strip():
                return k.strip()
    return ""


def _is_keyed(config: dict, key_name: str) -> bool:
    return bool(_get_first_key(config, key_name))


def _read_provider_matrix() -> dict:
    """Read tool reliability from .data/provider_matrix.json if present."""
    matrix_path = os.path.join(ROOT_DIR, ".data", "provider_matrix.json")
    if os.path.exists(matrix_path):
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("matrix", {})
        except Exception:
            pass
    return {}


def _probe_models_url(url: str, api_key: str) -> tuple:
    """Probe a provider's /v1/models endpoint using urllib.
    Returns (available: bool, detail: str, model_ids: list[str]).
    """
    if not url or not api_key:
        return False, "unconfigured", []
    
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Mizune/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("id") for m in body.get("data", []) if m.get("id")]
                return True, "live", models
            return True, f"HTTP {resp.status}", []
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return False, "daily cap / rate limit (429)", []
        if e.code == 401:
            return False, "invalid API key (401)", []
        return False, f"HTTP {e.code}", []
    except Exception as e:
        return False, f"connection error: {e}", []


def list_models(config: dict) -> list:
    """Build model catalog listing every configured provider/model with health & reliability.
    NEVER INCLUDES ANY SECRET KEY MATERIAL IN OUTPUT.
    """
    current_primary = config.get("ai_model", "groq")
    matrix_data = _read_provider_matrix()
    catalog = []

    for provider, spec in PROVIDER_SPECS.items():
        key_name = spec["key_name"]
        keyed = _is_keyed(config, key_name)
        active_key = _get_first_key(config, key_name)
        configured_model = config.get(spec["model_cfg"], spec["default_model"])

        # Tool reliability from provider_matrix.json
        tool_rel = "unmeasured"
        if provider in matrix_data:
            p_matrix = matrix_data[provider]
            tc = p_matrix.get("tool_choice", {})
            tool_rel = tc.get("verdict", "unmeasured")

        # Live probe if keyed and url available
        available = False
        detail = "key not configured" if not keyed else "keyed"
        remote_models = []

        if keyed:
            if spec["models_url"]:
                available, detail, remote_models = _probe_models_url(spec["models_url"], active_key)
            else:
                available = True
                detail = "keyed"

        # Determine primary model to display
        model_id = configured_model
        if remote_models and configured_model not in remote_models and len(remote_models) > 0:
            # Keep configured model or fallback
            pass

        is_curr = (provider == current_primary)

        item = {
            "provider": provider,
            "model": model_id,
            "keyed": keyed,
            "available": available,
            "detail": detail,
            "tool_reliability": tool_rel,
            "is_current": is_curr,
        }
        catalog.append(item)

    # Save to .data/model_catalog.json cache
    try:
        os.makedirs(os.path.join(ROOT_DIR, ".data"), exist_ok=True)
        cache_path = os.path.join(ROOT_DIR, ".data", "model_catalog.json")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "catalog": catalog,
                "current_primary": current_primary
            }, f, indent=2)
    except Exception:
        pass

    # SECURITY ASSERTION: Ensure no API key string is present in output
    config_keys_to_check = [
        v for k, v in config.items()
        if ("key" in k.lower() or "secret" in k.lower() or "token" in k.lower())
        and isinstance(v, str) and len(v) > 8
    ]
    catalog_str = json.dumps(catalog)
    for secret in config_keys_to_check:
        if secret in catalog_str:
            raise SecurityError(f"CRITICAL SECURITY FAILURE: API Key leak detected in model catalog!")

    return catalog


class SecurityError(Exception):
    pass


if __name__ == "__main__":
    from server.config import load_config
    cfg = load_config()
    res = list_models(cfg)
    print("==========================================================================================")
    print("=== MIZUNE MODEL CATALOG (Task Pack 11.1) ===")
    print("==========================================================================================")
    print(json.dumps(res, indent=2))
