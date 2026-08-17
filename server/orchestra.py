"""
AGENT ORCHESTRA — judge-and-advocates deliberation (Z6).

Where mesh.py fans ONE question across PROVIDERS and reconciles, the orchestra fans
it across MODELS INSIDE MISTRAL and runs an actual argument with rounds:

  TRIAGE  one cheap call decides SETTLED vs CONTESTED. A settled fact gets a
          single direct answer (2 calls) and never convenes anybody.
  R0  every advocate answers the same question IN PARALLEL and IN ISOLATION,
      each under a different stance so the panel cannot quietly collapse into
      four copies of one opinion.
  R1  the judge SCORES each answer 0-10 and names a specific defect in each.
      CODE then decides:
        CASE 1 ADOPT  - best >= ADOPT_MIN_SCORE and score spread <= ADOPT_SPREAD.
                        The judge's improved rewrite is returned. Done.
        CASE 2 REJECT - anything else. Each advocate receives ONLY the defect
                        found in its OWN answer, so independence survives.
  R2  advocates revise WITH FULL VISIBILITY of every answer, because by now the
      goal has flipped from diversity to convergence. Judge synthesises. Done.

WHY CODE OWNS THE DECISION: in the 18-debate soak on 2026-08-02 the judge chose
ADOPT 18 times out of 18 - including on ten deliberately contentious questions -
because "at least one answer is substantially right" is always true with four
competent models. The entire refinement path was dead code. The judge is now only
asked to score and to name defects, which the benchmark showed it does well, and
the threshold is applied here. Same reason agreement is now MEASURED from the
score spread instead of being asserted by the judge: it read HIGH 17/18 while
carrying no information and gating nothing.

WHY MISTRAL-ONLY: 4 keys x ~1B tokens/month is the only budget big enough to run
debates. Groq caps by noon and Cerebras is a single key. Measured 2026-08-02:
mistral-large-latest returned HTTP 429 on 2 of 6 benchmark cases, so the flagship
is deliberately NOT the default judge - a rate-limited judge stalls everything.
mistral-medium-latest scored 6/6 on winner-picking with strong synthesis.

READ-ONLY: this module never executes tools. It builds text arguments only.
"""

import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import log_info
from .harness import HARNESS
from .tracing import observe, update_current_span
from .orchestra_tools import calc, gather_grounding

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

DEFAULT_JUDGE = "mistral-medium-latest"

# Fixed panel. Names are the persona layer; `model` and `stance` are what actually
# change the output. Different MODELS give different failure modes, different
# STANCES give different angles of attack - temperature alone gives neither, it
# just adds noise that inflates disagreement and buys expensive extra rounds.
# Briefs are METHOD, not flavour. A one-line stance ("be empirical") produced
# confident invented statistics; a stated procedure produces arguments that can be
# checked. Each brief now says HOW to attack the question and what a good answer
# from that seat must contain, including what to do with fetched sources.
DEFAULT_PANEL: List[Dict[str, str]] = [
    {"id": "light",     "name": "Light Yagami",   "model": "ministral-8b-latest",
     "stance": "ATTACK THE PREMISE",
     "brief": "Method: (1) state the assumption the question smuggles in as given; "
              "(2) test whether it actually holds; (3) say what the answer becomes once it "
              "is dropped. If the premise survives scrutiny, say so plainly and answer the "
              "question as asked - a manufactured objection is worse than none."},
    {"id": "senku",     "name": "Senku Ishigami", "model": "magistral-small-latest",
     "stance": "BREAKS AT SCALE?",
     "brief": "Method: give at least one concrete quantity - a rate, a limit, a size, a "
              "cost - and the point at which the obvious answer stops working. Take numbers "
              "from the reference material when it supplies them and name the source. When "
              "you have no measured figure, say 'order of magnitude' and show the arithmetic "
              "rather than asserting a precise-sounding number you cannot support."},
    {"id": "ayanokoji", "name": "Ayanokoji",      "model": "mistral-small-latest",
     "stance": "SIMPLEST PATH",
     "brief": "Method: state the minimum that actually satisfies the requirement, then name "
              "each thing the others would add and say precisely what breaks if it is left "
              "out. Anything that survives that test is load-bearing and you must concede it. "
              "Simplicity is the goal, not fewer words."},
    {"id": "vanitas",   "name": "Vanitas",        "model": "ministral-14b-latest",
     "stance": "COST FIRST",
     "brief": "Method: account for the full cost - tokens, latency, money, maintenance, and "
              "the failure you inherit later - then say whether the benefit is worth it. "
              "Distinguish a one-off cost from a recurring one; they are not comparable and "
              "conflating them is the usual error. Name the cheaper alternative you rejected."},
]

# Decision thresholds. These live in code, not in the judge's prompt, because the
# soak proved a prompted judge will always find a reason to adopt.
ADOPT_MIN_SCORE = 9.0     # "I would ship this unchanged" - raised from 8.0 on
                          # 2026-08-02: at 8.0 mid-difficulty questions still
                          # adopted too readily. Higher bar = more refinement.
ADOPT_SPREAD = 2.0        # score range across the panel that still counts as agreement
REFINE_TOP_N = 2          # how many advocates get a second draft in R2
# Phrasings that are ALWAYS a matter of judgement, whatever the classifier says.
# "how do/should/can" is restricted to FIRST PERSON. Measured 2026-08-05: the older
# pattern included "you", so "How do you spell 'necessary'?" was promoted to a
# four-way debate - while _TRIAGE_SYS lists spelling as a SETTLED example, so the
# override was contradicting the prompt it backstops. Advice is asked about one's
# OWN situation; "how do you spell X" is a question about the world.
_ADVISORY_RE = re.compile(
    r"\b(should|good enough|better than|best way|best approach|worth it|worth doing|"
    r"how (?:do|should|can) (?:i|we)\b|which (?:is|one)|recommend|advice|"
    r"pros and cons|trade[- ]?offs?|vs\.?|versus)\b", re.IGNORECASE)
R2_PEER_CHARS = 420       # how much of each peer answer is replayed into R2 context

DB_PATH = os.path.join(".data", "orchestra.db")
_db_lock = threading.Lock()


