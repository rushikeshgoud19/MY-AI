"""Read-only grounding tools for the Agent Orchestra.

WHY THIS EXISTS: the panel is confidently quantitative and entirely ungrounded.
Senku says things like "~100k writes/sec" and "2-10x faster" - those numbers are
GENERATED, not measured, and a judge scoring an answer has no way to tell the
difference. These tools put real, fetched text in front of the advocates before
they argue.

HARD CONSTRAINT: everything here is READ-ONLY and side-effect free. No writes, no
sends, no code execution, no filesystem access. server/orchestra.py states
"this module never executes tools" and that guarantee is load-bearing - four
models arguing is safe precisely because nothing they say runs. Grounding reads
the world; it never touches it.

BACKEND CHAIN - FREE FIRST, re-measured 2026-08-03 when firecrawl credits ran low.
A grounding layer that dies when a credit balance hits zero is not a grounding
layer, so the metered backend is now a bonus rather than a dependency:
  1. marginalia          FREE, NO KEY. 20 rows on every query tested, ~1s. Independent
                         index that favours technical writing. The dependable one.
                         Retried once: a single slow response used to drop the whole
                         chain to nothing.
  2. html.duckduckgo.com FREE, NO KEY, opportunistic. Note the HOST - plain
                         duckduckgo.com/html/ is DEAD (200 with no result markup),
                         html.duckduckgo.com/html/ still parses. It RATE LIMITS hard:
                         two queries succeeded, the next two returned 0 rows in 0.3s,
                         which is a block page wearing a 200. Merged when it answers,
                         never depended on, 10-minute cooldown the moment it goes quiet.
  3. firecrawl v2        METERED. Better snippets, but only consulted when the free
                         backends came up short AND a key exists. creditsUsed is
                         reported upward so the spend is never silent.
  4. wikipedia           LAST RESORT. Its search returns something for EVERY query
                         whether relevant or not, so its hits alone must pass the
                         relevance gate below.
Rejected after testing: searx public instances (403/429/non-JSON), s.jina.ai (401,
now key-gated), mojeek and ddg-lite (no parseable rows).

Losing search must degrade the answer, never break the debate: every failure path
returns empty and the panel simply argues ungrounded.
"""

import ast
import json
import operator
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from .config import log_info

_UA = "Mizune-Orchestra/1.0 (personal assistant; contact via repo)"
WIKI_API = "https://en.wikipedia.org/w/api.php"


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# --------------------------------------------------------------------- wikipedia
def wikipedia_search(query: str, n: int = 3) -> List[Dict[str, str]]:
    """Titles + plain-text extracts for a query. Returns [] on any failure."""
    try:
        url = (WIKI_API + "?action=query&list=search&format=json&srlimit=" + str(max(1, min(5, n)))
               + "&srsearch=" + urllib.parse.quote(query))
        hits = json.loads(_get(url)).get("query", {}).get("search", [])
        titles = [h["title"] for h in hits]
        if not titles:
            return []
        # One extra call fetches intro extracts for every hit at once.
        url2 = (WIKI_API + "?action=query&prop=extracts&exintro=1&explaintext=1&format=json"
                "&redirects=1&titles=" + urllib.parse.quote("|".join(titles)))
        pages = json.loads(_get(url2)).get("query", {}).get("pages", {})
        out = []
        for p in pages.values():
            txt = re.sub(r"\s+", " ", (p.get("extract") or "")).strip()
            if txt:
                out.append({"title": p.get("title", ""), "extract": txt[:700]})
        return out
    except Exception as e:
        log_info(f"[ORCHESTRA-TOOLS] wikipedia lookup failed: {e}")
        return []


