#!/usr/bin/env python
"""Slash commands must work in BOTH surfaces and must never swallow ordinary chat.

/usage, /insights, /model, /status and /help are wired into process_command, which is the one
door shared by the WebSocket path and inbound WhatsApp. So every case here is run twice: bare,
and inside the real WhatsApp wrapper. A suite once passed 13/13 on bare text while the feature
was broken in production for exactly this reason.

The decoys matter as much as the commands: handle_slash must return None for anything it does
not own, or adding a command here silently eats a normal message.

Read-only. /model with an argument WRITES config, so it is exercised live on the VM instead of
here, where it would repoint this laptop's brain as a side effect of running tests.

    .venv\\Scripts\\python.exe scripts/test_slash_commands.py
"""
import json
import os
import sys

# Windows consoles default to cp1252 and the command replies carry emoji (they are written for
# WhatsApp, where emoji are correct). Same guard smoke_test.py uses: reconfigure rather than
# strip the emoji, so the test prints what production actually sends.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.slash_commands import handle_slash  # noqa: E402

CONFIG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))

WRAP = ("[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {t}\n"
        "(SYSTEM: This is Master Rushi commanding you directly in this chat.)")

# (command, substring that must appear in the reply)
MUST_ANSWER = [
    ("/help", "/usage"),
    ("/commands", "/insights"),
    ("/usage", "USAGE"),
    ("/insights", "INSIGHTS"),
    ("/insights 7", "7 day"),
    ("/model", "Brain"),
    ("/status", "STATUS"),
    ("/health", "STATUS"),
]

# Must return None so the normal path handles them.
MUST_PASS_THROUGH = [
    "play blinding lights",
    "remind me in 20 minutes to eat",
    "what model are you using",
    "send a whatsapp to Owais saying hi",
    "hey how are you",
    "/nonexistentcommand",        # unknown slash -> not ours
    "the file is at /usr/local/bin",
    "run /usr/bin/python for me",
]

fails = []


def check(label, text, want_sub=None, want_none=False):
    try:
        out = handle_slash(text, CONFIG)
    except Exception as e:
        fails.append((label, text, f"RAISED {e}"))
        print(f"**FAIL**  {label:<8} {text[:44]:<46} RAISED {e}")
        return
    if want_none:
        ok = out is None
        detail = "None" if ok else f"SWALLOWED -> {str(out)[:50]}"
    else:
        ok = out is not None and want_sub.lower() in out.lower()
        detail = (str(out).splitlines()[0][:56] if out else "None")
        if out and want_sub.lower() not in out.lower():
            detail = f"missing {want_sub!r} -> {detail}"
    if not ok:
        fails.append((label, text, detail))
    print(f"{'PASS' if ok else '**FAIL**'}  {label:<8} {text[:44]:<46} {detail}")


print("-- COMMANDS ANSWER (bare + wrapped) " + "-" * 32)
for cmd, sub in MUST_ANSWER:
    check("bare", cmd, sub)
    check("wrapped", WRAP.format(t=cmd), sub)

print("\n-- MUST PASS THROUGH (never swallow normal chat) " + "-" * 19)
for t in MUST_PASS_THROUGH:
    check("bare", t, want_none=True)
    check("wrapped", WRAP.format(t=t), want_none=True)

# A report that cannot fail proves nothing: assert the reports carry REAL structure, not just
# a header. /insights must name a source or state that one is missing - never a bare zero.
print("\n-- REPORTS CARRY EVIDENCE " + "-" * 41)
ins = handle_slash("/insights", CONFIG) or ""
has_evidence = ("Messages:" in ins or "Tool calls:" in ins)
states_gaps = ("!" in ins) or ("not found" in ins)
print(f"{'PASS' if has_evidence else '**FAIL**'}  insights reports real counters")
if not has_evidence:
    fails.append(("insights", "/insights", "no counters in output"))
print(f"{'PASS' if (has_evidence or states_gaps) else '**FAIL**'}  insights states missing sources rather than printing bare zeros")

use = handle_slash("/usage", CONFIG) or ""
has_brain = "Brain now:" in use or "provider" in use.lower()
print(f"{'PASS' if has_brain else '**FAIL**'}  usage names the current brain")
if not has_brain:
    fails.append(("usage", "/usage", "no brain named"))

total = len(MUST_ANSWER) * 2 + len(MUST_PASS_THROUGH) * 2 + 3
print(f"\n{total - len(fails)}/{total} checks correct")
if fails:
    print("\nFAILURES:")
    for label, text, detail in fails:
        print(f"  [{label}] {text[:60]}\n      -> {detail}")
sys.exit(1 if fails else 0)
