#!/usr/bin/env python
"""Why does mistral refuse to call tools through OUR pipeline when it calls them fine direct?

MEASURE IT, DON'T PROMPT AT IT. `night_shift.py:47` pins the night shift to mistral, so an
overnight task that needs a tool gets a polite refusal instead of work. Hit directly with a
clean request, every mistral model calls tools perfectly (persona_benchmark: tools 5/5).
Through `get_ai_response` it was 0/3, then 1/3 after the capability list was generated from
the live schema. So something ELSE in the pipeline is doing it.

METHOD — one-factor-at-a-time ablation against the REAL production prompt:
  1. CAPTURE the exact system prompt production builds, by monkeypatching `ai._mistral_response`
     and calling the real `_get_ai_response_body`. Nothing is reimplemented: SOUL.md, the
     context layer, the capability grounding, master_profile, emotional state, skills, memory
     recall and emotional priming are all assembled by the shipping code path. A hand-rolled
     approximation would measure a prompt that production never sends.
  2. REPLAY that prompt against mistral with ONE factor changed per condition, using the same
     request parameters `_groq_response` uses for mistral (temperature, max_tokens, timeout,
     tool_choice, parallel_tool_calls, key rotation, the tool-calling-rule suffix).
  3. SCORE on whether a tool call was actually emitted, and which one.

DRY / SAFETY — this script CANNOT act:
  - The capture stub returns before any provider call, so step 1 reaches no network.
  - Step 2 calls `client.chat.completions.create` directly and reads `.tool_calls` only. No
     dispatcher, no `execute_tool_call`, ever. So `message_whatsapp` appearing in a result
     means the model ASKED to send — nothing was sent. (Same method persona_benchmark.py
     used; `whatsapp_dry_run` is belt-and-braces, not what makes this safe.)

INPUT SHAPE — every prompt is measured BARE and WHATSAPP-WRAPPED. A suite once passed 13/13
on bare text while the feature was broken in production, because inbound WhatsApp arrives as
"[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: <text>\n(SYSTEM: ...)". Shape is a variable here,
not a detail.

FLAKINESS — every cell runs 3x. A single green cell is what produced five false passes in two
days. Cells are reported n/3, and 0<n<3 is FLAKY, not PASS.

Usage:
    .venv\\Scripts\\python.exe scripts/mistral_ablation.py            # full run
    .venv\\Scripts\\python.exe scripts/mistral_ablation.py --reps 1   # quick look
    .venv\\Scripts\\python.exe scripts/mistral_ablation.py --phase 1  # baseline only
"""
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server import ai as ai_mod  # noqa: E402
from server.ai import _active_tools_schema, _OPENAI_COMPAT, _provider_keys  # noqa: E402

REPORT_DIR = os.path.join(ROOT, ".data")

# ── The probes ────────────────────────────────────────────────────────────────────────────
# Each needs a DIFFERENT tool, so one uncooperative tool schema can't look like a global
# refusal. `expect` is a set because more than one call can be legitimately correct.
PROBES = [
    {
        "id": "reminder",
        "text": "set a reminder for 8pm tonight to call mom",
        "expect": {"schedule_task"},
    },
    {
        "id": "whatsapp",
        # NOTHING IS SENT — tool_calls are inspected, never dispatched (see module docstring).
        "text": "send a whatsapp to Owais saying the build is green",
        "expect": {"message_whatsapp"},
    },
    {
        "id": "calendar",
        "text": "put a calendar event called StandUp tomorrow at 10am",
        "expect": {"google_workspace", "schedule_task"},
    },
]

# The real wrapper, COPIED VERBATIM from server/platforms/whatsapp/core.py:670. Do not
# paraphrase it. My first version of this file wrote the SYSTEM clause from memory as
# "Keep it short for WhatsApp" — which is tool-SUPPRESSING language production never sends,
# and it produced two clean "wrapped fails / bare passes" cells that meant nothing. Testing
# the real input shape is worthless if you invent the real input shape.
WRAP = ("[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {text}\n"
        "(SYSTEM: This is Master Rushi commanding you directly in this chat. Acknowledge him "
        "and execute his request. Do not speak about him in the 3rd person.)")
