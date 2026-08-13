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


def _looks_failed(text: str) -> bool:
    """True when a provider returned Mizune's in-character failure line instead of an answer.
    With no_fallback the cascade no longer rescues a dead provider, so this sentinel is the
    ONLY signal that a call produced nothing usable — used for answers AND the verifier."""
    t = str(text or "").strip().lower()
    if not t:
        return True
    return any(kw in t for kw in ("tangled", "not configured", "trouble thinking"))


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
            # no_fallback is LOAD-BEARING: without it the cascade silently answers with a
            # different provider on 429 and the answer gets filed under the wrong name —
            # observed 2026-07-27 (groq capped -> cerebras answered -> reported as 3 models).
            text_res, _ = get_ai_response(
                question,
                [],
                config,
                hints={"force_provider": p_name, "no_fallback": True},
                system_prompt_override=prompt_override
            )
            duration = time.time() - start_t
            clean_text = str(text_res or "").strip()
            return p_name, clean_text, duration, not _looks_failed(clean_text)
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

    # 3. Choose Verifier — build an ORDERED CANDIDATE LIST, not a single pick.
    # Being "keyed" does not mean being usable: on 2026-07-27 groq was keyed but at its daily
    # cap, so a single held-out pick failed and turned two perfectly good answers into a
    # failure line. Held-out candidates come first (a model grading its own answer is weaker
    # evidence), then the producers as a last resort — flagged as not held out.
    if verifier:
        verifier_candidates = [verifier]
    else:
        verifier_candidates = [c for c in ["gemini", "openrouter", "groq", "mistral", "cerebras"]
                               if c not in answers and _is_provider_keyed(config, c)]
        producers = (["mistral"] if "mistral" in answers else []) + \
                    [p for p in answers if p != "mistral"]
        verifier_candidates += producers

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

    consolidated_raw = ""
    verifier = None
    for candidate in verifier_candidates:
        log_info(f"[MESH] Reconciling claims using verifier '{candidate}' "
                 f"(held_out={candidate not in answers})...")
        verifier_start = time.time()
        try:
            verifier_res, _ = get_ai_response(
                verifier_prompt,
                [],
                config,
                hints={"force_provider": candidate, "no_fallback": True},
                system_prompt_override="You are a strict, impartial fact-verification system. Do NOT invoke tools. Output plain text only."
            )
            latencies[f"verifier_{candidate}"] = round(time.time() - verifier_start, 2)
            text = str(verifier_res or "").strip()
        except Exception as e:
            latencies[f"verifier_{candidate}"] = round(time.time() - verifier_start, 2)
            log_info(f"[MESH] Verifier '{candidate}' error: {e}")
            text = ""
        if not _looks_failed(text):
            verifier, consolidated_raw = candidate, text
            break
        log_info(f"[MESH] Verifier '{candidate}' unusable — trying next candidate")

    if verifier is None:
        # Every candidate is down. Return the producers' answers UNRECONCILED and say so —
        # never present an unverified single answer as if it had been cross-checked.
        log_info(f"[MESH] All verifier candidates failed ({verifier_candidates})")
        return {
            "mesh": False,
            "reason": f"{len(answers)} models answered but no verifier was reachable",
            "consolidated": list(answers.values())[0],
            "answers": answers,
            "latencies": latencies
        }

    verifier_held_out = verifier not in answers

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
        "verifier_held_out": verifier_held_out,
        "answers": answers,
        "consolidated": consolidated,
        "agreement": agreement,
        "notes": notes,
        "latencies": latencies
    }