# --------------------------------------------------------------------------- store
def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS debates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started REAL, finished REAL, question TEXT, verdict TEXT,
        agreement TEXT, rounds INTEGER, calls INTEGER, tokens INTEGER,
        case_taken TEXT, judge TEXT, transcript TEXT)""")
    return con


def save_debate(rec: Dict[str, Any]) -> Optional[int]:
    try:
        # `with con:` is sqlite3's TRANSACTION context manager, not a closing one —
        # it commits or rolls back and leaves the connection open. Every debate
        # leaked one. `closing(...)` first, then the connection itself, keeps the
        # transaction semantics and actually releases the handle.
        with _db_lock, closing(_db()) as con, con:
            cur = con.execute(
                "INSERT INTO debates(started,finished,question,verdict,agreement,rounds,"
                "calls,tokens,case_taken,judge,transcript) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (rec.get("started"), rec.get("finished"), rec.get("question"),
                 rec.get("verdict"), rec.get("agreement"), rec.get("rounds"),
                 rec.get("calls"), rec.get("tokens"), rec.get("case"),
                 rec.get("judge"), json.dumps(rec.get("transcript") or [])))
            return cur.lastrowid
    except Exception as e:
        log_info(f"[ORCHESTRA] could not persist debate: {e}")
        return None


def recent_debates(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        # `with con:` is sqlite3's TRANSACTION context manager, not a closing one —
        # it commits or rolls back and leaves the connection open. Every debate
        # leaked one. `closing(...)` first, then the connection itself, keeps the
        # transaction semantics and actually releases the handle.
        with _db_lock, closing(_db()) as con, con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT id,started,finished,question,verdict,agreement,rounds,calls,"
                "tokens,case_taken,judge FROM debates ORDER BY id DESC LIMIT ?",
                (max(1, min(100, limit)),)).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log_info(f"[ORCHESTRA] could not read debates: {e}")
        return []


# --------------------------------------------------------------------------- client
# --------------------------------------------------------------------------- seams
#
# The orchestra's capabilities, declared before anything can consume them. See
# server/harness.py for why a consumer is not allowed to outrun its provider.
#
# These four were chosen because each is a place the orchestra could plausibly be pointed
# somewhere else, and today cannot be:
#
#  * llm        — every advocate, judge and synthesis call goes to Mistral, through one
#                 hardcoded URL and one key pool. When those four keys are capped the
#                 whole debate engine is down, and there is no seam to hang a fallback on.
#                 This is the single point of failure the FEATURE_MATRIX blames for the
#                 scheduler's flaky rows, appearing again here.
#  * grounding  — already has four backends inside `gather_grounding`, with no way to
#                 swap the set or test the debate without a network.
#  * store      — one sqlite file; a debate is worth keeping even when it is not.
#  * invariants — arithmetic and citation checks are hardcoded into the judge branch.
#                 The harness calls these "package-owned invariants" and keeps them in a
#                 registry precisely so new ones can be added without editing the judge.
SEAM_LLM = "orchestra.llm"
SEAM_GROUNDING = "orchestra.grounding"
SEAM_STORE = "orchestra.store"
SEAM_INVARIANTS = "orchestra.invariants"

HARNESS.declare(
    SEAM_LLM, "Chat completion for advocates, judge and synthesis",
    methods=("complete",), declared_by="orchestra")
HARNESS.declare(
    SEAM_GROUNDING, "Evidence retrieval for a debate question",
    methods=("gather",), declared_by="orchestra")
HARNESS.declare(
    SEAM_STORE, "Durable debate record",
    methods=("save", "recent"), declared_by="orchestra")
HARNESS.declare(
    SEAM_INVARIANTS, "Model-free defect checks run on every advocate answer",
    methods=("check",), declared_by="orchestra")


def _keys(config: dict) -> List[str]:
    raw = config.get("mistral_api_key")
    keys = raw if isinstance(raw, list) else [raw]
    return [k for k in keys if k]


class _KeyPool:
    """Round-robins the 4 Mistral keys and parks one that reports 429.

    Deliberately local to this module rather than reusing ai.py's driver: the
    orchestra needs a SPECIFIC model per call, which get_ai_response cannot
    express, and putting a per-call model override into the shared driver would
    mean touching the hot path every user message travels through.
    """

    def __init__(self, keys: List[str]):
        self._keys = keys
        self._i = 0
        self._cooldown: Dict[str, float] = {}
        self._lock = threading.Lock()

    def take(self) -> Optional[str]:
        with self._lock:
            now = time.time()
            for _ in range(len(self._keys)):
                k = self._keys[self._i % len(self._keys)]
                self._i += 1
                if self._cooldown.get(k, 0) <= now:
                    return k
            return None                      # every key is cooling down

    def park(self, key: str, seconds: float = 45.0):
        with self._lock:
            self._cooldown[key] = time.time() + seconds


def _call(pool: "_KeyPool", model: str, system: str, user: str,
          temperature: float = 0.3, max_tokens: int = 900,
          attempts: int = 3) -> Dict[str, Any]:
    """One chat completion. Returns {ok, text, tokens, error}. Never raises."""
    last_err = "no key available"
    for _ in range(attempts):
        key = pool.take()
        if not key:
            time.sleep(1.5)
            continue
        body = json.dumps({
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            MISTRAL_URL, data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            ch = d["choices"][0]
            txt = (ch["message"]["content"] or "").strip()
            # finish_reason is the DETERMINISTIC truncation signal. The soak used a
            # regex on the tail and mis-flagged answers that legitimately ended in
            # markdown; the API tells us outright, so trust it instead of guessing.
            fin = ch.get("finish_reason", "")
            return {"ok": bool(txt), "text": txt, "truncated": fin == "length",
                    "tokens": d.get("usage", {}).get("total_tokens", 0), "error": ""}
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 429:
                pool.park(key)               # rotate to a sibling key, do not give up
                continue
            try:
                last_err += " " + e.read().decode()[:160]
            except Exception:
                pass
            break
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"ok": False, "text": "", "truncated": False, "tokens": 0, "error": last_err}


# --------------------------------------------------------------- seam providers
#
# Every provider below wraps code that already existed and calls it verbatim. That is
# deliberate: the debate engine works, and a seam is supposed to change WHERE a capability
# can be swapped, not WHAT it currently does. If a debate behaves differently after this
# commit, the wiring is wrong, not the design.


class MistralAdapter:
    """The `orchestra.llm` provider: Mistral chat completions over a rotating key pool.

    ONE BEHAVIOURAL CHANGE, stated because everything else here is a pure rewiring:
    `orchestra_answer` used to build a fresh `_KeyPool` per debate, so a key parked for a
    429 was un-parked the moment the next debate started. The adapter is registered once
    per process, so the pool — and its cooldowns — now persist across debates. That is
    the better behaviour (a rate limit does not reset because a new question arrived), but
    it is a change, not a no-op.

    Consequence to know about: the key list is captured at registration. A config reload
    that changes `mistral_api_key` will not be picked up until something re-registers the
    seam.
    """

    name = "mistral"

    def __init__(self, keys: List[str]):
        self._pool = _KeyPool(keys)

    def complete(self, model: str, system: str, user: str,
                 temperature: float = 0.3, max_tokens: int = 900) -> Dict[str, Any]:
        return _call(self._pool, model, system, user, temperature, max_tokens)


class _SearchGrounding:
    """The `orchestra.grounding` provider: the existing multi-backend search chain."""

    name = "search"

    def gather(self, question: str, query: str, api_key: str = "") -> Dict[str, Any]:
        return gather_grounding(question, query, api_key=api_key)


class _SqliteDebateStore:
    """The `orchestra.store` provider: the sqlite debate log in .data/orchestra.db."""

    name = "sqlite"

    def save(self, rec: Dict[str, Any]) -> Optional[int]:
        return save_debate(rec)

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return recent_debates(limit)


class _DefaultInvariants:
    """The `orchestra.invariants` provider: arithmetic and citation checks.

    Registered as a list so a new check is an append here rather than another branch
    inside the judge. Each entry returns a defect string or a falsy value.
    """

    name = "arithmetic+citations"

    def __init__(self) -> None:
        self.checks: List[Tuple[str, Callable[[str, str], str]]] = [
            ("ARITHMETIC", lambda txt, ground: _check_arithmetic(txt)),
            ("FABRICATED", lambda txt, ground: _check_citations(txt, ground)),
        ]

    def check(self, text: str, ground_text: str) -> List[str]:
        """Every defect found in one answer. Order is stable, for stable defect strings."""
        found = []
        for _label, fn in self.checks:
            try:
                d = fn(text, ground_text)
            except Exception as e:                 # a broken check must not kill a debate
                log_info(f"[ORCHESTRA] invariant {_label} raised: {e}")
                continue
            if d:
                found.append(d)
        return found


# Grounding, store and invariants have no configuration, so they are wired at import.
# The LLM adapter needs the config's API keys, so it is wired per call in
# `orchestra_answer` — see `_llm_for`.
HARNESS.provide(SEAM_GROUNDING, _SearchGrounding(), source="orchestra.search")
HARNESS.provide(SEAM_STORE, _SqliteDebateStore(), source="orchestra.sqlite")
HARNESS.provide(SEAM_INVARIANTS, _DefaultInvariants(), source="orchestra.default")


def register_llm_seam(config: dict) -> bool:
    """Wire the default Mistral adapter. Call at startup, where config lives.

    Providers belong at the composition root, not inside business logic. The first
    version of this registered lazily on the first debate, and the boot-time seam check
    duly printed `!! orchestra.llm <- NOBODY` on every single start — an alarm that always
    fires is one nobody reads, which is the exact failure this codebase already learned
    from a judge that reported agreement HIGH 17 times out of 18.

    Returns False when there are no keys to build an adapter from, so the graph shows the
    seam genuinely unwired instead of pretending.
    """
    if HARNESS.has(SEAM_LLM):
        return True                       # someone registered a different adapter: theirs wins
    keys = _keys(config)
    if not keys:
        return False
    HARNESS.provide(SEAM_LLM, MistralAdapter(keys), source="orchestra.mistral")
    return True


def _llm_for(config: dict):
    """Resolve the LLM seam for a debate, wiring the default if startup did not.

    The fallback keeps scripts and tests working without a full server boot. An adapter
    someone else already registered — a replay adapter, or a different provider for when
    Mistral is capped — always wins, which is the entire point of the seam.
    """
    register_llm_seam(config)
    return HARNESS.require(SEAM_LLM, consumer="orchestra_answer")


# --------------------------------------------------------------------------- prompts
_ADVOCATE_SYS = (
    "You are {name}, one of four independent advocates answering a question for a judge.\n"
    "YOUR ASSIGNED STANCE: {stance}. {brief}\n"
    "Argue your stance honestly - do not invent flaws that are not there, and if the "
    "straightforward answer is simply correct, say so.\n"
    "FORMAT: plain prose, 120 words maximum. NO markdown headings, NO bold, NO bullet "
    "lists - they burn your budget and get you cut off mid-sentence. End with one complete "
    "sentence stating your recommendation.\n"
    "SHOW YOUR ARITHMETIC. If you state a figure you worked out (a total, a cost, a ratio, "
    "a saving), add a line at the very end for each one:\n"
    "  CALC: <expression> = <the figure you stated>\n"
    "using ONLY digits and + - * / ( ) - no units, no words, no commas inside numbers. "
    "Maximum two CALC lines, and they do NOT count toward your 120 words. A figure you "
    "cannot express as a CALC line is a figure you have not actually computed: say it is "
    "unknown instead of stating it.\n"
    # "write NO CALC line at all" was read as an instruction to write the words
    # "NO CALC" - observed 2026-08-05. Say what to do, not what not to do.
    "If you computed nothing, simply end after your recommendation and omit the CALC "
    "line - do not write a placeholder, and do not write the words 'no calc'.\n"
    "ATTRIBUTE FIGURES YOU DID NOT COMPUTE. A price, benchmark, percentage, date or "
    "study must come from the REFERENCE MATERIAL above, and you name its source in "
    "square brackets exactly as it appears there, e.g. [Pricing]. If the reference "
    "material does not contain it, say the figure is unverified - NEVER invent a "
    "source, paper, study or year, and never cite from memory."
)

# Deterministic arithmetic check. The panel kept sourcing real numbers and then
# multiplying them wrong: three runs of the Mistral pricing probe produced three
# different wrong products, each extrapolated onward with total confidence
# (2026-08-05). Asking a model to check a model's sum adds a call and another
# opinion; `calc` already walks an AST and refuses anything that is not arithmetic,
# so the check is free and cannot be argued with. Same principle as the ADOPT
# threshold: CODE OWNS THE DECISION wherever the answer is decidable.
# The expression is captured loosely on purpose. A tight [0-9+-*/(). ] class would
# silently ignore a malformed CALC line, which is the one case most likely to be
# hiding a number nobody computed - and it would leave `calc`'s rejection path dead.
# Anything non-arithmetic reaching calc is refused by its AST walk (ast.Call and
# friends raise), so a junk or hostile expression is reported, not evaluated.
_CALC_RE = re.compile(r"^\s*CALC:\s*(.{1,200}?)\s*=\s*([-+]?[0-9][0-9,]*\.?[0-9]*)\s*$",
                      re.MULTILINE | re.IGNORECASE)
# Advocates round for readability ("about 0.6"), which is honest; 5% absorbs that
# while still catching the 2.8x and 25x errors actually observed.
_CALC_TOLERANCE = 0.05


# Fabricated citations are as decidable as fabricated sums: either the cited thing
# is in the reference material or it is not. Probe 7 produced "([A Comparative
# Analysis], 2023)" out of nothing, and a made-up study is more persuasive than an
# unsourced number precisely because it wears the costume of evidence.
_CITE_RE = re.compile(
    r"\[([^\[\]]{8,80})\]\s*,?\s*(?:19|20)\d{2}"      # [A Comparative Analysis], 2023
    r"|\(([^()]{8,80}?),\s*(?:19|20)\d{2}\)"          # (Smith et al., 2019)
    r"|\[([^\[\]]{8,80})\]"                           # [Exact Source Title]
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _check_citations(text: str, ground_text: str) -> str:
    """Return a defect when an answer cites something absent from the reference material."""
    haystack = _norm(ground_text)
    bogus = []
    for m in _CITE_RE.finditer(text or ""):
        cited = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        # Title-like only: a phrase with a space. Bare "[unknown]" or "[1]" is not a
        # citation and flagging it would train the panel to stop bracketing anything.
        if " " not in cited or not re.search(r"[A-Za-z]", cited):
            continue
        needle = _norm(cited)
        if not needle:
            continue
        if not haystack:
            bogus.append("'%s' (nothing was grounded for this question)" % cited)
        elif needle not in haystack:
            bogus.append("'%s'" % cited)
    if not bogus:
        return ""
    return ("FABRICATED CITATION (checked, not judged): cites " + "; ".join(bogus[:2]) +
            " which does not appear in the reference material.")


def _check_arithmetic(text: str) -> str:
    """Return a defect string when a stated figure does not match its own expression."""
    bad = []
    for expr, claimed in _CALC_RE.findall(text or ""):
        got = calc(expr)
        if isinstance(got, str):                      # calc reports failure as "error: ..."
            bad.append("'%s' is not evaluable arithmetic" % expr.strip())
            continue
        try:
            want = float(claimed.replace(",", ""))
        except ValueError:
            continue
        scale = max(abs(got), abs(want), 1e-9)
        if abs(got - want) / scale > _CALC_TOLERANCE:
            bad.append("states %s but %s = %s" % (claimed, expr.strip(), round(got, 6)))
    if not bad:
        return ""
    return ("ARITHMETIC IS WRONG (checked, not judged): " + "; ".join(bad[:2]) +
            ". Every figure derived from it is wrong too.")

# The judge SCORES and names defects; the ADOPT/REJECT decision is then made in CODE.
# Soak 2026-08-02: with the judge deciding, ADOPT fired 18/18 - including on ten
# genuinely contentious questions - because "at least one answer is substantially
# right" is always true with four competent models. That made the entire refinement
# path dead code. Scoring is the thing the judge benchmark proved it is good at
# (naming specific errors), so it does that and code applies the threshold.
_JUDGE_REVIEW_SYS = (
    "You are Alucard, an impartial judge reviewing four independent advocates.\n"
    "Score each advocate 0-10 on whether their answer is CORRECT, COMPLETE, and free of "
    "unaddressed objections raised by the others. Be harsh: 8+ means you would ship this "
    "answer unchanged. An answer that is merely reasonable is a 5-6.\n"
    "Name the single most important DEFECT in each answer - a real, specific one. If an "
    "answer genuinely has no defect, use an empty string.\n"
    "JUDGE THE SOURCE, NOT JUST THE NUMBER. The REFERENCE MATERIAL the advocates were "
    "given is shown above, with each source's title in square brackets. Check what a cited "
    "source actually IS before you accept a figure taken from it. Ask: could a document "
    "like that carry a fact like this?\n"
    "  A current API price read off a company FUNDING or VALUATION story -> defect, "
    "however plausible the number looks.\n"
    "  Throughput for a hosted API argued from a CONSUMER GPU forum thread about running "
    "models locally -> defect, different system entirely.\n"
    "  A figure with no source named at all -> defect. An admitted unknown is better "
    "than a confident unattributed number, and should score HIGHER than one.\n"
    "A well-written answer resting on the wrong source is not an 8. The prose is not the "
    "evidence.\n"
    "Reply as STRICT JSON, nothing else:\n"
    '{"scores":{"<id>":<0-10>,...},"defects":{"<id>":"<specific defect>",...},'
    '"best":"<id of highest scoring>","improved":"<the best answer rewritten with your own '
    'improvements folded in, plain prose, under 200 words>"}'
)

_JUDGE_FINAL_SYS = (
    "You are Alucard, delivering the final answer after a round of revisions.\n"
    "Synthesise the revised advocate answers into ONE answer, adding your own improvements "
    "where they are warranted.\n"
    "Each answer arrives with the SCORE YOU GAVE IT and the DEFECT YOU NAMED. They are "
    "your own findings from minutes ago - honour them:\n"
    "- Never carry a claim into the final answer if you marked it defective. Catching an "
    "error and then repeating it is worse than never catching it.\n"
    "- If you flagged a number, price, or date as unsourced or outdated, do NOT restate it "
    "as fact. Drop it, or say plainly that the figure could not be verified.\n"
    "- Weight a low-scored answer accordingly; 'not revised' means it never improved.\n"
    "Reply as STRICT JSON, nothing else:\n"
    '{"agreement":"HIGH|LOW","answer":"<final answer, under 250 words>"}'
)

# Measured 2026-08-05: this prompt is the reason the panel invented Mistral prices.
# Asked "what does Mistral charge per million tokens", it replied NONE - reading a
# live-pricing lookup as "a matter of opinion" because the question also asked which
# option was cheaper. Grounding never ran, so four advocates argued from nothing and
# filled the gap with numbers. Two changes: it now writes a WEB query (marginalia and
# duckduckgo are tried long before wikipedia, so encyclopedia phrasing was aiming at
# the last-resort backend), and NONE is narrowed to questions with no checkable fact
# anywhere in them. A wasted search costs one cheap call; a skipped one costs the
# whole answer.
_QUERY_SYS = (
    "Give ONE short WEB SEARCH QUERY that would surface FACTUAL, checkable material "
    "for the question - prices, limits, versions, specs, dates, documented behaviour, "
    "names of technologies.\n"
    "Most questions have a factual part even when they also ask for a judgement. If ANY "
    "part of the question could be checked against a source, write the query for THAT "
    "part and ignore the opinion part.\n"
    "Reply exactly NONE only when nothing in the question could be checked against any "
    "source at all - pure ethics, pure taste, or reasoning about the user's own private "
    "situation that no public page describes.\n"
    "Examples:\n"
    "  'What does Mistral charge per million tokens, and is 5 calls cheaper than 1?'\n"
    "    -> Mistral API pricing per million tokens\n"
    "  'Should I use SQLite or Postgres for a single-user app?'\n"
    "    -> SQLite vs Postgres single writer limits\n"
    "  'Is it wrong to lie to a friend to protect their feelings?' -> NONE\n"
    "Reply with the query or NONE, nothing else."
)

_TRIAGE_SYS = (
    "Classify the question. Reply with ONE word and nothing else.\n"
    "SETTLED - a single well-established factual answer that competent people do not "
    "dispute: arithmetic, definitions, dates, capitals, spelling, unit conversion.\n"
    "CONTESTED - anything involving judgement, trade-offs, design choices, ethics, "
    "prediction, advice, or 'how should I / what is the best way' - thoughtful people "
    "could reasonably disagree.\n"
    "Naming two options does not make a question contested. A comparison with a "
    "MEASURABLE answer - which is faster, smaller, cheaper by a fixed rule - is SETTLED, "
    "however it is phrased. A comparison that depends on the asker's own situation is "
    "CONTESTED.\n"
    "Examples:\n"
    "  'Is 17 a prime number?' -> SETTLED\n"
    "  'How many days in a leap year?' -> SETTLED\n"
    "  'What is the capital of Australia?' -> SETTLED\n"
    "  'Is it faster to insert 10,000 rows in one transaction or one at a time?'\n"
    "    -> SETTLED (measurable; one right answer)\n"
    "  'Should I use SQLite or Postgres for my app?'\n"
    "    -> CONTESTED (depends on the asker's situation)\n"
    "  'How do I make landing pages as good as Apple's?' -> CONTESTED\n"
    "  'Should logs be JSON or plain text?' -> CONTESTED\n"
    "  'Is SQLite good enough for my app?' -> CONTESTED\n"
    "WHEN IN DOUBT REPLY CONTESTED. A wasted debate costs tokens; a settled-path answer "
    "to a question that deserved a debate costs correctness, and the second is worse."
)

_SOLO_SYS = (
    "Answer the question directly and correctly in plain prose, under 80 words. "
    "No preamble, no markdown."
)

# A settled question can still be one the model cannot answer from memory. These
# are the markers of a fact that MOVES - it still has a single right answer, so it
# needs no debate, but it does need looking up. Deliberately generous: a false
# positive costs one HTTP fetch on a path that still uses only two model calls,
# while a miss costs an invented figure with no check anywhere behind it.
_VOLATILE_RE = re.compile(
    r"\b(right now|currently|current|today|todays|latest|newest|nowadays|these days|"
    r"as of|this (?:year|month|quarter)|up to date|up-to-date|"
    r"price|prices|pricing|cost per|rate limit|quota|free tier|"
    r"latest version|current version|release)\b", re.IGNORECASE)

_SOLO_GROUNDED_SYS = (
    "Answer the question directly in plain prose, under 80 words, USING THE "
    "REFERENCE MATERIAL provided above the question.\n"
    "The answer moves over time, so state only what the reference material "
    "supports and name the source in square brackets as it appears there. If the "
    "reference material does not answer it, say plainly that you could not verify "
    "a current figure and say where to check - NEVER supply one from memory.\n"
    "No preamble, no markdown."
)

_ASSIGN_SYS = (
    "You assign debate stances. Given a question and four fixed stances, reply as STRICT "
    "JSON mapping advocate id to a REPLACEMENT stance ONLY where the fixed one would waste "
    "the seat on this particular question. Replace at most two. Reply {} to keep all four.\n"
    'Format: {"<id>":"<SHORT STANCE IN CAPS>"}'
)


def _json_from(text: str) -> Optional[dict]:
    """Models wrap JSON in prose or fences no matter how firmly you ask them not to."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------- engine
