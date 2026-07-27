#!/usr/bin/env python3
"""
server/build_log.py — Deterministic day collector (Task Pack 5: Phase B.1).

NO LLM IN THIS FILE.
Collects data from:
  1. Local git commits (via content_engine)
  2. GitHub activity (via gh CLI, cross-checked with gh api)
  3. Mizune's telemetry (.data/missions.db, .data/mizune_memory.db, .data/night_shift.db)

Produces a ranked candidate list and a plain-text WhatsApp-ready digest.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.content_engine import build_work_digest


def run_gh_cli(args: list) -> str:
    """Run gh CLI command safely."""
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_github_activity(days: int = 1) -> dict:
    """Collect GitHub PRs, CI states, and issues safely with cross-checking."""
    activity = {
        "prs": [],
        "issues": [],
        "ci_checks": [],
        "cross_check_count": 0
    }

    # 1. PR list — ACCOUNT-WIDE, not repo-scoped.
    # `gh pr list` without --repo silently scopes to the CURRENT repo. Run from this repo that
    # is rushikeshgoud19/MY-AI, which has never had a PR, so it returned [] every time while
    # Rushi had 11 PRs authored and 3 open on traceroot — including #1619, the single most
    # postable thing he has. The date-filtered cross-check below happened to return 0 as well,
    # so the two agreed on a wrong answer and it looked verified. This is exactly what the
    # task pack warned about in bold: never report "none" off a single query shape.
    api_prs = run_gh_cli(["api", "search/issues?q=author:rushikeshgoud19+type:pr&sort=updated&per_page=30"])
    all_prs = []
    if api_prs:
        try:
            for it in json.loads(api_prs).get("items", []):
                all_prs.append({
                    "number": it.get("number"),
                    "title": it.get("title", ""),
                    "state": (it.get("state") or "").upper(),
                    "repo": (it.get("repository_url") or "").rsplit("/", 1)[-1],
                    "createdAt": it.get("created_at", ""),
                    "updatedAt": it.get("updated_at", ""),
                    "url": it.get("html_url", ""),
                })
        except Exception:
            pass

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    activity["prs"] = [p for p in all_prs
                       if p.get("updatedAt", "") >= cutoff or p.get("createdAt", "") >= cutoff]

    # OPEN PRs are reported regardless of the date window. "Nothing changed today" is not the
    # same as "nothing is in flight", and a PR sitting open awaiting review is worth writing
    # about on a day with no commits.
    activity["open_prs"] = [p for p in all_prs if p.get("state") == "OPEN"]

    # 2. Check CI state for open PRs — pass --repo, since these live in OTHER people's repos
    for pr in activity.get("open_prs", [])[:5]:
        if True:
            num = pr.get("number")
            repo = pr.get("repo")
            owner_repo = None
            if pr.get("url"):
                bits = pr["url"].split("/")
                if len(bits) >= 5:
                    owner_repo = f"{bits[3]}/{bits[4]}"
            checks_raw = run_gh_cli(["pr", "checks", str(num)] +
                                    (["--repo", owner_repo] if owner_repo else []) +
                                    ["--json", "name,bucket"])
            if checks_raw:
                try:
                    checks = json.loads(checks_raw)
                    pass_count = sum(1 for c in checks if c.get("bucket") == "pass")
                    fail_count = sum(1 for c in checks if c.get("bucket") == "fail")
                    activity["ci_checks"].append({
                        "pr_number": num,
                        "pass": pass_count,
                        "fail": fail_count,
                        "total": len(checks)
                    })
                except Exception:
                    pass

    # 3. Issues List
    issues_raw = run_gh_cli(["issue", "list", "--author", "rushikeshgoud19", "--limit", "15", "--json", "number,title,state,createdAt,url"])
    if issues_raw:
        try:
            issues = json.loads(issues_raw)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            activity["issues"] = [i for i in issues if i.get("createdAt", "") >= cutoff]
        except Exception:
            pass

    # 4. Cross-check with gh api search to avoid empty single-query bugs
    api_raw = run_gh_cli(["api", "search/issues?q=author:rushikeshgoud19+updated:>=" + (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")])
    if api_raw:
        try:
            res = json.loads(api_raw)
            activity["cross_check_count"] = res.get("total_count", 0)
        except Exception:
            pass

    return activity


def get_mizune_telemetry(days: int = 1) -> dict:
    """Collect local telemetry from .data/ DBs safely."""
    telemetry = {
        "completed_missions": 0,
        "verified_missions": 0,
        "tool_seals_count": 0,
        "night_shift_reports": []
    }

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 1. Missions DB
    missions_db = os.path.join(base_dir, ".data", "missions.db")
    if os.path.exists(missions_db):
        try:
            conn = sqlite3.connect(missions_db)
            cur = conn.cursor()
            cur.execute("SELECT status, title FROM missions WHERE status IN ('done', 'verified')")
            rows = cur.fetchall()
            conn.close()
            telemetry["completed_missions"] = len(rows)
            telemetry["verified_missions"] = sum(1 for r in rows if r[0] == "verified")
        except Exception:
            pass

    # 2. Seals in mizune_memory.db
    memory_db = os.path.join(base_dir, ".data", "mizune_memory.db")
    if os.path.exists(memory_db):
        try:
            conn = sqlite3.connect(memory_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM history WHERE content LIKE '%[TOOL RESULTS]%'")
            count = cur.fetchone()[0]
            conn.close()
            telemetry["tool_seals_count"] = count
        except Exception:
            pass

    # 3. Night Shift DB
    night_db = os.path.join(base_dir, ".data", "night_shift.db")
    if os.path.exists(night_db):
        try:
            conn = sqlite3.connect(night_db)
            cur = conn.cursor()
            cur.execute("SELECT shift_date, summary FROM shift_reports ORDER BY id DESC LIMIT 3")
            rows = cur.fetchall()
            conn.close()
            telemetry["night_shift_reports"] = [{"date": r[0], "summary": r[1]} for r in rows]
        except Exception:
            pass

    return telemetry


def collect_day(days: int = 1, repo: str = None) -> dict:
    """Collect all build log data deterministically."""
    git_digest = build_work_digest(days=days, repo=repo)
    github_act = get_github_activity(days=days)
    mizune_tel = get_mizune_telemetry(days=days)

    # Ranking Highlights
    highlights = []
    # Add signal commits
    for c in git_digest.get("signal_commits", []):
        highlights.append({"type": "commit", "title": c["subject"], "sha": c["sha"], "detail": c["body"][:120]})

    # Add PRs
    for pr in github_act.get("prs", []):
        highlights.append({"type": "pr", "title": f"PR #{pr.get('number')}: {pr.get('title')}", "url": pr.get("url")})

    # Add Telemetry Highlights
    if mizune_tel["completed_missions"] > 0:
        highlights.append({"type": "telemetry", "title": f"{mizune_tel['completed_missions']} autonomous missions executed ({mizune_tel['verified_missions']} verified)"})
    if mizune_tel["tool_seals_count"] > 0:
        highlights.append({"type": "telemetry", "title": f"{mizune_tel['tool_seals_count']} deterministic tool seals logged"})

    today_date = datetime.now().strftime("%Y-%m-%d")

    return {
        "date": today_date,
        "days_window": days,
        "git": git_digest,
        "github": github_act,
        "mizune": mizune_tel,
        "highlights": highlights
    }


def render_digest(day: dict) -> str:
    """Render plain-text WhatsApp-friendly summary of the collected day/window."""
    lines = [f"BUILD LOG DIGEST ({day['date']}) — Last {day['days_window']} Day(s)"]
    lines.append("=" * 60)

    git = day.get("git", {})
    commits = git.get("commit_count", 0)
    files = git.get("files_changed", 0)
    ins = git.get("insertions", 0)
    lines.append(f"Git Activity: {commits} substantive commit(s), {files} file(s) changed (+{ins} lines)")

    github = day.get("github", {})
    prs = github.get("prs", [])
    issues = github.get("issues", [])
    lines.append(f"GitHub Activity: {len(prs)} PR(s) updated, {len(issues)} Issue(s) opened (Cross-check count: {github.get('cross_check_count', 0)})")

    # Open PRs are shown even on a quiet day — work awaiting review is still real work, and
    # this is the section that was silently empty while three PRs sat open on traceroot.
    open_prs = github.get("open_prs", [])
    ci_by_pr = {c.get("pr_number"): c for c in github.get("ci_checks", [])}
    if open_prs:
        lines.append(f"Open PRs ({len(open_prs)}):")
        for p in open_prs[:5]:
            ci = ci_by_pr.get(p.get("number"))
            ci_txt = f" — CI {ci['pass']}/{ci['total']} passing" if ci and ci.get("total") else ""
            lines.append(f"  - {p.get('repo')}#{p.get('number')} {p.get('title','')[:60]}{ci_txt}")

    mizune = day.get("mizune", {})
    lines.append(f"Mizune Telemetry: {mizune.get('completed_missions', 0)} mission(s) completed, {mizune.get('tool_seals_count', 0)} tool seal(s) logged")

    lines.append("\nHIGHLIGHTS & STORY CANDIDATES:")
    highlights = day.get("highlights", [])
    if not highlights:
        lines.append("  (Nothing substantial today. Quiet day — no manufactured milestones.)")
    else:
        for idx, h in enumerate(highlights[:6], 1):
            lines.append(f"  {idx}. [{h['type'].upper()}] {h['title']}")

    return "\n".join(lines)


if __name__ == "__main__":
    days_arg = 1
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        days_arg = int(sys.argv[1])
    elif "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
            days_arg = int(sys.argv[idx + 1])

    data = collect_day(days=days_arg)
    print(render_digest(data))
