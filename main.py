import sys
import os
import time
import threading
import psutil

def parent_watchdog():
    """Kills the backend instantly if the Tauri desktop app closes, preventing ghost servers."""
    parent_pid = os.getppid()
    while True:
        if not psutil.pid_exists(parent_pid):
            print(f"[Main] Parent process (Tauri) {parent_pid} died. Shutting down backend to free port 8001.")
            os._exit(0)
        time.sleep(1)

# Start the Tauri watchdog in a background thread
watchdog_thread = threading.Thread(target=parent_watchdog, daemon=True)
watchdog_thread.start()

# Clear out any ghost servers holding the port before starting
import socket
PORT = 8001
for _ in range(5):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('localhost', PORT)) != 0:
            break
    time.sleep(1)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Execute server.py in the exact same process and namespace
print("[main.py] Proxying execution to server.py...")
server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
with open(server_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), server_path, 'exec')
    exec(code, globals())
