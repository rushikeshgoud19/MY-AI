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
import threading
import time
import uuid
from typing import Any, Dict, Optional

from .config import log_info


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

    def context_line(self, origin_platform: str) -> str:
        """One line of situational context for the system prompt."""
        devices = self.list_devices()
        origin = f"Master is messaging from: {origin_platform}."
        if not devices:
            return f"{origin} No remote devices are online; actions run on this server."
        listing = "; ".join(
            f"{name} (can: {', '.join(d['capabilities']) or 'basic actions'})"
            for name, d in devices.items()
        )
        return (
            f"{origin} Online devices: {listing}. "
            f"Use the remote_device_command tool to run actions on a specific device "
            f"(e.g. downloads on Master's laptop)."
        )

    # ── Command routing (called from dispatcher worker threads) ──

    def send_command(self, device_name: str, action: str, args: dict, timeout: float = 45.0) -> str:
        with self._lock:
            device = self._devices.get(device_name)
        if not device:
            online = ", ".join(self.list_devices().keys()) or "none"
            return f"Device '{device_name}' is not online. Online devices: {online}."
        if not self._loop:
            return "Device routing unavailable: server event loop not ready."

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