# capture_input=False for the same reason ai.py sets it: the config dict travels
# through here and would put API keys into the trace payload.
@observe(name="Mizune.Orchestra", type="span", capture_input=False)
def orchestra_answer(question: str, config: dict,
                     panel: Optional[List[Dict[str, str]]] = None,
                     judge: Optional[str] = None,
                     dynamic_stances: bool = True,
                     triage: bool = True,
                     grounding: bool = True,
                     on_event: Optional[Callable[[dict], None]] = None) -> Dict[str, Any]:
    """Run a full deliberation. Returns a result dict; never raises.

    on_event receives progress dicts as the debate happens so a dashboard can
    render the real thing instead of an idle animation pretending to be one.
    """
    started = time.time()
    panel = [dict(p) for p in (panel or DEFAULT_PANEL)]
    judge_model = judge or config.get("orchestra_judge") or DEFAULT_JUDGE
    keys = _keys(config)
    stats = {"calls": 0, "tokens": 0, "truncated": 0}
    transcript: List[Dict[str, Any]] = []

    def emit(kind, **kw):
        ev = {"kind": kind, "t": round(time.time() - started, 2),
              "calls": stats["calls"], "tokens": stats["tokens"], **kw}
        transcript.append(ev)
        if on_event:
            try:
                on_event(ev)
            except Exception:
                pass                          # a broken listener must not kill the debate

    if len(keys) < 1:
        return {"ok": False, "error": "no mistral_api_key configured", "transcript": transcript}

    llm = _llm_for(config)

    def run(model, system, user, temp=0.3, mx=900):
        r = llm.complete(model, system, user, temp, mx)
        stats["calls"] += 1
        stats["tokens"] += r.get("tokens", 0)
        return r

    # Hoisted out of the debate path so the SETTLED path can ground too. Returns
    # (prefix_for_a_prompt, raw_text_for_the_citation_check); both empty when
    # grounding is off or nothing was found, and the caller simply argues unaided.
    def fetch_grounding():
        if not grounding:
            return "", ""
        gq = run("ministral-8b-latest", _QUERY_SYS, question, temp=0.0, mx=24)
        g = HARNESS.require(SEAM_GROUNDING, consumer="orchestra.fetch_grounding").gather(
            question, gq["text"] if gq["ok"] else "",
            api_key=config.get("firecrawl_api_key", ""))
        emit("grounding", ok=bool(g.get("ok")), query=g.get("query", ""),
             sources=g.get("sources", []), chars=len(g.get("text", "")),
             backend=g.get("backend", "none"), credits=g.get("credits", 0),
             reason=g.get("reason", ""))
        if not g.get("ok"):
            return "", ""
        # Name the backend that actually answered. Claiming "Wikipedia" for what
        # marginalia or firecrawl fetched misstates how authoritative the block is,
        # and both the advocates and the judge weigh it accordingly.
        prefix = ("REFERENCE MATERIAL (fetched from %s just now; use it where "
                  "relevant, ignore it where not):\n%s\n\n"
                  % (g.get("backend", "the web"), g["text"]))
        return prefix, g["text"]

    # ---- triage: never convene four advocates over a settled fact ------------
    # The soak billed 6 calls and ~2,250 tokens to answer "Is 17 a prime number?",
    # the same cost as a hard ethics question. A debate is only worth paying for
    # when there is something to disagree about, so one cheap call decides.
    if triage:
        # ministral-8b, not 3b. Measured 2026-08-02: 3b called "Is 17 a prime number?"
        # and "How many days are in a leap year?" CONTESTED, which sent settled facts to
        # a full four-way debate and made the cheap path the expensive one. 8b got all
        # five probe questions right at the same latency.
        t = run("ministral-8b-latest", _TRIAGE_SYS, question, temp=0.0, mx=8)
        verdict_word = (t["text"] or "").strip().upper()
        # Code overrides the classifier UPWARDS only. "Is SQLite good enough for my
        # app?" was still classified SETTLED even with that exact phrasing given as a
        # CONTESTED example - advisory questions phrased as yes/no read as factual to
        # a small model. These patterns are always a matter of judgement, so they can
        # never take the single-answer path. The override is one-directional on
        # purpose: it can promote a debate, never suppress one.
        if _ADVISORY_RE.search(question):
            verdict_word = "CONTESTED"
        if verdict_word.startswith("SETTLED"):
            # UNDISPUTED IS NOT THE SAME AS KNOWABLE FROM MEMORY. 17 is prime
            # forever; what something costs today has exactly one right answer that
            # the model does not have. Measured 2026-08-05: "what does Mistral
            # charge per million tokens right now" triaged SETTLED and returned
            # "$0.25 ... as of the latest pricing information" - an invented figure
            # on the one path that skips grounding and every fact check. So a
            # settled question that is also VOLATILE still gets searched; it just
            # does not need four advocates arguing about it.
            volatile = bool(_VOLATILE_RE.search(question))
            gp, gt = fetch_grounding() if volatile else ("", "")
            emit("triage", verdict="SETTLED",
                 note=("volatile fact; grounded single answer" if volatile
                       else "single answer; no debate needed"),
                 volatile=volatile)
            solo = run(judge_model, _SOLO_SYS if not volatile else _SOLO_GROUNDED_SYS,
                       gp + question, temp=0.2, mx=300)
            # The solo answer gets the same deterministic checks as an advocate's.
            # There is no judge on this path to hand a defect to, so a failed check
            # is treated exactly like a failed call: fall through and convene the
            # panel, which does have somewhere to put it.
            bad = ""
            if solo["ok"]:
                bad = (_check_arithmetic(solo["text"])
                       or _check_citations(solo["text"], gt))
                if bad:
                    emit("factcheck", arithmetic=[], citations=[], solo=True,
                         detail={"solo": bad[:260]})
            if solo["ok"] and not bad:
                emit("verdict", case="SETTLED", agreement="HIGH", answer=solo["text"])
                return _finish(question, solo["text"], "HIGH", 0, stats,
                               "SETTLED", judge_model, started, transcript)
            # If the direct answer failed or failed a check, fall through to the panel.
        else:
            emit("triage", verdict="CONTESTED", note="convening the panel")

    # ---- optional: judge retunes stances for THIS question -------------------
    # Fixed stances guarantee a diversity floor; this pass only raises the ceiling
    # where a generic stance would waste a seat. It can replace at most two, so it
    # can never collapse the panel into one viewpoint.
    if dynamic_stances:
        fixed = "\n".join(f'{p["id"]}: {p["stance"]}' for p in panel)
        r = run(judge_model, _ASSIGN_SYS, f"QUESTION: {question}\n\nFIXED STANCES:\n{fixed}",
                temp=0.2, mx=260)
        repl = _json_from(r["text"]) or {}
        changed = 0
        for p in panel:
            new = repl.get(p["id"])
            if new and isinstance(new, str) and changed < 2:
                p["stance"] = new.strip()[:40].upper()
                p["brief"] = "Argue specifically from this angle."
                changed += 1
        emit("stances", panel=[{"id": p["id"], "name": p["name"], "model": p["model"],
                                "stance": p["stance"]} for p in panel], replaced=changed)

    # ---- grounding: one shared set of facts, or none ------------------------
    # The panel is confidently quantitative and entirely ungrounded - "~100k
    # writes/sec" is generated, not measured. One cheap call picks a search phrase
    # (or says NONE for normative questions), then a plain HTTP fetch does the rest,
    # so grounding costs one call rather than one per advocate. Everyone sees the
    # SAME facts: private research per advocate would multiply cost and let them
    # argue from different private evidence, which is worse than arguing from none.
    # ground_text is kept alongside the prefix: the citation check needs the raw
    # material to test a claimed source against, without the wrapper prose.
    ground_prefix, ground_text = fetch_grounding()

    # ---- R0: parallel, isolated ---------------------------------------------
    emit("round", round=0, phase="fan-out",
         advocates=[{"id": p["id"], "name": p["name"], "model": p["model"],
                     "stance": p["stance"]} for p in panel])

    def ask_advocate(p):
        sys_p = _ADVOCATE_SYS.format(name=p["name"], stance=p["stance"], brief=p["brief"])
        return p, run(p["model"], sys_p, ground_prefix + f"QUESTION: {question}", temp=0.4, mx=700)

    answers: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(panel)) as ex:
        for p, r in ex.map(ask_advocate, panel):
            if r["ok"]:
                answers[p["id"]] = r["text"]
            if r.get("truncated"):
                stats["truncated"] += 1
            emit("answer", id=p["id"], name=p["name"], ok=r["ok"],
                 truncated=bool(r.get("truncated")), text=r["text"][:900], error=r["error"])

    if len(answers) < 2:
        return {"ok": False, "error": f"only {len(answers)} advocate(s) answered",
                "calls": stats["calls"], "tokens": stats["tokens"], "transcript": transcript}

    def block(d: Dict[str, str]) -> str:
        by_id = {p["id"]: p for p in panel}
        return "\n\n".join(
            f'[{by_id[i]["name"]} · {by_id[i]["stance"]} · id={i}]\n{t}' for i, t in d.items())

    # ---- R1: judge scores; CODE decides ------------------------------------
    emit("round", round=1, phase="critique", judge=judge_model)
    # The judge sees the reference material too. It was previously given the question
    # and the answers only, so the "judge the source, not just the number" rule asked
    # it to assess something it could not see - and it duly scored 8/10 an answer
    # arguing about an API-based orchestra from a consumer-GPU forum thread
    # (2026-08-05). A rule about sources is worthless to a reader without the sources.
    r = run(judge_model, _JUDGE_REVIEW_SYS,
            f"QUESTION: {question}\n\n{ground_prefix}ADVOCATE ANSWERS:\n{block(answers)}",
            temp=0.2, mx=1000)
    review = _json_from(r["text"]) or {}

    raw_scores = review.get("scores") or {}
    scores: Dict[str, float] = {}
    for k, v in raw_scores.items():
        if k in answers:
            try:
                scores[k] = max(0.0, min(10.0, float(v)))
            except (TypeError, ValueError):
                pass
    defects = {k: str(v) for k, v in (review.get("defects") or {}).items()
               if k in answers and str(v).strip()}

    # Arithmetic is checked, not judged. A wrong product is not a matter of opinion,
    # so it does not go to the judge for scoring - it is verified here and forced
    # into the record. The defect rides the channel opened when synthesis started
    # receiving the judge's findings, so a checked-wrong figure now reaches R2 AND
    # the final answer instead of being silently re-asserted.
    arith_bad, cite_bad = [], []
    # The judge's OWN scores, before any fact-check cap. Agreement is a measurement of
    # how much the PANEL disagrees, and the cap below is a penalty on one answer — two
    # different things that were sharing one dict. A single unverifiable citation took
    # 9,9,9,9 to 9,9,9,5, pushed the spread to 4.0 past ADOPT_SPREAD, and reported the
    # panel as split when three advocates agreed exactly. Measured on the VM 2026-08-09:
    # agreement=LOW on both debates, the second one saying in its own answer "no
    # verified source confirms these rates" — the citation check firing. With grounding
    # thin, that fires often, so EVERY debate was taking the expensive R2 path (11 calls)
    # and the cheap ADOPT path was unreachable for reasons unrelated to consensus.
    judge_scores: Dict[str, float] = dict(scores)
    invariants = HARNESS.require(SEAM_INVARIANTS, consumer="orchestra.judge")
    for i, txt in answers.items():
        found = invariants.check(txt, ground_text)
        if not found:
            continue
        if found[0].startswith("ARITHMETIC"):
            arith_bad.append(i)
        if any(d.startswith("FABRICATED") for d in found):
            cite_bad.append(i)
        merged = " ".join(found)
        defects[i] = (defects[i] + " " + merged) if defects.get(i) else merged
        # Cap the score below ADOPT_MIN_SCORE. An answer whose own arithmetic
        # contradicts itself, or which cites a source that does not exist, must
        # never short-circuit the debate as CASE 1 ADOPT.
        if i in scores:
            scores[i] = min(scores[i], 5.0)
    if arith_bad or cite_bad:
        emit("factcheck", arithmetic=arith_bad, citations=cite_bad,
             detail={i: defects[i][-260:] for i in set(arith_bad) | set(cite_bad)})

    # If the judge produced no usable scores at all we cannot make an honest
    # decision, so we escalate rather than silently adopting. Escalating costs
    # tokens; adopting on no evidence costs correctness.
    if not scores:
        best_id, best_score, spread = None, 0.0, 10.0
    else:
        # Winner comes from the CAPPED scores — an answer with broken arithmetic or a
        # fabricated citation must not win. Spread comes from the judge's raw scores —
        # see judge_scores above for why mixing the two mislabels the panel.
        best_id = max(scores, key=lambda k: scores[k])
        best_score = scores[best_id]
        spread = max(judge_scores.values()) - min(judge_scores.values())

    # Agreement is now MEASURED from the score spread rather than asserted by the
    # judge. The soak had it constant at HIGH 17/18 while changing nothing, which
    # made it a label nobody read.
    agreement = "HIGH" if spread <= ADOPT_SPREAD else "LOW"
    emit("scores", scores=scores, defects={k: v[:200] for k, v in defects.items()},
         best=best_id, best_score=best_score, spread=round(spread, 1), agreement=agreement)

    # CASE 1 — code's call, not the judge's: the best answer must be genuinely
    # strong AND the panel must not be split.
    if best_id and best_score >= ADOPT_MIN_SCORE and agreement == "HIGH" and review.get("improved"):
        emit("verdict", case="ADOPT", winner=best_id, agreement=agreement,
             answer=review["improved"])
        return _finish(question, review["improved"], agreement, 1, stats,
                       "ADOPT", judge_model, started, transcript)

    # CASE 2 — not good enough, or the panel is split: critique and refine.
    critiques = dict(defects)
    for i in answers:
        if not critiques.get(i):
            sc = scores.get(i)
            critiques[i] = (f"Scored {sc:g}/10. Strengthen your weakest claim and make it "
                            "specific." if sc is not None else
                            "Not scored. Restate your argument with concrete support.")
    emit("critique", agreement=agreement, scores=scores,
         critiques={k: str(v)[:400] for k, v in critiques.items()})

    # ---- R2: revise with FULL visibility -------------------------------------
    # Round 1 kept each advocate blind to the others to protect independence.
    # Here the goal flips to convergence, so everyone sees everything.
    #
    # COST: only the CONTENDERS revise. Re-running all four cost ~13 calls and
    # ~8.4k tokens a debate, and the bottom two were being paid to rewrite answers
    # the judge had already scored out of contention. Their R0 arguments still go
    # into everyone's context and into the final synthesis, so nothing is lost from
    # the record - they simply stop paying for a second draft nobody adopts.
    ranked = sorted(answers, key=lambda i: scores.get(i, 0), reverse=True)
    contenders = set(ranked[:REFINE_TOP_N])
    emit("round", round=2, phase="refine", visibility="full",
         revising=[i for i in ranked if i in contenders])
    # Peer answers are clipped in the R2 context: an advocate needs the GIST of the
    # others to converge, not their full text a second time.
    all_answers = block({i: t[:R2_PEER_CHARS] for i, t in answers.items()})

    def revise(p):
        if p["id"] not in answers:
            return p, {"ok": False, "text": "", "tokens": 0, "error": "did not answer R0"}
        if p["id"] not in contenders:
            return p, {"ok": False, "text": "", "tokens": 0, "error": ""}   # scored out
        sys_p = _ADVOCATE_SYS.format(name=p["name"], stance=p["stance"], brief=p["brief"])
        user = (f"QUESTION: {question}\n\nTHE JUDGE'S CRITIQUE OF YOUR ANSWER:\n"
                f"{critiques.get(p['id'], 'Be more specific.')}\n\n"
                f"ALL ANSWERS FROM THE PANEL (you may now see them all):\n{all_answers}\n\n"
                "Give your revised answer. Keep your stance. Under 160 words.")
        return p, run(p["model"], sys_p, user, temp=0.35, mx=700)

    revised: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(panel)) as ex:
        for p, rr in ex.map(revise, panel):
            if rr["ok"]:
                revised[p["id"]] = rr["text"]
            if rr["ok"] or rr["error"]:
                if rr.get("truncated"):
                    stats["truncated"] += 1
                emit("revision", id=p["id"], name=p["name"], ok=rr["ok"],
                     truncated=bool(rr.get("truncated")), text=rr["text"][:900], error=rr["error"])

    # Synthesise from the revisions PLUS the un-revised originals, so an argument
    # that scored low still reaches the judge - it just did not get a second draft.
    final_pool = {**answers, **revised} if revised else answers

    # Measured 2026-08-05: the judge scored a fabricated price 3-5/10 and named
    # "uses outdated/unsourced pricing" as the defect - then synthesised those same
    # invented figures into the final answer. The reason was here: synthesis received
    # ONLY the question and the answers, so the judge re-read the fabrication with no
    # memory of having caught it, and an un-revised 3/10 original arrived looking
    # exactly like a 9/10 one. Its own findings now travel with each answer.
    def scored_block(d: Dict[str, str]) -> str:
        by_id = {p["id"]: p for p in panel}
        out = []
        for i, t in d.items():
            sc = scores.get(i)
            head = f'[{by_id[i]["name"]} · {by_id[i]["stance"]} · id={i}'
            head += f' · YOUR SCORE {sc:g}/10' if sc is not None else ' · unscored'
            if not revised.get(i) and i in answers and sc is not None:
                head += ' · not revised'
            head += ']'
            d_txt = str(defects.get(i) or "").strip()
            if d_txt:
                head += f'\nDEFECT YOU NAMED: {d_txt}'
            out.append(f"{head}\n{t}")
        return "\n\n".join(out)

    r = run(judge_model, _JUDGE_FINAL_SYS,
            f"QUESTION: {question}\n\n{ground_prefix}REVISED ANSWERS:\n"
            f"{scored_block(final_pool)}",
            temp=0.25, mx=1100)
    final = _json_from(r["text"]) or {}
    answer = final.get("answer") or r["text"] or "The panel could not reach an answer."
    agreement = str(final.get("agreement", agreement)).upper()
    emit("verdict", case="SYNTHESISE", agreement=agreement, answer=answer)
    return _finish(question, answer, agreement, 2, stats, "SYNTHESISE",
                   judge_model, started, transcript)


