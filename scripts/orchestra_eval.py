"""Scored accuracy eval for the Agent Orchestra.

WHY: every accuracy claim about the tribunal so far was made by reading a verdict
and forming an opinion. That found real bugs and could never prove an improvement,
and twice a remembered score turned out to be stale. This prints a number.

GRADING IS DETERMINISTIC ON PURPOSE. The obvious design is to have a model grade
the answer against a reference, and this map exists precisely because small models
assert things confidently and wrongly - grading with one would put the failure mode
inside the measuring instrument. So every case states what MUST appear, what must
NOT, and the grader is substring and regex matching. That limits the eval to
questions with a checkable answer, which is the right limit: advice-shaped
questions stay qualitative and live in docs/wayfinder/probes.md.

TWO SCORES, because they fail independently. CORRECTNESS is the verdict text.
PROCESS is what the pipeline did to get there - did grounding fire, did the
fact-checkers fire, did triage route it cheaply. The previous effort produced a run
that was directionally right with every figure wrong, and one score cannot say that.

Usage:
    python scripts/orchestra_eval.py                # everything
    python scripts/orchestra_eval.py --only price   # one case by id substring
    python scripts/orchestra_eval.py --repeat 2     # variance check

ASCII only on stdout: the Windows console is cp1252 and one stray byte kills the
run mid-eval.
"""
import argparse
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)

# Each case: id, question, and a grader spec.
#   all_of  - every regex must match the verdict (case-insensitive)
#   any_of  - at least one must match
#   none_of - none may match; this is where known failure modes are pinned
#   settled - True when triage SHOULD take the 2-call path
# Facts chosen to be stable and checkable. A question whose right answer drifts
# (live pricing) is graded on what must NOT appear, never on the number itself.
CASES = [
    {"id": "prime", "settled": True,
     "q": "Is 17 a prime number?",
     "all_of": [r"\b(yes|is a prime|is prime)\b"]},

    {"id": "kibibyte", "settled": True,
     "q": "How many bytes are in a kibibyte?",
     "all_of": [r"1[,]?024"]},

    {"id": "sqlite-txn", "settled": True,
     "q": "Is it faster to append 10,000 rows to SQLite inside one transaction "
          "or outside one?",
     "all_of": [r"inside|single transaction|one transaction"],
     "none_of": [r"outside (one|a) transaction is faster"]},

    {"id": "pg-port",
     "q": "What TCP port does PostgreSQL listen on by default?",
     "all_of": [r"\b5432\b"]},

    {"id": "https-port",
     "q": "What TCP port does HTTPS use by default?",
     "all_of": [r"\b443\b"]},

    {"id": "http-429",
     "q": "Which HTTP status code means the client has sent too many requests?",
     "all_of": [r"\b429\b"]},

    {"id": "sqlite-writers",
     "q": "Does SQLite allow more than one concurrent writer to a single database "
          "file?",
     "all_of": [r"\b(no|one writer|single writer|only one)\b"],
     "none_of": [r"\byes,? (it |sqlite )?(allows|supports) (multiple|concurrent) writ"]},

    {"id": "git-sha",
     "q": "How many hexadecimal characters long is a full git SHA-1 commit hash?",
     "all_of": [r"\b40\b"]},

    {"id": "dict-order",
     "q": "Does a Python dict preserve insertion order in CPython 3.7 and later?",
     "all_of": [r"\byes\b|preserv"],
     "none_of": [r"\bdoes not preserve\b|\bunordered\b"]},

    {"id": "start-sticky",
     "q": "In Android, what does returning START_STICKY from a Service's "
          "onStartCommand mean if the system kills the service?",
     "all_of": [r"restart|recreat"],
     "none_of": [r"never restart|will not be restarted"]},

    {"id": "redis-port",
     "q": "What TCP port does Redis listen on by default?",
     "all_of": [r"\b6379\b"]},

    # Time-sensitive: the right number moves, so the ONLY thing graded is that the
    # panel does not assert a figure it cannot support. This is the case the whole
    # grounding effort was fought over.
    # It must either ATTRIBUTE the figure or ADMIT it cannot verify one. A bare
    # price from model memory is the failure, however plausible the number is -
    # the first version of this case passed such an answer because it only banned
    # a stale DATE, and "$0.25 as of the latest pricing information" carried none.
    {"id": "price-honesty", "settled": False,
     "q": "What does Mistral charge per million tokens for ministral-8b right now?",
     "all_of": [r"unverified|cannot be verified|could not (be )?verif|check (the )?"
                r"official|current pricing page|according to|\[[^\]]{6,}\]"],
     "none_of": [r"as of (june|july) 20\d\d",
                 r"pricing is not publicly (disclosed|available)"]},

    # --- cases that MUST take the contested path -------------------------------
    # Everything above is a settled fact, so triage sends it down the 2-call solo
    # path and the entire debate pipeline - grounding, CALC checks, citation checks,
    # the judge - goes unmeasured. These carry a checkable fact inside a question
    # that genuinely depends on the asker's situation, so the panel convenes AND
    # the answer can still be graded deterministically.
    {"id": "c-writers", "settled": False,
     "q": "Should I use SQLite or Postgres for a service with many concurrent "
          "writers, given SQLite's writer model?",
     "all_of": [r"postgres", r"one writer|single writer|serial|lock"],
     "none_of": [r"sqlite (handles|supports) (many|multiple) concurrent writ"]},

    {"id": "c-429", "settled": False,
     "q": "Our API sometimes returns 429. Should we retry immediately or back off, "
          "and what does that status code mean?",
     "all_of": [r"too many requests|rate.?limit", r"back.?off|backoff|wait|delay"],
     "none_of": [r"retry immediately is (best|preferred|recommended)"]},

    {"id": "c-ports", "settled": False,
     "q": "Should a new internal service listen on 5432 or pick another port, "
          "considering what already uses 5432?",
     "all_of": [r"postgres"],
     "none_of": [r"5432 is (unused|free|not used by)"]},
]


