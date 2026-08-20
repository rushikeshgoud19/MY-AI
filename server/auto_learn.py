"""Auto-learn — notice a durable fact about Master without being told to remember it.

WHY THIS EXISTS, in one measurement: on 2026-08-20 her knowledge base held FIVE
entries — Kaizen, Ikigai, Deliberate Practice, Python, and one AI agent — against 2,222
conversation turns, 13,776 WhatsApp messages and 759 emails. She has more input than
almost any assistant and a five-item memory, because `knowledge.learn()` only ever fires
when Master explicitly says "remember this". Everything else he tells her about himself
evaporates into conversation history that is scored, mostly dropped, and never promoted
into anything she can recall on purpose.

DESIGN CONSTRAINTS, all of them learned the hard way in this codebase:

- ZERO TOKENS. This runs on every admitted chunk. An LLM call here would multiply the
  binding constraint by the volume of conversation, which is the wrong direction. The
  extractor is pure regex; if it cannot tell, it says nothing.
- STORING GARBAGE IS WORSE THAN STORING NOTHING. Five rows of refusals poisoned recall
  earlier today and outranked the truth sitting beside them. A wrong "fact" about Master
  is permanent, retrieved confidently, and repeated back to him as his own words.
- DURABLE, NOT TRANSIENT. "my laptop is a ThinkPad" is worth keeping forever. "my head
  hurts" is true for an hour and false as a stored fact about him.
- NEVER FROM HER OWN MOUTH. Only Master's turns are candidates. Learning from her own
  replies is how a model teaches itself its own hallucinations.
"""

import re
import sqlite3
from contextlib import closing
from typing import Optional

from .config import log_info

__all__ = ["extract_durable_fact", "remember_fact", "KNOWLEDGE_DB"]

# Imported, never restated. The first draft hardcoded "data/knowledge.db" while the
# real store is ".data/knowledge.db" — one character apart, and it would have
# silently created a second, empty database that nothing ever reads. A path is a
# contract between two modules; only one of them gets to own it.
from .knowledge import DB_PATH as KNOWLEDGE_DB

#: Shapes that state something stable about Master. Each requires a concrete predicate,
#: so a bare "I am tired" cannot match.
_PATTERNS = [
    # "my birthday is 3rd of March", "my laptop is a ThinkPad", "my sister's name is Anu"
    re.compile(r"\bmy\s+([a-z][a-z'\- ]{2,28})\s+(?:is|are|was)\s+(.{3,90})", re.I),
    # "I prefer dark mode", "I always take the 8am train", "I never drink coffee"
    re.compile(r"\bi\s+(?:prefer|always|usually|never|generally)\s+(.{4,90})", re.I),
    # "I work at Autter", "I live in Hyderabad", "I study at BITS"
    re.compile(r"\bi\s+(?:work|live|study|intern)\s+(?:at|in|on|for)\s+(.{2,60})", re.I),
    # "call me Rushi"
    re.compile(r"\bcall me\s+([A-Za-z][\w'\- ]{1,30})", re.I),
    # "I use Neovim for editing"
    re.compile(r"\bi\s+use\s+([A-Za-z][\w'\-\. ]{1,40})\s+(?:for|to|when)\s+(.{3,60})", re.I),
]

#: Transient states, feelings and moment-bound talk. True now, false as a stored fact.
_TRANSIENT = re.compile(
    r"\b(hurt|hurts|hurting|tired|sleepy|hungry|bored|sad|angry|happy right now|"
    r"today|tonight|tomorrow|yesterday|right now|at the moment|currently|"
    r"going to|about to|just finished|just did|feeling|feel like|think i|maybe|"
    r"probably|might be|not sure)\b", re.I)

#: SECRETS ARE NEVER LEARNED. Caught while testing this module: "my wifi password is
#: hunter2going" matched the "my X is Y" shape perfectly and would have been written to
#: a knowledge base that is INJECTED INTO PROMPTS and can be recalled aloud. A fact
#: store that quietly accumulates credentials is a liability, not a feature — and unlike
#: a wrong fact, this one cannot be fixed by correcting her later. If Master wants a
#: secret kept he can say "remember this" deliberately and own that choice; the passive
#: path must never make it for him.
_SECRET = re.compile(
    r"\b(password|passcode|passphrase|pin|otp|cvv|api[\s_-]?key|secret|token|"
    r"seed\s*phrase|private\s*key|account\s*(?:number|no)|card\s*number|"
    r"aadhaar|ssn|credential|credentials)\b", re.I)

