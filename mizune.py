import sys
import threading
import uvicorn
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

from client.bridge import WebSocketBridge
from client.app import MainWindow

import subprocess

# --- Background Server Runner ---
def run_server():
    global server_process
    CREATE_NO_WINDOW = 0x08000000
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW
    )

# --- System Tray Icon Generator ---
def create_tray_icon():
    # Create a simple purple glowing circle icon programmatically
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#a777e3"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(8, 8, 48, 48)
    painter.end()
    return QIcon(pixmap)

def main():
    # 1. Start the FastAPI backend in a daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 2. Initialize PyQt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Keep running when widget is hidden

    # 3. Setup WebSocket Bridge
    bridge = WebSocketBridge()
    bridge.start()

    # 4. Setup Floating Widget
    widget = MainWindow(bridge)
    
    # Global hotkey removed to prevent Qt event loop freezing (Not Responding error)
    
    # 6. Setup System Tray
    tray = QSystemTrayIcon(create_tray_icon(), app)
    menu = QMenu()
    
    show_action = menu.addAction("Show Mizune (Alt+Space)")
    show_action.triggered.connect(widget.toggle_visibility)
    
    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)
    
    tray.setContextMenu(menu)
    tray.show()
    
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            widget.toggle_visibility()
            
    tray.activated.connect(on_tray_activated)
    
    # Show widget on startup and force it to foreground
    widget.showNormal()
    widget.raise_()
    widget.activateWindow()
    
    # 7. Start UI Loop
    try:
        sys.exit(app.exec())
    finally:
        bridge.stop()
        bridge.wait()
        if 'server_process' in globals() and server_process:
            server_process.terminate()
            server_process.kill()

if __name__ == "__main__":
    main()
