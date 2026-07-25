import asyncio
import os
import websockets
import json

# Target number comes from the environment — never hardcode a real phone number in a
# tracked file (this repo is public; a hardcoded number is a spam/SIM-swap target).
#   set TEST_WA_JID=<number>@s.whatsapp.net
TEST_JID = os.getenv("TEST_WA_JID", "0000000000@s.whatsapp.net")


async def test():
    try:
        async with websockets.connect('ws://localhost:9876') as ws:
            await ws.send(json.dumps({'type': 'send_message', 'to_jid': TEST_JID, 'text': 'Test message from script'}))
            print("Message sent to bridge.")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
