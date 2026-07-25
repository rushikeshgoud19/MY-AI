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


VOICE_PROMPT = """You write a LinkedIn post for Rushikesh, a CS student who builds Mizune — a
self-hosted autonomous AI assistant that runs on a single 898MB cloud VM.

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


def pick_story_commits(d: dict, n: int = 3) -> list:
    """DETERMINISTIC selection — code picks, not the model. Prefer commits that carry a real
    explanation (long body = the author documented a root cause) and match the signal pattern.
    Handing the model ONE commit at a time is what stops it inventing causal links between
    unrelated fixes (observed: it merged a TypeError fix and a benchmark fix into one false story)."""
    pool = d["signal_commits"] or d["all_commits"]
    scored = sorted(pool, key=lambda c: (len(c["body"]), len(c["subject"])), reverse=True)
    return scored[:n]


def draft_post(commit: dict, config: dict) -> str:
    """LLM VOICES ONE COMMIT. Override form ⇒ tools blocked, cannot act."""
    try:
        from server.ai import get_ai_response
        res, _ = get_ai_response(
            VOICE_PROMPT.format(date=commit["date"], subject=commit["subject"],
                                body=commit["body"] or "(no extended description)"),
            [], config,
            system_prompt_override=("You are a precise technical writer. You never invent facts and "
                                    "never combine separate issues. Output only the post text."))
        return str(res or "").strip()
    except Exception as e:
        return f"(LLM voicing unavailable: {e})"


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
    print(f"\nDrafting {len(picks)} option(s) — ONE commit each, so the model can't invent "
          f"links between unrelated fixes...\n")
    drafts = []
    for i, c in enumerate(picks, 1):
        post = draft_post(c, config)
        drafts.append((c, post))
        print("-" * 74)
        print(f"OPTION {i} — from commit {c['sha']} ({c['date']}): {c['subject'][:60]}")
        print("-" * 74)
        print(post)
        print()

    print("=" * 74)
    print("BEFORE POSTING — verify each claim against the commit shown above it. The model")
    print("voices facts but a weak provider can still drift; you are the last check.")
    print("Put any repo link in the FIRST COMMENT (LinkedIn suppresses posts with external")
    print("links). Post Tue-Thu 9-11am IST. Reply to comments within the first hour.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(f"# Drafts generated {d['generated_at']}\n\n{digest}\n")
            for i, (c, post) in enumerate(drafts, 1):
                f.write(f"\n---\n\n## Option {i} — commit {c['sha']} ({c['date']})\n"
                        f"**Source commit:** {c['subject']}\n\n{post}\n")
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
