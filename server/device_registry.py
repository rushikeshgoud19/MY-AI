"""Device node registry — Hermes-level remote execution.

Devices (laptop, phone, tablet) run a small agent that connects OUT to this
server's WebSocket and registers itself with its capabilities. Mizune's brain
can then route actions to any online device ("download this on my laptop")
via the remote_device_command tool, and the result flows back here.

Thread-safety: send_command is called from the AI dispatcher (worker threads),
while WebSocket sends happen on the event loop — we bridge with
asyncio.run_coroutine_threadsafe and wait on a threading.Event.
"""
import asyncio
import json
import re
import threading
import time
import uuid
from typing import Any, Dict, Optional

from .config import log_info


def _posix_to_windows(cmd: str) -> str:
    """Translate the handful of POSIX-isms an LLM reliably emits into cmd.exe equivalents.

    Deliberately CONSERVATIVE: only rewrites unambiguous leading-utility cases and /tmp/ paths,
    and bails out entirely if the command already looks Windows/PowerShell-flavoured. A wrong
    translation is worse than none, so anything unrecognised passes through untouched.
    """
    if not cmd or not cmd.strip():
        return cmd
    s = cmd.strip()
    low = s.lower()

    # Already Windows-y or explicitly a shell we shouldn't rewrite → leave alone.
    if (low.startswith(("powershell", "pwsh", "cmd ", "cmd.exe", "type ", "dir", "del ",
                        "copy ", "move ", "ren ", "start ", "tasklist", "taskkill", "where ",
                        "findstr", "wmic", "reg ", "sc ", "net ", "python", "py ", "pip",
                        "npm", "git", "code ", "explorer"))
            or ":\\" in s or "%" in s):
        return cmd

    out = s
    # Leading-utility swaps (only at the start of the command — safe, unambiguous).
    leading = [
        (r"^cat\s+", "type "),
        (r"^ls\s*$", "dir"),
        (r"^ls\s+", "dir "),
        (r"^rm\s+-rf\s+", "rmdir /s /q "),
        (r"^rm\s+-f\s+", "del /q "),
        (r"^rm\s+", "del "),
        (r"^grep\s+", "findstr "),
        (r"^which\s+", "where "),
        (r"^mkdir\s+-p\s+", "mkdir "),
        (r"^touch\s+(\S+)", r"type nul > \1"),
        (r"^ps\s+aux\s*$", "tasklist"),
    ]
    for pat, rep in leading:
        new = re.sub(pat, rep, out, count=1, flags=re.IGNORECASE)
        if new != out:
            out = new
            break

    # /tmp/foo  ->  %TEMP%\foo   (the single most common path mistake)
    out = re.sub(r"/tmp/([\w.\-]+)", r"%TEMP%\\\1", out)
    # bare /tmp -> %TEMP%  (otherwise cmd.exe parses "/tmp" as a switch)
    out = re.sub(r"(?<![\w/])/tmp(?![\w/])", "%TEMP%", out)
    # $HOME / ~ -> %USERPROFILE%
    out = out.replace("$HOME", "%USERPROFILE%").replace(" ~/", " %USERPROFILE%\\")
    return out


