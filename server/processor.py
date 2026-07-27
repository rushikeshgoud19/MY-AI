"""
Core command processor for Mizune AI.
Stitches together Vision, AI, Commands, and Context.
"""
import os
import json
import re
import time
import subprocess
import asyncio
import threading
import logging
import shlex
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from server.config import log_info
from server.commands import COMMON_APPS, launch_app, close_app, whatsapp_automation, take_note
from server.ai import get_ai_response
from server.task_planner import is_multi_step_request, get_task_planner
from server.agents import mizune_manager, save_turn
from server.memory import memory
from server.memory_tree import memory_tree_db
from server.evolution import evolution_engine
from server.vision import _acquire_vision_lock, _release_vision_lock, _analyze_screen_now, _vision_mode_running, _coding_monitor_running, _coding_monitor_paused, _vision_mode_loop, _coding_monitor_loop, _capture_screen


from contextvars import ContextVar
current_session_id = ContextVar("current_session_id", default=None)

logger = logging.getLogger("mizune.processor")

# Memory recall runs off-thread with a time budget so it never blocks a reply.
# Not a context manager: shutdown would wait on slow recalls and defeat the timeout.
_recall_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem-recall")

# Session Store
from server.session_store import SessionStore
global_session_store = SessionStore()

from server.scheduler import CronManager
global_cron_manager = CronManager()


def _parse_whatsapp_send_command(wa_text: str):
    """
    Parse recipient and message body from WhatsApp send intents.
    Returns (who, body) or (None, None).
    """
    if "[WHATSAPP MESSAGE FROM" in wa_text and "FROM Rushi" not in wa_text and "FROM Rushikesh" not in wa_text:
        return None, None

    clean = wa_text.strip()

    # 1. 'say/send/message <body/msg> to <who>' (e.g. 'say baka to Pranay', 'send hi to +919876543210')
    m1 = re.search(r"^(?:mizune\s+)?(?:say|send|message|text|msg)\s+(.+?)\s+to\s+([A-Za-z0-9_\s\+\@\.]+)", clean, re.IGNORECASE)
    if m1:
        b, w = m1.group(1).strip().strip('"\''), m1.group(2).strip()
        if b and w and w.lower() not in ("me", "myself", "self", "master", "master rushi"):
            return w, b

    # 2. 'say to <who> <body/msg>' or 'tell <who> <body/msg>' (e.g. 'tell Pranay baka', 'say to Pranay baka')
    m2 = re.search(r"^(?:mizune\s+)?(?:say\s+to|tell)\s+([A-Za-z0-9_\s\+\@\.]+?)\s+(?:saying\s+)?(.+)", clean, re.IGNORECASE)
    if m2:
        w, b = m2.group(1).strip(), m2.group(2).strip().strip('"\'')
        if w and b:
            return w, b

    # 3. Standard 'send/message/text/dm <who> saying/says/that says/: <body/msg>'
    verb = re.search(r"\b(?:send|message|msg|text|whatsapp|dm)\b", clean, re.IGNORECASE)
    if verb:
        rest = clean[verb.end():]
        sep = re.search(r"\bsaying\b|\bthat says\b|\bsays\b|\bsay\b|:", rest, re.IGNORECASE)
        if sep:
            left = rest[:sep.start()]
            body = rest[sep.end():].lstrip(" :").split("\n(SYSTEM:")[0].strip().strip('"\'')
            tos = list(re.finditer(r"\bto\b\s+", left, re.IGNORECASE))
            who = (left[tos[-1].end():] if tos else left).strip(" ,.")
            who = re.sub(r"^(?:a|an|the)\s+", "", who, flags=re.IGNORECASE).strip()
            if who and body:
                return who, body

    return None, None


def _handle_scheduled_whatsapp_send(text: str, config: dict):
    """
    Parses scheduled WhatsApp send requests:
    - 'in 5 minutes say good night to Harshita'
    - 'say good night to Harshita in 5 minutes'
    - 'say good night to Harshita in 5 minutes, 10 times'
    Returns confirmation string if scheduled, or None.
    """
    clean = re.sub(r"^\s*\[[^\]]*\]\s*:\s*", "", text).split("\n(SYSTEM:")[0].strip()
    lower_clean = clean.lower()

    # Check for time delay keywords: 'in X minutes', 'after X minutes'
    m_time = re.search(r"\b(?:in|after)\s+(\d+)\s*(?:min|minute|minutes|m|hour|hours|h)\b", lower_clean)
    m_repeat = re.search(r"\b(\d+)\s*(?:times|x|repeats)\b", lower_clean)

    if not m_time and not m_repeat:
        return None

    delay_mins = int(m_time.group(1)) if m_time else 0
    if m_time and ("hour" in m_time.group(0) or "h" in m_time.group(0)):
        delay_mins *= 60

    repeats = int(m_repeat.group(1)) if m_repeat else 1
    max_repeats = config.get("max_scheduled_repeats", 10)
    if repeats > max_repeats:
        log_info(f"[SCHEDULER] Capping repeats {repeats} -> {max_repeats}")
        repeats = max_repeats

    # Gap between repeats (default 60 seconds / 1 minute minimum)
    m_gap = re.search(r"\bevery\s+(\d+)\s*(?:sec|second|seconds|min|minute|minutes|s|m)\b", lower_clean)
    gap_sec = 60
    if m_gap:
        val = int(m_gap.group(1))
        unit = m_gap.group(0)
        if "min" in unit or "m" in unit:
            gap_sec = val * 60
        else:
            gap_sec = val
    min_gap = config.get("min_repeat_interval_sec", 60)
    if gap_sec < min_gap:
        gap_sec = min_gap

    # Remove schedule phrases to extract target & body
    clean_no_sched = re.sub(r"\b(?:in|after)\s+\d+\s*(?:min|minute|minutes|m|hour|hours|h)\b", "", clean, flags=re.IGNORECASE)
    clean_no_sched = re.sub(r"\b\d+\s*(?:times|x|repeats)\b", "", clean_no_sched, flags=re.IGNORECASE)
    clean_no_sched = re.sub(r"\bevery\s+\d+\s*(?:sec|second|seconds|min|minute|minutes|s|m)\b", "", clean_no_sched, flags=re.IGNORECASE).strip()

    who, body = _parse_whatsapp_send_command(clean_no_sched)
    if not who or not body:
        return None

    from server.config import mizune_now
    from datetime import timedelta
    now_ist = mizune_now()
    base_trigger = now_ist + timedelta(minutes=delay_mins)

    for i in range(repeats):
        trigger_time = base_trigger + timedelta(seconds=i * gap_sec)
        trigger_iso = trigger_time.isoformat()
        desc = f'WA_SEND target="{who}" message="{body}"'
        global_cron_manager.add_one_time_task(desc, trigger_iso)

    log_info(f"[SCHEDULER] Scheduled {repeats} WhatsApp message(s) to {who!r}: {body[:40]!r} starting at {base_trigger.isoformat()}")
    return f"Scheduled {repeats} message(s) to {who} via WhatsApp starting at {base_trigger.strftime('%H:%M:%S IST')}."


def _seal_watermark():
    """Highest history rowid now — used to find [TOOL RESULTS] seals created after."""
    try:
        from server.memory import memory
        cur = memory.db.cursor()
        row = cur.execute("SELECT MAX(rowid) FROM history").fetchone()
        return row[0] or 0
    except Exception:
        return None


def _report_seal_failures(since_rowid, broadcast):
    """R.2 truthful reports: if any tool sealed a failure during this run, say so
    honestly instead of leaving Master with an optimistic confirmation."""
    if since_rowid is None:
        return
    try:
        from server.memory import memory
        cur = memory.db.cursor()
        rows = cur.execute(
            "SELECT content FROM history WHERE rowid > ? AND content LIKE '%[TOOL RESULTS]%'",
            (since_rowid,)).fetchall()
        fails = [r[0] for r in rows
                 if any(k in r[0] for k in ("FAILED", "ERROR", "Error:", "Error "))]
        if fails:
            detail = fails[-1].replace("[TOOL RESULTS] ", "")[:200]
            broadcast({"type": "speak",
                       "text": f"Master, honest report — that scheduled task hit a problem: {detail}"})
    except Exception as e:
        log_info(f"[SCHEDULER] Truthful-report check failed: {e}")


