"""Phase Z2 — THE NIGHT SHIFT.

An 8-hour autonomous shift: an ordered queue of missions worked one at a time
between a start and a deadline, on a pinned provider (Mistral — the ~1B-tok/month
tank, so the shift never touches Master's daytime Groq budget), reporting NOTHING
until a single honest proof-of-work message at 07:40.

WHY THIS IS THE PHASE Z THESIS (what a rented cloud agent structurally cannot do):
  - PERSISTENCE: a shift survives restarts. Each item is a checkpointed mission; the
    shift row records where we are. A reboot at 03:00 resumes, it doesn't restart.
  - VERIFY-AFTER-ACT: every item is a mission, so every step must PROVE it worked
    (VERDICT: PASS from real tool evidence) before it counts. Unverified = reported
    as unverified. No theatre (Rule 8, Design Law 3).
  - OWNED ROUTING: pinning a provider so an 8h run doesn't drain the interactive tank
    is only possible because she owns her cascade. Hermes bills per token; she runs
    on a free tank she controls.

DESIGN LAWS honoured:
  - Law 3 DETERMINISTIC: the shift is driven by a cron + a DB queue, never by the model
    "deciding" to keep working. The 07:40 report is built by CODE from the DB.
  - Law 4 NEVER auto-fix / never act with consequences unsupervised: build shifts collect
    diagnoses, they do NOT commit or auto-fix (Rushi's 2026-07-23 call). No mission the
    shift plans should send/delete/pay — that stays interactive + confirmed.
  - Law 5 QUIET: exactly ONE message per shift (the morning report). Zero pings overnight.
  - Rule 8 VERIFY: the report reads mission_outcome() from the DB, not her narration.

STORAGE: .data/night_shift.db
  shifts(id, label, status, provider, started_at, deadline, budget_tokens,
         tokens_used, created_at, updated_at, report)
  shift_items(id, shift_id, idx, goal, status, mission_id, note)

status: shifts  = queued | running | done | expired | cancelled
        items   = pending | running | done | failed | skipped
"""
import os
import sqlite3
import threading
import time

from .config import log_info, mizune_now

DB_PATH = os.path.join(".data", "night_shift.db")

# The shift's fuel tank. Mistral = ~1B tok/month free across 4 keys and does real
# native tool calling (verified 2026-07-23). Pinned so the 8h run never eats the Groq
# daily budget Master needs during the day. The cascade still backs it up if Mistral dies.
SHIFT_PROVIDER = "mistral"

# Soft token budget for one shift. When crossed, the shift stops pulling NEW items and
# lets the current one finish, then writes the report early. Protects the monthly tank.
DEFAULT_BUDGET_TOKENS = 400_000

_shift_lock = threading.Lock()   # only one shift runs at a time on this box (898MB RAM)


# ── storage ──────────────────────────────────────────────────────────────────

def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY, label TEXT, status TEXT, provider TEXT,
        started_at TEXT, deadline TEXT, budget_tokens INTEGER,
        tokens_used INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, report TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS shift_items (
        id INTEGER PRIMARY KEY, shift_id INTEGER, idx INTEGER, goal TEXT,
        status TEXT, mission_id INTEGER, note TEXT)""")
    return con


def _touch(con, shift_id, **fields):
    sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    con.execute(f"UPDATE shifts SET {sets} WHERE id=?",
                (*fields.values(), mizune_now().isoformat(), shift_id))
    con.commit()


# ── public API ────────────────────────────────────────────────────────────────

def queue_shift(label: str, goals: list, config: dict,
                deadline_iso: str = None, budget_tokens: int = None) -> int:
    """Create a QUEUED shift. It does not run now — start_shift() (cron at 22:00) runs it.
    `goals` is an ordered list of mission goals (natural language), each a checkable task."""
    goals = [g.strip() for g in (goals or []) if g and g.strip()]
    if not goals:
        return 0
    con = _db()
    now = mizune_now().isoformat()
    cur = con.execute(
        "INSERT INTO shifts (label, status, provider, deadline, budget_tokens, "
        "created_at, updated_at, report) VALUES (?, 'queued', ?, ?, ?, ?, ?, '')",
        (label or "Night shift", SHIFT_PROVIDER, deadline_iso,
         budget_tokens or DEFAULT_BUDGET_TOKENS, now, now))
    sid = cur.lastrowid
    for i, g in enumerate(goals):
        con.execute(
            "INSERT INTO shift_items (shift_id, idx, goal, status, mission_id, note) "
            "VALUES (?, ?, ?, 'pending', NULL, '')", (sid, i, g))
    con.commit()
    con.close()
    log_info(f"[SHIFT] queued #{sid} '{label}' with {len(goals)} items.")
    return sid


def _deadline_default() -> str:
    """06:00 IST today if it's still before then, else 06:00 tomorrow."""
    import datetime
    now = mizune_now()
    six = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= six:
        six = six + datetime.timedelta(days=1)
    return six.isoformat()


