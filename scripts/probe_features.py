"""Live feature probe for Mizune — evidence over claims, no local imports.

The repo's own harness (scripts/feature_audit.py) imports the whole stack — torch,
ChromaDB, Faster-Whisper — before it checks anything, which takes minutes on a laptop and
never reaches a probe. This talks to the running VM over the same socket the phone uses.

Rule inherited from FEATURE_MATRIX.md: a feature PASSES only when evidence proves it.
Mizune saying it worked is never evidence. Where a claim can be checked against a frame
type, a tool actually executing, or an HTTP body, that is what is scored.

ASCII-only output: the Windows console is cp1252.
"""
import json
import sys
import time
import urllib.request

import websocket

WS = "ws://40.123.215.32:8001/ws"
HTTP = "http://40.123.215.32:8001"


def key():
    try:
        with open("config.json", encoding="utf-8") as fh:
            return str(json.load(fh).get("dashboard_api_key", "")).strip()
    except Exception:
        return ""


def a(s):
    return str(s).encode("ascii", "replace").decode("ascii")


def ask(question, want_types=("speak",), timeout=150):
    """Send one turn; return (text, frame_types_seen, seconds)."""
    k = key()
    ws = websocket.create_connection(WS + (("?key=" + k) if k else ""), timeout=20)
    ws.settimeout(timeout)
    t0 = time.time()
    chunks, seen = [], set()
    try:
        while time.time() - t0 < timeout:
            raw = ws.recv()
            try:
                d = json.loads(raw)
            except Exception:
                continue
            t = d.get("type")
            seen.add(t)
            if t == "hello":
                ws.send(json.dumps({"type": "chat", "text": question}))
                continue
            if t == "speak":
                chunks.append(d.get("text") or "")
            if t == "status" and (d.get("text") or "").lower().startswith("idle"):
                break
    except Exception:
        pass
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return "\n".join(chunks), seen, time.time() - t0


RESULTS = []


def score(name, verdict, evidence):
    RESULTS.append((name, verdict, evidence))
    print("%-22s %-6s %s" % (name, verdict, a(evidence)[:110]))
    sys.stdout.flush()


def http(path):
    try:
        with urllib.request.urlopen(HTTP + path, timeout=15) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except Exception as e:
        return 0, "%s: %s" % (type(e).__name__, e)


def main():
    # 1. health
    st, body = http("/health")
    score("health", "PASS" if st == 200 else "FAIL", "HTTP %s %s" % (st, body[:60]))

    # 2. device registry - real endpoint, not her prose
    st, body = http("/api/devices")
    score("device_nodes", "PASS" if st == 200 else "FAIL", "HTTP %s %s" % (st, body[:80]))

    # 3. persona + basic chat
    txt, seen, secs = ask("Say hello in one short sentence.", timeout=90)
    score("chat_persona", "PASS" if txt.strip() else "FAIL",
          "%.0fs, %d chars, frames=%s" % (secs, len(txt), sorted(x for x in seen if x)))

    # 4. TTS - the audio frame must actually arrive
    score("tts_audio", "PASS" if "audio" in seen else "FAIL",
          "audio frame %s in same turn" % ("present" if "audio" in seen else "ABSENT"))

    # 5. turn ownership stamp (this session's work)
    score("turn_origin", "PASS" if "hello" in seen else "FAIL",
          "hello/client_id frame %s" % ("present" if "hello" in seen else "ABSENT"))

    # 6. web_search - the Autter failure. Evidence = a fact she cannot know without it.
    txt, seen, secs = ask(
        "Search the web and tell me, in one line, what the company Autter does.", timeout=170)
    hit = any(w in txt.lower() for w in ("code review", "pull request", "release", "ci",
                                         "pipeline", "software"))
    score("web_search", "PASS" if hit else "FAIL",
          "%.0fs: %s" % (secs, txt.strip()[:90] or "(no reply)"))

    # 7. memory - store then recall in a separate turn
    marker = "AUDIT%d" % int(time.time() % 100000)
    ask("Remember this exactly: my audit marker is %s. Just confirm." % marker, timeout=90)
    time.sleep(3)
    txt, _, secs = ask("What is my audit marker? Reply with just the code.", timeout=120)
    score("memory_recall", "PASS" if marker in txt.upper() else "FAIL",
          "%.0fs: stored %s, recalled %r" % (secs, marker, txt.strip()[:60]))

    # 8. orchestra - explicit trigger, must show a receipt
    txt, _, secs = ask(
        "orchestra: Is SQLite or Postgres better for a two-person startup? Pick one.",
        timeout=200)
    score("orchestra", "PASS" if "Alucard" in txt else "FAIL",
          "%.0fs: %s" % (secs, txt.strip()[-90:] or "(no reply)"))

    print()
    p = sum(1 for _, v, _ in RESULTS if v == "PASS")
    print("%d PASS / %d checks" % (p, len(RESULTS)))
    bad = [n for n, v, _ in RESULTS if v != "PASS"]
    if bad:
        print("NOT PASSING:", ", ".join(bad))


if __name__ == "__main__":
    main()
