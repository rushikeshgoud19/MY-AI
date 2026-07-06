"""Action execution for Mizune AI - opens/closes apps, controls PC."""
import subprocess
import webbrowser
import logging
import re
from urllib.parse import urlparse

log_info = logging.info

_SAFE_APP_NAME = re.compile(r"^[\w .+\-]+$")


COMMON_APPS = {
    "brave": "brave",
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "vscode": "code",
    "terminal": "wt",
    "discord": "discord",
    "spotify": "spotify",
    "telegram": "telegram",
    "whatsapp": "whatsapp://",
    "steam": "steam",
    "obs": "obs64",
    "blender": "blender",
    "figma": "figma",
    "excel": "excel",
    "word": "winword",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "teams": "Teams",
    "slack": "slack",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "calculator": "calc",
    "paint": "mspaint",
    "notepad": "notepad",
    "file explorer": "explorer",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
}


def _is_url_or_protocol(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} or value.startswith("ms-") or "://" in value


def _is_safe_app_name(value: str) -> bool:
    return bool(value and _SAFE_APP_NAME.fullmatch(value))


def _is_safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not any(c.isspace() for c in value)


def _start_app(exe: str):
    subprocess.Popen(["cmd", "/c", "start", "", exe])


def open_app(target: str) -> str:
    """Open an application or URL."""
    if not target:
        return "Please specify what to open."

    target = target.strip().lower()
    exe = COMMON_APPS.get(target, target)

    log_info(f"[ACTION] Launching: {exe}")
    if _is_url_or_protocol(exe):
        if exe.startswith("http") and not _is_safe_url(exe):
            return f"Sorry Master, I couldn't open {target}!"
        webbrowser.open(exe)
    else:
        if not _is_safe_app_name(exe):
            log_info(f"[ACTION] Blocked unsafe app target: {exe}")
            return f"Sorry Master, I couldn't open {target}!"
        try:
            _start_app(exe)
        except Exception as e:
            log_info(f"[ACTION] Failed to launch '{exe}': {e}")
            return f"Sorry Master, I couldn't open {target}!"

    return f"Opening {target} now!"


def close_app(target: str) -> str:
    """Close an application."""
    if not target:
        return "Please specify what to close."

    target = target.strip().lower()
    exe = COMMON_APPS.get(target, target)

    if exe.startswith("http") or exe.startswith("ms-"):
        return "Cannot close web pages."

    if not exe.endswith(".exe"):
        exe += ".exe"

    log_info(f"[ACTION] Closing: {exe}")
    if not _is_safe_app_name(exe):
        log_info(f"[ACTION] Blocked unsafe close target: {exe}")
        return f"Sorry Master, I couldn't close {target}!"

    try:
        subprocess.Popen(["taskkill", "/IM", exe, "/F"])
    except Exception as e:
        log_info(f"[ACTION] Failed to close '{exe}': {e}")
        return f"Sorry Master, I couldn't close {target}!"

    return f"Closing {target} now!"


def lock_pc() -> str:
    """Lock the PC."""
    log_info("[ACTION] Locking PC")
    try:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    except Exception as e:
        log_info(f"[ACTION] Lock failed: {e}")
        return "Couldn't lock the PC, Master!"
    return "PC locked!"


def sleep_pc() -> str:
    """Put PC to sleep."""
    log_info("[ACTION] Sleeping PC")
    try:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    except Exception as e:
        log_info(f"[ACTION] Sleep failed: {e}")
        return "Couldn't sleep the PC, Master!"
    return "PC going to sleep~"


def open_url(url: str, browser: str = None) -> str:
    """Open a URL in browser."""
    if not url.startswith("http"):
        url = "https://" + url

    log_info(f"[ACTION] Opening URL: {url}")
    if not _is_safe_url(url):
        return f"Sorry Master, I couldn't open {url}!"

    if browser:
        exe = COMMON_APPS.get(browser.lower(), browser)
        try:
            if not _is_safe_app_name(exe):
                raise ValueError("Unsafe browser or URL")
            subprocess.Popen(["cmd", "/c", "start", "", exe, url])
        except Exception as e:
            log_info(f"[ACTION] Browser launch failed: {e}")
            webbrowser.open(url)
    else:
        webbrowser.open(url)

    return f"Opening {url}"


def search_web(query: str, site: str = "google") -> str:
    """Search the web."""
    import urllib.parse

    encoded = urllib.parse.quote(query)
    urls = {
        "google": f"https://www.google.com/search?q={encoded}",
        "youtube": f"https://www.youtube.com/results?search_query={encoded}",
        "github": f"https://github.com/search?q={encoded}",
    }
    url = urls.get(site.lower(), urls["google"])

    log_info(f"[ACTION] Searching {site} for: {query}")
    webbrowser.open(url)
    return f"Searching {query} on {site}!"


def send_whatsapp_message(contact: str, message: str) -> str:
    """Send a WhatsApp message to a contact."""
    import urllib.parse

    log_info(f"[ACTION] Sending WhatsApp to {contact}: {message}")

    # WhatsApp Web URL with message pre-filled
    # Format: https://wa.me/<phone>?text=<message>
    # For contacts, we use the web WhatsApp search format
    encoded_message = urllib.parse.quote(message)
    encoded_contact = urllib.parse.quote(contact)

    # Open WhatsApp Web with the message
    url = f"https://web.whatsapp.com/send?phone=&text={encoded_message}"

    log_info(f"[ACTION] Opening WhatsApp Web...")
    webbrowser.open(url)

    return f"Opening WhatsApp to message {contact}: {message[:50]}..."


def open_whatsapp() -> str:
    """Open WhatsApp."""
    log_info("[ACTION] Opening WhatsApp")
    webbrowser.open("https://web.whatsapp.com")
    return "Opening WhatsApp Web!"
