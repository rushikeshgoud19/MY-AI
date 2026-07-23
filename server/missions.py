"""Mission engine (Phase H2) — missions, not commands.

A mission = a goal decomposed into steps, each with an OBJECTIVELY CHECKABLE
verification. Steps execute through the normal tool-calling brain; after each
action the verify clause runs and must yield VERDICT: PASS — a step is not done
because she SAYS so, but because she PROVED it (H2.2 verify-after-act).

Missions persist in .data/missions.db, survive restarts (resume_active_missions
is called at boot), execute sequentially in a daemon thread, and report
milestones to Master on WhatsApp + the live websocket.
"""
import json
import os
import re
import sqlite3
import threading
import time

from .config import log_info, mizune_now

DB_PATH = os.path.join(".data", "missions.db")
MAX_STEPS = 6
_run_lock = threading.Lock()          # one mission executes at a time


# ── storage ──────────────────────────────────────────────────────────────────

def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY, goal TEXT, origin TEXT, status TEXT,
        created_at TEXT, updated_at TEXT, report TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS mission_steps (
        id INTEGER PRIMARY KEY, mission_id INTEGER, idx INTEGER,
        action TEXT, verify TEXT, status TEXT, result TEXT, verdict TEXT)""")
    return con


def _touch(con, mission_id, **fields):
    sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    con.execute(f"UPDATE missions SET {sets} WHERE id=?",
                (*fields.values(), mizune_now().isoformat(), mission_id))
    con.commit()


# ── planning (LLM, NO tools — the _bg_guard enforces that for override calls) ─

_PLAN_PROMPT = """You are a mission planner for Mizune, a personal AI with these abilities:
- Google Calendar: create/read/cancel events
- Gmail: read recent/important emails
- Live web: web_search, read_webpage
- WhatsApp: send messages to Master or his contacts
- Phone: open apps/URLs, tap/type/read the screen, play/control music
- Laptop: run shell commands, background tasks (run_task), delegate coding to Claude (claude_task)
- Scheduling: reminders and future tasks

Decompose the GOAL into 2-{max_steps} sequential steps. If the GOAL states BOUNDARIES /
constraints (things NOT to do, or a scope limit), respect them in every step.
Each step needs:
- an ACTION: one imperative instruction executable with the abilities above
- a VERIFY: an OBJECTIVELY CHECKABLE condition proving the step worked, checkable with the same abilities (e.g. "the calendar shows an event called X tomorrow", "the file C:\\...\\y.txt exists on the laptop")

Reply with ONLY lines in this exact format, one line per step, nothing else
(NO JSON — the reply pipeline strips JSON):
STEP: <action> || VERIFY: <condition>