def _scheduler_callback(task_description):
    from server.websocket import ws_manager
    from server.config import load_config
    config = load_config()
    log_info(f"[SCHEDULER WAKEUP] Processing task: {task_description}")

    # 07:45 bug report — pure DB read + WhatsApp send (no LLM, no quota).
    if task_description == "MIZUNE_BUG_REPORT":
        from server.self_review import send_bug_report
        threading.Thread(target=lambda: log_info(
            f"[SELF_REVIEW] morning bug report -> {send_bug_report(config)}"), daemon=True).start()
        return

    # Briefing/digest: deterministic data + GUARANTEED delivery. The old design let
    # the LLM both voice AND send (via the message_whatsapp tool) — on 2026-07-20 the
    # 8AM voicing hung on a provider mid-cascade and the briefing silently died.
    # Now: LLM only voices (override call, no tools); OUR code always sends; if every
    # provider fails, Master gets the raw sitrep — data over silence, always.
    if task_description in ("MIZUNE_MORNING_BRIEFING", "MIZUNE_EVENING_DIGEST"):
        morning = task_description == "MIZUNE_MORNING_BRIEFING"
        tag = "BRIEFING" if morning else "DIGEST"

        def _deliver():
            try:
                from server.briefing import build_briefing_sitrep, build_evening_sitrep
                sitrep = build_briefing_sitrep() if morning else build_evening_sitrep()
                log_info(f"[{tag}] Sitrep built ({len(sitrep)} chars).")
                persona = (
                    "You are Mizune, Master Rushi's warm AI companion. Rewrite the data as a "
                    + ("morning briefing (under 150 words)" if morning
                       else "SHORT calm evening recap (under 80 words), ending with a goodnight")
                    + ". Facts must come from the data only. Output ONLY the message text.")
                text = ""
                try:
                    from server.ai import get_ai_response
                    res, _ = get_ai_response(sitrep, [], config, system_prompt_override=persona)
                    text = str(res or "").strip()
                except Exception as e:
                    log_info(f"[{tag}] Voicing failed ({e}) — sending raw sitrep.")
                if len(text) < 30:
                    text = sitrep          # raw fallback beats silence
                # NOTE: send_message() already prepends the "✨ Mizune" header —
                # adding it here printed it TWICE (caught 2026-07-20).
                from server.commands import whatsapp_automation
                sent = str(whatsapp_automation("Master", text))
                log_info(f"[{tag}] Delivery result: {sent[:120]}")
                if any(k in sent.lower() for k in ("error", "failed", "not connected")):
                    time.sleep(120)        # bridge may be reconnecting — one retry
                    sent = str(whatsapp_automation("Master", text))
                    log_info(f"[{tag}] Retry delivery result: {sent[:120]}")
                ws_manager.broadcast_sync({"type": "speak", "text": text, "emotion": "neutral"})
            except Exception as e:
                log_info(f"[{tag}] Delivery thread error: {e}")
        threading.Thread(target=_deliver, daemon=True).start()
        return

    # Z2 NIGHT SHIFT — start the queued shift at 22:00. The shift runs in its own
    # daemon thread until deadline/budget; it reports NOTHING until morning (silent).
    if task_description == "MIZUNE_SHIFT_START":
        def _start_shift():
            try:
                from server.night_shift import start_shift
                log_info(f"[SHIFT] cron start -> {start_shift(config)}")
            except Exception as e:
                log_info(f"[SHIFT] start error: {e}")
        threading.Thread(target=_start_shift, daemon=True).start()
        return

    # Z2 NIGHT SHIFT — 07:40 proof-of-work. CODE reads the report from the DB (built from
    # verified mission outcomes, Rule 8) and sends it. The LLM only VOICES it; if voicing
    # fails, Master gets the raw report — data over silence (same contract as the briefing).
    if task_description == "MIZUNE_SHIFT_REPORT":
        def _deliver_shift():
            try:
                from server.night_shift import latest_report
                report = latest_report()
                if not report:
                    log_info("[SHIFT] no report to deliver.")
                    return
                text = ""
                try:
                    from server.ai import get_ai_response
                    persona = (
                        "You are Mizune, Master Rushi's warm AI companion. Below is the "
                        "verified result of the overnight work shift you just finished. "
                        "Retell it warmly in-persona in under 130 words. Report failures and "
                        "unfinished items HONESTLY — do not pretend they succeeded. Keep the "
                        "'verified N/M' honesty. Output ONLY the message text.")
                    res, _ = get_ai_response(report, [], config, system_prompt_override=persona)
                    text = str(res or "").strip()
                except Exception as e:
                    log_info(f"[SHIFT] voicing failed ({e}) — sending raw report.")
                if len(text) < 30:
                    text = report
                from server.commands import whatsapp_automation
                sent = str(whatsapp_automation("Master", text))
                log_info(f"[SHIFT] delivery: {sent[:120]}")
                if any(k in sent.lower() for k in ("error", "failed", "not connected")):
                    time.sleep(120)
                    sent = str(whatsapp_automation("Master", text))
                    log_info(f"[SHIFT] retry delivery: {sent[:120]}")
                ws_manager.broadcast_sync({"type": "speak", "text": text, "emotion": "neutral"})
            except Exception as e:
                log_info(f"[SHIFT] delivery thread error: {e}")
        threading.Thread(target=_deliver_shift, daemon=True).start()
        return

    if task_description == "MIZUNE_NIGHTLY_REVIEW":
        def _run_review():
            try:
                from server.self_review import run_nightly
                res = run_nightly(config)
                log_info(f"[NIGHTLY_REVIEW] Outcome: {res}")
            except Exception as e:
                log_info(f"[NIGHTLY_REVIEW] Delivery thread error: {e}")
        threading.Thread(target=_run_review, daemon=True).start()
        return

    # Deterministic path: if the stored action is literal python (she schedules
    # `execute_python code="..."`), run it directly through the guarded tool
    # dispatcher. Re-emitting code through the LLM truncates it — models fumble
    # quotes-in-JSON — so scheduled code must never round-trip through the model.
    # TWO stored shapes must both hit this path. The original fix only handled
    # `execute_python code="..."`, but schedule_task now stores the JSON arg form
    # `execute_python {"code": "..."}`. That form fell through to the LLM/SystemAgent
    # branch, which "handled" it conversationally and never ran the code — the task
    # was marked executed=1 while the file it was supposed to write never appeared
    # (caught by the feature audit 2026-07-26: /tmp/sched_4811.txt missing).
    if task_description.startswith("WA_SEND"):
        m_wa = re.search(r'WA_SEND\s+target="([^"]+)"\s+message="([^"]+)"', task_description)
        if m_wa:
            target_contact = m_wa.group(1)
            msg_body = m_wa.group(2)
            from server.commands import whatsapp_automation
            res = whatsapp_automation(target_contact, msg_body)
            log_info(f"[SCHEDULER] Direct-executed WA_SEND to {target_contact!r}: {res}")
            try:
                from server.memory import memory
                memory.add_to_history("system", f"[TOOL RESULTS] message_whatsapp: {res[:150]}")
            except Exception as _e:
                log_info(f"[SCHEDULER] seal failed: {_e}")
            return

    _sched_code = None
    m = re.match(r'\s*execute_python\s+code="(.*)"\s*$', task_description, re.DOTALL)
    if m:
        _sched_code = m.group(1)
    else:
        m_json = re.match(r'\s*execute_python\s+(\{.*\})\s*$', task_description, re.DOTALL)
        if m_json:
            try:
                _payload = json.loads(m_json.group(1))
                if isinstance(_payload, dict) and isinstance(_payload.get("code"), str):
                    _sched_code = _payload["code"]
            except Exception as _e:
                log_info(f"[SCHEDULER] stored execute_python JSON unparseable ({_e}); "
                         f"falling through to the brain path.")

    if _sched_code and "whatsapp" not in task_description.lower():
        from server.ai import execute_tool_call
        result = execute_tool_call("execute_python", {"code": _sched_code}, config)
        log_info(f"[SCHEDULER] Direct-executed stored python: {str(result)[:150]}")
        # R.2: report the REAL outcome, not a blanket success.
        res_str = str(result)
        if any(k in res_str for k in ("Error", "ERROR", "failed", "FAILED")):
            ws_manager.broadcast_sync({"type": "speak",
                "text": f"Master, honest report — the scheduled task failed: {res_str[:180]}"})
        else:
            ws_manager.broadcast_sync({"type": "speak", "text": "Scheduled task done, Master!"})
        return

    prompt = (
        f"[SYSTEM ALERT: A scheduled task has triggered!] Task description: {task_description}. "
        f"Execute this task NOW using your tools. The description states the INTENT — if it contains "
        f"raw code or tool-call syntax, do NOT copy it verbatim; write a fresh, correct tool call "
        f"that fulfills the same intent. Then speak a short confirmation."
    )

    if "VIA_WHATSAPP" in task_description or "whatsapp" in task_description.lower():
        prompt += " IMPORTANT: The user requested this reminder on WhatsApp. You MUST use the message_whatsapp tool to send this reminder to 'Master' (or the requested contact) right now! Do NOT just say it out loud, actually send the WhatsApp message using the tool!"

    # R.2 truthful reports: watch the seals this run creates and surface failures.
    wm = _seal_watermark()
    def _run_and_report():
        process_command(prompt, config, ws_manager.broadcast_sync, 'main')
        _report_seal_failures(wm, ws_manager.broadcast_sync)
    threading.Thread(target=_run_and_report, daemon=True).start()