class DeviceRegistry:
    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop):
        self._loop = loop

    # ── Registration (called from the WebSocket handler, on the event loop) ──

    def register(self, device_name: str, websocket, capabilities=None, platform: str = "unknown"):
        with self._lock:
            self._devices[device_name] = {
                "ws": websocket,
                "capabilities": capabilities or [],
                "platform": platform,
                "connected_at": time.time(),
            }
        log_info(f"[DEVICES] '{device_name}' online ({platform}), capabilities: {capabilities}")

    def unregister_socket(self, websocket):
        """Remove whichever device owned this socket (called on disconnect)."""
        with self._lock:
            gone = [name for name, d in self._devices.items() if d["ws"] is websocket]
            for name in gone:
                del self._devices[name]
        for name in gone:
            log_info(f"[DEVICES] '{name}' offline.")

    # ── Introspection (for prompts / dashboard) ──

    def list_devices(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                name: {"capabilities": d["capabilities"], "platform": d["platform"]}
                for name, d in self._devices.items()
            }

    def is_online(self, device_name: str) -> bool:
        with self._lock:
            return device_name in self._devices

    def context_line(self, origin_platform: str) -> str:
        """One line of situational context for the system prompt."""
        devices = self.list_devices()
        origin = f"Master is messaging from: {origin_platform}."
        if not devices:
            return f"{origin} No remote devices are online; actions run on this server."
        # PLATFORM IS PART OF THE CONTRACT: without it the brain emitted POSIX commands
        # (`cat`, `echo x > /tmp/f`) at a WINDOWS laptop node and they silently failed
        # ("'cat' is not recognized as an internal or external command" — 2026-07-26).
        # The model can only pick correct syntax if it knows the target OS.
        listing = "; ".join(
            f"{name} [{d.get('platform') or 'unknown'} OS] "
            f"(can: {', '.join(d['capabilities']) or 'basic actions'})"
            for name, d in devices.items()
        )
        oses = {(d.get("platform") or "").lower() for d in devices.values()}
        shell_hint = ""
        if any(o.startswith("win") for o in oses):
            shell_hint = (
                " IMPORTANT: for a windows device use WINDOWS shell syntax — `type file` (not cat), "
                "`dir` (not ls), `del` (not rm), `%TEMP%\\name.txt` or `C:\\Users\\...` paths "
                "(never /tmp/...), and `echo text > C:\\path\\file.txt`."
            )
        return (
            f"{origin} Online devices: {listing}. "
            f"Use the remote_device_command tool to run actions on a specific device "
            f"(e.g. downloads on Master's laptop).{shell_hint}"
        )

    # ── Command routing (called from dispatcher worker threads) ──

    def wait_online(self, device_name: str, seconds: float) -> bool:
        """Block up to `seconds` for a device to (re)appear. Returns True if it's online.

        WHY: a laptop flaps — sleep, wifi drops, agent restarts (measured 276 online / 192 offline
        events in one log). device_agent retries every 10s, so a command that arrives during a gap
        used to fail instantly even though the device was back moments later. Waiting one reconnect
        cycle turns a spurious failure into a short delay."""
        deadline = time.time() + max(0.0, seconds)
        while True:
            if self.is_online(device_name):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(1.0)

    def send_command(self, device_name: str, action: str, args: dict, timeout: float = 45.0,
                     wait_for_device: float = 12.0) -> str:
        with self._lock:
            device = self._devices.get(device_name)
        if not device and wait_for_device > 0:
            # One reconnect cycle of grace before declaring it offline (see wait_online).
            log_info(f"[DEVICES] '{device_name}' not online; waiting up to "
                     f"{wait_for_device:.0f}s for it to reconnect...")
            if self.wait_online(device_name, wait_for_device):
                log_info(f"[DEVICES] '{device_name}' came back online — proceeding.")
                with self._lock:
                    device = self._devices.get(device_name)
        if not device:
            online = ", ".join(self.list_devices().keys()) or "none"
            return (f"Device '{device_name}' is not online (waited "
                    f"{wait_for_device:.0f}s). Online devices: {online}.")
        if not self._loop:
            return "Device routing unavailable: server event loop not ready."

        # DETERMINISTIC SHELL FIX (Design Law 1 — the prompt hint above is not enough on its own;
        # a weak provider still emits `cat`/`/tmp/...` at a Windows box and the command fails
        # silently while the model reports success). Translate at the choke point so EVERY path
        # (chat, mission, scheduled task) is covered.
        if action == "run_command" and (device.get("platform") or "").lower().startswith("win"):
            args = dict(args or {})
            original = str(args.get("command", ""))
            fixed = _posix_to_windows(original)
            if fixed != original:
                log_info(f"[DEVICES] translated POSIX->Windows for '{device_name}': "
                         f"{original[:70]!r} -> {fixed[:70]!r}")
                args["command"] = fixed

        request_id = uuid.uuid4().hex[:12]
        done = threading.Event()
        slot = {"event": done, "result": None}
        with self._lock:
            self._pending[request_id] = slot

        payload = json.dumps({
            "type": "device_command",
            "request_id": request_id,
            "action": action,
            "args": args or {},
        })

        try:
            fut = asyncio.run_coroutine_threadsafe(device["ws"].send_text(payload), self._loop)
            fut.result(timeout=10)
        except Exception as e:
            with self._lock:
                self._pending.pop(request_id, None)
            return f"Failed to reach device '{device_name}': {e}"

        if not done.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            return (f"Device '{device_name}' accepted the command but didn't finish within "
                    f"{int(timeout)}s. It may still complete in the background.")

        with self._lock:
            slot = self._pending.pop(request_id, slot)
        return str(slot.get("result") or "Done (no output).")

    def handle_result(self, request_id: str, result: Any):
        """Called from the WebSocket handler when a device replies."""
        with self._lock:
            slot = self._pending.get(request_id)
        if slot:
            slot["result"] = result
            slot["event"].set()


device_registry = DeviceRegistry()
