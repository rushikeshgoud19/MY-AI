#!/usr/bin/env python3
"""Force the R2.2 text-mode tool recovery path to fire.

WHY THIS EXISTS: the recovery code shipped 2026-07-26 and was deployed, but
`grep -c 'text-mode tool call' server.log` on the VM returned 0 across 57,685 lines
(~12h). The path had never executed in production. That is not a pass and not a fail —
it is UNEXERCISED, and waiting for a weak model to misbehave is not a test.

So: reproduce the exact condition the branch guards (a raw reply that `_clean_final_text`
reduces to empty), and assert the intent is recovered and dispatchable rather than
silently discarded.

    .venv\\Scripts\\python.exe scripts\\test_text_mode_recovery.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.ai import _recover_text_mode_tools, _clean_final_text, TOOLS_SCHEMA
from server.config import load_config

CONFIG = load_config()

# (label, raw model reply, expected tool name or None, expected args subset)
CASES = [
    ("groq shape: tool/data",
     '{"tool": "play_music", "data": {"query": "VIP by Sid"}}',
     "play_music", {"query": "VIP by Sid"}),

    ("tool/args",
     '{"tool": "notify_master", "args": {"message": "build finished"}}',
     "notify_master", {"message": "build finished"}),

    ("name/parameters",
     '{"name": "check_legit", "parameters": {"content": "you won a prize"}}',
     "check_legit", {"content": "you won a prize"}),

    ("action/arguments",
     '{"action": "recall_knowledge", "arguments": {"query": "kaizen"}}',
     "recall_knowledge", {"query": "kaizen"}),

    ("[function=x] shape",
     '[function=night_shift]{"action": "status"}',
     "night_shift", {"action": "status"}),

    ("nested args must not truncate the match",
     '{"tool": "schedule_task", "data": {"task": "ping", "when": {"in_minutes": 5}}}',
     "schedule_task", {"task": "ping"}),

    ("prose wrapper around the JSON",
     'Sure Master! {"tool": "play_music", "data": {"query": "Shakira"}} there you go~',
     "play_music", {"query": "Shakira"}),

    # NEGATIVE CONTROLS — recovery must not invent dispatches.
    ("hallucinated tool name is REJECTED",
     '{"tool": "delete_everything", "data": {"path": "/"}}',
     None, None),

    ("ordinary reply containing braces is NOT a tool call",
     'Use {this} format or {that} one, Master.',
     None, None),

    ("plain chat is NOT a tool call",
     'Good evening, Master! How can I help?',
     None, None),
]


def main():
    known = {t["function"]["name"] for t in TOOLS_SCHEMA
             if isinstance(t, dict) and "function" in t}
    print(f"TOOLS_SCHEMA exposes {len(known)} tools\n")

    failures = 0
    cleaned_to_empty = 0

    for label, raw, want_name, want_args in CASES:
        cleaned = _clean_final_text(raw)
        recovered = _recover_text_mode_tools(raw, CONFIG)

        got_name = recovered[0][0] if recovered else None
        got_args = recovered[0][1] if recovered else None

        ok = (got_name == want_name)
        if ok and want_args:
            ok = all(got_args.get(k) == v for k, v in want_args.items())

        # The branch only runs when cleanup empties the reply. Track that separately:
        # a case that recovers but never cleans to empty would be dead code in practice.
        if want_name and not cleaned.strip():
            cleaned_to_empty += 1

        failures += (not ok)
        print(f"{'ok  ' if ok else 'BAD '} {label}")
        print(f"      raw       : {raw[:72]}")
        print(f"      cleaned   : {cleaned[:60]!r}"
              f"{'   <- empty: branch fires' if not cleaned.strip() else ''}")
        print(f"      recovered : {got_name} {got_args if got_args else ''}")

    print(f"\nrecovery cases that also cleaned to empty: {cleaned_to_empty}"
          f"/{sum(1 for c in CASES if c[2])}")

    # Prove the recovered call is actually DISPATCHABLE, not just parsed. Uses a read-only
    # tool so the test has no side effects.
    print("\n--- dispatch proof (read-only tool) ---")
    raw = '{"tool": "recall_knowledge", "data": {"query": "continuous improvement"}}'
    recovered = _recover_text_mode_tools(raw, CONFIG)
    if not recovered:
        print("BAD  nothing recovered to dispatch")
        failures += 1
    else:
        from server.ai import execute_tool_call
        name, args = recovered[0]
        result = execute_tool_call(name, args, CONFIG)
        text = str(result or "")
        print(f"      dispatched {name}({args})")
        print(f"      result    : {text[:160]!r}")
        if not text.strip():
            print("BAD  dispatch returned nothing")
            failures += 1

    print(f"\nFAILURES = {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
