import os
import time
from typing import List, Dict, Optional
from ppadb.client import Client as AdbClient

from server.config import log_info

class AndroidPhoneBridge:
    """
    Bridge to control Android phone via ADB (Android Debug Bridge).
    Requires 'pure-python-adb' package and ADB enabled on phone.
    """
    def __init__(self, host="127.0.0.1", port=5037):
        self.host = host
        self.port = port
        self.client = None
        self.device = None
        self.connected = False
        self.device_id = None
        
        self.connect()
        
    def connect(self) -> bool:
        """Connect to ADB server and get the first attached device."""
        try:
            # We first try to start the adb server if it's not running
            os.system("adb start-server")
            
            self.client = AdbClient(host=self.host, port=self.port)
            devices = self.client.devices()
            
            if devices:
                self.device = devices[0]
                self.device_id = self.device.serial
                self.connected = True
                log_info(f"[PHONE] Successfully connected to Android device: {self.device_id}")
                return True
            else:
                log_info("[PHONE] No Android devices found. Make sure USB debugging is enabled or connected via TCP.")
                self.connected = False
                return False
        except Exception as e:
            log_info(f"[PHONE] Failed to connect to ADB: {e}")
            self.connected = False
            return False

    def get_messages(self, limit=10) -> List[Dict]:
        """Fetch recent SMS messages using ADB shell content query."""
        if not self.connected:
            return [{"sender": "System", "content": "Phone not connected"}]
            
        try:
            # Read SMS inbox using content provider
            result = self.device.shell(f"content query --uri content://sms/inbox --projection address:body:date --sort \"date DESC\" --limit {limit}")
            
            messages = []
            for line in result.strip().split('\n'):
                if not line.strip():
                    continue
                # Parsing ADB output: Row: 0 address=12345 body=Hello date=1623...
                parts = line.split(", ")
                msg = {"sender": "Unknown", "content": "", "date": ""}
                for p in parts:
                    if "=" in p:
                        key, val = p.split("=", 1)
                        if key.strip() == "address":
                            msg["sender"] = val
                        elif key.strip() == "body":
                            msg["content"] = val
                        elif key.strip() == "date":
                            msg["date"] = val
                messages.append(msg)
                
            return messages
        except Exception as e:
            log_info(f"[PHONE] Error reading messages: {e}")
            return []

    def take_photo(self) -> str:
        """Triggers the camera to take a photo. Note: varies heavily by device."""
        if not self.connected:
            return "Phone not connected"
            
        try:
            # Start camera
            self.device.shell("am start -a android.media.action.STILL_IMAGE_CAMERA")
            time.sleep(2)
            # Simulate pressing the capture button (KEYCODE_CAMERA)
            self.device.shell("input keyevent 27")
            time.sleep(1)
            # Close camera
            self.device.shell("input keyevent 4")
            
            return "Photo taken! Please check your phone gallery."
        except Exception as e:
            log_info(f"[PHONE] Error taking photo: {e}")
            return f"Failed to take photo: {e}"

    def get_location(self) -> str:
        """Attempts to get the last known location from the device."""
        if not self.connected:
            return "Phone not connected"
            
        try:
            result = self.device.shell("dumpsys location")
            # Extract relevant lines
            loc_lines = [line for line in result.split('\n') if 'last location' in line.lower() or 'gps' in line.lower()]
            if loc_lines:
                return "\n".join(loc_lines[:3])
            return "Location data found, but format is complex. Check dumpsys manually."
        except Exception as e:
            return f"Error getting location: {e}"

    def get_battery(self) -> str:
        if not self.connected:
            return "Phone not connected"
            
        try:
            result = self.device.shell("dumpsys battery")
            level = [line for line in result.split('\n') if 'level:' in line]
            if level:
                return f"Battery Level: {level[0].split(':')[1].strip()}%"
            return "Could not read battery"
        except Exception as e:
            return f"Error reading battery: {e}"