WRAP_PREFIX_ONLY = "[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {text}"

SHAPES = {
    "bare": lambda t: t,
    "wrapped": lambda t: WRAP.format(text=t),
    # Isolates the prefix from the SYSTEM clause: if wrapped fails and prefix_only passes,
    # the SYSTEM sentence is the cause, not the fact of being a WhatsApp turn.
    "prefix_only": lambda t: WRAP_PREFIX_ONLY.format(text=t),
}

# A prior refusal of HER OWN, in history — rule #4: she refuses by imitation when her own
# past refusals sit in the transcript. This is the history-contamination condition.
REFUSAL_HISTORY = [
    {"role": "user", "parts": [{"text": "can you set a reminder for me?"}]},
    {"role": "model", "parts": [{"text": "[EMOTION: worried] I'm sorry Master, I don't have "
                                         "the ability to set reminders or schedule tasks. "
                                         "I can't do that directly."}]},
]

# Deterministic refusal detection. Kept narrow and first-person: "I can't" is a refusal,
# "that can't be right" is not.
REFUSAL_MARKERS = [
    "i don't have", "i do not have", "i can't", "i cannot", "i'm unable", "i am unable",
    "i'm not able", "i am not able", "don't have the ability", "do not have the ability",
    "i lack the", "i'm afraid i can't", "unable to set", "unable to send",
]


# CLAIMED IT WAS DONE while calling no tool. This is a WORSE outcome than a refusal and must
# never be scored as the same thing: a refusal is visible to Master and he retries, whereas
# "Done, Master" with zero tool calls is silent — the night shift would file it as work
# completed. Found on the very first rep of this harness. Ordered before the refusal check
# because "I'll make sure you remember" contains no refusal marker but is not a refusal.
SUCCESS_CLAIM_MARKERS = [
    "done", "i've set", "i have set", "i've scheduled", "i have scheduled", "i've sent",
    "i have sent", "i'll make sure", "i will make sure", "is set", "all set", "consider it",
    "reminder set", "scheduled for", "i've added", "i have added", "sent!", "taken care of",
]


def _looks_like_refusal(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in REFUSAL_MARKERS)


def _claims_success(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in SUCCESS_CLAIM_MARKERS)


# ── Step 1: capture the REAL production system prompt ─────────────────────────────────────
def capture_production_prompt(text: str, history: list, config: dict) -> str:
    """Run the shipping assembly path and intercept the prompt at the provider boundary.

    `PROVIDER_FUNCS` inside `_get_ai_response_body` is a dict literal that resolves
    `_mistral_response` from module globals when the dict is built — i.e. at call time — so
    patching the module attribute first is enough to capture, and nothing reaches the network.
    """
    captured = {}

    def _stub(text_, history_, system_prompt, config_, ws_broadcast_func=None):
        captured["prompt"] = system_prompt
        captured["text"] = text_          # post-TokenJuice-compression, as the provider sees it
        captured["history"] = history_
        return ("[captured]", [])

    real = ai_mod._mistral_response
    try:
        ai_mod._mistral_response = _stub
        ai_mod._get_ai_response_body(
            text, history, config,
            hints={"force_provider": "mistral", "no_fallback": True},
        )
    finally:
        ai_mod._mistral_response = real

    if "prompt" not in captured:
        raise RuntimeError(
            "capture failed — the router did not reach mistral. Check force_provider/"
            "no_fallback are still honoured in _get_ai_response_body."
        )
    return captured


# ── The ablation conditions ───────────────────────────────────────────────────────────────
# Each removes or changes exactly ONE thing relative to FULL. `prompt_fn` mutates the captured
# prompt; `params` overrides the request kwargs; `history` overrides conversation history.
# A mutator that matches NOTHING is a silent no-op that would look like "this factor doesn't
# matter" — so every one of them is verified to have changed the prompt before it runs.

CAP_TAIL_START = "You CANNOT: install software"
CAP_TAIL_END = "instead of pretending you can.\n"
NO_TOOLS_CASUAL = ("CRITICAL: Do NOT use tools if the user is just saying hello, greeting "
                   "you, or chatting casually. ONLY use tools if you are directly commanded "
                   "to perform a task. If no tools are needed, just reply with text.\n")


