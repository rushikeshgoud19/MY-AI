"""
Morning briefing — deterministic data collection; the LLM only voices it.

Every collector is fail-safe: a missing DB or dead API skips that section,
it never crashes the briefing. Data sources:
  weather  → weather_news skill (Open-Meteo, no key)
  tasks    → data/schedules.db (one-time due today IST + recurring list)
  email    → cortex.db gmail_messages (important, last 24h)
  whatsapp → cortex.db whatsapp_messages (important/urgent, last 12h)
"""
import os
import sqlite3
import datetime

from .config import log_info, mizune_now, mizune_tz

BRIEFING_TASK_DESC = "MIZUNE_MORNING_BRIEFING"


def _weather() -> str:
    from .skills import skill_manager
    out = skill_manager.execute_skill("weather_news")
    if out and "error" not in str(out).lower()[:40]:
        return f"WEATHER:\n{str(out)[:400]}"
    return ""


def _todays_tasks() -> str:
    if not os.path.exists("data/schedules.db"):
        return ""
    con = sqlite3.connect("data/schedules.db")
    today = mizune_now().date()
    lines = []
    for desc, trig in con.execute(
            "SELECT description, trigger_time FROM one_time_tasks WHERE executed = 0"):
        try:
            dt = datetime.datetime.fromisoformat(trig)
            if dt.tzinfo is None:  # legacy naive rows were UTC
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            dt = dt.astimezone(mizune_tz())
            if dt.date() == today:
                lines.append(f"- {dt.strftime('%I:%M %p')}: {desc[:80]}")
        except Exception:
            continue
    for (desc, cron) in con.execute(
            "SELECT description, cron_expression FROM recurring_tasks"):
        # Never surface HER OWN plumbing to Master — the 8PM digest once told him
        # "a Mizune evening digest is set to recur daily at 8PM" (2026-07-20).
        if not str(desc).upper().startswith("MIZUNE_"):
            lines.append(f"- recurring ({cron}): {desc[:60]}")
    con.close()
    return "TODAY'S SCHEDULED TASKS:\n" + "\n".join(lines) if lines else ""


def _important_emails() -> str:
    if not os.path.exists("cortex.db"):
        return ""
    con = sqlite3.connect("cortex.db")
    since = mizune_now().timestamp() - 24 * 3600
    rows = []
    try:
        # Prefer high-importance; if none, fall back to most-recent so the briefing
        # always has something useful instead of coming up empty.
        rows = list(con.execute(
            "SELECT sender, subject, importance_score FROM gmail_messages "
            "WHERE timestamp > ? AND importance_score >= 5 "
            "ORDER BY importance_score DESC LIMIT 4", (since,)))
        if not rows:
            rows = list(con.execute(
                "SELECT sender, subject, importance_score FROM gmail_messages "
                "ORDER BY timestamp DESC LIMIT 4"))
    except sqlite3.OperationalError:
        rows = []
    con.close()
    if not rows:
        return ""
    lines = [f"- {str(snd)[:40]}: {str(subj)[:70]}" for snd, subj, imp in rows]
    return "RECENT EMAILS:\n" + "\n".join(lines)


def _important_whatsapp() -> str:
    if not os.path.exists("cortex.db"):
        return ""
    con = sqlite3.connect("cortex.db")
    since = mizune_now().timestamp() - 12 * 3600
    try:
        rows = list(con.execute(
            "SELECT sender_name, text, urgency FROM whatsapp_messages "
            "WHERE timestamp > ? AND (urgency >= 3 OR importance_score >= 0.5) "
            "ORDER BY urgency DESC, importance_score DESC LIMIT 3", (since,)))
    except sqlite3.OperationalError:
        rows = []
    con.close()
    if not rows:
        return ""
    lines = [f"- {snd[:30]}: {str(txt)[:80]}" for snd, txt, _u in rows]
    return "IMPORTANT WHATSAPP (12h):\n" + "\n".join(lines)


def _todays_calendar() -> str:
    """Real Google Calendar (live since Phase G) — the briefing's anchor item."""
    from server.integrations.google_api import global_google_api
    out = str(global_google_api.get_todays_calendar())
    # Skip the connection-nag inside a briefing; just stay quiet if not connected.
    if "isn't connected" in out or "expired" in out:
        return ""
    return "CALENDAR:\n" + out


