"""
WebSocket handler for Mizune AI.
"""
import json
import asyncio
import threading
import logging
from fastapi import WebSocket

__all__ = ["WebSocketManager", "ws_manager"]


from .config import log_info

logger = logging.getLogger("mizune.websocket")

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

def inject_trace_context(message_dict: dict) -> dict:
    """Inject OTel trace context into WebSocket message."""
    propagator = TraceContextTextMapPropagator()
    carrier = {}
    propagator.inject(carrier)
    message_dict["_trace_context"] = carrier
    return message_dict

class WebSocketManager:
    """Manages WebSocket connections and broadcasting messages."""
    def __init__(self):
        self.connected_clients: list[WebSocket] = []
        self._clients_lock = threading.Lock()
        self.main_loop = None

    def set_main_loop(self, loop):
        """Set the main asyncio event loop to use for thread-safe broadcasting."""
        self.main_loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._clients_lock:
            self.connected_clients.append(websocket)
        log_info("[WS] Client connected.")

    def disconnect(self, websocket: WebSocket):
        with self._clients_lock:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
        log_info("[WS] Client disconnected.")

    def broadcast_sync(self, message: dict) -> None:
        """Broadcast message to all connected WebSocket clients (thread-safe)."""
        loop = self.main_loop
        if loop is None or loop.is_closed():
            return

        async def _send():
            msg_injected = inject_trace_context(message.copy())
            data = json.dumps(msg_injected)
            dead = []
            with self._clients_lock:
                client_list = self.connected_clients.copy()
            for ws in client_list:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            with self._clients_lock:
                for ws in dead:
                    if ws in self.connected_clients:
                        try:
                            self.connected_clients.remove(ws)
                        except ValueError:
                            pass

        try:
            asyncio.run_coroutine_threadsafe(_send(), loop)
        except RuntimeError as e:
            log_info(f"[BROADCAST] Failed: {e}")

# Create a default instance to be imported
ws_manager = WebSocketManager()

