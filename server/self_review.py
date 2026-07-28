"""
Nightly Self-Review (Phase Q.1) — Mizune reads her OWN logs at 2AM IST while Master
sleeps ("dreaming"), aggregates her worst recurring failures, and REPORTS them:
  • stored in .data/self_review.db  → shown in the dashboard's Dreaming section
  • WhatsApp bug report at 7:45 AM  → lands BEFORE the 8AM briefing
She never edits code. Rushi reads the findings and fixes them himself (his call
2026-07-23: auto-dispatching Claude Code burned his quota, and he wants to own the fix).
Pure log analysis — no LLM call, no tokens, no quota.
"""
import os
import re
import sqlite3

from .config import log_info, mizune_now

DB_PATH = os.path.join(".data", "self_review.db")


def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS self_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        top_issue TEXT,
        report TEXT,
        dispatched INTEGER,
        branch_name TEXT,
        created_at TEXT
    )""")
    return con


def collect_failures(log_path="/home/azureuser/server.log") -> list:
    """Scan server.log for error signatures and aggregate recurring failure messages."""
    if not os.path.exists(log_path):
        log_path = os.path.join(".data", "server.log")
        if not os.path.exists(log_path):
            return []

    failures = {}
    signatures = [
        r"Provider '([^']+)' failed",
        r"\[GUARD\] blocked:?\s*(.*)",
        r"Error executing\s*(.*)",
        r"Traceback \(most recent call last\):?\s*(.*)",
        r"\[TOOL RESULTS\].*?(FAILED|ERROR).*",
        r"failed:\s*(.*)",
    ]

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-3000:]

        for line in lines:
            line_str = line.strip()
            for sig in signatures:
                m = re.search(sig, line_str, re.IGNORECASE)
                if m:
                    raw_msg = m.group(0)
                    norm = re.sub(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", "", raw_msg)
                    norm = re.sub(r"0x[0-9a-fA-F]+", "", norm)
                    norm = re.sub(r"\d+", "N", norm).strip()
                    if norm not in failures:
                        failures[norm] = {"count": 0, "example": line_str[:200]}
                    failures[norm]["count"] += 1
                    break
    except Exception as e:
        log_info(f"[SELF_REVIEW] Error collecting log failures: {e}")

    return sorted(failures.items(), key=lambda x: x[1]["count"], reverse=True)


def build_report(force=False):
    """Top-3 failure summary. None when the night was quiet (she stays silent)."""
    failures = collect_failures()
    if not failures and not force:
        return None

    top_issues = failures[:3]
    total_count = sum(f[1]["count"] for f in failures)
    if not force and (total_count < 3 or (top_issues and top_issues[0][1]["count"] < 2)):
        log_info(f"[SELF_REVIEW] Total error count {total_count} below threshold — quiet night.")
        return None

    top_name = top_issues[0][0] if top_issues else "Minor rate limits / transient timeouts"
    report_lines = [
        f"- {norm} (occurred {data['count']} times)\n  Example: {data['example']}"
        for norm, data in top_issues
    ]
    return {
        "top_issue": top_name,
        "total_count": total_count,
        "summary": "\n".join(report_lines) if report_lines else "No major errors found.",
    }


def run_nightly(config: dict, force: bool = False) -> str:
    """2AM: analyse the day's failures and STORE them. No code changes, no dispatch,
    no LLM, no quota. Delivery happens at 7:45 via send_bug_report()."""
    log_info("[SELF_REVIEW] Dreaming — reviewing today's failures...")
    report = build_report(force=force)
    today_str = mizune_now().strftime("%Y%m%d")
    con = _db()

    if not report:
        log_info("[SELF_REVIEW] Quiet night — nothing worth reporting.")
        con.execute(
            "INSERT INTO self_reviews (date, top_issue, report, dispatched, branch_name, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (today_str, "None", "Quiet night — no recurring errors.", 0, "", mizune_now().isoformat()))
        con.commit()
        con.close()
        return "Quiet night, Master — nothing broke worth mentioning."

    con.execute(
        "INSERT INTO self_reviews (date, top_issue, report, dispatched, branch_name, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (today_str, report["top_issue"], report["summary"], 0, "", mizune_now().isoformat()))
    con.commit()
    con.close()
    log_info(f"[SELF_REVIEW] Logged {report['total_count']} failures. Top: {report['top_issue'][:70]}")
    return f"Self-review done: {report['top_issue'][:60]}"


def latest_findings(limit: int = 1) -> list:
    """Most recent stored reviews, parsed into items — feeds the dashboard Dreaming tab."""
    try:
        con = _db()
        rows = con.execute(
            "SELECT date, top_issue, report, created_at FROM self_reviews"
            " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        con.close()
        out = []
        for date, top, rep, created in rows:
            items = []
            for block in str(rep).split("\n-"):
                block = block.strip().lstrip("-").strip()
                if not block or block.lower().startswith("quiet night"):
                    continue
                head, _, ex = block.partition("Example:")
                m = re.search(r"\(occurred (\d+) times\)", head)
                items.append({
                    "title": re.sub(r"\s*\(occurred \d+ times\)", "", head).strip()[:120],
                    "count": int(m.group(1)) if m else 1,
                    "example": ex.strip()[:220],
                })
            out.append({"date": date, "top_issue": top, "created_at": created, "items": items})
        return out
    except Exception as e:
        log_info(f"[SELF_REVIEW] latest_findings failed: {e}")
        return []


def send_bug_report(config: dict) -> str:
    """07:45 — WhatsApp Master the night's findings, BEFORE the 8AM briefing.
    CODE delivers, never the LLM — the rule that stopped briefings silently vanishing."""
    found = latest_findings(1)
    if not found or not found[0]["items"] or found[0]["top_issue"] == "None":
        log_info("[SELF_REVIEW] Nothing to report this morning.")
        return "nothing to report"

    f = found[0]
    lines = [f"🐛 Nightly bug report — {len(f['items'])} issue(s) found while you slept:", ""]
    for i, it in enumerate(f["items"], 1):
        lines.append(f"{i}. {it['title']}  ({it['count']}x)")
        if it["example"]:
            lines.append(f"   {it['example'][:150]}")
    lines.append("")
    lines.append("Full details in the Dreaming tab, Master. I didn't touch the code — that's your call. 💙")
    text = "\n".join(lines)

    try:
        from .commands import whatsapp_automation
        sent = str(whatsapp_automation("Master", text))
        log_info(f"[SELF_REVIEW] Bug report delivery: {sent[:100]}")
    except Exception as e:
        log_info(f"[SELF_REVIEW] Bug report delivery failed: {e}")
        return f"delivery failed: {e}"

    try:
        from .websocket import ws_manager
        ws_manager.broadcast_sync({"type": "speak", "text": text, "emotion": "neutral"})
    except Exception:
        pass
    return "sent"
