"""
WebSocket handler for Mizune AI.
"""
import json
import asyncio
import contextvars
import threading
import logging
import uuid
from fastapi import WebSocket

__all__ = [
    "WebSocketManager", "ws_manager", "turn_origin", "set_turn_origin", "ORIGIN_SYSTEM",
]

#: Origin used when no client started the turn — the subconscious heartbeat, a cron
#: task, the nightly self-review, a WhatsApp reply. Anything a human at a client did
#: not ask for.
ORIGIN_SYSTEM = "system"

#: Who the turn currently being processed belongs to.
#:
#: Every frame this server sends goes to EVERY connected client — there is no addressing
#: in the protocol — so a client could not tell its own reply from a cron job's, or from
#: her answer to somebody else's WhatsApp message. The phone worked around that with a
#: 90-second timer: "if I sent something recently, this is probably for me". A timer
#: cannot be right; a proactive tick landing inside the window is indistinguishable from
#: a real reply, and one that arrives late is discarded.
#:
#: A ContextVar rather than a parameter because the alternative is threading an argument
#: through 20+ broadcast sites across processor, scheduler, missions, self-review and the
#: platform bridges. Set it once where a turn BEGINS and every frame that turn produces
#: is stamped automatically: `asyncio.create_task` and `asyncio.to_thread` both copy the
#: current context, which is exactly how a turn's work fans out here.
turn_origin: contextvars.ContextVar = contextvars.ContextVar("turn_origin", default=ORIGIN_SYSTEM)

#: Has an entry point in this process ever claimed a turn for a client?
#:
#: Deploy safety, and it is not theoretical. The VM's entry file (`backend_main.py`) is
#: mirrored by hand and is NOT part of the `server/` copy. Ship this module without
#: mirroring the `set_turn_origin()` call into that file and every frame would stamp
#: "system" — perfectly formed, entirely wrong — and the phone, seeing a stamp it can
#: read, would trust it and go silent for real replies too. Bricking her voice as the
#: reward for a partial deploy is not an acceptable failure mode.
#:
#: So: stamp nothing until something claims a turn. An un-mirrored backend emits no
#: `origin` at all, the phone sees no opinion, and it falls back to the timer it uses
#: today. Deploy order stops mattering.
_origin_wired = False


def set_turn_origin(client_id: str) -> None:
    """Claim the current turn for `client_id`. Call where a client turn BEGINS."""
    global _origin_wired
    _origin_wired = True
    turn_origin.set(client_id)


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
        self._client_ids: dict = {}
        self._clients_lock = threading.Lock()
        self.main_loop = None

    def set_main_loop(self, loop):
        """Set the main asyncio event loop to use for thread-safe broadcasting."""
        self.main_loop = loop

    def client_id(self, websocket: WebSocket) -> str:
        """The id handed to this client on connect, or ORIGIN_SYSTEM if unknown."""
        with self._clients_lock:
            return self._client_ids.get(websocket, ORIGIN_SYSTEM)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        cid = uuid.uuid4().hex[:12]
        with self._clients_lock:
            self.connected_clients.append(websocket)
            self._client_ids[websocket] = cid
        # Tell the client its own id, so it can recognise the frames stamped with it.
        # Sent directly rather than broadcast: it is the one frame that is genuinely
        # for one client only.
        try:
            await websocket.send_text(json.dumps({"type": "hello", "client_id": cid}))
        except Exception as e:
            log_info(f"[WS] Could not send hello to {cid}: {e}")
        log_info(f"[WS] Client connected ({cid}).")

    def disconnect(self, websocket: WebSocket):
        with self._clients_lock:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            cid = self._client_ids.pop(websocket, "?")
        log_info(f"[WS] Client disconnected ({cid}).")

    def broadcast_sync(self, message: dict) -> None:
        """Broadcast message to all connected WebSocket clients (thread-safe)."""
        loop = self.main_loop
        if loop is None or loop.is_closed():
            return

        # Stamp HERE, on the calling thread, while the turn's context is still current.
        # `_send` runs on the main loop in a different context, where turn_origin would
        # always read back as the default.
        stamped = dict(message)
        if _origin_wired:
            stamped.setdefault("origin", turn_origin.get())

        async def _send():
            msg_injected = inject_trace_context(dict(stamped))
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