def start_shift(config: dict, shift_id: int = None) -> str:
    """Begin the most recent QUEUED shift (or a specific one). Runs its queue to
    completion / deadline / budget in a daemon thread. Returns immediately."""
    con = _db()
    if shift_id is None:
        row = con.execute(
            "SELECT id FROM shifts WHERE status='queued' ORDER BY id DESC LIMIT 1").fetchone()
        shift_id = row[0] if row else None
    con.close()
    if not shift_id:
        log_info("[SHIFT] start requested but no queued shift.")
        return "no queued shift"
    threading.Thread(target=_run_shift, args=(shift_id, config), daemon=True).start()
    return f"shift #{shift_id} starting"


def _run_shift(shift_id: int, config: dict):
    if not _shift_lock.acquire(blocking=False):
        log_info(f"[SHIFT] #{shift_id} not started — another shift is already running.")
        return
    try:
        from .missions import start_mission, mission_outcome
        con = _db()
        row = con.execute(
            "SELECT status, deadline, budget_tokens, tokens_used FROM shifts WHERE id=?",
            (shift_id,)).fetchone()
        if not row:
            con.close(); return
        status, deadline, budget, used = row
        if status not in ("queued", "running"):
            con.close(); return

        deadline = deadline or _deadline_default()
        started = mizune_now().isoformat()
        _touch(con, shift_id, status="running", started_at=started, deadline=deadline)
        import datetime
        try:
            dl = datetime.datetime.fromisoformat(deadline)
        except Exception:
            dl = datetime.datetime.fromisoformat(_deadline_default())

        milestones = []
        opts = {
            "hints": {"force_provider": SHIFT_PROVIDER, "intent": "autonomous"},
            "silent": True,
            "sink": milestones.append,
            "bypass_cap": True,
        }

        items = con.execute(
            "SELECT id, idx, goal, status FROM shift_items WHERE shift_id=? ORDER BY idx",
            (shift_id,)).fetchall()
        con.close()

        log_info(f"[SHIFT] #{shift_id} running {len(items)} items until {deadline} on {SHIFT_PROVIDER}.")

        for item_id, idx, goal, istatus in items:
            if istatus in ("done", "failed", "skipped"):
                continue
            # HARD STOPS before pulling a new item ---------------------------------
            if mizune_now() >= dl:
                _mark_item(shift_id, item_id, "skipped", "deadline reached before start")
                log_info(f"[SHIFT] #{shift_id} deadline reached — skipping remaining items.")
                continue
            u = _tokens_used_estimate(shift_id)
            if u >= (budget or DEFAULT_BUDGET_TOKENS):
                _mark_item(shift_id, item_id, "skipped", "token budget spent")
                log_info(f"[SHIFT] #{shift_id} budget spent (~{u} tok) — skipping rest.")
                continue

            _mark_item(shift_id, item_id, "running", "")
            log_info(f"[SHIFT] #{shift_id} item {idx + 1}: {goal[:80]}")
            try:
                # run_async=False: this thread owns execution and blocks until the
                # mission finishes, so the queue stays strictly sequential.
                start_mission(goal, f"night_shift:{shift_id}", config,
                              opts=opts, run_async=False)
            except Exception as e:
                log_info(f"[SHIFT] #{shift_id} item {idx + 1} crashed: {e}")
                _mark_item(shift_id, item_id, "failed", f"crash: {str(e)[:120]}")
                continue

            # Ground truth from the mission DB — NOT from what she said (Rule 8).
            mid = _latest_mission_for(shift_id, idx)
            outcome = mission_outcome(mid) if mid else {"found": False}
            if outcome.get("found") and outcome["status"] == "done":
                _mark_item(shift_id, item_id, "done",
                           f"{outcome['verified']}/{outcome['total']} steps verified", mid)
            else:
                v = outcome.get("verified", 0); t = outcome.get("total", 0)
                _mark_item(shift_id, item_id, "failed",
                           f"{outcome.get('status','?')} ({v}/{t} verified)", mid)

        final = "expired" if mkexp(shift_id, dl) else "done"
        # set status FIRST so the report header reflects the real final state, then store it.
        con = _db(); _touch(con, shift_id, status=final); con.close()
        report = build_proof_of_work(shift_id)
        con = _db(); _touch(con, shift_id, report=report); con.close()
        log_info(f"[SHIFT] #{shift_id} {final}. Report ready ({len(report)} chars).")
    except Exception as e:
        log_info(f"[SHIFT] #{shift_id} fatal: {e}")
    finally:
        _shift_lock.release()


