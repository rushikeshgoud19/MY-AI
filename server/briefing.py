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
        if desc != BRIEFING_TASK_DESC:
            lines.append(f"- recurring ({cron}): {desc[:60]}")
    con.close()
    return "TODAY'S SCHEDULED TASKS:\n" + "\n".join(lines) if lines else ""


def _important_emails() -> str:
    if not os.path.exists("cortex.db"):
        return ""
    con = sqlite3.connect("cortex.db")
    since = mizune_now().timestamp() - 24 * 3600
    try:
        rows = list(con.execute(
            "SELECT sender, subject, importance_score FROM gmail_messages "
            "WHERE timestamp > ? AND importance_score >= 7 "
            "ORDER BY importance_score DESC LIMIT 3", (since,)))
    except sqlite3.OperationalError:
        rows = []
    con.close()
    if not rows:
        return ""
    lines = [f"- [{imp}/10] {snd[:40]}: {subj[:70]}" for snd, subj, imp in rows]
    return "IMPORTANT EMAILS (24h):\n" + "\n".join(lines)


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


def build_briefing_sitrep() -> str:
    parts = []
    for collector in (_weather, _todays_tasks, _important_emails, _important_whatsapp):
        try:
            part = collector()
            if part:
                parts.append(part)
        except Exception as e:
            log_info(f"[BRIEFING] Collector {collector.__name__} failed: {e}")
    header = f"Good morning report for {mizune_now().strftime('%A, %B %d — %I:%M %p')}"
    return header + ("\n\n" + "\n\n".join(parts) if parts else "\n\n(Quiet day: no data worth flagging.)")


def ensure_briefing_scheduled(config, cron_manager) -> None:
    """Register the daily briefing as a recurring task exactly once."""
    try:
        if not config.get("briefing_enabled", True):
            return
        con = sqlite3.connect(cron_manager.db_path)
        exists = list(con.execute(
            "SELECT 1 FROM recurring_tasks WHERE description = ? LIMIT 1",
            (BRIEFING_TASK_DESC,)))
        con.close()
        if exists:
            return
        cron = config.get("briefing_cron", "0 8 * * *")  # 8:00 AM IST daily
        cron_manager.add_recurring_task(BRIEFING_TASK_DESC, cron)
        log_info(f"[BRIEFING] Morning briefing registered ({cron}).")
    except Exception as e:
        log_info(f"[BRIEFING] Could not register briefing: {e}")
