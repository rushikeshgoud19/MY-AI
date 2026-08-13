#!/usr/bin/env python
"""Capability contract PoC: ONE capability (schedule_task) proved end-to-end.

WHY THIS FILE EXISTS
--------------------
Three separate times this project shipped a check that could not fail:

  - the nightly build log ran 3 nights and collected nothing; every layer was "fine"
  - the deploy smoke gate stayed GREEN over a dead Google Calendar for days, because it
    passed unless the reply contained one of four exact phrases
  - a privacy test passed by checking the reply contained the word "sorry"

All three share one shape: the check read the AGENT'S WORDS instead of the WORLD.
`schedule_task` returns the string "Task scheduled successfully for 06:30 PM." whether or
not a row ever reached data/schedules.db. Every layer above it -- the model, the reply, a
smoke test, a human reading the chat -- sees success. Nothing in that chain can see the gap.

So this file does the only thing that closes it: after the action, go LOOK at
`one_time_tasks` and demand a row that did not exist a moment ago, with the right
description, unexecuted, at the right trigger time. That is the capability contract for
schedule_task, and it is enforced by stepproof's `@verified(verifier=...)`.

BOTH DIRECTIONS ARE DEMONSTRATED, because a check that has never been seen to fail is not
evidence of anything (see docs/HARNESS_DESIGN.md, "negative-control rule"):

  DIRECTION 1 (green)  real CronManager write   -> row present   -> seal verified=True
  DIRECTION 2 (red)    "break it" fixture that returns the SAME success string and writes
                       nothing                  -> row absent    -> VerificationError

Run:
    .venv\\Scripts\\python.exe scripts\\harness_poc.py

Exit 0 means BOTH directions behaved: the check went green on a real write AND red on a
silent no-op. Exit 1 means the harness itself is broken and must not be trusted.

Touches nothing in server/. Writes only to a throwaway temp directory.
"""
from __future__ import annotations

import contextlib
import datetime
import io
import logging
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _ascii(text):
    """This console is cp1252. stepproof's report() uses em-dashes; a UnicodeEncodeError
    mid-run would make the harness itself the thing that silently didn't happen."""
    return str(text).encode("ascii", "replace").decode("ascii")


# ---------------------------------------------------------------------------
# stepproof bootstrap
# ---------------------------------------------------------------------------
# Normally `pip install stepproof`. Until that lands in .venv, fall back to the local
# working copy so this file is runnable TODAY -- a design document whose proof does not
# execute is exactly the class of artifact this harness exists to distrust.
def _load_stepproof():
    try:
        import stepproof  # noqa: F401
        return "site-packages"
    except ImportError:
        pass
    repo = os.environ.get("STEPPROOF_REPO") or os.path.join(
        os.path.expanduser("~"), "OneDrive", "Desktop", "agentse")
    if os.path.isdir(os.path.join(repo, "stepproof")):
        sys.path.insert(0, repo)
        import stepproof  # noqa: F401
        return repo
    raise SystemExit(
        "stepproof not found. Run: .venv\\Scripts\\python.exe -m pip install stepproof\n"
        "or set STEPPROOF_REPO to the local checkout.")


_STEPPROOF_FROM = _load_stepproof()

from stepproof import Ledger, VerificationError, report, set_ledger, verified  # noqa: E402


# ---------------------------------------------------------------------------
# THE CAPABILITY CONTRACT -- schedule_task
# ---------------------------------------------------------------------------
# Ground truth: server/scheduler.py:CronManager.add_one_time_task inserts into
#   one_time_tasks(id, description, trigger_time, executed)
# in data/schedules.db. The contract below is the ONLY definition of "it happened".
#
# Four conjuncts, and each one is load-bearing:
#   1. the row exists at all                 -- catches the silent no-op
#   2. id > baseline_id                      -- catches a PRE-EXISTING identical row being
#                                               mistaken for the one we just made
#   3. description matches exactly           -- catches a write that dropped/mangled the text
#   4. trigger_time within TOLERANCE_S       -- catches a timezone bug, which is the way this
#                                               capability actually rots: the row is there,
#                                               so an existence-only check passes, and the
#                                               reminder fires at 06:30 UTC instead of IST
#   5. executed = 0                          -- an already-fired row is not a future reminder
#
# Conjunct 3 uses a PARAMETERIZED query, not stepproof's `sqlite ... where ...` clause DSL,
# because `action_to_take` is MODEL OUTPUT. stepproof's own collector docstring says the
# `where` string must come from your code and never from model output; honouring that is
# the difference between a verifier and a SQL injection.

TOLERANCE_S = 90.0