def _finish(question, answer, agreement, rounds, stats, case, judge, started, transcript):
    rec = {"started": started, "finished": time.time(), "question": question,
           "verdict": answer, "agreement": agreement, "rounds": rounds,
           "calls": stats["calls"], "tokens": stats["tokens"], "case": case,
           "judge": judge, "transcript": transcript}
    rec["id"] = HARNESS.require(SEAM_STORE, consumer="orchestra._finish").save(rec)
    # Push the shape of the debate onto the trace span so TraceRoot shows WHY a
    # debate was expensive (which path it took), not merely that it was.
    try:
        update_current_span({
            "orchestra.case": case,
            "orchestra.rounds": rounds,
            "orchestra.agreement": agreement,
            "orchestra.calls": stats["calls"],
            "orchestra.tokens": stats["tokens"],
            "orchestra.truncated": stats.get("truncated", 0),
            "orchestra.judge": judge,
            "orchestra.debate_id": rec.get("id"),
        })
    except Exception:
        pass                       # tracing must never break a deliberation
    log_info(f"[ORCHESTRA] {case} after R{rounds} · agreement={agreement} · "
             f"{stats['calls']} calls · {stats['tokens']} tokens")
    return {"ok": True, "answer": answer, "agreement": agreement, "rounds": rounds,
            "calls": stats["calls"], "tokens": stats["tokens"], "case": case,
            "judge": judge, "id": rec["id"], "transcript": transcript}


