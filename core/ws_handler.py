"""WebSocket handler for Mizune AI."""
import asyncio
import json
import logging
from typing import List

from fastapi import WebSocket


log_info = logging.info


class WebSocketHandler:
    """Thread-safe WebSocket connection manager."""

    def __init__(self):
        self._clients: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def add_client(self, websocket: WebSocket) -> None:
        """Add a new client connection."""
        await websocket.accept()
        async with self._lock:
            self._clients.append(websocket)
        log_info("[WS] Client connected.")

    async def remove_client(self, websocket: WebSocket) -> None:
        """Remove a client connection."""
        async with self._lock:
            if websocket in self._clients:
                self._clients.remove(websocket)
        log_info("[WS] Client disconnected.")

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all connected clients."""
        data = json.dumps(message)
        dead = []
        async with self._lock:
            clients = self._clients.copy()
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        async with self._lock:
            for ws in dead:
                if ws in self._clients:
                    self._clients.remove(ws)

    def get_client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)


# Global handler instance
ws_handler = WebSocketHandler()


async def handle_websocket_message(websocket: WebSocket, message: str) -> None:
    """Handle incoming WebSocket message."""
    try:
        msg = json.loads(message)
        action = msg.get("type")
        target = msg.get("target")

        if action == "NOTE" and target:
            from server import take_note
            take_note(target)
        elif action == "chat":
            text = msg.get("text", "").strip()
            if text:
                await ws_handler.broadcast({"type": "user_input", "text": text})
                await ws_handler.broadcast({"type": "status", "text": "Thinking..."})

                # Process chat in thread pool
                from server import process_command
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, process_command, text)
                await ws_handler.broadcast({"type": "speak", "text": res})
                await ws_handler.broadcast({"type": "status", "text": "Idle"})

    except Exception as e:
        log_info(f"[WS] Error processing message: {e}")