def schedule_task_evidence(db_path, action_to_take, expected_trigger_iso, baseline_id, **_):
    """Return (ok, evidence). Evidence is prose a human can audit six weeks later."""
    if not os.path.exists(db_path):
        return False, "no scheduler database at " + db_path

    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT id, description, trigger_time, executed FROM one_time_tasks "
            "WHERE description = ? AND id > ? ORDER BY id DESC",
            (action_to_take, baseline_id)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM one_time_tasks").fetchone()[0]
        con.close()
    except sqlite3.Error as exc:
        return False, "query failed on " + db_path + ": " + str(exc)

    if not rows:
        return False, (
            "NO new row in one_time_tasks for description "
            + repr(action_to_take[:60])
            + " (table holds " + str(total) + " row(s), none newer than id "
            + str(baseline_id) + ") -- the task was reported scheduled but nothing "
            "will ever fire")

    row_id, desc, trigger_time, executed = rows[0]

    if executed:
        return False, ("row id=" + str(row_id) + " exists but executed=1 -- this is a "
                       "spent row, not a pending reminder")

    try:
        actual = datetime.datetime.fromisoformat(trigger_time)
        expected = datetime.datetime.fromisoformat(expected_trigger_iso)
    except ValueError as exc:
        return False, ("row id=" + str(row_id) + " has an unparseable trigger_time "
                       + repr(trigger_time) + ": " + str(exc))

    if (actual.tzinfo is None) != (expected.tzinfo is None):
        return False, ("row id=" + str(row_id) + " trigger_time " + repr(trigger_time)
                       + " has different tz-awareness than expected "
                       + repr(expected_trigger_iso) + " -- it will fire at the wrong hour")

    drift = abs((actual - expected).total_seconds())
    if drift > TOLERANCE_S:
        return False, ("row id=" + str(row_id) + " trigger_time is " + str(trigger_time)
                       + ", expected " + str(expected_trigger_iso) + " -- off by "
                       + ("%.0f" % drift) + "s, beyond the " + ("%.0f" % TOLERANCE_S)
                       + "s tolerance")

    return True, ("one_time_tasks id=" + str(row_id) + " description=" + repr(desc[:50])
                  + " trigger_time=" + str(trigger_time) + " executed=0, drift "
                  + ("%.1f" % drift) + "s (table now holds " + str(total) + " row(s))")


# ---------------------------------------------------------------------------
# DIRECTION 1 -- the real thing
# ---------------------------------------------------------------------------
@verified(verifier=schedule_task_evidence,
          actor="mizune.tool.schedule_task",
          authorization="master:chat-request")
def schedule_task_real(db_path, action_to_take, delay_minutes,
                       expected_trigger_iso, baseline_id):
    """Mirrors server/ai.py:1441 -- same write, same success string it hands the model."""
    # Importing anything under server/ drags in skill loading and chatty INFO logs. Muffle
    # them so the harness's OWN verdict is the only thing on stdout.
    logging.disable(logging.INFO)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from server.scheduler import CronManager
            CronManager(db_path=db_path).add_one_time_task(action_to_take, expected_trigger_iso)
    finally:
        logging.disable(logging.NOTSET)
    stamp = datetime.datetime.fromisoformat(expected_trigger_iso).strftime("%I:%M %p")
    return "Task scheduled successfully for " + stamp + "."


# ---------------------------------------------------------------------------
# DIRECTION 2 -- the "break it" fixture (the negative control)
# ---------------------------------------------------------------------------
# This is the ONLY reason to trust direction 1. It reproduces the real failure mode
# faithfully: identical return string, no exception, no log line, no row. If the check
# cannot go red here, it is decoration and must not be registered.
@verified(verifier=schedule_task_evidence,
          actor="mizune.tool.schedule_task",
          authorization="negative-control:fixture")
def schedule_task_broken(db_path, action_to_take, delay_minutes,
                         expected_trigger_iso, baseline_id):
    """Returns success. Writes nothing. Nobody lies; the reminder never fires."""
    stamp = datetime.datetime.fromisoformat(expected_trigger_iso).strftime("%I:%M %p")
    return "Task scheduled successfully for " + stamp + "."


# One fixture per CONJUNCT, not one per check -- otherwise the weak conjuncts are never
# exercised and the contract quietly degrades to "a row exists". This one writes a REAL row
# at the WRONG hour (naive UTC instead of aware IST -- the exact shape of the legacy rows
# server/scheduler.py:_as_aware exists to paper over). An existence-only check passes here.
# The contract must not.
@verified(verifier=schedule_task_evidence,
          actor="mizune.tool.schedule_task",
          authorization="negative-control:fixture")