# Provenance for the verdict Mizune is ABOUT to voice. Thread-local because two
# requests can be in flight at once and the wrong receipt on the wrong answer is
# worse than no receipt. Set by the tool, consumed by the processor after the model
# has spoken - so she gets to say the answer in her own words while the numbers
# behind it stay code-owned. Lesson 4: LLMs voice, code delivers.
_pending = threading.local()


def recent_run(window: float = 120.0) -> Optional[Dict[str, Any]]:
    """The verdict from a tribunal that already sat on this thread, if very recent.

    Observed live 2026-08-03: asked one question, she called the tool TWICE and two
    full tribunals sat - 6,089 then 6,720 tokens for a single request. The existing
    arg-hash dedup missed it because the model reworded the question slightly
    between calls, so the hashes differed while the INTENT was identical.
    A tribunal is the most expensive thing she can do; within one turn it should
    sit once. Matching on thread+time rather than on wording is deliberate - the
    wording is exactly the part that proved unreliable.
    """
    prev = getattr(_pending, "last", None)
    if prev and (time.time() - prev[0]) < window:
        return prev[1]
    return None


def remember_run(res: Dict[str, Any]) -> None:
    _pending.last = (time.time(), res)


def stash_provenance(res: Dict[str, Any]) -> None:
    # The verdict text is stashed alongside the receipt. Observed live: handed the
    # tribunal's answer and asked to relay it, she replied "Done!" and dropped the
    # entire verdict. Letting her voice it is worth doing, but Master getting the
    # answer cannot depend on her choosing to include it - so the processor checks
    # and substitutes. LLMs voice, code delivers.
    _pending.answer = (res.get("answer") or "") if res.get("ok") else ""
    if not res.get("ok"):
        _pending.line = None
        return
    case = str(res.get("case") or "").upper()
    if case == "SETTLED":
        _pending.line = "— settled question, answered directly (no debate needed)"
        return
    who = "adopted and improved one advocate's answer" if case == "ADOPT" \
        else "synthesised after a round of revisions"
    _pending.line = (f"⚖️ Alucard {who} · agreement {res.get('agreement', '?')} · "
                     f"round {res.get('rounds', '?')} · {res.get('calls', '?')} calls · "
                     f"{res.get('tokens', '?')} tokens")


