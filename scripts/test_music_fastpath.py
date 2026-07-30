#!/usr/bin/env python
"""Prove the music fast-path fires on real requests and does NOT hijack anything else.

play_music is the 3rd most-used side-effecting tool in the real seals (16 calls) with no
deterministic pre-LLM fast-path - the same profile that measured schedule_task at 69%.

THE DECOYS ARE THE POINT. The one that matters most is "play the song Sarthak sent me", which
must keep routing through read_whatsapp -> play_music (shipped in dc12642). A greedy music
fast-path would silently search YouTube for the literal words "the song sarthak sent me" and
the feature would break in a way nobody notices until he asks for a song by a friend.

Both input shapes, because the ablation measured bare 95% / wrapped 79% and inbound WhatsApp
is wrapped in production.

Parser only - nothing plays, nothing is sent.

    .venv\\Scripts\\python.exe scripts/test_music_fastpath.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.processor import _parse_music_command  # noqa: E402

WRAP = ("[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {t}\n"
        "(SYSTEM: This is Master Rushi commanding you directly in this chat.)")

# (text, expected_tool, expected_key_fragment or None)
MUST_PLAY = [
    ("play blinding lights", "blinding lights", "phone"),
    ("play VIP by Sid Sriram", "vip by sid sriram", "phone"),
    ("put on some lofi", "lofi", "phone"),
    ("play thunderstruck on my laptop", "thunderstruck", "laptop"),
    ("mizune play the song Kesariya", "kesariya", "phone"),
    ("play arijit singh please", "arijit singh", "phone"),
]

MUST_CONTROL = [
    ("pause the music", "pause"),
    ("pause", "pause"),
    ("stop the song", "pause"),
    ("resume the music", "resume"),
    ("resume", "resume"),
    ("next song", "next"),
    ("skip this", "next"),
    ("skip the track", "next"),
]

MUST_STAY_QUIET = [
    # THE CRITICAL ONE - must defer to read_whatsapp, not search for these literal words.
    "play the song Sarthak sent me",
    "play the song Sarthak sent me on whatsapp",
    "play that link Owais shared",
    "play the song from the message",
    # Not music at all.
    "play chess with me",
    "lets play a game",
    "play it safe with the deploy",
    "play devil's advocate for a second",
    # Substring traps - \bplay\b must not match inside another word.
    "display the results",
    "replay the last mission",
    "the audio player is broken",
    # Ordinary conversation.
    "what's playing right now",
    "the build is playing up again",
]

fails = []


def check(label, text, expect_tool, expect_a=None, expect_b=None):
    tool, args = _parse_music_command(text)
    ok = (tool == expect_tool)
    detail = f"{tool} {args}"
    if ok and tool == "play_music":
        q = (args or {}).get("query", "").lower()
        if expect_a and expect_a not in q:
            ok, detail = False, f"query {q!r} missing {expect_a!r}"
        elif expect_b and (args or {}).get("device") != expect_b:
            ok, detail = False, f"device {(args or {}).get('device')!r} != {expect_b!r}"
        # The wrapper must never leak into the search query.
        elif any(bad in q for bad in ("message from", "system:", "whatsapp)")):
            ok, detail = False, f"wrapper leaked into query: {q!r}"
    elif ok and tool == "control_music":
        if expect_a and (args or {}).get("action") != expect_a:
            ok, detail = False, f"action {(args or {}).get('action')!r} != {expect_a!r}"
    if not ok:
        fails.append((label, text, detail))
    print(f"{'PASS' if ok else '**FAIL**'}  {label:<8} {text[:52]:<54} {detail[:52]}")


print("-- MUST PLAY " + "-" * 52)
for t, q, dev in MUST_PLAY:
    check("bare", t, "play_music", q, dev)
    check("wrapped", WRAP.format(t=t), "play_music", q, dev)

print("\n-- MUST CONTROL " + "-" * 49)
for t, act in MUST_CONTROL:
    check("bare", t, "control_music", act)
    check("wrapped", WRAP.format(t=t), "control_music", act)

print("\n-- MUST STAY QUIET (decoys) " + "-" * 38)
for t in MUST_STAY_QUIET:
    check("bare", t, None)
    check("wrapped", WRAP.format(t=t), None)

total = (len(MUST_PLAY) + len(MUST_CONTROL) + len(MUST_STAY_QUIET)) * 2
print(f"\n{total - len(fails)}/{total} cases correct")
if fails:
    print("\nFAILURES:")
    for label, text, detail in fails:
        print(f"  [{label}] {text[:70]}\n      -> {detail}")
sys.exit(1 if fails else 0)
