#!/usr/bin/env python
"""Prove the reminder fast-path fires on real requests and stays QUIET on everything else.

A fast-path that hijacks ordinary conversation is worse than the bug it fixes, so the decoys
here matter more than the positives. Every case is checked in BOTH input shapes: bare text and
the real WhatsApp wrapper from platforms/whatsapp/core.py:670 — a suite once passed 13/13 on
bare text while the feature was broken in production, and the ablation measured a genuine
bare-95% / wrapped-79% gap, so shape is a variable, not a detail.

Parser only. Nothing is scheduled and nothing is sent.

    .venv\\Scripts\\python.exe scripts/test_reminder_fastpath.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.config import mizune_now  # noqa: E402
from server.processor import _parse_reminder_command  # noqa: E402

WRAP = ("[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {t}\n"
        "(SYSTEM: This is Master Rushi commanding you directly in this chat. Acknowledge him "
        "and execute his request. Do not speak about him in the 3rd person.)")

# (text, should_fire, expected_minutes or None, body_must_contain or None)
MUST_FIRE = [
    ("remind me in 20 minutes to check the build", 20, "check the build"),
    ("remind me in 2 hours to eat", 120, "eat"),
    ("remind me to call mom in 45 minutes", 45, "call mom"),
    ("set a reminder for 20 minutes to push the branch", 20, "push the branch"),
    ("remind me in 1 day to renew the domain", 1440, "renew the domain"),
]

# Absolute-clock cases: minutes depend on the current time, so assert a sane window instead
# of a fixed number. Asserting "some positive delay under 24h" is the real invariant.
MUST_FIRE_CLOCK = [
    "remind me to call mom at 8pm",
    "remind me at 8:30 pm to take the tablet",
    "remind me to submit the assignment at 11:45 pm",
    "remind me tomorrow at 9am to email the professor",
    "remind me at 20:00 to stop working",
]

MUST_STAY_QUIET = [
    # No time expressed: she should ASK, not guess.
    "remind me what we did yesterday",
    "remind me why we pinned mistral to the night shift",
    "can you remind me how the fast-path works",
    # Asking ABOUT reminders is not setting one.
    "what reminders do i have",
    "cancel my reminder for 8pm",
    "delete the reminder at 9pm",
    "show me my reminders for tomorrow",
    # Past tense is a statement, not a request.
    "she reminded me at 3am that the build was broken",
    # Not a reminder at all — these belong to other fast-paths or the model.
    "in 5 minutes say good night to Owais",
    "send a whatsapp to Owais saying the build is green",
    "what time is it",
    "mission: verify the calendar works",
]

fails = []


def check(label, text, fire_expected, mins=None, contains=None):
    delay, what = _parse_reminder_command(text)
    fired = bool(delay and what)
    ok = (fired == fire_expected)
    detail = f"delay={delay} what={what!r}"
    if ok and fired:
        if mins is not None and delay != mins:
            ok, detail = False, f"expected {mins}min, got {delay}min"
        # "tomorrow at 9am" asked at 05:40 is legitimately ~27h out (today's 9am is 200min
        # away, plus a day), so the ceiling is two days, not one. The first version of this
        # bound failed a CORRECT parse — the test was wrong, not the code.
        elif mins is None and not (0 < delay <= 2 * 1440 + 60):
            ok, detail = False, f"implausible delay {delay}min"
        if ok and contains and contains.lower() not in (what or "").lower():
            ok, detail = False, f"body {what!r} missing {contains!r}"
        # The body must never still carry the time phrase or the wrapper.
        if ok and re.search(r"\bat\s+\d|\bin\s+\d|SYSTEM:|MESSAGE FROM", what or ""):
            ok, detail = False, f"body not cleaned: {what!r}"
    if not ok:
        fails.append((label, text, detail))
    print(f"{'PASS' if ok else '**FAIL**'}  {label:<9} {text[:58]:<60} {detail[:60]}")


print(f"now = {mizune_now().strftime('%Y-%m-%d %I:%M %p %Z')}\n")

print("-- MUST FIRE (relative) " + "-" * 40)
for text, mins, body in MUST_FIRE:
    check("bare", text, True, mins, body)
    check("wrapped", WRAP.format(t=text), True, mins, body)

print("\n-- MUST FIRE (absolute clock) " + "-" * 34)
for text in MUST_FIRE_CLOCK:
    check("bare", text, True, None, None)
    check("wrapped", WRAP.format(t=text), True, None, None)

print("\n-- MUST STAY QUIET " + "-" * 45)
for text in MUST_STAY_QUIET:
    check("bare", text, False)
    check("wrapped", WRAP.format(t=text), False)

total = (len(MUST_FIRE) + len(MUST_FIRE_CLOCK) + len(MUST_STAY_QUIET)) * 2
print(f"\n{total - len(fails)}/{total} cases correct")
if fails:
    print("\nFAILURES:")
    for label, text, detail in fails:
        print(f"  [{label}] {text[:70]}\n      -> {detail}")
sys.exit(1 if fails else 0)