# --------------------------------------------------------------------- calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calc(expr: str) -> Any:
    """Evaluate arithmetic with an AST walk, never eval().

    eval() on model-authored text is remote code execution wearing a hat. This
    walks a parsed tree and refuses every node type that is not arithmetic, so the
    worst a malformed expression can do is raise.
    """
    def ev(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise ValueError("only numbers allowed")
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            # Guard the exponent BEFORE computing. 2**10**10 is not a big number,
            # it is a hang followed by an OOM - no result-size check downstream
            # ever gets the chance to run.
            if isinstance(node.op, ast.Pow) and (abs(right) > 1024 or abs(left) > 1e6):
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported expression")
    try:
        v = ev(ast.parse(str(expr).strip(), mode="eval").body)
        # Both branches matter. The original check tested only float, so 2**99999
        # returned a 30,000-digit INT that escaped intact and then blew up in the
        # caller on str() - Python refuses int->str conversion beyond 4300 digits.
        # bit_length() is used rather than str() because measuring the number must
        # not trigger the very conversion that fails.
        if isinstance(v, int) and v.bit_length() > 256:
            raise ValueError("result too large")
        if isinstance(v, float) and (v != v or abs(v) > 1e15):
            raise ValueError("out of range")
        return v
    except Exception as e:
        return f"error: {e}"


# --------------------------------------------------------------------- grounding
_STOP = {"the", "a", "an", "is", "are", "should", "would", "could", "do", "does", "did",
         "if", "it", "its", "or", "and", "to", "of", "for", "in", "on", "at", "be", "by",
         "with", "as", "that", "this", "than", "then", "not", "no", "can", "will", "what",
         "why", "how", "when", "who", "better", "worse", "more", "less", "own", "their"}


def _key_terms(question: str, limit: int = 4) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-']+", question)
    seen, out = set(), []
    for w in words:
        lw = w.lower()
        if lw in _STOP or len(lw) < 4 or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
    return out[:limit]


# --------------------------------------------------------------------- firecrawl
# Real web search, unlike Wikipedia. It is also METERED - credits are finite and
# do not reset like a token budget - so results are cached and every call reports
# what it spent. Wikipedia stays as the free fallback when credits run out or the
# service is down; losing search must degrade the answer, not break the debate.
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
_fc_cache: Dict[str, List[Dict[str, str]]] = {}
_fc_credits_used = 0


def firecrawl_credits() -> int:
    """Credits spent by this process since start. Surfaced so the cost is visible."""
    return _fc_credits_used


def firecrawl_search(query: str, api_key: str, n: int = 3) -> List[Dict[str, str]]:
    """Web search. Returns [] on any failure so the caller can fall back."""
    global _fc_credits_used
    key = f"{query.lower().strip()}::{n}"
    if key in _fc_cache:
        return _fc_cache[key]
    if not api_key:
        return []
    try:
        body = json.dumps({"query": query, "limit": max(1, min(5, n))}).encode()
        req = urllib.request.Request(
            FIRECRAWL_URL, data=body,
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json", "User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read())
        _fc_credits_used += int(d.get("creditsUsed") or 0)
        raw = d.get("data")
        if isinstance(raw, dict):
            raw = raw.get("web") or []
        out = []
        for it in (raw or []):
            desc = re.sub(r"\s+", " ", str(it.get("description") or "")).strip()
            title = str(it.get("title") or "").strip()
            if not (title or desc):
                continue
            out.append({"title": title[:120], "url": str(it.get("url") or "")[:200],
                        "extract": desc[:700]})
        _fc_cache[key] = out
        return out
    except Exception as e:
        log_info(f"[ORCHESTRA-TOOLS] firecrawl search failed: {e}")
        return []


# ------------------------------------------------------------------- free search
# MEASURED 2026-08-03 against four varied queries:
#   marginalia          20 rows every time, ~1s, free, NO KEY. Independent index that
#                       favours technical writing and blogs. The dependable one.
#   html.duckduckgo.com 10 good rows - but note the HOST. duckduckgo.com/html/ is dead
#                       (200 with no result markup); html.duckduckgo.com/html/ still
#                       works. It RATE LIMITS hard: two queries succeeded, the next two
#                       returned 0 rows in 0.3s, which is a block page wearing a 200.
#                       Therefore opportunistic only - merged when it answers, never
#                       depended on, and put on cooldown the moment it goes quiet.
# Everything else failed: searx public instances (403/429/non-JSON), s.jina.ai (401,
# now needs a key), mojeek and ddg-lite (no parseable rows), wikipedia (no rows for
# technical queries - it stays as a last resort only).
MARGINALIA_API = "https://api.marginalia.nu/public/search/"
DDG_HTML = "https://html.duckduckgo.com/html/?q="
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
_ddg_cooldown_until = 0.0


def _strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# --------------------------------------------------------------- page fetching
# Until now the reference block was built entirely from search-result DESCRIPTIONS
# - at most 900 characters of blurb across three hits - while every backend
# returned a url that nothing ever opened. Measured: the Mistral pricing question
# grounded on a valuation article's summary line while an actual pricing page sat
# one fetch away. Snippets say a page is ABOUT pricing; only the page has the table.
#
# Everything here obeys the module rule that losing search must degrade the answer
# and never break the debate: bounded read, bounded time, and any failure returns
# empty so the caller falls back to the snippet it already had.
_PAGE_BYTES = 400_000          # a document larger than this is not a doc page
_PAGE_TIMEOUT = 6              # per page; two fetches is the whole added latency
_DROP_BLOCKS = re.compile(r"<(script|style|noscript|svg)\b[^>]*>.*?</\1>",
                          re.IGNORECASE | re.DOTALL)


def fetch_page(url: str, terms: List[str], width: int = 700) -> str:
    """Readable text from one page, focused on `terms`. Empty string on any problem."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_PAGE_TIMEOUT) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            # A PDF or an image decodes to noise that looks like text to a model.
            if "html" not in ctype and "text/plain" not in ctype:
                return ""
            raw = r.read(_PAGE_BYTES).decode("utf-8", "replace")
    except Exception:
        return ""
    text = _strip_tags(_DROP_BLOCKS.sub(" ", raw))
    return _best_window(text, terms, width) if text else ""


def _best_window(text: str, terms: List[str], width: int) -> str:
    """The `width` characters of `text` densest in `terms`.

    Naive truncation takes a page's navigation and cookie banner. The fact that was
    wanted is usually in a table halfway down, so the window is chosen by where the
    query's own words actually land.
    """
    if len(text) <= width:
        return text
    lowered = text.lower()
    hits = []
    for t in terms:
        t = (t or "").lower()
        if len(t) < 3:
            continue
        start = 0
        while True:
            i = lowered.find(t, start)
            if i < 0 or len(hits) > 400:
                break
            hits.append(i)
            start = i + len(t)
    if not hits:
        return text[:width]
    # Slide a window over the hit positions and keep the densest. Numbers count
    # for something too: a question answered by a figure is answered by the part
    # of the page that HAS figures.
    best_i, best_score = 0, -1
    for h in hits:
        s = max(0, h - width // 3)
        chunk = text[s:s + width]
        score = sum(1 for x in hits if s <= x < s + width)
        score += min(6, len(re.findall(r"\d", chunk)) // 8)
        if score > best_score:
            best_i, best_score = s, score
    return text[best_i:best_i + width]


def marginalia_search(query: str, n: int = 5) -> List[Dict[str, str]]:
    # It is a small public service and occasionally just takes too long. One retry,
    # because losing the PRIMARY backend to a single slow response drops the whole
    # chain to nothing - observed exactly that on a query that works fine on retry.
    for attempt in (1, 2):
        try:
            d = json.loads(_get(MARGINALIA_API + urllib.parse.quote(query), timeout=30))
            out = []
            for r in (d.get("results") or [])[:max(1, n)]:
                title = str(r.get("title") or "").strip()
                desc = str(r.get("description") or "").strip()
                if title:
                    out.append({"title": title[:120], "url": str(r.get("url") or "")[:200],
                                "extract": desc[:700]})
            return out
        except Exception as e:
            if attempt == 2:
                log_info(f"[ORCHESTRA-TOOLS] marginalia failed twice: {e}")
                return []
            time.sleep(1.0)
    return []


def ddg_search(query: str, n: int = 5) -> List[Dict[str, str]]:
    """Best-effort. Silently yields nothing while cooling down after a block."""
    global _ddg_cooldown_until
    if time.time() < _ddg_cooldown_until:
        return []
    try:
        req = urllib.request.Request(DDG_HTML + urllib.parse.quote(query),
                                     headers={"User-Agent": _BROWSER_UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.S)
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
        rows = [{"title": _strip_tags(t)[:120], "url": "", "extract": _strip_tags(s)[:700]}
                for t, s in zip(titles, snips)][:max(1, n)]
        if not rows:
            # A 200 with no rows is the block page. Back off rather than hammer it.
            _ddg_cooldown_until = time.time() + 600
        return rows
    except Exception:
        _ddg_cooldown_until = time.time() + 600
        return []


def _relevant(query: str, title: str) -> bool:
    """Does this article plausibly answer the query, or is it a coincidence?

    Wikipedia's search always returns SOMETHING. Asking it about
    "should an AI have the right to refuse its owner" returned
    "2026 FIFA World Cup officials" and "Ted Lasso" - confidently, at rank 1.
    Feeding that to the panel as reference material is not neutral, it actively
    poisons the debate, so a hit has to share a real term with the query or it
    is dropped. Irrelevant grounding is strictly worse than none.
    """
    qt = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-']{3,}", query)} - _STOP
    tt = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-']{3,}", title)} - _STOP
    shared = qt & tt
    if not shared:
        return False
    # One shared common word is a coincidence, not a match. "Should an AI assistant
    # have the right to refuse its owner" shares "right" with "The customer is
    # always right", which is how a retail slogan got admitted as evidence in an
    # AI-autonomy debate. Demand either a distinctive term or two overlaps.
    return any(len(w) >= 7 for w in shared) or len(shared) >= 2


# Raised from 900 when page fetching landed: a fetched window carries real content
# where a snippet carried a sentence fragment, and 900 chars across three sources
# left barely 300 each. This block is read by five advocates and twice by the judge,
# so every extra character is paid for seven times - hence 1500, not 5000.
def gather_grounding(question: str, query: str = "", api_key: str = "",
                     max_chars: int = 1500) -> Dict[str, Any]:
    """Fetch reference material. Costs ZERO LLM calls on its own.

    `query` should be a focused search phrase chosen by the caller (the orchestra
    asks a cheap model for one, and passes "" / "NONE" for normative questions
    where an encyclopedia has nothing useful to add). Falling back to naive
    keyword extraction is kept only as a last resort, and every hit still has to
    pass the relevance gate.

    Shared across all four advocates on purpose: giving each its own research
    budget would multiply cost and let them argue from different private facts,
    which is worse than arguing from none. One set of facts, four readings of it.
    """
    # Strip quotes/punctuation the model wraps around its phrase, and keep it short -
    # Wikipedia search degrades badly on long quoted sentences.
    query = re.sub(r'^["\'\s]+|["\'\s.]+$', "", (query or "").strip())
    query = " ".join(query.split()[:6])

    # NONE means the caller judged an encyclopedia useless here - usually a purely
    # normative question. Falling back to keyword extraction at that point defeats
    # the entire check: it is what admitted "The customer is always right" into a
    # debate about AI autonomy. Respect the refusal.
    if not query or query.upper() == "NONE":
        return {"ok": False, "query": "", "sources": [], "text": "", "backend": "none",
                "credits": firecrawl_credits(),
                "reason": "no factual grounding applicable to this question"}

    # FREE FIRST. Firecrawl produced better snippets but it is metered and will run
    # out; a grounding layer that dies when a credit balance hits zero is not a
    # grounding layer. Marginalia and DDG cost nothing and are merged for coverage -
    # Marginalia's index is independent and technical, DDG's is mainstream, and the
    # union beats either alone. Firecrawl is now a bonus, not a dependency.
    #
    # The relevance gate is applied to WIKIPEDIA ONLY: real search engines have
    # already ranked for relevance, and re-filtering on title-word overlap would
    # discard good technical sources whose titles do not repeat the query. Wikipedia
    # needs it because its search returns something for every query regardless.
    used: List[str] = []
    hits: List[Dict[str, str]] = []
    seen_titles = set()

    def add(rows, label):
        added = 0
        for h in rows:
            key = h["title"].lower()[:60]
            if key and key not in seen_titles:
                seen_titles.add(key)
                hits.append(h)
                added += 1
        if added:
            used.append(label)

    add(marginalia_search(query, n=4), "marginalia")
    add(ddg_search(query, n=4), "ddg")
    if len(hits) < 2 and api_key:
        add(firecrawl_search(query, api_key, n=4), "firecrawl")
    if not hits:
        add([h for h in wikipedia_search(query, n=4) if _relevant(query, h["title"])],
            "wikipedia")

    backend = "+".join(used) if used else "none"
    if not hits:
        return {"ok": False, "query": query, "sources": [], "text": "", "backend": "none",
                "credits": firecrawl_credits(),
                "reason": "no relevant source found - proceeding ungrounded"}

    # Open the hits rather than quoting their search blurb. A failed fetch silently
    # keeps the snippet, so this can improve the block and never empty it.
    #
    # ALL THREE are fetched, and the budget is then filled BEST-FIRST rather than in
    # search order. Measured 2026-08-05: for "what does Mistral charge per million
    # tokens", marginalia ranked a company-valuation article first and a vendor
    # directory second, while the hit actually titled "Pricing" came third. Fetching
    # the top two got two pages that could not answer the question and skipped the
    # one that could. Search rank answers "what is about this topic"; it does not
    # answer "what contains this fact".
    terms = _key_terms(question, limit=6) or query.split()

    def _density(txt: str) -> int:
        low = (txt or "").lower()
        hits_ = sum(low.count(t.lower()) for t in terms if len(t) > 2)
        # A question answered by a figure is answered by the part that has figures.
        return hits_ + min(6, len(re.findall(r"\d", txt or "")) // 10)

    cand = []
    fetched = 0
    for h in hits[:3]:
        body = fetch_page(h["url"], terms) if h.get("url") else ""
        if body:
            fetched += 1
        text = body or h["extract"]
        cand.append((_density(text), h["title"], text))
    cand.sort(key=lambda c: -c[0])

    parts, sources, total = [], [], 0
    for _score, title, text in cand:
        chunk = f"[{title}] {text}"
        if total + len(chunk) > max_chars:
            chunk = chunk[:max(0, max_chars - total)]
        if not chunk.strip():
            break
        parts.append(chunk)
        sources.append(title)
        total += len(chunk)
    if fetched:
        backend += "+page"
    return {"ok": True, "query": query, "sources": sources, "backend": backend,
            "credits": firecrawl_credits(), "text": "\n\n".join(parts),
            "fetched": fetched, "reason": ""}
