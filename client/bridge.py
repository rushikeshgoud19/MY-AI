import json
import websocket
from PyQt6.QtCore import QThread, pyqtSignal
import time
import logging

class WebSocketBridge(QThread):
    # Signals to emit to the PyQt UI
    status_signal = pyqtSignal(str, str) # text, color
    speak_signal = pyqtSignal(str)       # text
    emotion_signal = pyqtSignal(str)     # emotion_name
    mode_signal = pyqtSignal(str)        # mode_name
    refresh_graph_signal = pyqtSignal()  # Triggers graph reload
    whatsapp_signal = pyqtSignal(str)    # JSON string of whatsapp data
    kernel_signal = pyqtSignal(str)      # JSON string of kernel event
    memory_signal = pyqtSignal(str)      # JSON string of memory state
    
    def __init__(self, url="ws://127.0.0.1:8001/ws"):
        super().__init__()
        self.url = url
        self.ws = None
        self.running = True

    def run(self):
        while self.running:
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                self.ws.run_forever()
            except Exception as e:
                logging.error(f"[BRIDGE] WS Error: {e}")
            
            if self.running:
                time.sleep(3) # Reconnect delay

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "status":
                text = data.get("text", "")
                color = "#a777e3" # Default purple
                if text == "Thinking..." or text == "Processing...":
                    color = "#ffcc00"
                elif text == "Listening...":
                    color = "#0f52ba"
                elif text == "Triggered":
                    color = "#ff00c8"
                self.status_signal.emit(text, color)
                
            elif msg_type == "speak":
                text = data.get("text", "").strip()
                # Clean up metadata
                import re
                text = re.sub(r'\[.*?\]', '', text).strip()
                self.speak_signal.emit(text)
                
            elif msg_type == "emotion":
                self.emotion_signal.emit(data.get("emotion", "neutral"))
                
            elif msg_type == "mode":
                self.mode_signal.emit(data.get("mode", "conversation"))
                
            elif msg_type == "refresh_graph":
                self.refresh_graph_signal.emit()
                
            elif msg_type == "whatsapp_alert":
                self.whatsapp_signal.emit(json.dumps(data))
                
            elif msg_type == "kernel_event":
                self.kernel_signal.emit(json.dumps(data.get("event", {})))
                
            elif msg_type == "memory_state":
                self.memory_signal.emit(json.dumps(data.get("state", {})))
                
        except Exception as e:
            logging.error(f"[BRIDGE] Error parsing message: {e}")

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, close_status_code, close_msg):
        self.status_signal.emit("Reconnecting...", "#ff6b6b")
        
    def on_open(self, ws):
        self.status_signal.emit("Online", "#4cd137")

    def send_chat(self, text):
        if self.ws and text.strip():
            try:
                self.ws.send(json.dumps({"type": "chat", "text": text.strip()}))
            except Exception as e:
                logging.error(f"[BRIDGE] Send error: {e}")

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
