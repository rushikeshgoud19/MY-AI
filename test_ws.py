import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://localhost:9876') as ws:
            await ws.send(json.dumps({'type': 'send_message', 'to_jid': '917815977345@s.whatsapp.net', 'text': 'Test message from script'}))
            print("Message sent to bridge.")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