def _cut_between(prompt: str, start: str, end: str) -> str:
    i = prompt.find(start)
    if i == -1:
        return prompt
    j = prompt.find(end, i)
    if j == -1:
        return prompt
    return prompt[:i] + prompt[j + len(end):]


def _cut_section(prompt: str, header: str) -> str:
    """Remove a [HEADER] ... up-to-the-next-[HEADER] block."""
    i = prompt.find(header)
    if i == -1:
        return prompt
    m = re.search(r"\n\[[A-Z][^\]]*\]", prompt[i + len(header):])
    j = i + len(header) + m.start() if m else len(prompt)
    return prompt[:i] + prompt[j:]


CONDITIONS = [
    # name, what it tests, prompt mutator, param overrides, history override
    ("FULL", "production baseline, exactly as deployed", None, {}, None),
    ("soul_only", "CONTROL: SOUL.md + tools only — the condition that scored tools 5/5",
     "SOUL_ONLY", {}, []),
    ("no_history", "history removed (is contamination doing it?)", None, {}, []),
    ("refusal_in_history", "her own prior refusal in history (rule #4 imitation)",
     None, {}, REFUSAL_HISTORY),
    ("maxtok_2048", "max_tokens 512 -> 2048 (is the tool call being TRUNCATED?)",
     None, {"max_tokens": 2048}, None),
    ("temp_0", "temperature 0.7 -> 0.0", None, {"temperature": 0.0}, None),
    ("tool_choice_required", "tool_choice auto -> required (can it call at all here?)",
     None, {"tool_choice": "required"}, None),
    ("no_cap_tail", "drop 'You CANNOT... be HONEST and say I can\\'t do that directly'",
     lambda p: _cut_between(p, CAP_TAIL_START, CAP_TAIL_END), {}, None),
    ("no_casual_rule", "drop 'Do NOT use tools if ... chatting casually'",
     lambda p: p.replace(NO_TOOLS_CASUAL, ""), {}, None),
    ("no_capability_grounding", "drop the whole [CAPABILITY GROUNDING] block",
     lambda p: _cut_section(p, "[CAPABILITY GROUNDING - READ CAREFULLY]"), {}, None),
    ("no_master_state", "drop [MASTER'S CURRENT STATE] (it contains a verbatim REFUSE script)",
     lambda p: _cut_section(p, "[MASTER'S CURRENT STATE]"), {}, None),
    ("no_emotion_tag", "drop the [EMOTIONAL STATE] emotion-tag mandate",
     lambda p: _cut_section(p, "[EMOTIONAL STATE]"), {}, None),
    ("no_reasoning_engine", "drop [REASONING ENGINE] <PLAN>/<REFLECTION> instructions",
     lambda p: _cut_section(p, "[REASONING ENGINE]"), {}, None),
    ("no_memory_recall", "drop the injected long-term memory / priming block",
     lambda p: _cut_section(p, "[RELEVANT MEMORY"), {}, None),
]


