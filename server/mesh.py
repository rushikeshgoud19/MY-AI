"""
Z5 MESH — Multi-Model Cognition & Cross-Model Verification (Phase Z5).

Fans out a high-stakes question to K independent LLM providers in parallel (using system_prompt_override
to block all tool execution), then uses a separate verifier model to reconcile claims, flag contradictions,
and output a single verified answer.

Safety Rules:
1. READ-ONLY: Tool execution is strictly suppressed via system_prompt_override (_bg_guard).
2. THREAD SAFETY: Parallel get_ai_response calls run in separate threads (thread-local _bg_guard).
3. NON-BLOCKING: Per-provider exceptions/timeouts are caught individually and isolated.
"""

import time
import json
import re
import concurrent.futures
from typing import Dict, Any, List

from .config import log_info
from .ai import get_ai_response, get_api_key, _OPENAI_COMPAT


def _is_provider_keyed(config: dict, p_name: str) -> bool:
    prof = _OPENAI_COMPAT.get(p_name)
    if not prof:
        return False
    key_name = prof.get("keys")
    if not key_name:
        return False
    key_val = get_api_key(config, key_name)
    return bool(key_val)


def mesh_answer(question: str, config: dict, providers: List[str] = None, verifier: str = None) -> Dict[str, Any]:
    """Execute cross-model parallel query and verification."""
    # 1. Determine usable providers
    if not providers:
        base_providers = ["mistral", "cerebras"]
        # Add third provider if keyed
        for candidate in ["gemini", "openrouter", "groq"]:
            if _is_provider_keyed(config, candidate) and candidate not in base_providers:
                base_providers.append(candidate)
                break
        providers = base_providers

    usable_providers = [p for p in providers if _is_provider_keyed(config, p)]
    
    if len(usable_providers) < 2:
        log_info(f"[MESH] Refused: need >= 2 usable providers, found {usable_providers}")
        return {
            "mesh": False,
            "reason": f"need >= 2 usable providers (found {usable_providers})",
            "consolidated": "Maa, Master, I need at least two active models configured to cross-check that."
        }

    log_info(f"[MESH] Fanning out question to {len(usable_providers)} providers: {usable_providers}")
    
    answers = {}
    latencies = {}

    # 2. Parallel Fan-Out
    def _fetch_provider_answer(p_name: str):
        start_t = time.time()
        try:
            prompt_override = (
                "You are a careful analyst. Answer the question factually and concisely. "
                "If you are unsure, say so."
            )
            text_res, _ = get_ai_response(
                question,
                [],
                config,
                hints={"force_provider": p_name},
                system_prompt_override=prompt_override
            )
            duration = time.time() - start_t
            clean_text = str(text_res or "").strip()
            if clean_text and not any(err_kw in clean_text.lower() for err_kw in ["tangled", "not configured", "trouble thinking"]):
                return p_name, clean_text, duration, True
            return p_name, clean_text, duration, False
        except Exception as e:
            duration = time.time() - start_t
            log_info(f"[MESH] Provider '{p_name}' failed: {e}")
            return p_name, f"Error: {e}", duration, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(usable_providers)) as executor:
        futures = [executor.submit(_fetch_provider_answer, p) for p in usable_providers]
        for future in concurrent.futures.as_completed(futures):
            p_name, text, duration, ok = future.result()
            latencies[p_name] = round(duration, 2)
            if ok:
                answers[p_name] = text

    if len(answers) < 2:
        log_info(f"[MESH] Insufficient successful answers ({len(answers)} returned)")
        fallback_text = list(answers.values())[0] if answers else "I couldn't cross-check that right now, Master."
        return {
            "mesh": False,
            "reason": f"Fewer than 2 providers returned valid answers (got {len(answers)})",
            "consolidated": fallback_text,
            "answers": answers,
            "latencies": latencies
        }

    # 3. Choose Verifier
    if not verifier:
        # Prefer a provider that did NOT participate in answering
        for candidate in ["gemini", "openrouter", "groq", "mistral", "cerebras"]:
            if candidate not in answers and _is_provider_keyed(config, candidate):
                verifier = candidate
                break
        if not verifier:
            # Fall back to strongest available provider in answers
            verifier = "mistral" if "mistral" in answers else list(answers.keys())[0]

    log_info(f"[MESH] Reconciling claims using verifier '{verifier}'...")

    formatted_answers = "\n\n".join(f"[Model: {p.upper()}]\n{ans}" for p, ans in answers.items())
    
    verifier_prompt = (
        f"You are an impartial AI fact-verifier and reconciler.\n"
        f"QUESTION: {question}\n\n"
        f"Here are the responses from K independent AI models:\n"
        f"{formatted_answers}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Compare the models' claims.\n"
        f"2. Identify areas where they AGREE.\n"
        f"3. Identify areas where they CONTRADICT each other or where one model makes an unverified claim.\n"
        f"4. Determine agreement level: HIGH (all agree on key facts), MIXED (minor differences or extra details), or CONFLICT (direct contradictions or false claims).\n"
        f"5. Output a final consolidated, accurate answer.\n\n"
        f"CRITICAL: Do NOT use tools. Do NOT return JSON. Output plain text using the exact labels below.\n\n"
        f"FORMAT YOUR RESPONSE EXACTLY AS:\n"
        f"AGREEMENT: [HIGH | MIXED | CONFLICT]\n"
        f"NOTES: <short explanation of consensus or conflicts>\n"
        f"CONSOLIDATED: <final factual verified answer>"
    )

    verifier_start = time.time()
    consolidated_raw = ""
    try:
        verifier_res, _ = get_ai_response(
            verifier_prompt,
            [],
            config,
            hints={"force_provider": verifier},
            system_prompt_override="You are a strict, impartial fact-verification system. Do NOT invoke tools. Output plain text only."
        )
        verifier_lat = round(time.time() - verifier_start, 2)
        latencies[f"verifier_{verifier}"] = verifier_lat
        consolidated_raw = str(verifier_res or "").strip()
    except Exception as e:
        log_info(f"[MESH] Verifier '{verifier}' error: {e}")
        consolidated_raw = f"AGREEMENT: UNKNOWN\nNOTES: Verifier failed ({e})\nCONSOLIDATED: " + list(answers.values())[0]

    # 4. Parse Verifier Output
    agreement = "unknown"
    notes = ""
    consolidated = consolidated_raw

    m_agr = re.search(r"AGREEMENT:\s*(HIGH|MIXED|CONFLICT)", consolidated_raw, re.IGNORECASE)
    if m_agr:
        agreement = m_agr.group(1).lower()

    m_notes = re.search(r"NOTES:\s*(.*?)(?=CONSOLIDATED:|$)", consolidated_raw, re.IGNORECASE | re.DOTALL)
    if m_notes:
        notes = m_notes.group(1).strip()

    m_cons = re.search(r"CONSOLIDATED:\s*(.*)", consolidated_raw, re.IGNORECASE | re.DOTALL)
    if m_cons:
        consolidated = m_cons.group(1).strip()

    return {
        "mesh": True,
        "question": question,
        "providers_used": list(answers.keys()),
        "verifier": verifier,
        "answers": answers,
        "consolidated": consolidated,
        "agreement": agreement,
        "notes": notes,
        "latencies": latencies
    }
