"""Run one orchestra deliberation and stream it as NDJSON on stdout.

This is what the Agentic OS console drives, so the tribunal on screen is a real
debate happening right now rather than an animation pretending to be one. One
JSON object per line, flushed immediately, so the reader can render each event
as it lands instead of waiting for the whole debate.

Usage:
    python scripts/run_orchestra.py "your question here"

ASCII only on stdout: the Windows console is cp1252 and a stray non-ASCII byte
kills the run mid-debate.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main():
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        emit({"kind": "error", "error": "no question given"})
        return 2

    # Imported late and with stderr noise tolerated: importing the server package
    # pulls in skills/memory and prints a lot, none of which may reach stdout or
    # it would corrupt the NDJSON stream.
    try:
        from server.orchestra import orchestra_answer
    except Exception as e:
        emit({"kind": "error", "error": "import failed: %s: %s" % (type(e).__name__, e)})
        return 1

    try:
        cfg = json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))
    except Exception as e:
        emit({"kind": "error", "error": "config.json unreadable: %s" % e})
        return 1

    emit({"kind": "start", "question": question})
    try:
        res = orchestra_answer(question, cfg, on_event=emit)
    except Exception as e:
        emit({"kind": "error", "error": "%s: %s" % (type(e).__name__, e)})
        return 1
    emit({"kind": "done", "result": {k: v for k, v in res.items() if k != "transcript"}})
    return 0


if __name__ == "__main__":
    # Everything the imported modules print must go to stderr, never stdout.
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        from io import TextIOWrapper
        if hasattr(_real_stdout, "buffer"):
            _real_stdout = TextIOWrapper(_real_stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
    _emit_target = _real_stdout

    def emit(obj, _t=_emit_target):          # noqa: F811  (rebind to the real stdout)
        _t.write(json.dumps(obj, ensure_ascii=True) + "\n")
        _t.flush()

    sys.exit(main())
