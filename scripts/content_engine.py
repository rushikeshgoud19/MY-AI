"""Content engine — turn REAL git work into LinkedIn/X post drafts.

WHY THIS SHAPE (read before "improving" it into a poster):
LinkedIn's User Agreement §8.2 prohibits automated access, bots, scrapers, headless browsers and
unofficial interfaces. Enforcement in 2026 escalates to permanent suspension, and measured
restriction rates for automation tools run ~23% within 90 days. So this tool NEVER touches
LinkedIn: it reads Rushi's own git history, drafts posts, and hands them to him. He posts manually.
Zero ToS surface, and it solves the actual bottleneck — not "how do I post" but "what do I say".

HOUSE RULES honoured:
  - DETERMINISTIC DATA, LLM ONLY VOICES: the git log is parsed by code; the model only writes prose
    about facts it was handed. It cannot invent work that isn't in the commits.
  - NEVER INVENT SUCCESS: commits are quoted as-is; if a week has nothing substantial, it says so
    instead of manufacturing a milestone.
  - ANTI-SLOP LINTER & VOICE CONTRACT: Every draft is checked deterministically against banned
    phrases, sentence rhythm, emoji/em-dash caps, and the FABRICATED NUMBER CHECK.

USAGE
  .venv\\Scripts\\python.exe scripts\\content_engine.py                  # last 7 days
  .venv\\Scripts\\python.exe scripts\\content_engine.py --days 14
  .venv\\Scripts\\python.exe scripts\\content_engine.py --digest-only    # no LLM, just the facts
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Commits that are noise for storytelling purposes.
SKIP_PAT = re.compile(
    r"^(merge |bump |wip\b|typo|formatting|lint\b|chore\(deps\)|update readme$|initial commit)",
    re.IGNORECASE)

# A commit is "story-worthy" if it reads like a fix/perf/feature with substance.
SIGNAL_PAT = re.compile(
    r"\b(fix|fixed|root.?caus|bug|leak|crash|oom|perf|optimi[sz]|reduce|cut |latency|token|"
    r"verify|verified|reliab|fail(over|ure)?|deploy|implement|build|ship|add(ed)?|refactor)\b",
    re.IGNORECASE)


def git(*args, cwd=None):
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=25,
                           cwd=cwd, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def build_work_digest(days: int = 7, repo: str = None) -> dict:
    """DETERMINISTIC: parse real commits from the last N days. No LLM involved."""
    repo = repo or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw = git("log", f"--since={days}.days.ago", "--no-merges",
              "--pretty=format:%h\x1f%as\x1f%s\x1f%b\x1e", cwd=repo)
    commits = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 3:
            continue
        sha, date, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        if SKIP_PAT.match(subject):
            continue
        commits.append({"sha": sha, "date": date, "subject": subject,
                        "body": body.strip()[:600],
                        "signal": bool(SIGNAL_PAT.search(subject))})

    stat = git("diff", "--shortstat", f"HEAD@{{{days}.days.ago}}", "HEAD", cwd=repo)
    files_changed = insertions = 0
    m = re.search(r"(\d+) files? changed", stat)
    if m:
        files_changed = int(m.group(1))
    m = re.search(r"(\d+) insertions?", stat)
    if m:
        insertions = int(m.group(1))

    return {
        "repo": os.path.basename(repo),
        "days": days,
        "generated_at": datetime.now().astimezone().isoformat(),
        "commit_count": len(commits),
        "signal_commits": [c for c in commits if c["signal"]],
        "all_commits": commits,
        "files_changed": files_changed,
        "insertions": insertions,
    }


def render_digest(d: dict) -> str:
    lines = [f"WORK DIGEST — last {d['days']} days in '{d['repo']}'",
             f"{d['commit_count']} substantive commits · {d['files_changed']} files changed · "
             f"+{d['insertions']} lines"]
    if not d["commit_count"]:
        lines.append("\n(No substantive commits in this window — nothing to post about. "
                     "That's a fine answer; don't manufacture a milestone.)")
        return "\n".join(lines)
    lines.append("\nMOST STORY-WORTHY:")
    for c in (d["signal_commits"] or d["all_commits"])[:8]:
        lines.append(f"  [{c['date']}] {c['subject']}")
        if c["body"]:
            first = [ln for ln in c["body"].splitlines() if ln.strip()]
            if first:
                lines.append(f"        ↳ {first[0][:150]}")
    return "\n".join(lines)


def load_voice_contract() -> str:
    """Load character/VOICE.md if present, else fallback."""
    voice_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "character", "VOICE.md")
    if os.path.exists(voice_path):
        try:
            with open(voice_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


VOICE_PROMPT = """You write a LinkedIn post for Rushikesh, a CS student who builds Mizune — a
self-hosted autonomous AI assistant that runs on a single 898MB cloud VM.

{voice_contract}

