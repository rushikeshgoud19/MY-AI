"""
Mizune WebSocket Server
Bridges Python core to React dashboard.
"""

import asyncio
import websockets
import json
import threading
from typing import Set, Dict, Callable


global_ws_server = None

class MizuneWebSocketServer:
    def __init__(self, core, host='localhost', port=8001):
        global global_ws_server
        self.core = core
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self._running = False
        self._server = None
        global_ws_server = self
    
    async def _handler(self, websocket, path):
        self.clients.add(websocket)
        print(f"[WebSocket] Client connected. Total: {len(self.clients)}")
        
        try:
            # Send initial state
            await websocket.send(json.dumps({
                'type': 'state',
                'data': self.core.get_state()
            }))
            
            async for message in websocket:
                data = json.loads(message)
                await self._handle_message(websocket, data)
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[WebSocket] Client disconnected. Total: {len(self.clients)}")
    
    async def _handle_message(self, client, data: Dict):
        msg_type = data.get('type')
        
        if msg_type == 'chat':
            response = self.core.receive_message(data['message'])
            # Response will be broadcast via callback
            
        elif msg_type == 'whatsapp_message':
            # 1. Forward the raw message to all UI dashboards
            payload = data.get('payload', {})
            alert_msg = {
                'type': 'whatsapp_alert',
                'sender': payload.get('sender', 'Unknown'),
                'message': payload.get('message', ''),
                'urgency': payload.get('urgency', 'normal')
            }
            self._broadcast(alert_msg)
            
            # 2. Check for "mizune" keyword to trigger AI response
            msg_text = payload.get('message', '').lower()
            if "mizune" in msg_text:
                self.core.receive_message(
                    f"A message from WhatsApp arrived. The sender's JID is '{payload.get('sender')}'. "
                    f"The message is: '{payload.get('message')}'. "
                    f"Please reply to them by using the message_whatsapp tool and passing their exact JID as the 'contact'."
                )
        
        elif msg_type == 'execute_skill':
            result = self.core.execute_skill(data['name'])
            await client.send(json.dumps({
                'type': 'skill_result',
                'data': result
            }))
        
        elif msg_type == 'focus_memory':
            self.core.focus_memory(data['itemId'])
        
        elif msg_type == 'phone_command':
            # Handle phone commands
            action = data.get('action')
            if action == 'get_messages':
                msgs = self.core.phone.get_messages()
                await client.send(json.dumps({
                    'type': 'phone_messages',
                    'data': [{'sender': m.sender, 'content': m.content} for m in msgs]
                }))
            elif action == 'take_photo':
                path = self.core.phone.take_photo()
                await client.send(json.dumps({
                    'type': 'phone_photo',
                    'data': {'path': path}
                }))
            elif action == 'get_location':
                loc = self.core.phone.get_location()
                await client.send(json.dumps({
                    'type': 'phone_location',
                    'data': loc
                }))
    
    def _broadcast(self, message: Dict):
        """Broadcast to all connected clients."""
        if not self.clients:
            return
        
        msg_json = json.dumps(message)
        disconnected = set()
        
        for client in self.clients:
            try:
                asyncio.create_task(client.send(msg_json))
            except:
                disconnected.add(client)
        
        self.clients -= disconnected
    
    def start(self):
        """Start WebSocket server in background thread."""
        self._running = True
        
        # Register callback with core
        self.core.register_dashboard_callback(self._broadcast)
        
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self._server = websockets.serve(
                self._handler, self.host, self.port,
                ping_interval=20, ping_timeout=10
            )
            
            print(f"[WebSocket] Server starting on ws://{self.host}:{self.port}")
            loop.run_until_complete(self._server)
            loop.run_forever()
        
        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._running = False
        if self._server:
            self._server.close()
