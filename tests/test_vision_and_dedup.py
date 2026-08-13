import asyncio
import sys
import json
import base64
import websockets

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WS_URI = "ws://40.123.215.32:8001/ws"

# A small valid JPEG base64 (1x1 red pixel / simple image)
TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP///////////////////////////////////"
    "///////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBAB"
    "AAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)

async def ws_ask(msg_payload, timeout=60):
    speaks = []
    async with websockets.connect(WS_URI, open_timeout=15) as ws:
        await ws.send(json.dumps(msg_payload))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
            except asyncio.TimeoutError:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            t = msg.get("type")
            if t == "speak" and msg.get("text"):
                speaks.append(msg["text"])
            elif t == "status" and msg.get("text") == "Idle" and speaks:
                break
    return speaks

async def main():
    print("--- 1. Testing learn() deduplication ---")
    url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    print("Learning URL first time...")
    r1 = await ws_ask({"type": "chat", "text": f"learn this: {url}"}, timeout=60)
    print("Reply 1:", " ".join(r1))

    print("Learning SAME URL second time...")
    r2 = await ws_ask({"type": "chat", "text": f"learn this: {url}"}, timeout=60)
    print("Reply 2:", " ".join(r2))

    print("\n--- 2. Testing mobile_vision path ---")
    r3 = await ws_ask({"type": "mobile_vision", "image_b64": TINY_JPEG_B64}, timeout=60)
    print("Vision reply:", " ".join(r3))

asyncio.run(main())