def schedule_task_wrong_hour(db_path, action_to_take, delay_minutes,
                             expected_trigger_iso, baseline_id):
    """Writes the row, but 5h30m off. The reminder fires -- at the wrong time."""
    skewed = (datetime.datetime.fromisoformat(expected_trigger_iso)
              .astimezone(datetime.timezone.utc).replace(tzinfo=None))
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO one_time_tasks (description, trigger_time) VALUES (?, ?)",
                (action_to_take, skewed.isoformat()))
    con.commit()
    con.close()
    stamp = datetime.datetime.fromisoformat(expected_trigger_iso).strftime("%I:%M %p")
    return "Task scheduled successfully for " + stamp + "."


# ---------------------------------------------------------------------------
# harness plumbing
# ---------------------------------------------------------------------------
def _baseline_max_id(db_path):
    """Snapshot BEFORE acting, so 'a row exists' cannot be satisfied by an old row."""
    if not os.path.exists(db_path):
        return 0
    try:
        con = sqlite3.connect(db_path)
        val = con.execute("SELECT COALESCE(MAX(id), 0) FROM one_time_tasks").fetchone()[0]
        con.close()
        return val
    except sqlite3.Error:
        return 0


def _expected_trigger(delay_minutes):
    """The trigger time the contract will demand. Computed BEFORE the action, on purpose:
    an expectation derived from the result is not an expectation."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist)
    return (now + datetime.timedelta(minutes=delay_minutes)).isoformat()


def main():
    workdir = tempfile.mkdtemp(prefix="mizune_harness_")
    db_path = os.path.join(workdir, "data", "schedules.db")
    ledger_path = os.path.join(workdir, "ledger.jsonl")
    set_ledger(Ledger(path=ledger_path))

    print("MIZUNE CAPABILITY HARNESS -- PoC: schedule_task")
    print("=" * 62)
    print("stepproof loaded from : " + _STEPPROOF_FROM)
    print("scratch scheduler db  : " + db_path)
    print("")

    action = "Speak out loud: Master, the harness proof is due."
    delay = 45.0
    outcomes = []

    # ---- DIRECTION 1: it must go GREEN when the effect is real -------------
    print("[1/3] GREEN DIRECTION -- real CronManager write, row should exist")
    baseline = _baseline_max_id(db_path)
    expected = _expected_trigger(delay)
    try:
        claim = schedule_task_real(db_path, action, delay, expected, baseline)
        print("      tool claimed  : " + claim)
        print("      verdict       : PASS (evidence found)")
        outcomes.append(True)
    except VerificationError as exc:
        print("      verdict       : UNEXPECTED FAIL -- " + str(exc)[:160])
        outcomes.append(False)

    print("")

    # ---- DIRECTION 2: it must go RED when the effect is absent -------------
    print("[2/3] RED DIRECTION -- 'break it' fixture, same success string, no row")
    baseline = _baseline_max_id(db_path)
    expected = _expected_trigger(delay)
    broken_action = action + " (negative control)"
    try:
        claim = schedule_task_broken(db_path, broken_action, delay, expected, baseline)
        print("      tool claimed  : " + claim)
        print("      verdict       : DID NOT FAIL -- the check is decorative, DO NOT SHIP")
        outcomes.append(False)
    except VerificationError as exc:
        print("      tool claimed  : Task scheduled successfully ...  (a lie by omission)")
        print("      verdict       : PASS (check went red as designed)")
        print("      caught        : " + _ascii(exc)[:200])
        outcomes.append(True)

    print("")

    # ---- DIRECTION 3: RED on a real row at the wrong hour -------------------
    print("[3/3] RED DIRECTION -- row IS written, but 5h30m off (tz rot)")
    baseline = _baseline_max_id(db_path)
    expected = _expected_trigger(delay)
    skew_action = action + " (tz negative control)"
    try:
        schedule_task_wrong_hour(db_path, skew_action, delay, expected, baseline)
        print("      verdict       : DID NOT FAIL -- contract degraded to 'a row exists'")
        outcomes.append(False)
    except VerificationError as exc:
        print("      verdict       : PASS (a trigger_time conjunct went red)")
        print("      caught        : " + _ascii(exc)[-190:])
        outcomes.append(True)

    # ---- the audit artifact ------------------------------------------------
    print("")
    print(_ascii(report()))
    print("")
    ok, detail = Ledger(path=ledger_path).verify_chain()
    print("ledger file           : " + ledger_path)
    print("tamper check          : " + ("INTACT" if ok else "BROKEN") + " -- " + _ascii(detail))

    print("")
    passed = all(outcomes)
    if passed:
        print("HARNESS SELF-TEST: PASS -- the schedule_task check demonstrably goes both "
              "green and red.")
    else:
        print("HARNESS SELF-TEST: FAIL -- this check has NOT earned the right to be "
              "registered.")

    shutil.rmtree(workdir, ignore_errors=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