GOAL: {goal}"""


# OPTS — optional per-mission execution options. None (the default) means the exact
# behaviour missions have always had. Night shifts (Z2) pass:
#   {"hints": {"force_provider": "mistral"},   # pin the fuel tank, cascade still backs it
#    "silent": True,                           # no 3AM WhatsApp pings — see _report
#    "sink": callable(str)}                    # milestones go here instead
def _hints(opts):
    return (opts or {}).get("hints")


def _plan(goal: str, config: dict, opts: dict = None):
    from .ai import get_ai_response
    raw, _ = get_ai_response(
        _PLAN_PROMPT.format(goal=goal, max_steps=MAX_STEPS), [], config,
        system_prompt_override="You are a precise mission planner. Output only STEP/VERIFY lines in the requested format.",
        hints=_hints(opts))
    pairs = re.findall(r"STEP:\s*(.+?)\s*\|\|\s*VERIFY:\s*(.+)", str(raw))
    steps = [{"action": a.strip(), "verify": v.strip()}
             for a, v in pairs if a.strip() and v.strip()][:MAX_STEPS]
    if not steps:
        log_info(f"[MISSION] plan parse failed; raw was: {str(raw)[:200]}")
    return steps or None


# ── execution ────────────────────────────────────────────────────────────────

def _report(text: str, opts: dict = None):
    """Milestone report → live websocket + WhatsApp (loop-safe ✨ prefix).

    SILENT mode (night shifts): a 6-step mission at 03:00 would fire 6 WhatsApp
    messages while Master sleeps — the fastest way to get muted forever (Design Law 5,
    quiet by default). Silent milestones go to the shift's sink and are retold ONCE in
    the 07:40 proof-of-work report."""
    if (opts or {}).get("silent"):
        log_info(f"[MISSION silent] {text[:160]}")
        try:
            sink = (opts or {}).get("sink")
            if sink:
                sink(text)
        except Exception as e:
            log_info(f"[MISSION] milestone sink failed: {e}")
        return
    try:
        from .websocket import ws_manager
        ws_manager.broadcast_sync({"type": "speak", "text": text, "emotion": "neutral"})
    except Exception:
        pass
    try:
        # send_message() already prepends the "✨ Mizune" header — don't double it.
        from .commands import whatsapp_automation
        whatsapp_automation("Master", text)
    except Exception as e:
        log_info(f"[MISSION] WhatsApp report failed: {e}")


def _brain(text: str, config: dict, opts: dict = None) -> str:
    from .ai import get_ai_response
    res, _ = get_ai_response(text, [], config, hints=_hints(opts))
    return str(res or "").strip()


def _verify(verify_clause: str, config: dict, opts: dict = None) -> tuple:
    """Two-stage verify-after-act. Stage 1 gathers CURRENT facts with tools (its
    output may be a raw fast-tracked tool result). Stage 2 is a no-tools judgment
    call that rules PASS/FAIL from that evidence. Returns (passed, detail)."""
    from .ai import get_ai_response
    evidence = _brain(
        f"[MISSION VERIFY] Use your tools to gather the CURRENT facts needed to check "
        f"this condition, and report just the facts: {verify_clause}", config, opts)
    judge, _ = get_ai_response(
        f"Condition to verify: {verify_clause}\n\nEvidence gathered just now:\n{evidence[:800]}\n\n"
        f"Does the evidence prove the condition is true RIGHT NOW? Reply with exactly "
        f"'VERDICT: PASS' or 'VERDICT: FAIL' plus one short reason.",
        [], config,
        system_prompt_override="You are a strict verifier. Output only the verdict line.",
        hints=_hints(opts))
    judge = str(judge or "")
    passed = "PASS" in judge[:60].upper()
    return (passed, f"{judge[:120]} | evidence: {evidence[:160]}")


def _execute_mission(mission_id: int, config: dict, opts: dict = None):
    with _run_lock:
        con = _db()
        row = con.execute("SELECT goal FROM missions WHERE id=?", (mission_id,)).fetchone()
        if not row:
            con.close()
            return
        goal = row[0]
        steps = con.execute(
            "SELECT id, idx, action, verify, status FROM mission_steps "
            "WHERE mission_id=? ORDER BY idx", (mission_id,)).fetchall()

        for sid, idx, action, verify, status in steps:
            if status == "done":
                continue                      # resume: skip already-verified steps
            # WAIT_UNTIL <iso> steps just sleep (checkpointed, restart-safe)
            wait = re.match(r"WAIT_UNTIL\s+(\S+)", action)
            if wait:
                try:
                    import datetime
                    target = datetime.datetime.fromisoformat(wait.group(1))
                    while mizune_now() < target:
                        time.sleep(min(60, max(1, (target - mizune_now()).total_seconds())))
                except Exception:
                    pass
                con.execute("UPDATE mission_steps SET status='done', verdict='(wait elapsed)' WHERE id=?", (sid,))
                con.commit()
                continue

            con.execute("UPDATE mission_steps SET status='running' WHERE id=?", (sid,))
            con.commit()
            log_info(f"[MISSION {mission_id}] step {idx + 1}: {action[:80]}")

            result = _brain(
                f"[MISSION STEP {idx + 1}] Execute exactly this, using your tools, and state "
                f"honestly what happened: {action}", config, opts)
            passed, evidence = _verify(verify, config, opts)

            if not passed:                    # H2.3-lite: ONE informed retry
                log_info(f"[MISSION {mission_id}] step {idx + 1} verify FAILED — retrying once")
                result = _brain(
                    f"[MISSION STEP {idx + 1} — RETRY] The previous attempt did not verify "
                    f"({evidence[:120]}). Try a DIFFERENT way to: {action}", config, opts)
                passed, evidence = _verify(verify, config, opts)

            con.execute("UPDATE mission_steps SET status=?, result=?, verdict=? WHERE id=?",
                        ("done" if passed else "failed", result[:400], evidence, sid))
            con.commit()

            if not passed:
                _touch(con, mission_id, status="failed",
                       report=f"Step {idx + 1} could not be verified: {evidence[:150]}")
                _report(f"Master, mission '{goal[:60]}' hit a wall at step {idx + 1} "
                        f"({action[:60]}). Verification says: {evidence[:120]}", opts)
                con.close()
                return
            _report(f"Mission '{goal[:50]}': step {idx + 1}/{len(steps)} done ✓ (verified: {evidence[:90]})", opts)

        _touch(con, mission_id, status="done", report="all steps verified")
        _report(f"Mission COMPLETE, Master: '{goal[:70]}' — every step verified. ✅", opts)
        con.close()


# ── public API (called from the tool executor) ───────────────────────────────

def start_mission(goal: str, origin: str, config: dict,
                  opts: dict = None, run_async: bool = True) -> str:
    """opts/run_async default to None/True = the original behaviour, unchanged.
    Night shifts pass run_async=False so the shift worker can run its queue strictly
    sequentially and know when each mission actually finished."""
    goal = (goal or "").strip()
    if not goal:
        return "Error: the mission needs a goal, Master."
    con = _db()
    active = con.execute("SELECT COUNT(*) FROM missions WHERE status='active'").fetchone()[0]
    # The shift bypasses the cap: it is already serialised by _run_lock and runs exactly
    # one mission at a time, so it can't be the thing that overwhelms her.
    if active >= 3 and not (opts or {}).get("bypass_cap"):
        con.close()
        return "I already have 3 active missions, Master — finish or cancel one first."
    steps = _plan(goal, config, opts)
    if not steps:
        con.close()
        return "I couldn't build a concrete verifiable plan for that, Master — can you rephrase the goal?"
    now = mizune_now().isoformat()
    cur = con.execute(
        "INSERT INTO missions (goal, origin, status, created_at, updated_at, report) "
        "VALUES (?, ?, 'active', ?, ?, '')", (goal, origin, now, now))
    mid = cur.lastrowid
    for i, s in enumerate(steps):
        con.execute(
            "INSERT INTO mission_steps (mission_id, idx, action, verify, status, result, verdict) "
            "VALUES (?, ?, ?, ?, 'pending', '', '')", (mid, i, s["action"], s["verify"]))
    con.commit()
    con.close()
    if run_async:
        threading.Thread(target=_execute_mission, args=(mid, config, opts), daemon=True).start()
    else:
        _execute_mission(mid, config, opts)      # blocks: the shift worker owns the thread
    plan_txt = "; ".join(f"{i + 1}) {s['action'][:60]}" for i, s in enumerate(steps))
    return (f"Mission #{mid} accepted, Master: {len(steps)} steps — {plan_txt}. "
            f"I'll verify each step and report as I go.")


def mission_outcome(mission_id: int) -> dict:
    """Ground truth for a mission, read from the DB — never from what she SAID.
    Used by the night-shift proof-of-work report (Rule 8: verify, don't trust)."""
    con = _db()
    row = con.execute("SELECT goal, status, report FROM missions WHERE id=?",
                      (mission_id,)).fetchone()
    steps = con.execute(
        "SELECT idx, action, status, verdict FROM mission_steps WHERE mission_id=? ORDER BY idx",
        (mission_id,)).fetchall()
    con.close()
    if not row:
        return {"found": False}
    return {
        "found": True, "goal": row[0], "status": row[1], "report": row[2],
        "steps": [{"idx": s[0], "action": s[1], "status": s[2], "verdict": s[3]} for s in steps],
        "verified": sum(1 for s in steps if s[2] == "done"),
        "total": len(steps),
    }


def mission_status(config: dict = None) -> str:
    con = _db()
    rows = con.execute(
        "SELECT id, goal, status FROM missions ORDER BY id DESC LIMIT 5").fetchall()
    if not rows:
        con.close()
        return "No missions yet, Master."
    lines = []
    for mid, goal, status in rows:
        done = con.execute(
            "SELECT COUNT(*) FROM mission_steps WHERE mission_id=? AND status='done'", (mid,)).fetchone()[0]
        total = con.execute(
            "SELECT COUNT(*) FROM mission_steps WHERE mission_id=?", (mid,)).fetchone()[0]
        lines.append(f"#{mid} [{status}] {done}/{total} — {goal[:70]}")
    con.close()
    return "Missions:\n" + "\n".join(lines)


def cancel_mission(config: dict = None) -> str:
    con = _db()
    row = con.execute(
        "SELECT id, goal FROM missions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        con.close()
        return "No active mission to cancel, Master."
    _touch(con, row[0], status="cancelled", report="cancelled by Master")
    con.close()
    return f"Mission #{row[0]} ('{row[1][:50]}') cancelled, Master."


def resume_active_missions(config: dict) -> None:
    """Called at boot: pick up missions that were mid-flight when she restarted."""
    try:
        con = _db()
        # night_shift:* missions are owned by the shift resumer — resuming them here too
        # would run the same mission twice in parallel after a restart.
        rows = con.execute(
            "SELECT id, goal FROM missions WHERE status='active' "
            "AND COALESCE(origin,'') NOT LIKE 'night_shift:%'").fetchall()
        con.close()
        for mid, goal in rows:
            log_info(f"[MISSION] resuming #{mid}: {goal[:60]}")
            threading.Thread(target=_execute_mission, args=(mid, config), daemon=True).start()
    except Exception as e:
        log_info(f"[MISSION] resume failed: {e}")
