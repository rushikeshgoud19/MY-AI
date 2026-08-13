import asyncio
import sys
import json
import websockets

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


WS_URI = "ws://40.123.215.32:8001/ws"

async def ws_ask(query, timeout=60):
    speaks = []
    async with websockets.connect(WS_URI, open_timeout=15) as ws:
        await ws.send(json.dumps({"type": "chat", "text": query}))
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
    print("Learning deliberate practice...")
    replies = await ws_ask("learn this: https://en.wikipedia.org/wiki/Deliberate_practice", timeout=90)
    print("Reply:", " ".join(replies))
    
    print("\nAsking semantic recall question...")
    replies2 = await ws_ask("what do you know about getting better at skills", timeout=60)
    print("Reply:", " ".join(replies2))

asyncio.run(main())
