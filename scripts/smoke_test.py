"""Mizune deploy smoke test — the "never worse" gate.

Run BEFORE and AFTER every VM deploy:
    .venv/Scripts/python.exe scripts/smoke_test.py                 # tests the VM
    .venv/Scripts/python.exe scripts/smoke_test.py ws://localhost:8001/ws   # tests local

Checks: health endpoint, chat reply arrives, real TTS audio arrives,
calendar tool answers. Exit code 0 = safe to call the deploy good.
"""
import asyncio
import json
import sys
import urllib.request

# Windows consoles default to charmap — her replies contain emoji.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import websockets

try:
    import os
    from server.config import load_config
    _cfg = load_config()
    _key = (_cfg.get("dashboard_api_key") or "").strip()
except Exception:
    _key = ""

WS_URI = sys.argv[1] if len(sys.argv) > 1 else "ws://40.123.215.32:8001/ws"
if _key and "?key=" not in WS_URI:
    WS_URI = f"{WS_URI}?key={_key}" if "?" not in WS_URI else f"{WS_URI}&key={_key}"

HTTP_BASE = WS_URI.replace("ws://", "http://").replace("wss://", "https://").split("?")[0].rsplit("/ws", 1)[0]

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


async def ws_ask(query, timeout=60):
    """Send a chat message, collect speak/audio replies until idle or timeout."""
    speaks, got_audio = [], False
    async with websockets.connect(WS_URI, open_timeout=15) as ws:
        await ws.send(json.dumps({"type": "chat", "text": query}))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
            except asyncio.TimeoutError:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            t = msg.get("type")
            if t == "speak" and msg.get("text"):
                speaks.append(msg["text"])
            elif t == "audio" and msg.get("b64"):
                got_audio = True
            elif t == "status" and msg.get("text") == "Idle" and speaks:
                break
    return speaks, got_audio


async def main():
    # 1. health
    try:
        with urllib.request.urlopen(HTTP_BASE + "/health", timeout=10) as r:
            check("health endpoint", r.status == 200, HTTP_BASE + "/health")
    except Exception as e:
        check("health endpoint", False, str(e))

    # 2. chat reply + 3. real voice audio
    try:
        speaks, got_audio = await ws_ask("hey, quick status check — say ok")
        check("chat reply arrives", bool(speaks), (speaks[0][:80] if speaks else "no speak received"))
        check("TTS audio arrives", got_audio)
    except Exception as e:
        check("chat reply arrives", False, str(e))
        check("TTS audio arrives", False)

    # 4. calendar tool (Google connection)
    try:
        # SCORED BOTH DIRECTIONS. The old check passed unless the reply contained one of four
        # exact phrases, so it went GREEN on a completely dead calendar: on 2026-08-01 the VM's
        # tokens/token.json was MISSING and this still passed on "Fufufu." and on "Please
        # reconnect it so I can see your calendar" — neither of which contains those phrases.
        # It only failed when the model happened to pick the word "sorry". A deploy gate whose
        # verdict depends on which synonym an LLM chose is a coin flip, and rule 10 leans on it.
        # So: fail on ANY auth/connection language, AND require positive evidence that a
        # calendar was actually read. Absence of a complaint is not evidence of success.
        speaks, _ = await ws_ask("what's on my google calendar today")
        joined = " ".join(speaks).lower()
        bad_words = ("isn't connected", "not connected", "session expired", "sorry",
                     "reconnect", "re-connect", "connect your", "authorize", "authorise",
                     "sign in", "log in", "no access", "can't see your calendar",
                     "cannot see your calendar", "unable to access", "not authenticated",
                     "expired")
        bad = any(w in joined for w in bad_words)
        # Positive evidence: a real time, a real date, or an explicit empty-calendar answer
        # that only a successful API read produces.
        import re as _re
        good = bool(_re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)?", joined)) or any(
            w in joined for w in ("no events", "nothing scheduled", "nothing on your calendar",
                                  "your calendar is clear", "no meetings", "calendar is empty",
                                  "free today", "no appointments"))
        detail = (speaks[-1][:80] if speaks else "no reply")
        if bad:
            detail = "AUTH/CONNECTION problem in reply -> " + detail
        elif not good:
            detail = "no positive calendar evidence (no time, no 'no events') -> " + detail
        check("calendar answers", bool(speaks) and not bad and good, detail)
    except Exception as e:
        check("calendar answers", False, str(e))

    failed = [n for n, ok, _ in RESULTS if not ok]
    print()
    if failed:
        print(f"SMOKE FAILED ({len(failed)}/{len(RESULTS)}): {', '.join(failed)}")
        sys.exit(1)
    print(f"SMOKE PASSED ({len(RESULTS)}/{len(RESULTS)}) — safe to call this deploy good.")


asyncio.run(main())
