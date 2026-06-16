import ctypes
import time
import sys

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint)
    ]

def get_idle_time_seconds() -> int:
    """Returns the number of seconds the user has been idle (no mouse/keyboard input)."""
    if sys.platform != "win32":
        # Fallback for non-Windows (e.g., Mac/Linux). For now, assume 0 or dummy logic.
        return 0
        
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
        millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        return millis // 1000
    else:
        return 0

class AFKDetector:
    def __init__(self, afk_threshold_seconds: int = 600):
        self.afk_threshold_seconds = afk_threshold_seconds

    def is_afk(self) -> bool:
        """Returns True if the user has been idle for longer than the threshold."""
        idle_time = get_idle_time_seconds()
        return idle_time >= self.afk_threshold_seconds

    def get_idle_time(self) -> int:
        return get_idle_time_seconds()

# Global instance
afk_detector = AFKDetector(afk_threshold_seconds=600)  # 10 minutes