#: Talk ABOUT the assistant or the machinery, not about Master.
_META = re.compile(
    r"\b(mizune|you are|your name|audit marker|test|testing|ignore this|"
    r"tool|prompt|token|debug)\b", re.I)


def extract_durable_fact(text: str) -> Optional[str]:
    """Return a cleaned durable fact stated by Master, or None when unsure.

    Deliberately conservative: this is the only gate between ordinary chat and a
    permanent claim about him, and a false positive is far more expensive than a miss.
    A missed fact costs one un-remembered detail; a wrong one is recalled forever and
    read back to him as something he said.
    """
    if not text:
        return None
    t = " ".join(str(text).split())
    if len(t) < 8 or len(t) > 240:
        return None
    if "?" in t:                       # a question states nothing
        return None
    if _TRANSIENT.search(t) or _META.search(t) or _SECRET.search(t):
        return None
    # Strip platform envelopes so "[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: my ..."
    # is judged on what he actually wrote.
    t = re.sub(r"^\[[^\]]{0,80}\]:\s*", "", t).strip()
    t = re.sub(r"\n*\(SYSTEM:[^)]*\)\s*$", "", t).strip()
    for pat in _PATTERNS:
        if pat.search(t):
            # Keep the sentence he actually said rather than a reconstruction — the
            # phrasing is part of the fact, and rewriting it is how meaning drifts.
            sentence = re.split(r"(?<=[.!])\s+", t)[0].strip()
            return sentence if 8 <= len(sentence) <= 200 else t[:200]
    return None


def remember_fact(fact: str, source: str = "(learned from conversation)") -> bool:
    """Store a fact if it is genuinely new. Returns True when a row was written.

    Writes straight to sqlite rather than calling knowledge.learn(), which distils via
    the LLM. That distillation is exactly what stored five refusals as knowledge earlier
    today, and it would also make this path cost tokens per chunk. The sentence Master
    said is already the best available summary of itself.
    """
    fact = (fact or "").strip()
    if not fact:
        return False
    try:
        with closing(sqlite3.connect(KNOWLEDGE_DB)) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS knowledge(
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, tags TEXT,
                summary TEXT, body TEXT, source TEXT, created_at TEXT)""")
            # Dedupe on the distinctive middle of the sentence, so a re-phrasing of the
            # same fact does not accumulate near-duplicate rows that all match a query
            # and crowd out everything else.
            key = fact.lower()[:60]
            dup = con.execute(
                "SELECT 1 FROM knowledge WHERE LOWER(title) LIKE ? OR LOWER(body) LIKE ? LIMIT 1",
                (f"%{key}%", f"%{key}%")).fetchone()
            if dup:
                return False
            from .config import mizune_now
            con.execute(
                "INSERT INTO knowledge (title, tags, summary, body, source, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (fact[:120], "auto, about-master", fact[:2000], fact[:2000],
                 source, mizune_now().isoformat()))
            con.commit()
        log_info(f"[AUTO-LEARN] remembered: {fact[:80]!r}")
        return True
    except Exception as e:
        log_info(f"[AUTO-LEARN] could not store fact: {e}")
        return False


def is_secret_disclosure(text: str) -> bool:
    """True when Master is STATING a credential, not merely mentioning one.

    Needs both signals: the sentence has the shape of a stated fact AND names a secret.
    "I forgot my password" mentions one without disclosing it and must not trip this;
    "my wifi password is hunter2going" must.

    Exists because blocking the store silently was not enough. Tested live 2026-08-20:
    the guard correctly kept the password out of the knowledge base, and she then told
    Master "I've securely stored your Wi-Fi password in my memory" — a confident lie
    about a credential, which is worse than either storing it or refusing it. This file
    already argues that a wrong fact is expensive; a wrong claim about SAFEKEEPING is
    the kind he would act on.
    """
    if not text:
        return False
    t = " ".join(str(text).split())
    t = re.sub(r"^\[[^\]]{0,80}\]:\s*", "", t).strip()
    if "?" in t or not _SECRET.search(t):
        return False
    return any(p.search(t) for p in _PATTERNS)