NIGHTLY_TASK_DESC = "MIZUNE_NIGHTLY_REVIEW"
BUGREPORT_TASK_DESC = "MIZUNE_BUG_REPORT"   # 07:45 — lands BEFORE the 8AM briefing

def _last_night_review() -> str:
    db_path = os.path.join(".data", "self_review.db")
    if not os.path.exists(db_path):
        return ""
    try:
        con = sqlite3.connect(db_path)
        row = con.execute("SELECT top_issue, branch_name FROM self_reviews WHERE dispatched = 1 ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        if row:
            top_issue, branch = row
            return f"SELF-REVIEW: {top_issue} — fix drafted on branch {branch}"
    except Exception:
        pass
    return ""

def build_briefing_sitrep() -> str:
    parts = []
    for collector in (_todays_calendar, _weather, _todays_tasks, _important_emails, _important_whatsapp, _last_night_review):
        try:
            part = collector()
            if part:
                parts.append(part)
        except Exception as e:
            log_info(f"[BRIEFING] Collector {collector.__name__} failed: {e}")
    header = f"Good morning report for {mizune_now().strftime('%A, %B %d — %I:%M %p')}"
    return header + ("\n\n" + "\n\n".join(parts) if parts else "\n\n(Quiet day: no data worth flagging.)")


EVENING_TASK_DESC = "MIZUNE_EVENING_DIGEST"
SHIFT_START_DESC = "MIZUNE_SHIFT_START"     # Z2: begin the queued night shift (22:00)
SHIFT_REPORT_DESC = "MIZUNE_SHIFT_REPORT"   # Z2: deliver proof-of-work (07:40)


def _tomorrows_calendar() -> str:
    from server.integrations.google_api import global_google_api
    out = str(global_google_api.get_tomorrows_calendar())
    if "isn't connected" in out or "expired" in out:
        return ""
    return "TOMORROW:\n" + out


def build_evening_sitrep() -> str:
    """8PM digest: tomorrow's plan + still-pending tasks. Deliberately shorter
    and calmer than the morning briefing — a wind-down, not a wake-up."""
    parts = []
    for collector in (_tomorrows_calendar, _todays_tasks):
        try:
            part = collector()
            if part:
                parts.append(part)
        except Exception as e:
            log_info(f"[DIGEST] Collector {collector.__name__} failed: {e}")
    header = f"Evening digest for {mizune_now().strftime('%A, %B %d — %I:%M %p')}"
    return header + ("\n\n" + "\n\n".join(parts) if parts else "\n\n(Nothing pending, clear evening.)")


def ensure_briefing_scheduled(config, cron_manager) -> None:
    """Register the daily briefing, evening digest, and nightly review as recurring tasks exactly once."""
    try:
        if not config.get("briefing_enabled", True):
            return
        jobs = [
            (BRIEFING_TASK_DESC, config.get("briefing_cron", "0 8 * * *")),    # 8:00 AM IST
            (EVENING_TASK_DESC, config.get("digest_cron", "0 20 * * *")),      # 8:00 PM IST
            (NIGHTLY_TASK_DESC, config.get("nightly_cron", "0 2 * * *")),      # 2:00 AM IST
            (BUGREPORT_TASK_DESC, config.get("bugreport_cron", "45 7 * * *")), # 7:45 AM IST
        ]
        # Phase Z2 night shift: only registered if a shift is enabled, so a box that
        # never uses it stays clean. Start 22:00, proof-of-work report 07:40 (before the
        # 07:45 bug report + 08:00 briefing — the night's work leads the morning).
        if config.get("night_shift_enabled", False):
            jobs += [
                (SHIFT_START_DESC, config.get("shift_start_cron", "0 22 * * *")),   # 10:00 PM IST
                (SHIFT_REPORT_DESC, config.get("shift_report_cron", "40 7 * * *")), # 7:40 AM IST
            ]
        con = sqlite3.connect(cron_manager.db_path)
        for desc, cron in jobs:
            exists = list(con.execute(
                "SELECT 1 FROM recurring_tasks WHERE description = ? LIMIT 1", (desc,)))
            if not exists:
                cron_manager.add_recurring_task(desc, cron)
                log_info(f"[BRIEFING] {desc} registered ({cron}).")
        con.close()
    except Exception as e:
        log_info(f"[BRIEFING] Could not register briefing/digest: {e}")