def take_provenance() -> Optional[str]:
    """Return the pending provenance line ONCE, then clear it.

    Cleared on read so a later unrelated reply can never inherit a stale receipt
    and claim a deliberation that did not happen on that turn.
    """
    line = getattr(_pending, "line", None)
    _pending.line = None
    return line


def take_verdict() -> str:
    """The verdict text she was asked to relay, consumed once."""
    a = getattr(_pending, "answer", "") or ""
    _pending.answer = ""
    return a


def relay_failed(reply: str, verdict: str) -> bool:
    """True when her reply clearly did not carry the verdict.

    Deliberately conservative - it only fires on an obvious drop ("Done!"), never
    on a genuine paraphrase, because rewriting a good answer she voiced well would
    be worse than the problem it fixes.
    """
    if not verdict:
        return False
    body = (reply or "").strip()
    if len(body) < 120 and len(verdict) > 200:
        return True                       # an acknowledgement, not an answer
    # No meaningful overlap of longer words means she talked about something else.
    vw = {w.lower() for w in re.findall(r"[A-Za-z]{6,}", verdict)}
    bw = {w.lower() for w in re.findall(r"[A-Za-z]{6,}", body)}
    return len(vw & bw) < 3 if vw else False


def format_reply(res: Dict[str, Any]) -> str:
    """One-line provenance under the answer, matching how mesh reports itself."""
    if not res.get("ok"):
        return f"The orchestra couldn't deliberate: {res.get('error', 'unknown error')}"
    return (f"{res['answer']}\n\n"
            f"⚖️ Alucard's verdict · {res['case'].lower()} after round {res['rounds']} · "
            f"agreement {res['agreement']} · {res['calls']} calls · {res['tokens']} tokens")
