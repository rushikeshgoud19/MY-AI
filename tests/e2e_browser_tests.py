import json
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "e2e_browser_config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    required = [
        "chrome_exe",
        "brave_exe",
        "chrome_profile_dir",
        "brave_profile_dir",
        "youtube_url",
        "netflix_url",
    ]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")
    for key in ["chrome_exe", "brave_exe", "chrome_profile_dir", "brave_profile_dir"]:
        if not os.path.exists(cfg[key]):
            raise FileNotFoundError(f"Path not found for {key}: {cfg[key]}")
    return cfg


def launch_persistent(playwright, exe_path: str, user_data_dir: str, headless: bool, slow_mo: int):
    return playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        executable_path=exe_path,
        headless=headless,
        slow_mo=slow_mo,
        args=["--no-first-run", "--disable-features=TranslateUI"],
        viewport={"width": 1280, "height": 720},
    )


def click_first(page, selectors, timeout_ms=2000) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.click(timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def wait_for_video_playing(page, timeout_ms=30000) -> None:
    page.wait_for_function(
        """
        () => {
          const v = document.querySelector('video');
          if (!v) return false;
          if (v.readyState < 2) return false;
          if (v.paused) return false;
          return v.currentTime > 1;
        }
        """,
        timeout=timeout_ms,
    )


def run_youtube_test(playwright, cfg: dict) -> None:
    print("[YOUTUBE] Launching Chrome...")
    context = launch_persistent(
        playwright,
        cfg["chrome_exe"],
        cfg["chrome_profile_dir"],
        cfg.get("headless", False),
        int(cfg.get("slow_mo_ms", 0)),
    )
    page = context.new_page()
    try:
        page.goto(cfg["youtube_url"], wait_until="domcontentloaded", timeout=60000)

        click_first(page, ["button:has-text('Accept all')", "button:has-text('I agree')"])
        page.wait_for_selector("video", timeout=30000)

        click_first(page, ["button.ytp-large-play-button", "button.ytp-play-button"])
        wait_for_video_playing(page, timeout_ms=45000)
        print("[YOUTUBE] PASS: Video is playing.")
    finally:
        context.close()


def run_netflix_test(playwright, cfg: dict) -> None:
    print("[NETFLIX] Launching Brave...")
    context = launch_persistent(
        playwright,
        cfg["brave_exe"],
        cfg["brave_profile_dir"],
        cfg.get("headless", False),
        int(cfg.get("slow_mo_ms", 0)),
    )
    page = context.new_page()
    try:
        page.goto(cfg["netflix_url"], wait_until="domcontentloaded", timeout=60000)

        login_selectors = [
            "input[name='userLoginId']",
            "input[name='email']",
            "form[action*='login']",
        ]
        if any(page.locator(sel).count() > 0 for sel in login_selectors):
            raise AssertionError("Netflix login required. Please log in using the Brave profile.")

        click_first(page, [
            "a.profile-link",
            "div.profile",
            "div[data-uia='profile-name']",
            "span.profile-name",
        ])

        page.wait_for_selector("video", timeout=60000)
        click_first(page, ["button[data-uia='player-play-pause']"])
        wait_for_video_playing(page, timeout_ms=60000)
        print("[NETFLIX] PASS: Video is playing.")
    finally:
        context.close()


def main() -> int:
    cfg = load_config()
    failures = []

    with sync_playwright() as playwright:
        try:
            run_youtube_test(playwright, cfg)
        except Exception as exc:
            failures.append(f"YouTube test failed: {exc}")

        try:
            run_netflix_test(playwright, cfg)
        except Exception as exc:
            failures.append(f"Netflix test failed: {exc}")

    print("\n=== E2E TEST RESULTS ===")
    if failures:
        for msg in failures:
            print(f"FAIL: {msg}")
        return 1

    print("PASS: All E2E browser tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