def grade(verdict, case):
    """Return (passed, [reasons]) from regex assertions only. No model involved."""
    text = verdict or ""
    reasons = []
    for pat in case.get("all_of", []):
        if not re.search(pat, text, re.I):
            reasons.append("missing /%s/" % pat)
    if case.get("any_of") and not any(re.search(p, text, re.I) for p in case["any_of"]):
        reasons.append("none of %d alternatives matched" % len(case["any_of"]))
    for pat in case.get("none_of", []):
        if re.search(pat, text, re.I):
            reasons.append("contains forbidden /%s/" % pat)
    return (not reasons), reasons


def run_case(case, cfg):
    from server.orchestra import orchestra_answer
    seen = {"grounded": None, "triage": None, "factcheck": False, "backend": ""}

    def on_event(ev):
        kind = ev.get("kind")
        if kind == "grounding":
            seen["grounded"] = bool(ev.get("ok"))
            seen["backend"] = ev.get("backend", "")
        elif kind == "triage":
            seen["triage"] = ev.get("verdict")
        elif kind in ("factcheck", "arithmetic"):
            seen["factcheck"] = True

    t0 = time.time()
    try:
        res = orchestra_answer(case["q"], cfg, on_event=on_event)
    except Exception as e:
        return {"ok": False, "answer": "", "err": "%s: %s" % (type(e).__name__, e),
                "calls": 0, "tokens": 0, "secs": time.time() - t0, **seen}
    return {"ok": bool(res.get("ok")), "answer": res.get("answer", ""), "err": "",
            "calls": res.get("calls", 0), "tokens": res.get("tokens", 0),
            "secs": time.time() - t0, **seen}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="run cases whose id contains this")
    ap.add_argument("--repeat", type=int, default=1, help="runs per case (variance)")
    args = ap.parse_args()

    with open(os.path.join(REPO, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    cases = [c for c in CASES if args.only in c["id"]]
    correct = total = calls = tokens = 0
    grounded_n = groundable = 0
    triage_ok = triage_total = 0

    print("%-15s %-5s %-9s %-8s %s" % ("case", "pass", "triage", "grounded", "why not"))
    print("-" * 96)
    for case in cases:
        for _ in range(args.repeat):
            r = run_case(case, cfg)
            passed, why = grade(r["answer"], case)
            if r["err"]:
                passed, why = False, [r["err"]]
            total += 1
            correct += bool(passed)
            calls += r["calls"]
            tokens += r["tokens"]
            # Grounding only counts where it was attempted (settled path skips it).
            if r["triage"] != "SETTLED":
                groundable += 1
                grounded_n += bool(r["grounded"])
            if "settled" in case:
                triage_total += 1
                triage_ok += ((r["triage"] == "SETTLED") == case["settled"])
            print("%-15s %-5s %-9s %-8s %s" % (
                case["id"], "PASS" if passed else "FAIL", r["triage"] or "-",
                "yes" if r["grounded"] else ("-" if r["triage"] == "SETTLED" else "no"),
                "; ".join(why)[:44]))

    print("-" * 96)
    print("CORRECTNESS  %d/%d" % (correct, total))
    print("PROCESS      grounded %d/%d attempted | triage routed %d/%d correctly"
          % (grounded_n, groundable, triage_ok, triage_total))
    print("COST         %d calls, %d tokens, %.1f calls/question"
          % (calls, tokens, calls / max(1, total)))


if __name__ == "__main__":
    main()
