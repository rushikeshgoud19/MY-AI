#!/usr/bin/env python3
"""
scripts/capture_shots.py — Auth-free screenshots via Playwright (Task Pack 5: Phase B.3).

PUBLIC URLs ONLY. No login flows, no stored credentials.
Captures screenshots of public GitHub PRs, issues, or repo pages into .data/shots/YYYY-MM-DD/<slug>.png.
If a page requires login, it is skipped and logged in the manual capture checklist.
"""

import os
import sys
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

DEFAULT_TARGETS = [
    {"name": "my_ai_repo", "url": "https://github.com/rushikeshgoud19/MY-AI"},
    {"name": "profile_readme", "url": "https://github.com/rushikeshgoud19/rushikeshgoud19"},
    {"name": "traceroot_pr", "url": "https://github.com/traceroot-ai/traceroot/pull/1619"},
]


def manual_checklist() -> list:
    """Instructions for auth-required visuals that cannot be automated without credentials."""
    return [
        "1. TraceRoot Dashboard: Go to app.traceroot.ai -> Login -> Traces tab -> Filter last 24h -> Screenshot the Latency & Tokens panel.",
        "2. Azure Portal VM Metrics: Go to portal.azure.com -> MizuneVM -> Metrics -> Screenshot CPU & Network activity graph.",
        "3. Private Repositories / Settings: Open any internal repository settings pages directly in browser."
    ]


def capture_screenshots(targets: list = None) -> tuple:
    """Capture public URL screenshots into .data/shots/YYYY-MM-DD/."""
    targets = targets or DEFAULT_TARGETS
    today_dir = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(".data", "shots", today_dir)
    os.makedirs(out_dir, exist_ok=True)

    captured_files = []
    skipped_targets = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        for t in targets:
            name = t["name"]
            url = t["url"]
            out_path = os.path.join(out_dir, f"{name}.png")

            print(f"Navigating to [{name}]: {url} ...")
            try:
                page.goto(url, wait_until="networkidle", timeout=25000)

                # Check for login walls
                title = page.title().lower()
                current_url = page.url.lower()

                if "sign in" in title or "login" in current_url or "session" in current_url:
                    print(f"⚠️  Auth wall detected for [{name}]. SKIPPING as per safety rules.")
                    skipped_targets.append({"name": name, "url": url, "reason": "Auth wall / login redirect"})
                    continue

                page.screenshot(path=out_path, full_page=False)
                size_bytes = os.path.getsize(out_path)
                captured_files.append({"name": name, "path": out_path, "bytes": size_bytes})
                print(f"[OK] Saved screenshot: {out_path} ({size_bytes} bytes)")

            except Exception as e:
                print(f"[FAIL] Failed to capture [{name}]: {e}")
                skipped_targets.append({"name": name, "url": url, "reason": str(e)})

        browser.close()

    return captured_files, skipped_targets


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Capture auth-free screenshots for build log attachments")
    parser.add_argument("--url", help="Add custom public URL to capture")
    parser.add_argument("--name", help="Custom target name for the URL")
    args = parser.parse_args()

    targets = list(DEFAULT_TARGETS)
    if args.url and args.name:
        targets.append({"name": args.name, "url": args.url})

    print("==========================================================================================")
    print("=== MIZUNE B.3 AUTH-FREE SCREENSHOT CAPTURE ===")
    print("==========================================================================================\n")

    captured, skipped = capture_screenshots(targets)

    print("\n==========================================================================================")
    print("=== CAPTURED FILES ===")
    print("==========================================================================================")
    for c in captured:
        print(f"  • [{c['name']}] Path: {c['path']} | Size: {c['bytes']:,} bytes")

    if skipped:
        print("\n==========================================================================================")
        print("=== SKIPPED (AUTH-WALLED / FAILED) ===")
        print("==========================================================================================")
        for s in skipped:
            print(f"  • [{s['name']}] URL: {s['url']} | Reason: {s['reason']}")

    print("\n==========================================================================================")
    print("=== MANUAL CAPTURE CHECKLIST (FOR AUTH-REQUIRED PAGES) ===")
    print("==========================================================================================")
    for item in manual_checklist():
        print(f"  {item}")
    print()


if __name__ == "__main__":
    main()
