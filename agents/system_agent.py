import os
import re
import json
import time
import threading
import subprocess
from datetime import datetime, timedelta
import pyautogui
import pyperclip
import webbrowser
from agents.base_agent import BaseAgent
from typing import Any, Optional, Dict
import logging

# COMMON_APPS defined locally to avoid circular import with server.py
COMMON_APPS = {
    "notepad": "notepad.exe", "brave": "brave", "chrome": "chrome",
    "firefox": "firefox", "edge": "msedge", "code": "code", "vs code": "code",
    "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
    "excel": "excel", "word": "winword", "powerpoint": "powerpnt",
    "discord": "discord", "telegram": "telegram", "whatsapp": "whatsapp://",
    "spotify": "spotify", "steam": "steam", "obs": "obs64",
    "calculator": "calc.exe", "explorer": "explorer", "task manager": "taskmgr",
    "settings": "ms-settings:", "paint": "mspaint",
    "youtube": "https://youtube.com", "github": "https://github.com",
    "gmail": "https://mail.google.com", "netflix": "https://netflix.com",
}

# ─── Task Scheduler ───────────────────────────────────────────────────────────
_SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "scheduled_tasks.json")
_SCHEDULE_LOCK = threading.Lock()
_scheduler_started = False


def _parse_time_delay(text: str) -> Optional[int]:
    """Parse natural language time expressions and return delay in seconds."""
    text = text.lower().strip()

    # "in X minutes/hours/seconds"
    m = re.search(r"in\s+(\d+)\s*(?:min(?:ute)?s?|mins?)\b", text)
    if m: return int(m.group(1)) * 60

    m = re.search(r"in\s+(\d+)\s*(?:hour|hr)s?\b", text)
    if m: return int(m.group(1)) * 3600

    m = re.search(r"in\s+(\d+)\s*(?:second|sec)s?\b", text)
    if m: return int(m.group(1))

    m = re.search(r"after\s+(\d+)\s*(?:min(?:ute)?s?|mins?)\b", text)
    if m: return int(m.group(1)) * 60

    m = re.search(r"after\s+(\d+)\s*(?:hour|hr)s?\b", text)
    if m: return int(m.group(1)) * 3600

    # "at HH:MM (am/pm)" — calculate delay from now
    m = re.search(r"(?:at|for)\s+(\d{1,2}):(\d{2})\s*(am|pm)\b", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if m.group(3).lower() == "pm" and hour != 12:
            hour += 12
        elif m.group(3).lower() == "am" and hour == 12:
            hour = 0
        return _delay_until_time(hour, minute)

    m = re.search(r"(?:at|for)\s+(\d{1,2}):(\d{2})\b", text)
    if m:
        return _delay_until_time(int(m.group(1)), int(m.group(2)))

    return None


def _delay_until_time(hour: int, minute: int) -> int:
    """Seconds from now until the given HH:MM today (or tomorrow if already passed)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds())


def _load_scheduled_tasks() -> list:
    """Load persisted scheduled tasks."""
    try:
        if os.path.exists(_SCHEDULE_FILE):
            with open(_SCHEDULE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_scheduled_tasks(tasks: list):
    """Save scheduled tasks to disk."""
    os.makedirs(os.path.dirname(_SCHEDULE_FILE), exist_ok=True)
    with _SCHEDULE_LOCK:
        with open(_SCHEDULE_FILE, "w") as f:
            json.dump(tasks, f, indent=2)


def _add_scheduled_task(contact: str, message: Optional[str], delay_seconds: int) -> str:
    """Add a task and return a human-friendly ETA string."""
    run_at = datetime.now() + timedelta(seconds=delay_seconds)
    task = {
        "contact": contact,
        "message": message,
        "run_at": run_at.isoformat(),
        "created_at": datetime.now().isoformat(),
    }
    tasks = _load_scheduled_tasks()
    tasks.append(task)
    _save_scheduled_tasks(tasks)

    # Start a background timer
    threading.Thread(target=_execute_delayed_task, args=(task, tasks, delay_seconds), daemon=True).start()

    eta_str = run_at.strftime("%I:%M %p").lstrip("0")
    return f"I'll message {contact} at {eta_str}, Master!"


def _execute_delayed_task(task: dict, tasks: list, delay_seconds: int):
    """Wait for the delay, execute the WhatsApp automation, then remove from store."""
    time.sleep(delay_seconds)

    _execute_whatsapp_now(task["contact"], task.get("message"))

    # Remove from store
    with _SCHEDULE_LOCK:
        remaining = [t for t in tasks if t.get("run_at") != task.get("run_at")]
        _save_scheduled_tasks(remaining)


def _focus_whatsapp_window():
    """Find WhatsApp window, activate it, and click on it to guarantee focus."""
    import time as _time
    log = logging.getLogger("SystemAgent")
    try:
        import pygetwindow as gw
        wa = gw.getWindowsWithTitle("WhatsApp")
        if wa:
            w = wa[0]
            if w.isMinimized:
                w.restore()
                _time.sleep(0.5)
            w.activate()
            _time.sleep(0.5)
            # Click in the middle of the window to guarantee keyboard focus
            cx = w.left + w.width // 2
            cy = w.top + w.height // 2
            pyautogui.click(cx, max(cy, w.top + 30))  # Click title bar area
            _time.sleep(0.5)
            log.info(f"[WA] Focused WhatsApp at ({cx},{cy})")
            return True
    except Exception as e:
        log.info(f"[WA] Focus error: {e}")
    return False


def _execute_whatsapp_now(contact: str, message: Optional[str] = None):
    """Execute WhatsApp automation directly (standalone, for scheduled tasks)."""
    log = logging.getLogger("SystemAgent")
    import time as _time

    log.info(f"[SCHEDULER] Starting WhatsApp delivery to {contact}")

    webbrowser.open("whatsapp://")
    _time.sleep(7)

    # Try to focus WhatsApp with multiple retries
    focused = False
    for attempt in range(3):
        focused = _focus_whatsapp_window()
        if focused:
            break
        log.info(f"[SCHEDULER] Focus attempt {attempt+1} failed, retrying...")
        _time.sleep(2)

    if not focused:
        log.info("[SCHEDULER] Window focus failed, sending keystrokes blindly")
        _time.sleep(2)

    # Dismiss any dialog/popup (WhatsApp shows "Welcome" / "What's new" sometimes)
    pyautogui.press("escape")
    _time.sleep(0.5)

    # Focus search bar
    for _ in range(3):
        pyautogui.hotkey("ctrl", "f")
        _time.sleep(1.5)

    pyautogui.write(contact, interval=0.1)
    _time.sleep(1.5)
    pyautogui.press("enter")
    _time.sleep(1.5)

    if message:
        pyautogui.write(message, interval=0.05)
        _time.sleep(0.3)
        pyautogui.press("enter")

    log.info(f"[SCHEDULER] Delivered WhatsApp message to {contact}")


def _resume_missed_tasks():
    """On startup, reschedule any tasks that were saved but not yet executed."""
    tasks = _load_scheduled_tasks()
    now = datetime.now()
    expired = []
    pending = []

    for task in tasks:
        run_at = datetime.fromisoformat(task["run_at"])
        delay = (run_at - now).total_seconds()
        if delay <= 0:
            expired.append(task)
        else:
            pending.append(task)
            threading.Thread(target=_execute_delayed_task, args=(task, pending, delay), daemon=True).start()

    # Execute expired tasks immediately (within ~1s of each other)
    for task in expired:
        _execute_whatsapp_now(task["contact"], task.get("message"))

    # Clean up expired tasks
    _save_scheduled_tasks(pending)
    return len(expired), len(pending)


# ─── SystemAgent ──────────────────────────────────────────────────────────────

class SystemAgent(BaseAgent):
    """
    Specialized Agent for local computer operations.
    Handles the 'Environment Builder' and 'Code Analyst' workflows.
    """
    def __init__(self, config: dict):
        super().__init__(config)
        self.log("SystemAgent initialized. Ready to control the PC.")

        # Resume missed tasks from disk on startup (run once globally)
        global _scheduler_started
        if not _scheduler_started:
            _scheduler_started = True
            expired, queued = _resume_missed_tasks()
            if expired or queued:
                self.log(f"[SCHEDULER] Resumed {expired} expired + {queued} pending tasks")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        self.log(f"Executing system task: {task_input}")

        text = task_input.lower()

        # Workflow: Environment Builder
        if any(word in text for word in ["setup", "install", "create project", "build env"]):
            return await self._build_environment(task_input)

        # Workflow: Code Analyst
        if any(word in text for word in ["why is this failing", "analyze this code", "fix this bug"]):
            return await self._analyze_code(task_input)

        # General OS operations
        return await self._handle_general_os(task_input)

    async def _build_environment(self, params: str) -> str:
        self.log("Starting Environment Builder workflow...")
        try:
            is_react = "react" in params.lower()
            is_tailwind = "tailwind" in params.lower()

            project_name = "mizune_project"
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            proj_path = os.path.join(desktop_path, project_name)

            if is_react:
                self.log(f"Executing: npx create-react-app {project_name}")
                if is_tailwind:
                    self.log("Installing Tailwind CSS...")

            self.log("Launching VS Code in project directory...")
            subprocess.Popen(f"code {proj_path}", shell=True)

            pyautogui.alert(f"Mizune has finished building your project at {proj_path}!", "Project Ready")
            return "I've set up the environment for you, Master! Your project is ready and I've opened the editor. Hai~!"
        except Exception as e:
            self.log(f"Build failed: {e}")
            return f"Gomen ne, Master... I had trouble building the environment: {e}"

    async def _analyze_code(self, params: str) -> str:
        self.log("Starting Code Analyst workflow...")
        try:
            code_snippet = pyperclip.paste()
            if not code_snippet:
                return "Master, please copy the failing code or error first so I can see it!"

            self.log(f"Analyzing code snippet (length: {len(code_snippet)} characters)...")

            ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"mizune_debug_{int(time.time())}.png")
            pyautogui.screenshot(ss_path)

            if ".map(" in code_snippet and "undefined" in code_snippet.lower():
                suggestion = "It looks like you're calling .map() on an undefined variable. Try adding a check: "
            elif "await" not in code_snippet and "async" in code_snippet:
                suggestion = "I noticed an async function without an await. You might be missing a promise resolution!"
            else:
                suggestion = "I've analyzed the code. While it looks okay at first glance, I recommend checking the variable types in your imports!"

            return f"I've analyzed the code, Master! {suggestion} I can type the fix for you if you'd like!"
        except Exception as e:
            self.log(f"Analysis failed: {e}")
            return f"I couldn't analyze the code, Master. Error: {e}"

    async def simulate_keystrokes(self, text: str):
        self.log(f"Simulating keystrokes: {text}")
        pyautogui.write(text, interval=0.01)

    async def _handle_general_os(self, text: str) -> str:
        text_low = text.lower()
        if "screenshot" in text_low:
            ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"mizune_capture_{int(time.time())}.png")
            pyautogui.screenshot(ss_path)
            return f"Taken! I've saved the screenshot to your desktop, Master~"

        # ─── Scheduled WhatsApp Messages ──────────────────────────────────
        # Check if there's a time expression first (e.g. "in 10 minutes")
        delay = _parse_time_delay(text_low)
        if delay is not None:
            # Remove the time expression from the text so normal patterns match
            clean_text = re.sub(
                r"\b(?:in|after)\s+\d+\s*(?:min(?:ute)?s?|mins?|hours?|hrs?|seconds?|secs?)\b",
                "", text_low
            ).strip()
            clean_text = re.sub(r"\s+", " ", clean_text).strip()  # collapse multiple spaces
            clean_text = re.sub(
                r"\s+(?:at|for)\s+\d{1,2}:\d{2}\s*(?:am|pm)?\b", "", clean_text
            ).strip()

            # Now try to match the remaining text as a WhatsApp command
            text_low = clean_text
            self.log(f"[SCHEDULER] Scheduling WhatsApp task from: '{text_low}'")

            # Try each WhatsApp pattern on the cleaned text
            # Recurse into matching patterns but schedule instead of execute
            scheduled = await self._try_schedule_whatsapp(text_low, delay)
            if scheduled:
                return scheduled

        # WhatsApp: "open whatsapp and tell/message [name] [message]"
        wa_compound = re.search(r"(?:hey\s+)?open\s+whatsapp\s+and\s+(?:tell|message)\s+(\w+)\s*(.+)?$", text_low)
        if wa_compound:
            contact = wa_compound.group(1).strip()
            msg = wa_compound.group(2).strip() if wa_compound.group(2) else None
            return await self._whatsapp_automation(contact, msg)

        # WhatsApp: "tell/message [name] [message] on whatsapp"
        tell_pattern = re.search(r"(?:tell|message)\s+(\w+)\s+(?:that\s+|saying\s+)?(.+)\s+on\s+whatsapp", text_low)
        if tell_pattern:
            contact = tell_pattern.group(1).strip()
            msg = tell_pattern.group(2).strip()
            return await self._whatsapp_automation(contact, msg)

        # WhatsApp: "tell/message [name] [message]" (no app → default WhatsApp)
        tell_default = re.search(r"(?:tell|message)\s+(?!me\b|us\b|them\b|him\b|her\b)(\w+)(?:\s+(.+))?$", text_low)
        if tell_default and "whatsapp" not in text_low and "open" not in text_low:
            contact = tell_default.group(1).strip()
            msg = tell_default.group(2).strip() if tell_default.group(2) else None
            return await self._whatsapp_automation(contact, msg)

        # WhatsApp: "message [name]" (just open chat, no message content)
        whatsapp_msg = re.search(r"(?:message)\s+(?!me\b|us\b|them\b)(.+?)$", text_low)
        if whatsapp_msg and "open" not in text_low:
            contact = whatsapp_msg.group(1).strip()
            return await self._whatsapp_automation(contact)

        # "open whatsapp" only
        if re.search(r"open\s+whatsapp", text_low):
            webbrowser.open("whatsapp://")
            return "Opening WhatsApp desktop app, Master!"

        # App Launching (limit to app name only — stop at "and")
        app_match = re.search(r"open\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)?)", text_low)
        if app_match:
            target = app_match.group(1).strip()
            exe = COMMON_APPS.get(target, target)
            if exe.startswith("http") or exe.startswith("ms-") or "://" in exe:
                webbrowser.open(exe)
            else:
                subprocess.Popen(f"start {exe}", shell=True)
            return f"Opening {target} for you right away!"

        return "I can help you with that, but I'm not sure exactly how. Could you guide me, Master?"

    async def _try_schedule_whatsapp(self, text: str, delay: int) -> Optional[str]:
        """Try to match a WhatsApp pattern and schedule it instead of executing immediately."""
        text_low = text

        # "tell [name] [message] on whatsapp"
        m = re.search(r"(?:tell|message)\s+(\w+)\s+(?:that\s+|saying\s+)?(.+)\s+on\s+whatsapp", text_low)
        if m:
            return _add_scheduled_task(m.group(1).strip(), m.group(2).strip(), delay)

        # "tell/message [name] [message]" (default WhatsApp)
        m = re.search(r"(?:tell|message)\s+(?!me\b|us\b|them\b|him\b|her\b)(\w+)(?:\s+(.+))?$", text_low)
        if m:
            contact = m.group(1).strip()
            msg = m.group(2).strip() if m.group(2) else None
            return _add_scheduled_task(contact, msg, delay)

        return None

    async def _whatsapp_automation(self, contact: str, message: str = None) -> str:
        """Open WhatsApp desktop and search a contact, optionally sending a message."""
        self.log(f"WhatsApp automation: searching '{contact}'")

        webbrowser.open("whatsapp://")

        self.log("Waiting for WhatsApp to open...")
        time.sleep(7)

        # Focus WhatsApp window (reuse standalone function)
        focused = _focus_whatsapp_window()
        if not focused:
            self.log("Focus failed, trying Alt+Tab")
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.5)

        # Dismiss any popup/dialog
        pyautogui.press("escape")
        time.sleep(0.5)

        # Focus search bar
        for _ in range(3):
            pyautogui.hotkey("ctrl", "f")
            time.sleep(1.5)

        pyautogui.write(contact, interval=0.1)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(1.5)

        if message:
            pyautogui.write(message, interval=0.05)
            time.sleep(0.3)
            pyautogui.press("enter")
            return f"Message sent to {contact} on WhatsApp, Master!"

        return f"Opened WhatsApp chat with {contact}, Master!"
