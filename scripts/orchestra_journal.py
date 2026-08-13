"""Decision journal over the orchestra's debate store.

The debates table already records what was asked, what was decided, how much the
panel agreed and what it cost. That is a log. What makes it a JOURNAL is being
able to come back months later and ask "what did we decide about X, did the panel
actually agree, and did I follow it?" - so this adds search, full recall, and an
outcome you can write back.

Invoked as a CLI by the Agentic OS dashboard, which has zero npm dependencies and
therefore no sqlite driver of its own. One JSON object on stdout, always.

    python scripts/orchestra_journal.py list  [query] [limit] [outcome]
    python scripts/orchestra_journal.py get   <id>
    python scripts/orchestra_journal.py mark  <id> <followed|rejected|pending|superseded> [note]

ASCII-safe: output is json.dumps(ensure_ascii=True) so a verdict containing an
emoji cannot kill the pipe on a cp1252 console.
"""
import json
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, ".data", "orchestra.db")

OUTCOMES = ("pending", "followed", "rejected", "superseded")


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True))
    sys.stdout.flush()


def connect():
    if not os.path.exists(DB):
        return None
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    # Added lazily so an existing store upgrades in place rather than needing a
    # migration step nobody will remember to run.
    cols = {r["name"] for r in con.execute("PRAGMA table_info(debates)")}
    if "outcome" not in cols:
        con.execute("ALTER TABLE debates ADD COLUMN outcome TEXT DEFAULT 'pending'")
    if "note" not in cols:
        con.execute("ALTER TABLE debates ADD COLUMN note TEXT DEFAULT ''")
    con.commit()
    return con


def row_summary(r):
    d = dict(r)
    d["outcome"] = d.get("outcome") or "pending"
    d["note"] = d.get("note") or ""
    return d


def cmd_list(query, limit, outcome=""):
    con = connect()
    if not con:
        return out({"debates": [], "total": 0, "note": "no debates yet"})
    sql = ("SELECT id,started,finished,question,verdict,agreement,rounds,calls,tokens,"
           "case_taken,judge,outcome,note FROM debates")
    where, args = [], []
    if query:
        where.append("(question LIKE ? OR verdict LIKE ? OR note LIKE ?)")
        args += ["%" + query + "%"] * 3
    # Filtering happens HERE, in SQL, not in the browser. Client-side filtering only
    # narrowed the rows already fetched, so a decision marked "followed" that sat
    # outside the first page simply vanished - a filter that searches only what is
    # already on screen is worse than no filter, because it looks like an answer.
    if outcome:
        where.append("COALESCE(outcome,'pending') = ?")
        args.append(outcome)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(200, limit)))
    rows = [row_summary(r) for r in con.execute(sql, args)]
    total = con.execute("SELECT COUNT(*) FROM debates").fetchone()[0]
    by_outcome = dict(con.execute(
        "SELECT COALESCE(outcome,'pending'), COUNT(*) FROM debates GROUP BY 1"))
    out({"debates": rows, "total": total, "matched": len(rows), "by_outcome": by_outcome})


def cmd_get(did):
    con = connect()
    if not con:
        return out({"error": "no debate store"})
    r = con.execute("SELECT * FROM debates WHERE id=?", (did,)).fetchone()
    if not r:
        return out({"error": "no debate with id %s" % did})
    d = row_summary(r)
    # The transcript is the interesting part on recall - every advocate's argument,
    # the judge's scores, and the specific defect he named in each.
    try:
        events = json.loads(d.get("transcript") or "[]")
    except Exception:
        events = []
    d.pop("transcript", None)
    d["answers"] = [e for e in events if e.get("kind") in ("answer", "revision")]
    d["scores"] = next((e for e in events if e.get("kind") == "scores"), None)
    d["critique"] = next((e for e in events if e.get("kind") == "critique"), None)
    d["grounding"] = next((e for e in events if e.get("kind") == "grounding"), None)
    d["triage"] = next((e for e in events if e.get("kind") == "triage"), None)
    out(d)


def cmd_mark(did, outcome, note):
    if outcome not in OUTCOMES:
        return out({"error": "outcome must be one of %s" % (OUTCOMES,)})
    con = connect()
    if not con:
        return out({"error": "no debate store"})
    cur = con.execute("UPDATE debates SET outcome=?, note=? WHERE id=?",
                      (outcome, note or "", did))
    con.commit()
    if not cur.rowcount:
        return out({"error": "no debate with id %s" % did})
    out({"ok": True, "id": did, "outcome": outcome, "note": note or ""})


def main():
    if len(sys.argv) < 2:
        return out({"error": "usage: list|get|mark"})
    cmd = sys.argv[1]
    try:
        if cmd == "list":
            q = sys.argv[2] if len(sys.argv) > 2 else ""
            n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            oc = sys.argv[4] if len(sys.argv) > 4 else ""
            return cmd_list(q, n, oc)
        if cmd == "get":
            return cmd_get(int(sys.argv[2]))
        if cmd == "mark":
            return cmd_mark(int(sys.argv[2]), sys.argv[3],
                            " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "")
        out({"error": "unknown command %r" % cmd})
    except Exception as e:
        out({"error": "%s: %s" % (type(e).__name__, e)})


if __name__ == "__main__":
    main()