Below is ONE commit he actually wrote. Write a LinkedIn post (110-180 words) about THIS ONE THING.

HARD RULES:
- Write about ONLY the commit below. Do NOT mention or combine any other work, and do NOT invent a
  causal link between separate issues. If the commit detail is thin, write a shorter post.
- Use ONLY facts present below. Invent NOTHING — no metrics, no users, no outcomes not stated.
- Lead with the concrete symptom or problem, not a conclusion. Engineers stop scrolling for a
  specific bug; nobody stops for "excited to share".
- Plain sentences. BANNED: "leveraged", "cutting-edge", "game-changing", "excited to share",
  "thrilled to announce", "delve", "robust solution". At most one emoji.
- First person. Say plainly what broke and what you got wrong — self-critical posts land best.
- End with one plain line of what you learned. At most 2 hashtags.
- Output ONLY the post text. No preamble, no "Here's a draft".

THE COMMIT:
Date: {date}
Title: {subject}
Details:
{body}

Context you may reference (true, but only if relevant): Mizune runs 24/7 on one 898MB Azure VM,
built solo, ~96 commits over 4 months.
"""


def is_emoji(char: str) -> bool:
    """Check if character is an emoji."""
    return unicodedata.category(char) in ("So", "Symbol, other") or (0x1F300 <= ord(char) <= 0x1FAFF)


def lint_draft(text: str, digest: str) -> tuple:
    """DETERMINISTIC LINTER for anti-slop checks.
    Returns (ok: bool, problems: list[str]).
    """
    problems = []

    # 1. Banned openers
    openers = ["excited to share", "thrilled to announce", "i'm happy to", "delighted"]
    text_lower = text.lower().strip()
    for opener in openers:
        if text_lower.startswith(opener):
            problems.append(f"Banned opener detected: '{opener}'")

    # 2. Banned words/phrases
    banned_words = [
        "leveraged", "cutting-edge", "game-changing", "seamless", "robust solution",
        "delve", "unlock", "elevate", "harness", "in today's fast-paced", "journey"
    ]
    for w in banned_words:
        if re.search(r"\b" + re.escape(w) + r"\b", text_lower):
            problems.append(f"Banned word/phrase detected: '{w}'")

    # 3. Emoji cap (max 1)
    emoji_count = sum(1 for ch in text if is_emoji(ch))
    if emoji_count > 1:
        problems.append(f"Too many emojis ({emoji_count} > max 1)")

    # 4. Hashtag cap (max 2)
    hashtags = re.findall(r"#\w+", text)
    if len(hashtags) > 2:
        problems.append(f"Too many hashtags ({len(hashtags)} > max 2)")

    # 5. Em-dash cap (max 2)
    em_dashes = text.count("—") + text.count("--")
    if em_dashes > 2:
        problems.append(f"Too many em-dashes ({em_dashes} > max 2)")

    # 6. Participial clause opener
    if re.match(r"^(?:having|being|building|working|developing|creating|using|leveraging|after building|after spending)\b", text_lower):
        problems.append("Post opens with a participial clause (AI tell)")

    # 7. Uniform rhythm check (all sentences similar length)
    # Needs a real sample. On three short sentences almost any honest draft looks "uniform" —
    # measured 2026-07-28, this rejected a perfectly good draft at lengths [5, 6, 7] and even
    # flagged [7, 3, 3], which has a spread of 4 and is not uniform at all. A linter that
    # rejects good writing gets switched off, and then it protects nothing. Five sentences
    # minimum, and the spread must be genuinely tight.
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip().split()) >= 3]
    if len(sentences) >= 5:
        lens = [len(s.split()) for s in sentences]
        if max(lens) - min(lens) <= 3:
            problems.append(f"Uniform sentence rhythm detected (lengths: {lens})")

    # 8. FABRICATED NUMBER CHECK (most important)
    # Extract all numerals/numbers in the text (e.g. '23%', '100k', '4', '898')
    # Dates, times and version strings are not CLAIMS, and treating them as invented metrics
    # is a false positive that blocks honest drafts — "On 2026-07-28 I fixed the send path"
    # was rejected for the fabricated numbers "2026" and "28". Strip those shapes first, then
    # judge what remains. The check exists to catch an invented statistic, which is the thing
    # that would actually embarrass him; it is not a ban on writing down the date.
    _scrubbed = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)          # ISO dates
    _scrubbed = re.sub(r"\b\d{1,2}[:/]\d{2}(?::\d{2})?\s*(?:am|pm)?\b", " ", _scrubbed, flags=re.I)  # times
    _scrubbed = re.sub(r"\bv?\d+\.\d+(?:\.\d+)?\b", " ", _scrubbed)  # versions like 0.1.0, 3.11
    _scrubbed = re.sub(r"\b(?:19|20)\d{2}\b", " ", _scrubbed)        # bare years

    numbers_in_draft = re.findall(r"\b\d+(?:\.\d+)?%?\b", _scrubbed)
    # Standard static numbers allowed from system context: 898 (VM MB), 24, 7, 96, 4 (months)
    allowed_static_numbers = {"898", "24", "7", "96", "4", "1", "2"}
    digest_lower = digest.lower()

    for num in numbers_in_draft:
        raw_num = num.rstrip("%")
        if raw_num in allowed_static_numbers:
            continue
        if num.lower() not in digest_lower and raw_num not in digest_lower:
            problems.append(f"Fabricated number detected: '{num}' does not appear in source digest")

    ok = len(problems) == 0
    return ok, problems


def pick_story_commits(d: dict, n: int = 3) -> list:
    """DETERMINISTIC selection — code picks, not the model."""
    pool = d["signal_commits"] or d["all_commits"]
    scored = sorted(pool, key=lambda c: (len(c["body"]), len(c["subject"])), reverse=True)
    return scored[:n]


def draft_post(commit: dict, config: dict, digest_context: str = "") -> tuple:
    """LLM VOICES ONE COMMIT with anti-slop linter & 1-retry fallback.
    Returns (post_text, ok, problems).
    """
    voice_contract = load_voice_contract()
    source_digest = f"{commit['subject']}\n{commit['body']}\n{digest_context}"
    
    prompt = VOICE_PROMPT.format(
        voice_contract=voice_contract,
        date=commit["date"],
        subject=commit["subject"],
        body=commit["body"] or "(no extended description)"
    )

    try:
        from server.ai import get_ai_response
        # Attempt 1
        res, _ = get_ai_response(
            prompt,
            [], config,
            system_prompt_override=("You are a precise technical writer matching Rushi's exact voice. "
                                    "You never invent facts or numbers. Output only the post text."))
        draft = str(res or "").strip()
        ok, problems = lint_draft(draft, source_digest)

        if ok:
            return draft, True, []

        # Attempt 2 (Retry with linter feedback)
        retry_prompt = (
            f"{prompt}\n\n"
            f"CRITICAL FIX REQUIRED: Your previous draft failed anti-slop linter checks with problems:\n"
            + "\n".join([f"- {p}" for p in problems]) + "\n\n"
            f"Rewrite the post fixing ALL of these issues. Do NOT invent numbers or use banned words."
        )

        res2, _ = get_ai_response(
            retry_prompt,
            [], config,
            system_prompt_override=("You are a precise technical writer. Fix the linter problems. Output only the post text."))
        draft2 = str(res2 or "").strip()
        ok2, problems2 = lint_draft(draft2, source_digest)

        if ok2:
            return draft2, True, []
        else:
            # Return draft WITH problem list attached so user sees what failed
            problem_summary = "\n\n[LINTER PROBLEMS ATTACHED]:\n" + "\n".join([f"⚠️ {p}" for p in problems2])
            return draft2 + problem_summary, False, problems2

    except Exception as e:
        return f"(LLM voicing unavailable: {e})", False, [str(e)]


def main():
    ap = argparse.ArgumentParser(description="Draft LinkedIn posts from real git work")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--digest-only", action="store_true", help="skip the LLM, print facts only")
    ap.add_argument("--drafts", type=int, default=2, help="how many post options to draft")
    ap.add_argument("--out", default=None, help="also write the drafts to this file")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    d = build_work_digest(args.days)
    digest = render_digest(d)
    print("=" * 74)
    print(digest)
    print("=" * 74)

    if args.digest_only or not d["commit_count"]:
        return

    try:
        from server.config import load_config
        config = load_config()
    except Exception:
        config = {}

    picks = pick_story_commits(d, n=args.drafts)
    print(f"\nDrafting {len(picks)} option(s) — ONE commit each, with voice contract + anti-slop linter...\n")
    drafts = []
    for i, c in enumerate(picks, 1):
        post, ok, problems = draft_post(c, config, digest_context=digest)
        drafts.append((c, post, ok, problems))
        status_str = "PASS" if ok else "FAIL (Problems Attached)"
        print("-" * 74)
        print(f"OPTION {i} — from commit {c['sha']} ({c['date']}): {c['subject'][:60]} [{status_str}]")
        print("-" * 74)
        print(post)
        print()

    print("=" * 74)
    print("BEFORE POSTING — verify each claim against the commit shown above it.")
    print("Put any repo link in the FIRST COMMENT.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(f"# Drafts generated {d['generated_at']}\n\n{digest}\n")
            for i, (c, post, ok, problems) in enumerate(drafts, 1):
                f.write(f"\n---\n\n## Option {i} — commit {c['sha']} ({c['date']}) [Linter: {'PASS' if ok else 'FAIL'}]\n"
                        f"**Source commit:** {c['subject']}\n\n{post}\n")
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
