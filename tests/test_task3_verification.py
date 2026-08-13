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
    print("--- 1. Testing allowlist refusal on C:\\Windows ---")
    r1 = await ws_ask("index files in C:\\Windows", timeout=30)
    print("Refusal reply:", " ".join(r1))

    print("\n--- 2. Indexing test_mizune_brain folder ---")
    r2 = await ws_ask("index files in Desktop/test_mizune_brain", timeout=45)
    print("Index reply:", " ".join(r2))

    print("Waiting 10s for background indexing to complete...")
    await asyncio.sleep(10)

    print("\n--- 3. Querying question answerable ONLY from local file ---")
    r3 = await ws_ask("what is the secret hackathon keyword?", timeout=45)
    print("Knowledge recall reply:", " ".join(r3))

asyncio.run(main())