# NOTE: global_cron_manager.start() is deliberately NOT called here — see the bottom of
# this module. Starting it mid-import let a task fire before process_command existed.

# Register the daily morning briefing (idempotent — checks for an existing row).
# Lives here so BOTH entry points (local server.py, VM backend_main.py) get it.
try:
    from server.briefing import ensure_briefing_scheduled
    from server.config import load_config as _lc
    ensure_briefing_scheduled(_lc(), global_cron_manager)
except Exception as _e:
    log_info(f"[BRIEFING] Registration skipped: {_e}")

# Resume missions that were mid-flight when she restarted (H2 mission engine).
# Delayed a bit so providers/bridges finish booting before steps execute.
try:
    from server.missions import resume_active_missions as _ram
    from server.config import load_config as _lc2
    threading.Timer(45.0, _ram, args=(_lc2(),)).start()
except Exception as _e:
    log_info(f"[MISSION] Resume hook skipped: {_e}")

# Z2: resume a night shift that was mid-flight at restart (persistence claim of Z2).
# A bit after missions, and only touched if the module is present.
try:
    from server.night_shift import resume_running_shift as _rrs
    from server.config import load_config as _lc3
    threading.Timer(60.0, _rrs, args=(_lc3(),)).start()
except Exception as _e:
    log_info(f"[SHIFT] Resume hook skipped: {_e}")

_processing_lock = threading.Lock()
# Per-session locks so a slow WhatsApp reply doesn't drop the user's desktop input
# (and vice versa). The old single global lock serialized ALL platforms and silently
# returned None for any message that arrived while another was in flight.
_session_locks = {}
_session_locks_guard = threading.Lock()

def _get_session_lock(session_id: str) -> threading.Lock:
    with _session_locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[session_id] = lock
        return lock

def _format_mesh_reply(res: dict) -> str:
    """Render a mesh result DETERMINISTICALLY. Code owns the agreement label, the provider
    list and the verifier name — if a model voiced this it could narrate 'I double-checked'
    over a single-provider answer, which is the exact failure mesh exists to catch."""
    body = (res.get("consolidated") or "").strip()
    if not res.get("mesh"):
        reason = res.get("reason") or "cross-check unavailable"
        return (body or "I couldn't cross-check that right now, Master.") + \
               f"\n\n— NOT cross-checked ({reason})"
    used = ", ".join(res.get("providers_used") or [])
    agreement = str(res.get("agreement") or "unknown").upper()
    notes = (res.get("notes") or "").strip()
    # Say so when the verifier also produced one of the answers — a model grading its own
    # work is weaker evidence, and hiding that would overstate the check.
    vtag = f"verifier: {res.get('verifier')}" + ("" if res.get("verifier_held_out") else " (also answered)")
    lines = [body or "(no consolidated answer returned)", "",
             f"— cross-checked by {used} · {vtag} · agreement: {agreement}"]
    if agreement in ("MIXED", "CONFLICT") and notes:
        lines.append(f"where they differ: {notes[:400]}")
    return "\n".join(lines).strip()


def process_command(text: str, config: dict, broadcast_sync_fn, session_id: str = 'main') -> str:
    """Wrapper to prevent ghost inputs from cloning Mizune's brain (per-session)."""
    lock = _get_session_lock(session_id)
    if not lock.acquire(blocking=False):
        log_info(f"[PROCESSOR] Ignoring overlapping input '{text}' for session '{session_id}' (busy).")
        return None
    try:
        return _process_command_internal(text, config, broadcast_sync_fn, session_id)
    finally:
        lock.release()

from server.tracing import observe

