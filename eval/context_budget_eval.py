#!/usr/bin/env python3
"""What does Mizune's hard context budget cost in answer quality?

`ContextManager.hard_budget` (server/context_manager.py) keeps prompts small by
dropping the OLDEST turns until history fits. That is the knob behind the input-token
reduction. This measures the other side of the trade: how far back a fact can sit and
still be there when it is needed.

THE QUESTION THIS ANSWERS
    Not "did trimming hurt?" — trimming always hurts eventually. The useful number is
    the RECALL HORIZON: at a given budget, the greatest conversational depth at which
    a fact is still recoverable. Below the horizon the budget is free. Above it, the
    fact is gone before the model is ever asked, and no better model recovers it.

METHOD — the grader is exact match, not a model.
    Each probe plants a distinctive token ("my deploy key is NOVA-7731") in an early
    turn, buries it under D filler exchanges, and asks for it back. An answer is
    correct iff it contains the planted token. There is no LLM judge, so there is no
    judge to calibrate: correctness here is decidable, and decidable things belong in
    code. (Same principle as ADOPT_MIN_SCORE in server/orchestra.py, and for the same
    reason — a prompted judge finds a way to pass everything.)

TWO TIERS
    offline (default)  no API calls. Runs the real ContextManager over a
                       depth x budget grid and reports whether the planted fact
                       SURVIVED the trim. This is the ceiling on answer quality.
    live (--live)      at the production budget, calls Mistral across the depth sweep
                       and grades the actual answers. Retention is the ceiling; this
                       is how close the model gets to it.

USAGE
    python eval/context_budget_eval.py
    python eval/context_budget_eval.py --live
    python eval/context_budget_eval.py --json eval/results.json

Run from the repository root.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import statistics
import sys
import time
import types
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "server"

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
LIVE_MODEL = "mistral-small-latest"

# `context_token_budget` in config.json. 4000 is what production runs.
PRODUCTION_BUDGET = 4000
BUDGETS: List[int] = [1000, 2000, 4000, 8000]

# Filler exchanges between the planted fact and the question. One exchange is a
# user turn plus a model turn.
DEPTHS: List[int] = [0, 2, 4, 8, 12, 16, 24, 32, 48]

# Live tier is expensive in calls, so it sweeps depth at one budget.
LIVE_DEPTHS: List[int] = [0, 4, 8, 12, 16, 24, 32]


# --------------------------------------------------------------------------- imports
def load_context_manager():
    """Import server.context_manager WITHOUT executing server/__init__.py.

    server/__init__.py eagerly imports audio, vision, tts and agents — microphone and
    camera modules that have no business loading inside an eval, and that have been
    observed to rewrite tracked files as a side effect. Registering a bare package
    object with a __path__ lets the module's relative imports (`.tokenjuice`,
    `.config`) resolve against the real files while the package __init__ never runs.
    """
    if "server" not in sys.modules:
        pkg = types.ModuleType("server")
        pkg.__path__ = [str(SERVER_DIR)]  # makes `from .tokenjuice import ...` resolve
        sys.modules["server"] = pkg

    cm = importlib.import_module("server.context_manager")

    # config.log_info appends to server_debug.log. An eval must not write to the
    # running system's log, so silence it for this process only.
    cm.log_info = lambda *_a, **_k: None
    return cm.ContextManager


# --------------------------------------------------------------------------- corpus
# Filler turn lengths mirror the real distribution in .data/session_store.db
# (session 'main': n=367 turns with counts, min 1 / median 24 / max 254 tokens).
# Synthetic rather than copied, so no private conversation content lives in the repo.
FILLER_MIN_TOKENS, FILLER_MED_TOKENS, FILLER_MAX_TOKENS = 8, 24, 254

_FILLER_WORDS = (
    "server restart queue latency memory disk cache retry backlog worker schedule "
    "deploy rollback metric alert threshold window session token prompt context "
    "battery sensor sync upload digest reminder calendar summary note draft"
).split()

_SUBJECTS = [
    ("deploy key", "NOVA"), ("backup code", "ORCA"), ("router tag", "FLINT"),
    ("build slot", "CEDAR"), ("mesh id", "HALO"), ("vault pin", "QUARTZ"),
    ("relay name", "PIPER"), ("shard label", "TALON"), ("bucket ref", "MARLIN"),
    ("agent seat", "VESPER"), ("job handle", "COBALT"), ("probe code", "AURUM"),
    ("lane id", "SABLE"), ("plan slug", "INDIGO"), ("crate tag", "OSPREY"),
    ("gate name", "BASALT"),
]


def _filler_text(rng: random.Random) -> str:
    """A turn whose length is drawn from a realistic right-skewed distribution."""
    n = int(rng.triangular(FILLER_MIN_TOKENS, FILLER_MAX_TOKENS, FILLER_MED_TOKENS))
    return " ".join(rng.choice(_FILLER_WORDS) for _ in range(max(1, n)))


def build_probes(n_probes: int, depth: int, seed: int) -> List[Dict[str, Any]]:
    """Probes at one depth. Seeded on depth so every budget sees identical inputs."""
    rng = random.Random(seed + depth * 1009)
    probes = []
    for i in range(n_probes):
        subject, stem = _SUBJECTS[i % len(_SUBJECTS)]
        value = f"{stem}-{7000 + (i * 137) % 2999}"

        chronicle: List[Dict[str, Any]] = [
            {"role": "user", "parts": [{"text": f"Remember this: my {subject} is {value}."}]},
            {"role": "model", "parts": [{"text": f"Noted. Your {subject} is {value}."}]},
        ]
        for _ in range(depth):
            chronicle.append({"role": "user", "parts": [{"text": _filler_text(rng)}]})
            chronicle.append({"role": "model", "parts": [{"text": _filler_text(rng)}]})
        question = f"What is my {subject}? Answer with the code only."
        chronicle.append({"role": "user", "parts": [{"text": question}]})

        probes.append({"id": i, "subject": subject, "value": value,
                       "question": question, "chronicle": chronicle})
    return probes


# --------------------------------------------------------------------------- measure
def estimate_tokens(text: str) -> int:
    """The estimator production uses (server/context_manager.py): ~4 chars/token."""
    return len(text) // 4


def _context_text(prepared: List[Dict[str, Any]]) -> str:
    return "\n".join(e["parts"][0]["text"] for e in prepared)


def _prepare(ContextManager, budget: Optional[int],
             probe: Dict[str, Any]) -> List[Dict[str, Any]]:
    cfg = {"ai_model": "mistral",
           "context_token_budget": budget if budget else 10 ** 9}
    cm = ContextManager(cfg)
    # prepare_context builds its own list, but copy defensively so one probe is never
    # consumed by the budget that ran before it.
    chronicle = json.loads(json.dumps(probe["chronicle"]))
    prepared, _ = cm.prepare_context(chronicle)
    return prepared


def run_grid(ContextManager, n_probes: int, seed: int) -> List[Dict[str, Any]]:
    """depth x budget: retention of the planted fact, and prompt size."""
    rows = []
    for depth in DEPTHS:
        probes = build_probes(n_probes, depth, seed)
        raw = int(statistics.median(
            estimate_tokens(_context_text(p["chronicle"])) for p in probes))
        for budget in BUDGETS:
            tokens, retained = [], 0
            for probe in probes:
                text = _context_text(_prepare(ContextManager, budget, probe))
                tokens.append(estimate_tokens(text))
                if probe["value"] in text:
                    retained += 1
            rows.append({
                "depth": depth,
                "budget": budget,
                "untrimmed_tokens": raw,
                "median_prompt_tokens": int(statistics.median(tokens)),
                "retained": retained,
                "n": n_probes,
                "retention_pct": round(100 * retained / n_probes, 1),
            })
    return rows


def recall_horizon(rows: List[Dict[str, Any]], budget: int) -> Optional[int]:
    """Deepest depth that is 100% retained with no loss at any shallower depth.

    Deliberately not `max(depths where retention == 100)`. Retention is expected to
    fall monotonically with depth, but it is measured, not guaranteed — a single
    lucky cell past a drop-off would otherwise report a horizon the system does not
    actually have. Scanning the prefix reports the depth up to which recall is
    genuinely reliable.
    """
    at = {r["depth"]: r["retention_pct"] for r in rows if r["budget"] == budget}
    horizon = None
    for depth in sorted(at):
        if at[depth] < 100.0:
            break
        horizon = depth
    return horizon


# --------------------------------------------------------------------------- live
class MistralClient:
    """Minimal Mistral caller with key rotation. Parks a key on HTTP 429."""

    def __init__(self, keys: List[str]) -> None:
        if not keys:
            raise ValueError("no Mistral API keys configured")
        self.keys = list(keys)
        self.idx = 0

    def complete(self, system: str, user: str, retries: int = 4) -> Optional[str]:
        body = json.dumps({
            "model": LIVE_MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.0,   # deterministic: this is a measurement, not a demo
            "max_tokens": 40,
        }).encode()

        for _ in range(retries):
            key = self.keys[self.idx % len(self.keys)]
            req = urllib.request.Request(
                MISTRAL_URL, data=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    return json.loads(resp.read().decode())["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code == 429:           # capped key: rotate and back off
                    self.idx += 1
                    time.sleep(2.0)
                    continue
                return None
            except Exception:
                time.sleep(1.0)
        return None


def load_mistral_keys() -> List[str]:
    raw = os.getenv("MISTRAL_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if keys:
        return keys
    cfg_path = REPO_ROOT / "config.json"
    if cfg_path.exists():
        val = json.loads(cfg_path.read_text(encoding="utf-8")).get("mistral_api_key") or []
        if isinstance(val, str):
            val = [val]
        return [k for k in val if k]
    return []


LIVE_SYSTEM = ("Answer using only the conversation provided. "
               "If the answer is not in it, reply exactly: UNKNOWN.")


def run_live(ContextManager, n_probes: int, seed: int, budget: int,
             client: MistralClient, pause: float) -> List[Dict[str, Any]]:
    """Sweep depth at one budget, grading real answers by exact match."""
    rows = []
    for depth in LIVE_DEPTHS:
        probes = build_probes(n_probes, depth, seed)
        correct = errors = retained = 0
        for probe in probes:
            prepared = _prepare(ContextManager, budget, probe)
            text = _context_text(prepared)
            if probe["value"] in text:
                retained += 1
            transcript = "\n".join(
                f"{e['role'].upper()}: {e['parts'][0]['text']}" for e in prepared)
            answer = client.complete(
                LIVE_SYSTEM,
                f"CONVERSATION:\n{transcript}\n\nQUESTION: {probe['question']}")
            if answer is None:
                errors += 1
            elif probe["value"].lower() in answer.lower():
                correct += 1
            time.sleep(pause)

        graded = n_probes - errors
        rows.append({
            "depth": depth, "budget": budget,
            "retained": retained, "correct": correct,
            "graded": graded, "errors": errors,
            "accuracy_pct": round(100 * correct / graded, 1) if graded else None,
        })
        print(f"  depth={depth:>3}  retained={retained}/{n_probes}  "
              f"answered={correct}/{graded}"
              f"{'  (errors %d)' % errors if errors else ''}", flush=True)
    return rows


# --------------------------------------------------------------------------- report
def print_report(rows: List[Dict[str, Any]], live: Optional[List[Dict[str, Any]]],
                 n_probes: int) -> None:
    print("\nRETENTION OF A PLANTED FACT  (depth x budget, % of probes)")
    print("=" * 74)
    print(f"{'depth':>6} {'untrimmed':>10} | " +
          " ".join(f"{('b=' + str(b)):>12}" for b in BUDGETS))
    print("-" * 74)
    for depth in DEPTHS:
        at = {r["budget"]: r for r in rows if r["depth"] == depth}
        raw = at[BUDGETS[0]]["untrimmed_tokens"]
        cells = []
        for b in BUDGETS:
            r = at[b]
            cells.append(f"{r['retention_pct']:>5.0f}% {r['median_prompt_tokens']:>5}t")
        print(f"{depth:>6} {raw:>10} | " + " ".join(f"{c:>12}" for c in cells))
    print("-" * 74)
    print("  cells show: % of probes where the fact survived, and median prompt tokens")

    print("\nRECALL HORIZON  (deepest depth with 100% retention)")
    for b in BUDGETS:
        h = recall_horizon(rows, b)
        if h is None:
            print(f"  budget {b:>5}: fact lost even at depth 0")
        else:
            tok = next(r["median_prompt_tokens"] for r in rows
                       if r["budget"] == b and r["depth"] == h)
            print(f"  budget {b:>5}: {h:>2} exchanges  (~{tok} prompt tokens)")

    prod = recall_horizon(rows, PRODUCTION_BUDGET)
    if prod is not None:
        print(f"\nProduction runs context_token_budget={PRODUCTION_BUDGET}. "
              f"A fact stays recoverable for {prod} exchanges.")
        print("  Past that it is dropped before the model is asked — a better model "
              "does not recover it.")

    if live:
        print("\nLIVE ANSWERS vs RETENTION CEILING "
              f"({LIVE_MODEL}, budget {PRODUCTION_BUDGET}, n={n_probes})")
        print("-" * 74)
        print(f"{'depth':>6} {'fact kept':>11} {'answered':>11} {'gap':>8}")
        for r in live:
            gap = r["retained"] - r["correct"]
            acc = f"{r['correct']}/{r['graded']}"
            print(f"{r['depth']:>6} {str(r['retained']) + '/' + str(n_probes):>11} "
                  f"{acc:>11} {gap:>8}")
        print("-" * 74)
        print("  gap = probes where the fact WAS in context but the answer still missed it.")
        print("  retention is the ceiling; the gap is what the model leaves on the table.")


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probes", type=int, default=16, help="probes per cell (default 16)")
    ap.add_argument("--seed", type=int, default=20260823, help="RNG seed")
    ap.add_argument("--live", action="store_true", help="also call Mistral and grade answers")
    ap.add_argument("--pause", type=float, default=0.4, help="seconds between live calls")
    ap.add_argument("--json", metavar="PATH", help="write full results as JSON")
    args = ap.parse_args()

    ContextManager = load_context_manager()
    print(f"{args.probes} probes per cell, depths {DEPTHS}, budgets {BUDGETS}, "
          f"seed={args.seed}")

    rows = run_grid(ContextManager, args.probes, args.seed)

    live_rows = None
    if args.live:
        keys = load_mistral_keys()
        if not keys:
            print("\n--live requested but no Mistral key found "
                  "(MISTRAL_API_KEY or config.json). Skipping live tier.", file=sys.stderr)
        else:
            print(f"\nlive tier: {LIVE_MODEL}, {len(keys)} key(s), "
                  f"{args.probes * len(LIVE_DEPTHS)} calls")
            live_rows = run_live(ContextManager, args.probes, args.seed,
                                 PRODUCTION_BUDGET, MistralClient(keys), args.pause)

    print_report(rows, live_rows, args.probes)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "config": {"probes": args.probes, "seed": args.seed,
                       "depths": DEPTHS, "budgets": BUDGETS,
                       "production_budget": PRODUCTION_BUDGET,
                       "live_model": LIVE_MODEL if live_rows else None},
            "grid": rows,
            "live": live_rows,
            "recall_horizon": {str(b): recall_horizon(rows, b) for b in BUDGETS},
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