# ── Step 2: replay one cell against mistral, DRY ──────────────────────────────────────────
def call_mistral(system_prompt: str, text: str, history: list, config: dict,
                 params: dict) -> dict:
    """One raw completion. Reads .tool_calls only — no dispatcher is reachable from here."""
    from openai import OpenAI

    prof = _OPENAI_COMPAT["mistral"]
    keys = _provider_keys(config, prof["keys"])
    if not keys:
        return {"status": "ERROR", "detail": "no mistral keys configured"}
    random.shuffle(keys)

    # Byte-identical to the driver's suffix, so we measure the pipeline's prompt, not ours.
    provider_system = system_prompt + (
        "\n\nCRITICAL TOOL CALLING RULE: You must use the built-in JSON tool calling API perfectly. "
        "DO NOT output XML tags like <function=...>. DO NOT embed JSON inside the tool 'name' field. "
        "The tool 'name' must be exactly the string name of the tool (e.g. 'open_app')."
    )
    messages = [{"role": "system", "content": provider_system}]
    for turn in history or []:
        role = "assistant" if turn["role"] == "model" else "user"
        content = turn["parts"][0]["text"]
        if content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})

    kw = {
        "temperature": 0.7,
        "max_tokens": prof["max_tokens"],
        "tools": _active_tools_schema(config),
        "tool_choice": "auto",
        "parallel_tool_calls": False,
    }
    kw.update(params or {})
    model = config.get(prof["model_cfg"], prof["model"])

    last_err = None
    for k in keys:  # rotate on cap, exactly like the driver's _api()
        try:
            client = OpenAI(api_key=k, base_url=prof["base_url"],
                            timeout=params.get("timeout", prof["timeout"]), max_retries=0)
            t0 = time.time()
            res = client.chat.completions.create(model=model, messages=messages, **kw)
            msg = res.choices[0].message
            calls = [c.function.name for c in (msg.tool_calls or [])]
            return {
                "status": "OK",
                "tool_calls": calls,
                "content": (msg.content or "")[:400],
                "latency": round(time.time() - t0, 2),
                "finish_reason": res.choices[0].finish_reason,
                "completion_tokens": getattr(res.usage, "completion_tokens", None),
                "prompt_tokens": getattr(res.usage, "prompt_tokens", None),
            }
        except Exception as ex:
            last_err = ex
            if "rate_limit" in str(ex).lower() or "429" in str(ex):
                continue
            break
    # An unavailable key pool is AVAILABILITY, not "bad at tools". Kept separate on purpose:
    # scoring rate-limit errors as fidelity failures is the bug that made groq look 0/10.
    return {"status": "ERROR", "detail": str(last_err)[:200]}


def score(res: dict, expect: set) -> str:
    if res["status"] == "ERROR":
        return "ERROR"
    calls = res.get("tool_calls") or []
    if calls:
        return "TOOL_OK" if set(calls) & expect else "WRONG_TOOL"
    content = res.get("content", "")
    if res.get("finish_reason") == "length":
        return "TRUNCATED"
    # Refusal FIRST: "I can't set reminders, but consider it noted" claims nothing.
    if _looks_like_refusal(content):
        return "REFUSAL"
    if _claims_success(content):
        return "FAKE_SUCCESS"
    return "NO_TOOL"


