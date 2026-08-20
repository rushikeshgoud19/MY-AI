"""Compounding knowledge base (Phase HB.1) — "learn this, remember it forever".

Master sends a URL (article or YouTube) or a chunk of text → Mizune fetches the
readable content, has the LLM distil a titled summary + tags, and stores it in
.data/knowledge.db. Later "what do you know about X" keyword-searches the store
and returns the distilled notes WITH their sources. This is the memory that
compounds — every article he feeds her makes her permanently smarter about his world.
"""
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request

from .config import log_info, mizune_now

DB_PATH = os.path.join(".data", "knowledge.db")


def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY, title TEXT, source TEXT, tags TEXT,
        summary TEXT, body TEXT, created_at TEXT)""")
    return con


def _backfill_chroma():
    from .memory import memory
    if not memory or not memory.chroma_client:
        return
    try:
        collection = memory.chroma_client.get_or_create_collection("knowledge")
        con = _db()
        db_count = con.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        count = collection.count()
        if db_count > count:
            rows = con.execute("SELECT id, title, tags, summary, source FROM knowledge").fetchall()
            docs, metas, ids = [], [], []
            existing_data = collection.get(include=[])
            existing = set(existing_data["ids"]) if existing_data and "ids" in existing_data else set()
            for kid, title, tags, summary, source in rows:
                str_id = f"kn_{kid}"
                if str_id not in existing:
                    docs.append(f"{title} {tags} {summary}")
                    metas.append({"kid": kid, "title": title, "source": source})
                    ids.append(str_id)
            if docs:
                collection.add(documents=docs, metadatas=metas, ids=ids)
                log_info(f"[KNOWLEDGE] Backfilled {len(docs)} items to Chroma")
        con.close()
    except Exception as e:
        log_info(f"[KNOWLEDGE] Backfill failed: {e}")


def _fetch_text(url: str) -> tuple:
    """Return (title, text). Handles articles and YouTube (transcript via timedtext)."""
    yt = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})", url)
    if yt:
        return _youtube_text(yt.group(1), url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    page = urllib.request.urlopen(req, timeout=15).read(800_000).decode("utf-8", "replace")
    import html as _html
    title_m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    title = _html.unescape(title_m.group(1)).strip() if title_m else url
    page = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", page)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", page))
    return title[:120], re.sub(r"\s+", " ", text).strip()


def _youtube_text(vid: str, url: str) -> tuple:
    """Best-effort YouTube transcript + title (no API key; uses public endpoints)."""
    title = f"YouTube {vid}"
    try:
        watch = urllib.request.Request("https://www.youtube.com/watch?v=" + vid,
                                       headers={"User-Agent": "Mozilla/5.0"})
        html_page = urllib.request.urlopen(watch, timeout=15).read().decode("utf-8", "replace")
        tm = re.search(r'"title":"([^"]{3,120})"', html_page)
        if tm:
            title = tm.group(1).encode().decode("unicode_escape", "ignore")
    except Exception:
        pass
    for lang in ("en", "en-US", "en-GB"):
        try:
            tt = f"https://www.youtube.com/api/timedtext?lang={lang}&v={vid}"
            xml = urllib.request.urlopen(tt, timeout=12).read().decode("utf-8", "replace")
            if xml.strip():
                import html as _html
                text = _html.unescape(re.sub(r"<[^>]+>", " ", xml))
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 40:
                    return title[:120], text
        except Exception:
            continue
    return title[:120], f"(No transcript available for this video: {url})"


def learn(source: str, config: dict, body_override: str = None) -> str:
    source = (source or "").strip()
    if not source:
        return "What should I learn, Master? Give me a link or some text."
    is_url = source.startswith(("http://", "https://"))
    is_file = source.startswith("file://")
    try:
        if body_override:
            title = os.path.basename(source.replace("file://", ""))
            body = body_override
        elif is_url:
            title, body = _fetch_text(source)
        else:
            title, body = None, source
        if not body or len(body) < 40:
            return "There wasn't enough readable content there to learn, Master."
        body = body[:8000]

        # Distil with the LLM (no-tools override — pure text out).
        from .ai import get_ai_response
        distilled, _ = get_ai_response(
            f"Source: {source}\n\nContent:\n{body}", [], config,
            system_prompt_override=(
                "Summarize this for a personal knowledge base. Output EXACTLY:\n"
                "TITLE: <short title>\nTAGS: <3-6 comma-separated lowercase keywords>\n"
                "SUMMARY: <5-8 tight bullet points, each on its own line starting with '- '>"))
        d = str(distilled or "")
        tm = re.search(r"TITLE:\s*(.+)", d)
        tg = re.search(r"TAGS:\s*(.+)", d)
        sm = re.search(r"SUMMARY:\s*(.+)", d, re.S)
        final_title = (tm.group(1).strip() if tm else (title or source))[:120]
        tags = (tg.group(1).strip().lower() if tg else "")[:200]
        summary = (sm.group(1).strip() if sm else d.strip())[:2000]

        con = _db()
        cursor = con.cursor()
        src_val = source if (is_url or is_file) else "(text)"
        existing_row = None
        if is_url or is_file:
            existing_row = cursor.execute("SELECT id FROM knowledge WHERE source = ?", (src_val,)).fetchone()
            
        if existing_row:
            kid = existing_row[0]
            cursor.execute(
                "UPDATE knowledge SET title = ?, tags = ?, summary = ?, body = ?, created_at = ? WHERE id = ?",
                (final_title, tags, summary, body, mizune_now().isoformat(), kid))
        else:
            cursor.execute(
                "INSERT INTO knowledge (title, source, tags, summary, body, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (final_title, src_val, tags, summary, body, mizune_now().isoformat()))
            kid = cursor.lastrowid
        con.commit()
        con.close()
        
        from .memory import memory
        if memory and memory.chroma_client:
            try:
                collection = memory.chroma_client.get_or_create_collection("knowledge")
                collection.upsert(
                    documents=[f"{final_title} {tags} {summary}"],
                    metadatas=[{"kid": kid, "title": final_title, "source": src_val}],
                    ids=[f"kn_{kid}"]
                )
            except Exception as e:
                log_info(f"[KNOWLEDGE] Chroma store failed: {e}")

        log_info(f"[KNOWLEDGE] Learned '{final_title}' ({len(body)} chars, tags: {tags})")
        return f"Got it, Master — I've learned '{final_title}' and saved it to memory. Ask me about it anytime! 🧠"
    except Exception as e:
        log_info(f"[KNOWLEDGE] learn failed: {e}")
        return f"I couldn't learn that, Master: {e}"


import re as _re

#: Words that carry no retrieval signal. Kept small on purpose — over-filtering
#: throws away the very term the question is about.
_STOPWORDS = {"what", "when", "where", "which", "who", "why", "how", "the", "and",
              "for", "you", "your", "my", "mine", "me", "is", "are", "was", "were",
              "do", "does", "did", "tell", "just", "with", "about", "reply", "code",
              "give", "get", "please", "can", "could", "would", "that", "this",
              "have", "has", "had", "from", "into", "any", "all"}


def recall(query: str, config: dict = None) -> str:
    query = (query or "").strip()
    con = _db()
    if not query:
        rows = con.execute(
            "SELECT title, tags, source FROM knowledge ORDER BY id DESC LIMIT 8").fetchall()
        con.close()
        if not rows:
            return "My knowledge base is empty, Master — teach me something with 'learn this: <link>'."
        return "Here's what I've learned so far, Master:\n" + "\n".join(
            f"- {t} ({tags})" for t, tags, _ in rows)
    
    rows = None
    from .memory import memory
    if memory and memory.chroma_client:
        _backfill_chroma()
        try:
            collection = memory.chroma_client.get_collection("knowledge")
            results = collection.query(query_texts=[query], n_results=3)
            if results and results.get("metadatas") and results["metadatas"] and results["metadatas"][0]:
                kids = [m.get("kid") for m in results["metadatas"][0] if m.get("kid")]
                if kids:
                    placeholders = ",".join("?" * len(kids))
                    con2 = _db()
                    db_rows = con2.execute(f"SELECT id, title, summary, source FROM knowledge WHERE id IN ({placeholders})", kids).fetchall()
                    con2.close()
                    if db_rows:
                        row_dict = {r[0]: (r[1], r[2], r[3]) for r in db_rows}
                        rows = [row_dict[k] for k in kids if k in row_dict]
        except Exception as e:
            log_info(f"[KNOWLEDGE] Chroma recall failed: {e}")

    if not rows:
        # KEYWORD fallback, not whole-question LIKE.
        #
        # This used to be `like = f"%{query.lower()}%"` — the ENTIRE user question as one
        # pattern. "What is my audit marker? Reply with just the code." is a 50-character
        # string that appears verbatim in no title, tag or body, so the fallback could
        # never fire for a natural-language question; it only worked when the phrasing
        # happened to be a literal substring of the stored text. Measured 2026-08-17: 0
        # matches for that question against a knowledge base holding 5 rows that contain
        # the marker. The data was there the whole time and the search could not reach it,
        # so she answered from her own head and invented a value.
        #
        # Match on the significant words instead, and rank by how many of them a row
        # contains, so a row mentioning several query terms beats one mentioning any.
        words = [w for w in _re.findall(r"[a-z0-9_]{3,}", query.lower())
                 if w not in _STOPWORDS][:8]
        if words:
            score = " + ".join(
                "(CASE WHEN LOWER(title) LIKE ? OR LOWER(tags) LIKE ? "
                "OR LOWER(body) LIKE ? THEN 1 ELSE 0 END)" for _ in words)
            params = []
            for w in words:
                params += [f"%{w}%"] * 3
            rows = con.execute(
                f"SELECT title, summary, source, ({score}) AS hits FROM knowledge "
                f"WHERE hits > 0 ORDER BY hits DESC, id DESC LIMIT 3", params).fetchall()
            rows = [(t, s_, src) for t, s_, src, _h in rows]
    
    con.close()
    if not rows:
        return f"I don't have anything on '{query}' yet, Master. Teach me with 'learn this: <link>'."
    out = []
    for title, summary, source in rows:
        src = f"\nSource: {source}" if source and source != "(text)" else ""
        out.append(f"📚 {title}\n{summary}{src}")
    return f"Here's what I know about '{query}', Master:\n\n" + "\n\n".join(out)


def index_files(root: str, pattern: str = None, config: dict = None) -> str:
    """Ask laptop device agent for files, read them, and index into Chroma knowledge DB."""
    root = (root or "Desktop").strip()
    config = config or {}

    from .device_registry import device_registry
    res_str = device_registry.send_command("laptop", "list_files", {"root": root, "pattern": pattern, "max": 100})
    log_info(f"[INDEX_FILES] list_files('{root}') returned: {res_str[:200]}")
    if "not online" in res_str.lower():
        return "Your laptop device agent isn't connected right now, Master."
    if "Refused:" in res_str or "Error:" in res_str:
        return res_str

    import json, threading
    try:
        files = json.loads(res_str)
    except Exception as e:
        return f"Couldn't parse file list from laptop: {res_str[:150]}"

    if not files or not isinstance(files, list):
        return f"No matching files found in '{root}' to index, Master."

    def _bg_index():
        success_count = 0
        for f_path in files:
            try:
                content = device_registry.send_command("laptop", "read_file", {"path": f_path, "max_chars": 20000})
                if content and not any(content.startswith(p) for p in ("Error:", "Refused:", "Can't read")):
                    source_uri = f"file://{f_path}"
                    learn(source_uri, config, body_override=content)
                    success_count += 1
            except Exception as e:
                log_info(f"[INDEX_FILES] Error indexing {f_path}: {e}")
        log_info(f"[INDEX_FILES] Background index finished: {success_count}/{len(files)} files indexed.")

    threading.Thread(target=_bg_index, daemon=True).start()
    return f"Started indexing {len(files)} file(s) from '{root}' in the background, Master! I'll store their knowledge in my memory. 🧠"

