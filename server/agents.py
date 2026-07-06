"""
Multi-Agent orchestration and background workers for Mizune AI.
"""
import os
import cv2
import time
import json
import sqlite3
import threading
import traceback
import logging
from typing import Dict, Any, List

__all__ = ["DataCollectionWorker", "CameraAgent", "mizune_manager", "save_turn"]


from .config import log_info

logger = logging.getLogger("mizune.agents")

# Setup Data Directory
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_collector")
os.makedirs(_DATA_DIR, exist_ok=True)
_DB_PATH = os.path.join(_DATA_DIR, "mizune_memory.db")

def _init_db():
    try:
        conn = sqlite3.connect(_DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT,
                content TEXT,
                emotion TEXT,
                context_mode TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu_percent REAL,
                ram_percent REAL,
                active_window TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        log_info(f"[DB] Init error: {e}")

_init_db()

def save_turn(role: str, content: str, emotion: str = "neutral", context_mode: str = "conversation"):
    try:
        conn = sqlite3.connect(_DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversation_log (role, content, emotion, context_mode) VALUES (?, ?, ?, ?)",
            (role, content, emotion, context_mode)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log_info(f"[DB] Save error: {e}")

class DataCollectionWorker:
    """Runs in background collecting telemetry, screenshots, and context."""
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("data_collection_enabled", False)
        self.interval = config.get("data_collection_interval_sec", 10)
        self.scale = config.get("data_collection_screen_scale", 1.0)
        self.running = False
        self._thread = None

    def start(self):
        if not self.enabled:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log_info(f"[DATA AGENT] Started background collection (every {self.interval}s)")

    def stop(self):
        self.running = False

    def _loop(self):
        import psutil
        try:
            import pygetwindow as gw
        except ImportError:
            gw = None

        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                
                active_win = "Unknown"
                if gw:
                    try:
                        win = gw.getActiveWindow()
                        if win:
                            active_win = win.title
                    except Exception:
                        pass
                
                try:
                    conn = sqlite3.connect(_DB_PATH)
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO system_telemetry (cpu_percent, ram_percent, active_window) VALUES (?, ?, ?)",
                        (cpu, ram, active_win)
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    log_info(f"[DATA AGENT] DB error: {e}")

            except Exception as e:
                log_info(f"[DATA AGENT] Loop error: {e}")
                
            time.sleep(self.interval)

class CameraAgent:
    """Manages the webcam, captures frames, and detects if Master is present."""
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("data_collection_capture_camera", True)
        self.running = False
        self.cap = None
        self._thread = None
        self._latest_frame = None
        self._lock = threading.Lock()
        
        self.is_master_present = True 
        self._face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self._last_face_check = 0.0

    def start(self):
        if not self.enabled:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log_info("[CAMERA AGENT] Started background webcam monitor")

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def get_current_frame(self) -> bytes:
        with self._lock:
            if self._latest_frame is not None:
                _, buffer = cv2.imencode('.jpg', self._latest_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                return buffer.tobytes()
        return None
        
    def verify_master_now(self) -> bool:
        """Does a live check if the person on camera is Master."""
        with self._lock:
            frame = self._latest_frame
            
        if frame is None:
            return True # Assume True if camera is off
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            return True
            
        return False

    def _loop(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            log_info("[CAMERA AGENT] Could not open webcam 0")
            self.running = False
            return
            
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._latest_frame = frame
                
                if time.time() - self._last_face_check >= 2.0:
                    self._last_face_check = time.time()
                    is_present = self.verify_master_now()
                    if is_present != self.is_master_present:
                        self.is_master_present = is_present
                        status = "Master" if is_present else "Stranger/Empty"
                        
            time.sleep(0.05)
class MizuneManagerWrapper:
    """Wrapper to initialize ManagerAgent with workers for server compatibility."""
    def __init__(self, config: dict):
        # We initialize without config here, it's passed during initialize() from server.py
        from agents.manager_agent import ManagerAgent
        self.agent = ManagerAgent(config)
        self.workers = {}
        
    def initialize(self, config: dict):
        self.agent.config = config

        # On cloud there is no webcam or desktop to observe — skip the workers that would
        # try to grab /dev/video0 or read the active window, so we don't spin threads that
        # error every loop.
        from .config import is_cloud_mode
        cloud = is_cloud_mode(config)

        if not cloud:
            self.workers["data"] = DataCollectionWorker(config)
            self.workers["camera"] = CameraAgent(config)
        else:
            log_info("[BRAIN] Cloud mode: skipping CameraAgent + DataCollectionWorker (no local hardware).")
        
        # Connect Agentic Brains — each in its own guard so one broken agent
        # can't take down the other five (a NameError here used to kill ALL of
        # them, leaving "My planning brain isn't connected" for every task).
        brain_specs = [
            ("planner", "agents.task_planner_agent", "TaskPlannerAgent"),
            ("executor", "agents.action_executor_agent", "ActionExecutorAgent"),
            ("system", "agents.system_agent", "SystemAgent"),
            ("vision", "agents.vision_perception_agent", "VisionPerceptionAgent"),
            ("obsidian", "agents.new.obsidian_agent", "ObsidianAgent"),
            ("traceroot_analyst", "agents.traceroot_analyst_agent", "TracerootAnalystAgent"),
        ]
        import importlib
        for worker_name, module_path, class_name in brain_specs:
            try:
                mod = importlib.import_module(module_path)
                self.workers[worker_name] = getattr(mod, class_name)(config)
            except Exception as e:
                log_info(f"[BRAIN] Worker '{worker_name}' unavailable: {e}")
            
        self.agent.initialize(config, self.workers)
        
    def stop_all(self):
        self.agent.stop_all()
        
    async def execute(self, query: str, context: dict = None) -> str:
        return await self.agent.execute(query, context)
        
    @property
    def current_mode(self):
        return self.agent.current_mode
        
    @current_mode.setter
    def current_mode(self, value):
        self.agent.current_mode = value

mizune_manager = MizuneManagerWrapper({})