def mkexp(shift_id, dl) -> bool:
    """True if the deadline passed with items still pending (shift ran out of night)."""
    con = _db()
    pend = con.execute(
        "SELECT COUNT(*) FROM shift_items WHERE shift_id=? AND status IN ('pending','running')",
        (shift_id,)).fetchone()[0]
    con.close()
    return bool(pend) and mizune_now() >= dl


def _mark_item(shift_id, item_id, status, note, mission_id=None):
    con = _db()
    if mission_id is not None:
        con.execute("UPDATE shift_items SET status=?, note=?, mission_id=? WHERE id=?",
                    (status, note, mission_id, item_id))
    else:
        con.execute("UPDATE shift_items SET status=?, note=? WHERE id=?",
                    (status, note, item_id))
    con.commit(); con.close()


def _latest_mission_for(shift_id, idx):
    """The mission row this shift item just created (origin = night_shift:<sid>)."""
    from .missions import _db as _mdb
    con = _mdb()
    row = con.execute(
        "SELECT id FROM missions WHERE origin=? ORDER BY id DESC LIMIT 1",
        (f"night_shift:{shift_id}",)).fetchone()
    con.close()
    return row[0] if row else None


def _tokens_used_estimate(shift_id) -> int:
    """Best-effort spend estimate. We don't have per-call token accounting wired into
    the shift yet, so approximate from completed items (~ a mission ≈ 12k tokens across
    plan+steps+verify). Conservative — better to stop early than drain the tank."""
    con = _db()
    done = con.execute(
        "SELECT COUNT(*) FROM shift_items WHERE shift_id=? AND status IN ('done','failed')",
        (shift_id,)).fetchone()[0]
    con.close()
    return done * 12_000


# ── proof-of-work report (CODE builds it, from the DB — Law 3 + Rule 8) ────────

def build_proof_of_work(shift_id: int) -> str:
    con = _db()
    s = con.execute(
        "SELECT label, status, started_at, deadline FROM shifts WHERE id=?",
        (shift_id,)).fetchone()
    items = con.execute(
        "SELECT idx, goal, status, note FROM shift_items WHERE shift_id=? ORDER BY idx",
        (shift_id,)).fetchall()
    con.close()
    if not s:
        return ""
    label, status, started, deadline = s
    done = [i for i in items if i[2] == "done"]
    failed = [i for i in items if i[2] == "failed"]
    skipped = [i for i in items if i[2] == "skipped"]
    lines = [f"NIGHT SHIFT REPORT — {label} [{status}]",
             f"Window: {(started or '?')[11:16]} → {deadline[11:16] if deadline else '?'}",
             f"Verified {len(done)} / {len(items)} tasks."]
    if done:
        lines.append("\nDONE (verified):")
        lines += [f"  ✓ {g[:70]} — {note}" for _, g, _, note in done]
    if failed:
        lines.append("\nATTEMPTED, NOT VERIFIED:")
        lines += [f"  ✗ {g[:70]} — {note}" for _, g, _, note in failed]
    if skipped:
        lines.append("\nDID NOT REACH (out of time/budget):")
        lines += [f"  · {g[:70]}" for _, g, _, note in skipped]
    return "\n".join(lines)


def latest_report() -> str:
    """The most recent finished shift's report, for the 07:40 delivery + dashboard."""
    con = _db()
    row = con.execute(
        "SELECT report FROM shifts WHERE status IN ('done','expired') "
        "AND report != '' ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return row[0] if row and row[0] else ""


# ── boot resume ────────────────────────────────────────────────────────────────

def resume_running_shift(config: dict) -> None:
    """Called at boot: a shift that was mid-flight when she restarted picks up where it
    left off (items already 'done' are skipped inside _run_shift). This is the
    persistence claim of Z2 — a reboot at 03:00 does not lose the night."""
    try:
        con = _db()
        row = con.execute(
            "SELECT id FROM shifts WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        if row:
            log_info(f"[SHIFT] resuming running shift #{row[0]} after restart.")
            threading.Thread(target=_run_shift, args=(row[0], config), daemon=True).start()
    except Exception as e:
        log_info(f"[SHIFT] resume failed: {e}")
