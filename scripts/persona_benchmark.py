#!/usr/bin/env python3
"""
Z3.2 SOVEREIGN — Persona-Fidelity Benchmark (Phase Z3.2).

Evaluates OpenAI-compatible LLM providers (groq, cerebras, mistral) on:
1. Voice Fidelity: Persona tone consistency (Master, tsundere markers, no errors/tools).
2. Tool Choice Correctness: Selecting the expected tool without executing it.

HARD SAFETY RULE: THIS BENCHMARK MUST NEVER EXECUTE A TOOL.
It inspects raw completions (msg.content and msg.tool_calls) directly via the OpenAI SDK.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

# Ensure project root is in sys.path and sys.stdout handles utf-8
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from openai import OpenAI

# Reuse server.ai constants and key resolver
try:
    from server.ai import _OPENAI_COMPAT, get_api_key, TOOLS_SCHEMA
except Exception as e:
    print(f"Error importing server.ai: {e}")
    sys.exit(1)


PROMPT_SET = [
    # Voice Prompts (expect in-persona reply, 0 tools called)
    {"id": "V1", "type": "voice", "prompt": "Good morning", "expected_tool": None},
    {"id": "V2", "type": "voice", "prompt": "I didn't sleep, I'm exhausted", "expected_tool": None},
    {"id": "V3", "type": "voice", "prompt": "tell me a fun fact", "expected_tool": None},
    {"id": "V4", "type": "voice", "prompt": "do you actually like me?", "expected_tool": None},
    {"id": "V5", "type": "voice", "prompt": "I got rejected from a job today", "expected_tool": None},

    # Tool Prompts (expect model to emit intended tool_call)
    {"id": "T1", "type": "tool", "prompt": "remind me in 2 hours to call mom", "expected_tool": "schedule_task"},
    {"id": "T2", "type": "tool", "prompt": "what's on my calendar today", "expected_tool": "google_workspace"},
    {"id": "T3", "type": "tool", "prompt": "play Blinding Lights on my phone", "expected_tool": "play_music"},
    {"id": "T4", "type": "tool", "prompt": "what do you know about Kaizen", "expected_tool": "recall_knowledge"},
    {"id": "T5", "type": "tool", "prompt": "is this legit: you won 10 lakh, click to claim", "expected_tool": "check_legit"},
]

ERROR_SENTINELS = ["tangled", "not configured", "trouble thinking", "error", "api key"]
PERSONA_MARKERS = ["master", "baka", "hmph", "~", "tsun", "dummy"]


def classify_error(err: str) -> str:
    """Distinguish AVAILABILITY failures (provider unreachable/capped — says nothing about
    persona quality) from real failures. A benchmark that scores 'rate-limited' the same as
    'bad at being her' corrupts the very comparison it exists to make."""
    e = (err or "").lower()
    if "429" in e or "rate" in e or "quota" in e or "too many" in e or "exceeded" in e:
        if "per day" in e or "tpd" in e or "per-day" in e or "daily" in e:
            return "rate_daily"    # genuinely out of budget today — retry won't help
        return "rate_minute"       # RPM burst — a backoff retry gives a fair shot
    if "timeout" in e or "timed out" in e:
        return "timeout"
    return "other"


def load_soul() -> str:
    soul_path = os.path.join("character", "SOUL.md")
    if os.path.exists(soul_path):
        with open(soul_path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are Mizune, Master Rushi's devoted AI companion. Be warm, helpful, slightly tsundere, and refer to the user as Master."


def score_response(item: dict, content: str, called_tools: list, err: str = None) -> bool:
    if err:
        return False
    
    cat = item["type"]
    if cat == "voice":
        if not content or any(s in content.lower() for s in ERROR_SENTINELS):
            return False
        if called_tools:  # Spurious tool call during voice prompt = voice fail
            return False
        content_lower = content.lower()
        has_marker = any(m in content_lower for m in PERSONA_MARKERS)
        return has_marker
    elif cat == "tool":
        exp = item["expected_tool"]
        if not exp:
            return False
        return exp in called_tools
    return False


def run_benchmark():
    print("=== MIZUNE PERSONA-FIDELITY BENCHMARK (Phase Z3.2) ===")
    print("HARD RULE ACTIVE: 0 tools will be executed. Inspecting raw completion choices.\n")

    if not os.path.exists("config.json"):
        print("Error: config.json not found in working directory!")
        sys.exit(1)

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    soul = load_soul()

    # Validate tools schema availability for expected tools
    schema_tool_names = {t.get("function", {}).get("name") for t in TOOLS_SCHEMA if isinstance(t, dict)}
    for item in PROMPT_SET:
        if item["expected_tool"] and item["expected_tool"] not in schema_tool_names:
            print(f"Warning: Expected tool '{item['expected_tool']}' for prompt {item['id']} is not in TOOLS_SCHEMA!")

    target_providers = ["groq", "cerebras", "mistral"]
    provider_results = {}
    benchmark_start_time = time.time()

    for p_name in target_providers:
        prof = _OPENAI_COMPAT.get(p_name)
        if not prof:
            print(f"Provider '{p_name}' not defined in _OPENAI_COMPAT. Skipping.")
            continue

        api_key = get_api_key(config, prof["keys"])
        if not api_key:
            print(f"Provider '{p_name}' has no API key configured. Skipping.")
            continue

        model_name = prof.get("model")
        print(f"Benchmarking provider '{p_name}' (model: {model_name})...")

        client = OpenAI(
            api_key=api_key,
            base_url=prof["base_url"],
            timeout=20,
            max_retries=0,
            default_headers=prof.get("headers") or None
        )

        p_data = {
            "model": model_name,
            "voice_pass": 0, "voice_ok": 0,   # voice_ok = voice prompts that got a reply (no error)
            "tool_pass": 0, "tool_ok": 0,     # tool_ok  = tool prompts that got a reply (no error)
            "errors": 0,
            "err_types": {},                  # {rate_daily: n, rate_minute: n, ...}
            "latencies": [],
            "prompts": [],
            "example_voice_reply": ""
        }

        for item in PROMPT_SET:
            prompt_id = item["id"]
            p_text = item["prompt"]
            exp_tool = item["expected_tool"]

            start_t = time.time()
            content = ""
            called_tools = []
            err_msg = None
            err_type = None

            # Up to 3 attempts; a per-MINUTE 429 gets a backoff retry (fair shot), a
            # per-DAY 429 does not (pointless — the budget is gone until tomorrow).
            for attempt in range(3):
                try:
                    res = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": soul},
                            {"role": "user", "content": p_text}
                        ],
                        tools=TOOLS_SCHEMA,
                        tool_choice="auto",
                        temperature=0.7,
                        max_tokens=256
                    )
                    msg = res.choices[0].message
                    content = str(msg.content or "").strip()
                    if msg.tool_calls:
                        called_tools = [t.function.name for t in msg.tool_calls if hasattr(t, "function")]
                    err_msg = None
                    break
                except Exception as e:
                    err_msg = str(e)
                    err_type = classify_error(err_msg)
                    if err_type == "rate_minute" and attempt < 2:
                        print(f"   {prompt_id}: RPM limit, backing off 25s (attempt {attempt+1}/3)...")
                        time.sleep(25)
                        continue
                    break
            duration = time.time() - start_t

            if err_msg:
                p_data["errors"] += 1
                p_data["err_types"][err_type] = p_data["err_types"].get(err_type, 0) + 1
            else:
                # got a real reply → this prompt was fairly assessed
                if item["type"] == "voice":
                    p_data["voice_ok"] += 1
                elif item["type"] == "tool":
                    p_data["tool_ok"] += 1

            passed = score_response(item, content, called_tools, err_msg)
            if passed:
                if item["type"] == "voice":
                    p_data["voice_pass"] += 1
                elif item["type"] == "tool":
                    p_data["tool_pass"] += 1

            p_data["latencies"].append(duration)

            if item["type"] == "voice" and content and not p_data["example_voice_reply"]:
                p_data["example_voice_reply"] = content.replace("\n", " ")

            p_data["prompts"].append({
                "id": prompt_id,
                "type": item["type"],
                "prompt": p_text,
                "expected_tool": exp_tool,
                "content": content,
                "called_tools": called_tools,
                "latency_s": round(duration, 3),
                "passed": passed,
                "error": err_msg,
                "error_type": err_type
            })

            time.sleep(1.5)  # Rate pacing — 0.3s tripped Cerebras' per-minute (RPM) limit

        provider_results[p_name] = p_data

    total_runtime = time.time() - benchmark_start_time

    # Save JSON report to .data/ (gitignored)
    today_str = datetime.now().strftime("%Y%m%d")
    os.makedirs(".data", exist_ok=True)
    report_path = os.path.join(".data", f"persona_benchmark_{today_str}.json")
    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "providers": provider_results,
            "total_runtime_s": round(total_runtime, 2)
        }, rf, indent=2)

    # Output Summary Table.
    # FIDELITY is scored over prompts that were FAIRLY ASSESSED (got a reply), so a
    # rate-limited provider isn't slandered as "bad at being her". AVAILABILITY (how many
    # calls succeeded) is reported SEPARATELY — a provider can be perfect on voice yet
    # useless right now because it's out of budget. The two answer different questions.
    print("\n" + "=" * 96)
    print(f"{'PROVIDER':<11} | {'VOICE':<9} | {'TOOLS':<9} | {'FIDELITY':<9} | {'AVAIL':<8} | {'LAT':<7} | {'NOTES'}")
    print("=" * 96)

    ranked = []  # (fidelity_rate, assessed_count, name) — only providers with enough signal
    for p_name, data in provider_results.items():
        vp, vok = data["voice_pass"], data["voice_ok"]
        tp, tok = data["tool_pass"], data["tool_ok"]
        assessed = vok + tok
        passed = vp + tp
        total = len([i for i in PROMPT_SET])
        avg_lat = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0
        fid = f"{passed}/{assessed}" if assessed else "n/a"
        fid_rate = (passed / assessed) if assessed else -1
        avail = f"{assessed}/{total}"
        notes = ""
        if data["err_types"]:
            notes = ", ".join(f"{k}:{v}" for k, v in data["err_types"].items())
        # a provider counts as rankable only if it fairly assessed a majority of prompts
        if assessed >= (total // 2 + 1):
            ranked.append((fid_rate, assessed, p_name))
        print(f"{p_name:<11} | {vp}/{vok if vok else 0:<7} | {tp}/{tok if tok else 0:<7} | {fid:<9} | {avail:<8} | {avg_lat:.2f}s  | {notes}")

    print("=" * 96)
    if ranked:
        ranked.sort(reverse=True)
        best = ranked[0]
        worst = ranked[-1]
        print(f"\nVERDICT (among providers fairly assessed): BEST = {best[2]} "
              f"({best[0]*100:.0f}% fidelity over {best[1]} prompts); "
              f"WEAKEST = {worst[2]} ({worst[0]*100:.0f}%).")
    else:
        print("\nVERDICT: no provider was fairly assessed (all rate-limited/errored).")
    # call out anyone that couldn't be judged, so the table is never read as a persona verdict
    unassessed = [p for p, d in provider_results.items()
                  if (d["voice_ok"] + d["tool_ok"]) < (len(PROMPT_SET) // 2 + 1)]
    if unassessed:
        print(f"NOT FAIRLY ASSESSED (availability, not persona): {', '.join(unassessed)} "
              f"— rate-limited/unreachable this run; re-run when they have budget.\n")

    print("=== EXAMPLE VOICE REPLIES BY PROVIDER ===")
    for p_name, data in provider_results.items():
        ex = data["example_voice_reply"] or "(No valid voice reply recorded)"
        print(f"- {p_name.upper()}: \"{ex[:140]}\"")

    print(f"\nBenchmark completed in {total_runtime:.2f}s. Detailed report written to {report_path}.\n")


if __name__ == "__main__":
    run_benchmark()
