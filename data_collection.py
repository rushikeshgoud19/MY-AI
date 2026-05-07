import json
import math
import os
import threading
import time
from datetime import datetime
from typing import Optional, Callable

import pyautogui
from PIL import Image

try:
    import win32gui

    def get_active_window_title() -> str:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or ""
except Exception:
    try:
        import pygetwindow as gw

        def get_active_window_title() -> str:
            win = gw.getActiveWindow()
            return win.title if win else ""
    except Exception:
        def get_active_window_title() -> str:
            return ""


def _time_features(ts: float) -> dict:
    dt = datetime.fromtimestamp(ts)
    hour = dt.hour + dt.minute / 60.0
    weekday = dt.weekday()
    hour_rad = (hour / 24.0) * 6.283185307179586
    weekday_rad = (weekday / 7.0) * 6.283185307179586
    return {
        "hour": dt.hour,
        "minute": dt.minute,
        "weekday": weekday,
        "hour_sin": float(math.sin(hour_rad)),
        "hour_cos": float(math.cos(hour_rad)),
        "weekday_sin": float(math.sin(weekday_rad)),
        "weekday_cos": float(math.cos(weekday_rad)),
    }


class DataCollector:
    def __init__(
        self,
        dataset_path: str,
        camera_agent,
        get_mode: Callable[[], str],
        get_master_emotion: Callable[[], str],
        interval_sec: int = 5,
        screen_scale: float = 1.0,
        capture_screen: bool = True,
        capture_camera: bool = True,
        use_time_features: bool = True,
    ) -> None:
        self.dataset_path = dataset_path
        self.camera_agent = camera_agent
        self.get_mode = get_mode
        self.get_master_emotion = get_master_emotion
        self.interval_sec = max(1, int(interval_sec))
        self.screen_scale = float(screen_scale) if screen_scale else 1.0
        self.capture_screen = capture_screen
        self.capture_camera = capture_camera
        self.use_time_features = use_time_features

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        os.makedirs(self.dataset_path, exist_ok=True)
        while not self._stop_event.is_set():
            try:
                self._collect_once()
            except Exception:
                pass
            self._stop_event.wait(self.interval_sec)

    def _collect_once(self) -> None:
        ts = time.time()
        dt = datetime.fromtimestamp(ts)
        day = dt.strftime("%Y-%m-%d")
        sample_id = f"{int(ts * 1000)}"

        screen_path = None
        camera_path = None

        if self.capture_screen:
            screen_dir = os.path.join(self.dataset_path, "screen", day)
            os.makedirs(screen_dir, exist_ok=True)
            screen_path = os.path.join(screen_dir, f"{sample_id}.png")
            screenshot = pyautogui.screenshot()
            if self.screen_scale and self.screen_scale != 1.0:
                w, h = screenshot.size
                screenshot = screenshot.resize(
                    (int(w * self.screen_scale), int(h * self.screen_scale)),
                    Image.BILINEAR,
                )
            screenshot.save(screen_path, format="PNG")

        if self.capture_camera and self.camera_agent:
            cam_dir = os.path.join(self.dataset_path, "camera", day)
            os.makedirs(cam_dir, exist_ok=True)
            camera_path = os.path.join(cam_dir, f"{sample_id}.jpg")
            frame_bytes = self.camera_agent.get_current_frame()
            if frame_bytes:
                with open(camera_path, "wb") as f:
                    f.write(frame_bytes)
            else:
                camera_path = None

        meta_dir = os.path.join(self.dataset_path, "meta")
        os.makedirs(meta_dir, exist_ok=True)
        meta_path = os.path.join(meta_dir, f"{day}.jsonl")

        record = {
            "sample_id": sample_id,
            "session_id": self._session_id,
            "timestamp": dt.isoformat(),
            "unix_ts": ts,
            "mode": self.get_mode() if self.get_mode else "",
            "master_emotion": self.get_master_emotion() if self.get_master_emotion else "",
            "activity_label": "unlabeled",
            "emotion_label": "unlabeled",
            "identity_label": "unlabeled",
            "active_window_title": get_active_window_title(),
            "screen_path": screen_path,
            "camera_path": camera_path,
        }

        if self.use_time_features:
            record.update(_time_features(ts))

        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