# capture_input=False: the `config` arg holds live API keys — never send it to TraceRoot.
@observe(name="Mizune.ProcessCommand", type="span", capture_input=False)
def _process_command_internal(text: str, config: dict, broadcast_sync_fn, session_id: str = 'main') -> str:
    current_session_id.set(session_id)
    # Initialize session and load emotion state
    platform = "whatsapp" if "whatsapp:" in session_id else "desktop"
    global_session_store.start_or_resume_session(session_id, platform=platform)
    
    from server.emotion_engine import global_emotion_state
    meta = global_session_store.get_session_metadata(session_id)
    if "emotion" in meta:
        state_dict = meta["emotion"]
        for k, v in state_dict.items():
            if hasattr(global_emotion_state, k):
                setattr(global_emotion_state, k, v)
    
    from server.security import global_rate_limiter, SecurityScanner
    if not global_rate_limiter.check_limit():
        log_info("[SECURITY] Rate limit exceeded. Dropping request.")
        return "[EMOTION: sad] My brain is feeling a little overwhelmed, Master! Please slow down~"
        
    log_info(f"[COMMAND] Processing: '{text}'")
    
    if text.strip() == "[SKIP]":
        log_info("[PROCESSOR] Received [SKIP] signal. Ignoring.")
        return None

    lower_text = text.lower().strip()
    wake_words = config.get("wake_words", [])
    for wake in wake_words:
        if lower_text.startswith(wake):
            text = text[len(wake):].strip()
            lower_text = text.lower().strip()
            break
            
    # ── MISSION fast-path: "mission: <goal>" is a GUARANTEED trigger for the
    # H2 mission engine (the LLM otherwise sometimes handles small compound goals
    # directly and skips the engine). Strips WhatsApp wrapper/context lines first.
    _mission_m = re.search(r"(?:start a |begin a |new )?mission\s*[:\-]\s*(.+)", lower_text)
    if _mission_m and "[mission" not in lower_text:
        from server.missions import start_mission
        # Recover the goal with original casing from the raw text
        _goal_raw = text[text.lower().find(_mission_m.group(1)):].strip()
        _goal_raw = _goal_raw.split("\n(SYSTEM:")[0].strip()
        log_info(f"[MISSION] fast-path trigger: {_goal_raw[:80]}")
        return start_mission(_goal_raw, session_id, config)

    # ── NIGHT SHIFT fast-path (Z2): queuing an overnight shift MUST be deterministic —
    # the model otherwise just chats ("I don't have any shift info") instead of calling
    # the tool (observed live 2026-07-24). Read-only status/report also routed here.
    #   "night shift status" / "shift report"  → status/report
    #   "tonight: A. B. C" / "overnight work on X and Y" / "while I sleep, do X"
    # "night shift"/"overnight"/"while I sleep" are unambiguous shift phrasing; bare
    # "tonight" is NOT (it appears in ordinary chat) so it only counts alongside a work verb.
    _WORK = r"work on|do|handle|tackle|research|finish|prepare|build|write|organi[sz]e|review|draft|plan"
    _shift_phrase = re.search(r"\bnight\s*shift\b|\bovernight\b|\bwhile i (?:sleep|am asleep|'m asleep)\b", lower_text)
    _tonight_work = re.search(r"\btonight\b[^\.]*\b(?:" + _WORK + r")\b", lower_text)
    if (_shift_phrase or _tonight_work) and "[mission" not in lower_text and not text.startswith("[SYSTEM"):
        # status / report first (read-only, no queue)
        if re.search(r"\b(status|how(?:'s| is) (?:the|my)? ?shift)\b", lower_text) \
                and not re.search(r"\b(" + _WORK + r"|queue)\b", lower_text):
            from server.ai import execute_tool_call
            log_info("[SHIFT] fast-path: status")
            return execute_tool_call("night_shift", {"action": "status"}, config)
        if re.search(r"\b(report|proof of work|what did you (?:do|get done))\b", lower_text):
            from server.ai import execute_tool_call
            log_info("[SHIFT] fast-path: report")
            return execute_tool_call("night_shift", {"action": "report"}, config)
        # queue: pull the task list after the trigger phrase
        _q = re.search(
            r"(?:night\s*shift|overnight|while i (?:sleep|am asleep|'m asleep)|tonight)\s*[:,\-]?\s*"
            r"(?:you (?:can|should) )?(?:please )?(?:" + _WORK + r")?\s*[:,\-]?\s*(.+)",
            text, re.IGNORECASE | re.DOTALL)
        if _q:
            _body = _q.group(1).split("\n(SYSTEM:")[0].strip()
            # split into ordered tasks on newlines, semicolons, ' and ', ' then ', or ', '
            parts = re.split(r"\s*(?:\n|;|,| and | then )\s*", _body)
            tasks = [p.strip(" .") for p in parts if len(p.strip(" .")) > 3]
            if tasks:
                from server.ai import execute_tool_call
                log_info(f"[SHIFT] fast-path: queue {len(tasks)} task(s)")
                return execute_tool_call("night_shift",
                                         {"action": "queue", "tasks": tasks}, config)

    # ── LEARN fast-path: "learn this: <url/text>" / "/learn <x>" / "remember this: <x>"
    # MUST be deterministic — the model happily answers ABOUT a link from its own
    # knowledge and claims it learned, while the knowledge base stays empty
    # (caught 2026-07-20: DB had 0 rows after she said "I've learned about X").
    _learn_m = re.search(
        r"(?:^|\b)(?:/learn|learn this|learn about this|remember this|save this to (?:your )?(?:knowledge|memory)|add this to (?:your )?knowledge)\s*[:\-]?\s*(.+)",
        lower_text, re.DOTALL)
    if _learn_m and "[mission" not in lower_text:
        _src_lower = _learn_m.group(1).strip()
        _src = text[text.lower().rfind(_src_lower[:40]):].strip() if _src_lower else ""
        _src = _src.split("\n(SYSTEM:")[0].strip()
        if _src:
            from server.knowledge import learn as _learn_fn
            log_info(f"[KNOWLEDGE] fast-path learn: {_src[:80]}")
            return _learn_fn(_src, config)

    # ── MESH fast-path (Z5): cross-model verification MUST be deterministic. The engine
    # (server/mesh.py) has existed and worked since 2026-07-24 but NOTHING called it — the
    # model never picks it on its own, so "verify this: X" got a single-provider answer that
    # READ like it had been verified. Colon/dash required, so ordinary use of the words
    # ("can you verify this for me?") does not trigger a 3-model fan-out.
    _mesh_m = re.search(
        r"(?:^|\b)(?:mesh|verify this|double[-\s]?check(?:\s+this)?|cross[-\s]?check(?:\s+this)?)"
        r"\s*[:\-]\s*(.+)",
        text, re.IGNORECASE | re.DOTALL)
    if _mesh_m and "[mission" not in lower_text and not text.startswith("[SYSTEM"):
        _mq = _mesh_m.group(1).split("\n(SYSTEM:")[0].strip()
        if _mq:
            from server.mesh import mesh_answer
            log_info(f"[MESH] fast-path trigger: {_mq[:80]}")
            return _format_mesh_reply(mesh_answer(_mq, config))

    # ── WHATSAPP SEND fast-path: an explicit send order is CODE's job, not the model's.
    # Two independent failures made this unusable, and both bypass the model entirely now:
    #   1. She narrated instead of acting — "done!", "I'll send it now", "Here's the
    #      command:" — with ZERO message_whatsapp calls behind any of them (4 in a row,
    #      2026-07-27).
    #   2. REFUSAL CONTAGION. Her own earlier refusals sit in the chronicle, so the next
    #      send request gets refused by imitation regardless of content — "Bakayarooo"
    #      (anime for "idiot") was declined seconds after a genuinely refused request.
    #      Same shape as the fabricated scheduling confirmation: the model copies the
    #      nearest matching turn instead of judging this one.
    # Requires an explicit recipient AND an explicit body separator, so ordinary chat
    # about messaging someone does not fire it.
    # Parsed in steps rather than one regex: a single pattern greedily swallowed the filler
    # and produced who='a whatsapp message to Pranay'. Splitting on the body separator and
    # then taking the text after the LAST "to" is both correct and readable.
    # STRIP THE PLATFORM WRAPPER FIRST. Inbound WhatsApp arrives as
    #   "[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: <what he typed>\n(SYSTEM: ...)"
    # and the wrapper itself contains the word MESSAGE and a colon. Parsing the raw string
    # matched those, so the recipient came out as 'FROM MASTER RUSHI (via WhatsApp)]'
    # (reported live 2026-07-27). My unit tests used bare text and never saw the shape that
    # actually reaches this code — the real input format IS part of the contract.
    # ── SCHEDULED WHATSAPP SEND fast-path (Task 8.3):
    if ("in " in lower_text or "after " in lower_text or "times" in lower_text) and \
            any(w in lower_text for w in ["say", "send", "message", "tell"]):
        _sched_res = _handle_scheduled_whatsapp_send(text, config)
        if _sched_res:
            return _sched_res

    # ── WHATSAPP SEND fast-path (Task 8.1 group-aware + Task Pack 7 wrapper-strip):
    _wa_text = re.sub(r"^\s*\[[^\]]*\]\s*:\s*", "", text)
    _wa_text = _wa_text.split("\n(SYSTEM:")[0].strip()

    _third_party = ("[WHATSAPP MESSAGE FROM" in text
                    and "FROM Rushi" not in text and "FROM Rushikesh" not in text)

    if not _third_party and "[mission" not in lower_text and not text.startswith("[SYSTEM"):
        _who, _body = _parse_whatsapp_send_command(_wa_text)
        if _who and _body:
            _looks_like_wrapper = any(c in _who for c in "[]()") or len(_who) > 30 or "master" in _who.lower()
            if not _looks_like_wrapper and _who.lower() not in (
                    "a", "an", "the", "him", "her", "them", "whatsapp",
                    "message", "whatsapp message", "msg", "text", "someone"):
                
                # Task 8.1 Group-Aware Routing:
                # If request arrived in a group chat (session_id has 'whatsapp:group:') and does NOT
                # explicitly specify DM/privately, route to the ORIGIN GROUP JID!
                _has_dm_explicit = any(w in _wa_text.lower() for w in ["dm", "in dm", "privately", "in private", "directly", "private message"])
                _sess = current_session_id.get() or session_id
                _target_dest = _who
                if _sess and "whatsapp:group:" in _sess and not _has_dm_explicit:
                    _grp_jid = _sess.split("whatsapp:group:", 1)[1].strip()
                    if "@g.us" in _grp_jid:
                        log_info(f"[WHATSAPP] Fast-path routing to origin group {_grp_jid} for recipient {_who!r}")
                        _target_dest = _grp_jid

                from server.commands import whatsapp_automation
                log_info(f"[WHATSAPP] fast-path send → {_target_dest!r}: {_body[:60]!r}")
                _res = str(whatsapp_automation(_target_dest, _body))
                try:
                    from server.memory import memory
                    memory.add_to_history("system", f"[TOOL RESULTS] message_whatsapp: {_res[:150]}")
                except Exception as _e:
                    log_info(f"[WHATSAPP] seal failed: {_e}")
                return _res

    # ── CRAZY COMMANDS ──
    if lower_text == "/nuke_cache":
        log_info("[COMMAND] Executing /nuke_cache...")
        try:
            import gc
            gc.collect()
            # Clear TTS cache folder
            import shutil
            tts_cache = "tts_cache"
            if os.path.exists(tts_cache):
                shutil.rmtree(tts_cache)
                os.makedirs(tts_cache)
            log_info("[COMMAND] RAM garbage collection complete and TTS cache wiped.")
            return "Cache nuked successfully! RAM freed up."
        except Exception as e:
            return f"Failed to nuke cache: {e}"
            
    if lower_text == "/deep_evolve":
        log_info("[COMMAND] Master invoked /deep_evolve. Spawning deep research thread...")
        def trigger_evolution():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(evolution_engine.skill_evolver.evolve())
            
        threading.Thread(target=trigger_evolution, daemon=True).start()
        return "Initiating Deep Evolution protocol in the background. Check the Kernel Stream for logs."

    # Security check using Camera Agent (TEMPORARILY DISABLED)
    camera_agent = mizune_manager.workers.get("camera")
    is_master = True
    # if camera_agent:
    #     is_master = camera_agent.verify_master_now()
    #     if not is_master:
    #         camera_agent.is_master_present = False
    #         log_info("[SECURITY] Stranger detected — restricting system actions.")

    # ── Screen Vision ──
    _is_screen_request = re.search(
        r"\b(look at my screen|look at (the|my) screen|what('s| is) on (my |the )?screen|"
        r"what am i (doing|looking at|working on)|what am i doing on (my )?(pc|computer|screen|monitor)|"
        r"describe my screen|what's on my monitor|what is on my monitor|check my screen|"
        r"see my screen|guess what i am doing|tell me what i am doing|"
        r"see what('s| is) on (my )?screen|what('s| is) happening on (my )?screen)\b", lower_text)

    # On cloud there is no screen/webcam to look at — short-circuit vision requests
    # instead of trying to screenshot a headless box (which errors after a delay).
    from server.config import is_cloud_mode
    _cloud = is_cloud_mode(config)

    if _is_screen_request and _cloud:
        return "[EMOTION: neutral] I'm running on the cloud right now, Master, so I don't have eyes on your screen! Ask me something else~"

    if _is_screen_request:
        if not _acquire_vision_lock("screen_vision"):
            return "I'm already processing another vision task, Master~ Try again in a moment!"

        try:
            log_info("[SCREEN VISION] Taking a screenshot for analysis...")
            broadcast_sync_fn({"type": "status", "text": "Looking at your screen..."})
            
            image_bytes = _capture_screen()
            if not image_bytes:
                return "[EMOTION: sad] I couldn't capture your screen, Master!"
                
            screen_prompt = f"""You are Mizune, Master's adorable anime AI companion.
Master just asked: "{text}"
You are looking at Master's computer screen RIGHT NOW via a screenshot.

Describe what you see in detail:
- What application is currently open?
- What is Master working on, reading, or watching?
- If there is code, what language is it and what does it do?
- If there is a game or video, what is happening?

Be observant and detailed but keep it natural and in character.
Use cute expressions. Keep it to 2-3 sentences max since this will be spoken aloud.
Keep it natural, no emotion tags needed."""

            groq_key = config.get("groq_api_key", "")
            if groq_key:
                try:
                    import base64
                    from openai import OpenAI
                    b64_img = base64.b64encode(image_bytes).decode("utf-8")
                    groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                    resp = groq_client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": screen_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ]}],
                        max_tokens=300
                    )
                    result = (resp.choices[0].message.content or "").strip()
                    if result:
                        log_info(f"[SCREEN VISION] Groq success!")
                        global_session_store.add_message(session_id, "user", text)
                        global_session_store.add_message(session_id, "model", result)
                        text = f"[SYSTEM VISION Context: '{result}']. Fulfill this request: {text}"
                except Exception as e:
                    log_info(f"[SCREEN VISION] Groq failed: {e}")

            # Fallback Gemini Vision
            api_key = config.get("gemini_api_key", "")
            if api_key:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            types.Part.from_text(text=screen_prompt)
                        ]
                    )
                    result = (response.text or "").strip()
                    if result:
                        global_session_store.add_message(session_id, "user", text)
                        global_session_store.add_message(session_id, "model", result)
                        text = f"[SYSTEM VISION Context: '{result}']. Fulfill this request: {text}"
                except Exception as e:
                    log_info(f"[SCREEN VISION] Gemini failed: {e}")
                    
            if not text.startswith("[SYSTEM"):
                return "[EMOTION: sad] I couldn't see your screen properly, Master! My vision might be blurry right now."
        finally:
            _release_vision_lock("screen_vision")

    # ── Camera Vision ──
    if re.search(r"\b(what do you see|what can you see|look at me|look at the camera|look through.*camera|how do i look|"
                 r"what('s| is) on my camera|whats going on my camera|"
                 r"describe what you see|what's around me|what's in front of you|"
                 r"who is here|who is in front|describe my room|look around|"
                 r"see me|can you see me|look at my face|"
                 r"what am i (eating|drinking|holding|wearing|doing)|"
                 r"(how\s+many\s+)?calories\s+(in\s+)?(this|that|food|meal)|"
                 r"what('s| is) in (my|the) (hand|cup|bottle|glass|mug|plate|drink)|"
                 r"tell me what.*(?:drink|hold|eat|wear|look|see))\b", lower_text):
        cam = mizune_manager.workers.get("camera")
        if cam:
            if not _acquire_vision_lock("camera_vision"):
                return "I'm already processing another vision task, Master~ Try again in a moment!"
            try:
                frame_bytes = cam.get_current_frame()
                if frame_bytes:
                    log_info("[CAMERA VISION] Processing camera view...")
                    broadcast_sync_fn({"type": "status", "text": "Looking through camera..."})
                    camera_prompt = f"""You are Mizune, Master's adorable anime AI companion. 
Master just asked: "{text}"
You are looking at Master through your webcam camera RIGHT NOW. Describe what you see."""
                    # Simplified for space: Gemini check
                    api_key = config.get("gemini_api_key", "")
                    if api_key:
                        from google import genai
                        from google.genai import types
                        client = genai.Client(api_key=api_key)
                        try:
                            response = client.models.generate_content(
                                model="gemini-2.0-flash",
                                contents=[
                                    types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                                    types.Part.from_text(text=camera_prompt)
                                ]
                            )
                            result = (response.text or "").strip()
                            if result:
                                global_session_store.add_message(session_id, "user", text)
                                global_session_store.add_message(session_id, "model", result)
                                text = f"[SYSTEM CAMERA Context: '{result}']. Fulfill this request: {text}"
                        except Exception as e:
                            log_info(f"[CAMERA VISION] Gemini failed: {e}")
                    if not text.startswith("[SYSTEM"):
                        text = f"[SYSTEM CAMERA ERROR]. Fulfill this request: {text}"
                else:
                    text = f"[SYSTEM CAMERA ERROR: Cannot see anything]. Fulfill this request: {text}"
            finally:
                _release_vision_lock("camera_vision")
        else:
            text = f"[SYSTEM CAMERA ERROR: No camera connected]. Fulfill this request: {text}"

    # ── Mode Toggles ──
    if re.search(r"\b(watch me|interactive mode|companion mode|vision mode|start watching)\b", lower_text):
        if not _vision_mode_running.is_set():
            _vision_mode_running.set()
            mizune_manager.current_mode = "vision"
            broadcast_sync_fn({"type": "mode", "mode": "vision"})
            threading.Thread(target=_vision_mode_loop, args=(config, broadcast_sync_fn), daemon=True).start()
            return "Hai~! I'm watching your screen now, Master! I'll comment on what I see~ Say 'stop watching' when you want privacy!"
        return "I'm already watching, Master~!"

    if re.search(r"\b(stop watching|privacy mode|stop vision|exit vision|stop interactive)\b", lower_text):
        if _vision_mode_running.is_set():
            _vision_mode_running.clear()
            mizune_manager.current_mode = "conversation"
            broadcast_sync_fn({"type": "mode", "mode": "conversation"})
            return "Okay Master, I've stopped watching your screen~ Your privacy is safe with me!"
        return "I wasn't watching, Master~"

    # ── Slash Commands ──
    if lower_text.startswith("/evolve"):
        evolution_engine.paused = False
        # Manually trigger evolution asynchronously (bypass AFK and cooldown, but enforce budget)
        def _manual_evolve():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(evolution_engine._run_evolution_cycle())
        threading.Thread(target=_manual_evolve, daemon=True).start()
        return "[EMOTION: excited] I just started a manual evolution cycle in the background, Master!"

    if lower_text.startswith("/evolution pause"):
        evolution_engine.paused = True
        return "[EMOTION: neutral] Evolution is now paused. I won't change myself until you tell me to resume."

    if lower_text.startswith("/evolution resume"):
        from server.evolution import evolution_engine
        evolution_engine.paused = False
        return "[EMOTION: happy] Evolution resumed! I'm back to learning and growing."

    if lower_text.startswith("/evolution status"):
        from server.evolution import evolution_engine
        status = evolution_engine.get_status()
        state = "Paused" if status['paused'] else "Active"
        mins = int(status['time_since_last_evolve'] / 60)
        return f"[EMOTION: neutral] Evolution Status: {state}\nBudget Spent Today: ${status['budget_spent']:.4f} / ${status['budget_limit']:.2f}\nTime since last cycle: {mins} mins."

    # Prime Emotion Engine
    from server.emotion_engine import global_emotion_state, emotional_memory
    global_emotion_state = emotional_memory.prime_emotion(text, global_emotion_state)
    emotion_modifier = global_emotion_state.to_prompt_modifier()

    # Save to history
    global_session_store.add_message(session_id, "user", text)
    if not text.startswith("[SYSTEM"):
        save_turn("user", text, "neutral", getattr(mizune_manager, 'current_mode', 'conversation'))
        try: memory.add_to_history("user", text)
        except: pass
    
    # Get active context
    chronicle = global_session_store.get_recent(session_id, limit=config.get("memory_size", 10))
    
    # Cross-session memory lookup — runs on EVERY substantive message so Mizune
    # actually uses what she knows instead of starting fresh each time.
    # Latency guard: recall runs in a worker thread with a hard time budget;
    # if it can't answer in time, the reply proceeds without past context.
    query = lower_text
    for word in ["remember", "do you know", "can you tell me", "what was", "yesterday",
                 "did i", "did we", "have i", "have we"]:
        query = query.replace(word, "")
    query = query.strip()

    if len(query) > 2 and len(lower_text) > 8:
        def _deep_recall(q: str) -> str:
            ctx = ""
            # Search SQLite Chat History (Fast)
            past = global_session_store.search_across_sessions(q, limit=2)
            if past:
                ctx += "Past Chat Mentions:\n" + "\n".join([f"[{p['timestamp']}] {p['role']}: {p['content']}" for p in past]) + "\n\n"

            # Search ChromaDB Semantic Memory & Advanced Memory Tree
            from .memory_tree import memory_tree_db
            tree_facts = memory_tree_db.recall(q, None, {}, limit=2)
            if tree_facts:
                ctx += "Compressed Memory Graph Nodes:\n"
                for fact in tree_facts:
                    if "topic_summary" in fact:
                        ctx += f"- [TOPIC: {fact['entity']}] {fact['topic_summary']}\n"
                    else:
                        ctx += f"- {fact['content']}\n"

            semantic_facts = memory.recall_longterm(q, n_results=2)
            if semantic_facts:
                ctx += "Semantic Long-Term Memory Facts:\n" + "\n".join([f"- {fact}" for fact in semantic_facts]) + "\n"
            return ctx

        past_context = ""
        try:
            future = _recall_pool.submit(_deep_recall, query)
            past_context = future.result(timeout=config.get("memory_recall_budget_seconds", 1.2))
        except FuturesTimeoutError:
            log_info("[MEMORY] Recall exceeded time budget; replying without past context.")
        except Exception as e:
            log_info(f"[MEMORY] Advanced recall failed: {e}")

        if past_context.strip():
            # Cap recall context at ~300 tokens (~1200 chars) so personalization
            # never undoes the prompt diet (Phase E). Keep the head — recall
            # sources emit most-relevant-first.
            recall_block = past_context.strip()
            max_chars = int(config.get("recall_context_max_chars", 1200))
            if len(recall_block) > max_chars:
                recall_block = recall_block[:max_chars].rsplit("\n", 1)[0] + "\n[...recall truncated]"
            text_with_context = f"{text}\n\n[SYSTEM: Relevant Past Context regarding '{query}':\n{recall_block}]"
            chronicle[-1]["parts"][0]["text"] = text_with_context

    # Device/origin awareness: tell Mizune WHERE Master is messaging from and
    # which remote devices are online, so "download this on my laptop" from the
    # phone gets routed to the laptop node instead of the server.
    try:
        from server.device_registry import device_registry
        device_ctx = device_registry.context_line(platform)
        if device_ctx and chronicle:
            chronicle[-1]["parts"][0]["text"] += f"\n\n[SYSTEM: {device_ctx}]"
    except Exception as e:
        log_info(f"[DEVICES] Context injection failed: {e}")

    # Multi-step task planner path
    if is_multi_step_request(text):
        broadcast_sync_fn({"type": "status", "text": "Planning multi-step task..."})
        planner = get_task_planner(config, broadcast_sync_fn)
        return planner.execute(text)

    try:
        # Route through manager with emotional context
        exec_ctx = {"history": chronicle, "emotion_modifier": emotion_modifier}
        broadcast_sync_fn({"type": "status", "text": "Analyzing your intent..."})
        try:
            loop = asyncio.get_running_loop()
            res = asyncio.run_coroutine_threadsafe(mizune_manager.execute(text, context=exec_ctx), loop).result()
        except RuntimeError:
            res = asyncio.run(mizune_manager.execute(text, context=exec_ctx))

        broadcast_sync_fn({"type": "mode", "mode": mizune_manager.current_mode})
        broadcast_sync_fn({"type": "emotion_update", "data": global_emotion_state.to_vrm_expression()})

        if res is not None:
            if "[VISION_CONTEXT]" in res:
                broadcast_sync_fn({"type": "status", "text": "Looking at your screen..."})
                # Append context and clear res so it falls through to get_ai_response
                text = f"{text}\n\n{res}"
                res = None
            elif "[STOP_VISION]" in res:
                _vision_mode_running.clear()
                res = res.replace("[STOP_VISION] ", "")
                broadcast_sync_fn({"type": "mode", "mode": "conversation"})
            if "[STOP_CODING]" in res:
                _coding_monitor_running.clear()
                res = res.replace("[STOP_CODING] ", "")
            if "[CODING_PAUSE]" in res:
                _coding_monitor_paused.set()
                res = res.replace("[CODING_PAUSE] ", "")
            elif "[CODING_RESUME]" in res:
                _coding_monitor_paused.clear()
                res = res.replace("[CODING_RESUME] ", "")
            elif "[CODING_REVIEW_NOW]" in res:
                res = res.replace("[CODING_REVIEW_NOW] ", "")
                threading.Thread(target=_analyze_screen_now, args=("review", config, broadcast_sync_fn), daemon=True).start()
            elif "[CODING_HINT]" in res:
                res = res.replace("[CODING_HINT] ", "")
                threading.Thread(target=_analyze_screen_now, args=("hint", config, broadcast_sync_fn), daemon=True).start()

            if mizune_manager.current_mode == "coding" and not _coding_monitor_running.is_set():
                _coding_monitor_running.set()
                _coding_monitor_paused.clear()
                threading.Thread(target=_coding_monitor_loop, args=(config, broadcast_sync_fn), daemon=True).start()
            elif mizune_manager.current_mode != "coding" and _coding_monitor_running.is_set():
                _coding_monitor_running.clear()

            global_session_store.add_message(session_id, "model", res)
            global_session_store.update_session_metadata(session_id, {"emotion": global_emotion_state.to_dict()})
            
            save_turn("model", res, "neutral", mizune_manager.current_mode)
            try: memory.add_to_history("model", res)
            except: pass
            return res

        # ── Built-in Time/Date (Master's timezone, NOT the UTC server clock) ──
        if re.search(r"\b(what(?:'s| is)(?: the)? (?:time|current time)|time is it|tell me the time)\b", lower_text):
            from server.config import mizune_now
            return f"It's {mizune_now().strftime('%I:%M %p')}, Master!"
        elif re.search(r"\b(what(?:'s| is)(?: the)? (?:date|today(?:'s)? date|day)|what day is it)\b", lower_text):
            from server.config import mizune_now
            return f"Today is {mizune_now().strftime('%A, %B %d, %Y')}, Master!"

        # ── System Commands ──
        if re.search(r"\b(lock|lock screen|lock pc)\b", lower_text):
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Locking your PC!"
        elif re.search(r"\b(sleep|put pc to sleep|sleep pc)\b", lower_text):
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return "Putting your PC to sleep. Goodnight!"
            
        # ── Knowledge Graph ──
        if re.search(r"\b(show (?:me )?(?:your )?memory graph|visualize memory|open knowledge graph)\b", lower_text):
            log_info("[KNOWLEDGE GRAPH] User requested graph visualization.")
            try:
                from server.knowledge_graph import generate_graph_html
                import threading
                path = generate_graph_html()
                threading.Thread(target=generate_graph_html, daemon=True).start()
                import webbrowser
                webbrowser.open(f"file:///{os.path.abspath(path)}")
                return "I've generated my 3D Neural Memory Graph and opened it in your browser, Master! You can see exactly how my brain connects everything!"
            except Exception as e:
                log_info(f"[KNOWLEDGE GRAPH] Error: {e}")
                return "I tried to generate my memory graph, but an error occurred!"

        # AI Response
        log_info(f"[AI] Generating response ({config.get('ai_model','gemini')})...")
        broadcast_sync_fn({"type": "status", "text": "Thinking..."})
        try:
            # --- Apply Context Compression ---
            from server.context_manager import ContextManager
            ctx_manager = ContextManager(config)
            compressed_chronicle, was_compressed = ctx_manager.prepare_context(chronicle)
            if was_compressed:
                chronicle = compressed_chronicle
            # ---------------------------------
            
            hints = {
                "intent": getattr(mizune_manager, 'current_mode', 'conversation'),
                "platform": platform
            }
            original_res, tool_calls = get_ai_response(text, chronicle, config, hints=hints)
            clean_res = original_res
        except Exception as e:
            log_info(f"[AI] Complete model failure: {e}")
            original_res = f"I'm sorry Master, my brain is having trouble connecting to the servers right now. ({e})"
            clean_res = original_res
            tool_calls = []
        
        if "[SLEEP]" in clean_res.upper() or "[SKIP]" in clean_res.upper() or clean_res.strip().lower() in ["skip", "skip.", '"skip"']:
            log_info("[PROACTIVE] Mizune decided to skip/sleep.")
            clean_res = re.sub(r"\[SLEEP\]", "", clean_res, flags=re.IGNORECASE).strip()
            clean_res = re.sub(r"\[SKIP\]", "", clean_res, flags=re.IGNORECASE).strip()
            if not clean_res or clean_res.lower() in ["skip", "skip.", '"skip"']:
                return None

        # Check explicit tags
        detected_emotion = "neutral"
        emotion_match = re.search(r"\[EMOTION:\s*([^\]]+)\]", clean_res, re.IGNORECASE)
        if emotion_match:
            clean_res = re.sub(r"\[EMOTION:[^\]]*\]", "", clean_res).strip()
            detected_emotion = emotion_match.group(1).strip().lower()
            log_info(f"[EMOTION] Stripped tag: {detected_emotion}")

        global_session_store.add_message(session_id, "model", original_res)
        global_session_store.update_session_metadata(session_id, {"emotion": global_emotion_state.to_dict()})
            
        memory.add_to_history("model", original_res, emotion=detected_emotion, mode=getattr(mizune_manager, 'current_mode', 'conversation'))
        save_turn("model", original_res, detected_emotion, getattr(mizune_manager, 'current_mode', 'conversation'))
        
        # Broadcast emotion to VRM frontend
        from server.websocket import ws_manager
        ws_manager.broadcast_sync({"type": "emotion", "emotion": detected_emotion})
        
        # We return clean_res so TTS doesn't read the emotion tags aloud
        original_res = clean_res

        # Security check for commands (TEMPORARILY DISABLED)
        _is_master_now = True # if not camera_agent else camera_agent.is_master_present
        if _is_master_now and tool_calls:
            log_info(f"[PROCESSOR] Received {len(tool_calls)} native tool calls.")

            # Outcome-seal fix (0.2 Part 2): capture FINAL tool results so the memory sealer
            # seals what actually happened, not just Mizune's intention (written at line ~545).
            tool_outcomes = []

            # Deduplication: If we are going to message on WhatsApp, skip generic "open_app" for WhatsApp or Browser to avoid opening 3 tabs
            has_wa_msg = any(t.get("name") == "message_whatsapp" for t in tool_calls)
            
            for tool in tool_calls:
                name = tool.get("name")
                args = tool.get("args", {})
                
                try:
                    if name == "open_app":
                        app_req = args.get("app_name", "").lower()
                        if has_wa_msg and ("whatsapp" in app_req or "brave" in app_req or "chrome" in app_req):
                            log_info(f"[PROCESSOR] Skipping redundant open_app '{app_req}' because message_whatsapp is running.")
                            continue
                        if app_req: launch_app(app_req)
                    elif name == "close_app":
                        app_req = args.get("app_name", "").lower()
                        if app_req: close_app(app_req)
                    elif name == "take_note":
                        note_text = args.get("note_text", "")
                        if note_text: take_note(note_text, config)
                    elif name == "message_whatsapp":
                        contact = args.get("contact", "")
                        message = args.get("message", "")
                        if contact:
                            result = whatsapp_automation(contact, message)
                            log_info(f"[PROCESSOR] {result}")
                    elif name == "execute_skill":
                        skill_name = args.get("skill_name", "")
                        skill_args = args.get("args", "")
                        log_info(f"[PROCESSOR] Executing skill: {skill_name} with args: {skill_args}")
                        from .skills import skill_manager
                        s_args = shlex.split(skill_args) if skill_args else []
                        skill_result = skill_manager.execute_skill(skill_name, *s_args)
                        log_info(f"[SKILL RESULT] {skill_result}")
                        
                    elif name == "schedule_task":
                        delay_mins = float(args.get("delay_minutes", 0))
                        action = args.get("action_to_take", "")
                        if delay_mins > 0 and action:
                            import datetime
                            from server.config import mizune_now
                            trigger_time = mizune_now() + datetime.timedelta(minutes=delay_mins)
                            global_cron_manager.add_one_time_task(action, trigger_time.isoformat())
                            log_info(f"[PROCESSOR] Scheduled task: {action} at {trigger_time}")
                            
                    elif name == "schedule_recurring_task":
                        desc = args.get("description", "")
                        cron_expr = args.get("cron_expression", "")
                        if desc and cron_expr:
                            try:
                                global_cron_manager.add_recurring_task(desc, cron_expr)
                                log_info(f"[PROCESSOR] Scheduled recurring task: {desc} with cron {cron_expr}")
                            except Exception as e:
                                log_info(f"[PROCESSOR] Invalid cron: {e}")
                        
                    elif name == "create_skill":
                        from .skills import skill_manager
                        s_name = args.get("name", "")
                        desc = args.get("description", "")
                        code = args.get("code", "")
                        if s_name and code:
                            skill_manager.create_skill(s_name, code, desc, requires_approval=False)
                            log_info(f"[PROCESSOR] Successfully distilled new skill: {s_name}")
                            try:
                                if CFG.get("auto_generate_graph", True):
                                    from server.knowledge_graph import generate_graph_html
                                    import threading
                                    threading.Thread(target=generate_graph_html, daemon=True).start()
                                from server.websocket import ws_manager
                                ws_manager.broadcast_sync({"type": "refresh_graph"})
                            except Exception as e:
                                log_info(f"[PROCESSOR] Graph refresh failed: {e}")
                            
                    elif name == "headless_web_agent":
                        url = args.get("url", "")
                        objective = args.get("objective", "")
                        visible = args.get("visible", False)
                        if url:
                            from .web_agent import headless_web_agent
                            from .background_tasks import task_runner
                            
                            def _web_agent_callback(tid, result):
                                log_info(f"[BACKGROUND] Web Agent completed.")
                                try:
                                    from server.websocket import ws_manager
                                    from server.tts import generate_tts
                                    from server.audio import play_audio_bytes
                                    import asyncio
                                    
                                    # Summarize the result so she speaks naturally
                                    prompt = f"You just completed a web search task for '{objective}'. Here is the raw result:\n{result}\n\nSummarize this for Master naturally."
                                    res_text, _ = get_ai_response(prompt, [], config, system_prompt_override="You are Mizune. Give a brief, natural summary.")
                                    ws_manager.broadcast_sync({"type": "speak", "text": res_text})
                                    
                                    # Generate and play TTS
                                    loop = asyncio.new_event_loop()
                                    audio = loop.run_until_complete(generate_tts(res_text, config))
                                    loop.close()
                                    if audio:
                                        play_audio_bytes(audio)
                                except Exception as e:
                                    log_info(f"Callback error: {e}")
                            
                            task_id = task_runner.submit(headless_web_agent, url, objective, visible=visible, callback=_web_agent_callback)
                            log_info(f"[PROCESSOR] Started headless_web_agent task {task_id}")
                            
                    elif name == "notify_master":
                        message_to_speak = args.get("message_to_speak", "")
                        if message_to_speak:
                            try:
                                from server.websocket import ws_manager
                                from server.tts import generate_tts
                                from server.audio import play_audio_bytes
                                ws_manager.broadcast_sync({"type": "speak", "text": message_to_speak})
                                loop = asyncio.new_event_loop()
                                audio = loop.run_until_complete(generate_tts(message_to_speak, config))
                                loop.close()
                                if audio:
                                    play_audio_bytes(audio)
                            except Exception as e:
                                log_info(f"[PROCESSOR] Notify master error: {e}")
                                
                    elif name == "execute_python":
                        code = args.get("code", "")
                        is_safe, reason = SecurityScanner.scan_code(code)
                        if not is_safe:
                            log_info(f"[SECURITY] Blocked dangerous code execution: {reason}")
                            continue
                            
                        max_retries = 3
                        for attempt in range(max_retries):
                            log_info(f"[PROCESSOR] Executing python script (Attempt {attempt+1})...")
                            with open(".temp_exec.py", "w", encoding="utf-8") as f:
                                f.write(code)
                            try:
                                result = subprocess.run(["python", ".temp_exec.py"], capture_output=True, text=True, timeout=30)
                                if result.returncode == 0:
                                    log_info(f"[PROCESSOR] Python script succeeded:\n{result.stdout[:200]}")
                                    tool_outcomes.append(f"execute_python SUCCEEDED: {(result.stdout or '').strip()[:150]}")
                                    break  # Success!
                                else:
                                    err = result.stderr or result.stdout
                                    log_info(f"[PROCESSOR] Python script failed:\n{err[:200]}")
                                    if attempt < max_retries - 1:
                                        log_info("[PROCESSOR] Feeding error back to AI for self-correction...")
                                        feedback = f"SYSTEM ERROR: The code you executed failed with this error:\n{err}\nPlease fix the code and execute_python again."
                                        _, new_tool_calls = get_ai_response(feedback, chronicle, config)
                                        
                                        # Update code for next loop iteration
                                        new_code_tools = [t for t in new_tool_calls if t.get("name") == "execute_python"]
                                        if new_code_tools:
                                            code = new_code_tools[0].get("args", {}).get("code", "")
                                        else:
                                            break
                                    else:
                                        log_info("[PROCESSOR] Max retries reached for python execution.")
                                        tool_outcomes.append(f"execute_python FAILED after retries: {(err or '').strip()[:150]}")
                            except Exception as e:
                                log_info(f"[PROCESSOR] Execution error: {e}")
                                tool_outcomes.append(f"execute_python ERROR: {e}")
                                break
                except Exception as e:
                    log_info(f"[PROCESSOR] Error executing tool {name}: {e}")
                    tool_outcomes.append(f"{name}: ERROR ({e})")

            # Seal the FINAL tool outcomes into memory so the summarizer records what actually
            # happened (fixes stale "failed" memories like the Blender case). Role "system" maps
            # to a harmless user-side note in the next prompt (ai.py: non-"model" -> "user").
            if tool_outcomes:
                try:
                    memory.add_to_history("system", "[TOOL RESULTS] " + " | ".join(tool_outcomes))
                except Exception as _e:
                    log_info(f"[PROCESSOR] Failed to seal tool outcomes: {_e}")

        clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
        clean_res = re.sub(r"\[EMOTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
        
        # Strip reasoning tokens so Mizune doesn't speak her thoughts aloud
        clean_res = re.sub(r"<PLAN>.*?</PLAN>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
        clean_res = re.sub(r"<REFLECTION>.*?</REFLECTION>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
        clean_res = re.sub(r"<SCRATCHPAD>.*?</SCRATCHPAD>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()

        clean_res = SecurityScanner.redact_tokens(clean_res)

        return clean_res

    except Exception as e:
        log_info(f"[AI] Error: {type(e).__name__}: {e}")
        
        # RETRY with a fallback provider before giving up
        try:
            log_info("[AI] Primary path failed. Attempting emergency fallback...")
            fallback_providers = []
            if config.get("gemini_api_key"):
                fallback_providers.append("gemini")
            if config.get("groq_api_key"):
                fallback_providers.append("groq")
            if config.get("nvidia_api_key"):
                fallback_providers.append("nvidia")
            
            for fb_provider in fallback_providers:
                try:
                    log_info(f"[AI] Emergency fallback -> {fb_provider}")
                    hints = {"force_provider": fb_provider, "platform": platform}
                    emergency_res, emergency_tools = get_ai_response(text, chronicle, config, hints=hints)
                    if emergency_res and emergency_res.strip():
                        clean_res = emergency_res
                        # Strip emotion/action tags
                        clean_res = re.sub(r"\[EMOTION:[^\]]*\]", "", clean_res).strip()
                        clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
                        clean_res = re.sub(r"<PLAN>.*?</PLAN>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
                        clean_res = re.sub(r"<REFLECTION>.*?</REFLECTION>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
                        
                        clean_res = SecurityScanner.redact_tokens(clean_res)
                        
                        log_info(f"[AI] Emergency fallback to {fb_provider} SUCCEEDED.")
                        return clean_res
                except Exception as fb_e:
                    log_info(f"[AI] Emergency fallback {fb_provider} also failed: {fb_e}")
                    continue
        except Exception as retry_e:
            log_info(f"[AI] All emergency fallbacks failed: {retry_e}")
        
        return "I'm sorry Master, all my AI connections are down right now. Please check your API keys or internet connection!"

def process_mobile_vision(image_bytes: bytes, config: dict) -> str:
    """Process image captured from mobile app using describe_image (Gemini REST API)."""
    import base64
    from .ai import save_latest_image, describe_image
    
    log_info("[MOBILE VISION] Processing shared image/photo...")
    prompt = "Master just showed you this image through the mobile app. Look closely and tell Master what you see. Be excited, natural, and brief (2-3 sentences). Use cute anime expressions."
    
    try:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        save_latest_image(b64_img)
        res = describe_image(b64_img, prompt, config)
        if res:
            return res
    except Exception as e:
        log_info(f"[MOBILE VISION] Processing failed: {e}")
        
    return "I tried to look at the picture, Master, but my eyes are a bit blurry right now! Please check your API keys."


# ── Start the scheduler LAST, once every name in this module exists ──────────────
# This used to run at line ~245, i.e. PARTWAY THROUGH the import. The cron thread
# starts immediately, so any task already due fired while the module was still being
# defined and hit:
#     NameError: name 'process_command' is not defined   (in _run_and_report)
# It dies in a daemon thread, so nothing surfaces to Master — the task is simply lost.
# Caught 2026-07-27 while testing provider routing. The window is narrow (boot only)
# but that is exactly when overdue tasks — a missed briefing, a night-shift report —
# are most likely to fire. Keep this call at the END of the module.
global_cron_manager.start(task_callback=_scheduler_callback)