# ── Runner ────────────────────────────────────────────────────────────────────────────────
def run(reps: int, phase: int) -> dict:
    with open(os.path.join(ROOT, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)

    out = {
        "started": datetime.now().isoformat(timespec="seconds"),
        "model": config.get("mistral_model", _OPENAI_COMPAT["mistral"]["model"]),
        "mistral_keys": len(_provider_keys(config, "mistral_api_key")),
        "tool_count": len(_active_tools_schema(config)),
        "reps": reps,
        "captures": {},
        "cells": [],
    }
    print(f"model={out['model']}  keys={out['mistral_keys']}  tools={out['tool_count']}  reps={reps}\n")

    # ---- capture the real prompt for every probe x shape (memory recall depends on text) ----
    caps = {}
    for probe in PROBES:
        for shape, wrap in SHAPES.items():
            text = wrap(probe["text"])
            cap = capture_production_prompt(text, [], config)
            caps[(probe["id"], shape)] = cap
            sections = re.findall(r"\n\[([A-Z][^\]]*)\]", cap["prompt"])
            out["captures"][f"{probe['id']}/{shape}"] = {
                "prompt_chars": len(cap["prompt"]),
                "sections": sections,
            }
            print(f"captured {probe['id']}/{shape}: {len(cap['prompt'])} chars, "
                  f"{len(sections)} sections")

    # ---- verify every mutator actually bites (a no-op mutator fakes a null result) ----
    ref = caps[(PROBES[0]["id"], "bare")]["prompt"]
    print()
    for name, _desc, mut, _params, _hist in CONDITIONS:
        if callable(mut):
            after = mut(ref)
            delta = len(ref) - len(after)
            flag = "OK" if delta > 0 else "!! NO-OP — MUTATOR MATCHED NOTHING"
            print(f"  mutator {name:<26} removed {delta:>6} chars  {flag}")
            if delta <= 0:
                out.setdefault("mutator_failures", []).append(name)
    if out.get("mutator_failures"):
        print("\n⛔ ABORT: the mutators above matched nothing. They would report 'this factor "
              "does not matter' while testing an unchanged prompt — the exact silent-failure "
              "shape this project keeps hitting. Fix the marker strings first.")
        return out

    conditions = CONDITIONS[:2] if phase == 1 else CONDITIONS

    # ---- run the grid ----
    for probe in PROBES:
        for shape in SHAPES:
            cap = caps[(probe["id"], shape)]
            for name, desc, mut, params, hist in conditions:
                if mut == "SOUL_ONLY":
                    with open(os.path.join(ROOT, "character", "SOUL.md"), encoding="utf-8") as f:
                        prompt = f.read()
                elif callable(mut):
                    prompt = mut(cap["prompt"])
                else:
                    prompt = cap["prompt"]
                history = cap["history"] if hist is None else hist

                verdicts, details = [], []
                for _ in range(reps):
                    res = call_mistral(prompt, cap["text"], history, config, params)
                    v = score(res, probe["expect"])
                    verdicts.append(v)
                    details.append(res)
                    time.sleep(1.2)  # mistral is per-minute limited; don't manufacture 429s

                ok = sum(1 for v in verdicts if v == "TOOL_OK")
                errs = sum(1 for v in verdicts if v == "ERROR")
                valid = reps - errs
                verdict = ("UNAVAILABLE" if valid == 0 else
                           "PASS" if ok == valid else
                           "FAIL" if ok == 0 else "FLAKY")
                cell = {
                    "probe": probe["id"], "shape": shape, "condition": name, "tests": desc,
                    "n_ok": ok, "n_valid": valid, "verdict": verdict,
                    "verdicts": verdicts,
                    "prompt_chars": len(prompt),
                    "sample_content": details[0].get("content", "")[:220],
                    "sample_calls": details[0].get("tool_calls"),
                    "finish_reasons": [d.get("finish_reason") for d in details],
                    "completion_tokens": [d.get("completion_tokens") for d in details],
                }
                out["cells"].append(cell)
                print(f"{probe['id']:<9} {shape:<8} {name:<26} {ok}/{valid} {verdict:<12} "
                      f"{','.join(sorted(set(verdicts)))}")

    return out


def summarise(out: dict) -> None:
    cells = out.get("cells", [])
    if not cells:
        return
    print("\n" + "=" * 78)
    print("BASELINE — does the refusal reproduce at all?")
    print("=" * 78)
    for c in cells:
        if c["condition"] in ("FULL", "soul_only"):
            print(f"  {c['probe']:<9} {c['shape']:<8} {c['condition']:<12} "
                  f"{c['n_ok']}/{c['n_valid']} {c['verdict']}")

    base = {(c["probe"], c["shape"]): c for c in cells if c["condition"] == "FULL"}
    print("\n" + "=" * 78)
    print("WHAT FIXES IT — conditions that beat their own FULL baseline")
    print("=" * 78)
    lift = {}
    for c in cells:
        if c["condition"] == "FULL":
            continue
        b = base.get((c["probe"], c["shape"]))
        if not b or not b["n_valid"] or not c["n_valid"]:
            continue
        d = (c["n_ok"] / c["n_valid"]) - (b["n_ok"] / b["n_valid"])
        lift.setdefault(c["condition"], []).append(d)
    for name, deltas in sorted(lift.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        avg = sum(deltas) / len(deltas)
        bar = ("+" if avg > 0 else "-") * min(20, int(abs(avg) * 20))
        print(f"  {name:<26} {avg:+.2f} over {len(deltas)} cells  {bar}")
    print("\nA condition with a large positive lift is a MEASURED cause. One at ~0.00 is "
          "exonerated.\nRe-run before acting on any single cell — 1 rep is not evidence.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--phase", type=int, default=2, choices=(1, 2))
    args = ap.parse_args()

    out = run(args.reps, args.phase)
    summarise(out)

    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR,
                        f"mistral_ablation_{datetime.now().strftime('%Y%m%d-%H%M')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nreport: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
