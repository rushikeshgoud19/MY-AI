"""
System commands and app launching logic for Mizune AI.
"""
import os
import subprocess
import webbrowser
import time
import logging
import re
from urllib.parse import urlparse
try:
    import pyautogui
except ImportError:
    pyautogui = None

__all__ = ["launch_app", "close_app", "whatsapp_automation", "take_note", "search_memory", "get_system_info", "COMMON_APPS"]


from .config import log_info

logger = logging.getLogger("mizune.commands")
_SAFE_APP_NAME = re.compile(r"^[\w .+\-]+$")


def _is_url_or_protocol(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} or value.startswith("ms-") or "://" in value or value.endswith(":")


def _is_safe_app_name(value: str) -> bool:
    return bool(value and _SAFE_APP_NAME.fullmatch(value))


def _is_safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not any(c.isspace() for c in value)


def _start_app(exe: str):
    subprocess.Popen(["cmd", "/c", "start", "", exe])

# Expanded Dictionary of Common PC Apps
COMMON_APPS = {
    # Browsers
    "chrome": "chrome",
    "google chrome": "chrome",
    "brave": "brave",
    "brave browser": "brave",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "opera": "launcher", # Opera usually uses launcher.exe
    "opera gx": "launcher",
    
    # Dev Tools
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "cursor": "cursor",
    "terminal": "wt", # Windows Terminal
    "powershell": "powershell",
    "command prompt": "cmd",
    "cmd": "cmd",
    "git bash": "git-bash",
    "notepad": "notepad",
    "notepad++": "notepad++",
    "postman": "postman",
    "android studio": "studio64",
    "intellij": "idea64",
    
    # Communication / Social
    "whatsapp": "whatsapp://",
    "discord": "discord",
    "telegram": "telegram",
    "slack": "slack",
    "teams": "ms-teams",
    "microsoft teams": "ms-teams",
    "zoom": "zoom",
    "skype": "skype",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://reddit.com",
    "instagram": "https://instagram.com",
    
    # Media / Entertainment
    "spotify": "spotify",
    "steam": "steam",
    "epic games": "epicgameslauncher",
    "vlc": "vlc",
    "obs": "obs64",
    "obs studio": "obs64",
    "netflix": "https://netflix.com",
    "youtube": "https://youtube.com",
    "twitch": "https://twitch.tv",
    "crunchyroll": "https://crunchyroll.com",
    "whatsapp web": "https://web.whatsapp.com/",
    "whatsapp on web": "https://web.whatsapp.com/",
    "whatsapp browser": "https://web.whatsapp.com/",
    
    # Productivity / Office
    "word": "winword",
    "ms word": "winword",
    "microsoft word": "winword",
    "excel": "excel",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpnt",
    "ppt": "powerpnt",
    "outlook": "outlook",
    "onenote": "onenote",
    "notion": "notion",
    "obsidian": "obsidian",
    "calculator": "calc",
    "calendar": "outlookcal:",
    
    # System Utils
    "settings": "ms-settings:",
    "task manager": "taskmgr",
    "file explorer": "explorer",
    "explorer": "explorer",
    "paint": "mspaint",
    "snipping tool": "snippingtool",
    "control panel": "control",
    "registry editor": "regedit",
    "services": "services.msc",
    "device manager": "devmgmt.msc",
    
    # Creative / Design
    "photoshop": "photoshop",
    "illustrator": "illustrator",
    "premiere": "premiere",
    "after effects": "afterfx",
    "blender": "blender",
    "figma": "figma",
    "unity": "unityhub",
    "unreal": "unrealeditor",
}

def take_note(content: str, config: dict) -> bool:
    try:
        from server.memory import memory
        memory.store_longterm(content, metadata={"source": "explicit_note"})
        log_info(f"[ACTION] Semantic memory saved: {content}")
        return True
    except Exception as e:
        log_info(f"[ACTION] Failed to save semantic memory: {e}")
        return False

def search_memory(keyword: str) -> str:
    try:
        from server.memory import memory
        if not memory.db: return "Memory database offline."
        cursor = memory.db.cursor()
        cursor.execute("SELECT role, content FROM history WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 20", (f"%{keyword}%",))
        rows = cursor.fetchall()
        if not rows: return f"No memories found about '{keyword}'."
        
        results = []
        for r in reversed(rows):
            results.append(f"{r[0].upper()}: {r[1]}")
        return "\n".join(results)
    except Exception as e:
        log_info(f"[ACTION] Failed to search memory: {e}")
        return f"Error searching memory: {e}"


def launch_app(target: str):
    target = target.lower()
    if target in ("spotify", "spotify in browser", "spotify web", "spotify web player", "music"):
        log_info("[ACTION] Launching Spotify in browser tab")
        webbrowser.open_new_tab("https://open.spotify.com/")
        return

    # Check for direct URL intents like "youtube on brave"
    if "youtube" in target and ("brave" in target or "browser" in target):
        log_info("[ACTION] Launching YouTube in browser tab")
        webbrowser.open_new_tab("https://youtube.com/")
        return

    exe = COMMON_APPS.get(target, target)

    log_info(f"[ACTION] Launching: {exe}")
    if _is_url_or_protocol(exe):
        if exe.startswith("http") and not _is_safe_url(exe):
            log_info(f"[ACTION] Blocked unsafe URL target: {exe}")
            return
        # Use built-in webbrowser to explicitly request a new tab instead of a new window
        webbrowser.open_new_tab(exe)
    else:
        if not _is_safe_app_name(exe):
            log_info(f"[ACTION] Blocked unsafe launch target: {exe}")
            return
        try:
            _start_app(exe)
            
            # Windows 11 Notepad resumes previous tabs by default. 
            # Force a fresh tab so we don't overwrite user's work!
            if exe == "notepad":
                time.sleep(1.5)
                pyautogui.hotkey('ctrl', 'n')
                
        except Exception as e:
            log_info(f"[ACTION] Failed to launch '{exe}': {e}")

def _whatsapp_focus():
    """Find WhatsApp window or Browser window containing WhatsApp Web."""
    try:
        import pygetwindow as gw
        # Prioritize Desktop App
        wa = gw.getWindowsWithTitle("WhatsApp")
        # Check for browser titles if Desktop app isn't found
        if not wa:
            all_windows = gw.getAllTitles()
            for t in all_windows:
                if "WhatsApp" in t and ("Brave" in t or "Chrome" in t or "Edge" in t):
                    wa = gw.getWindowsWithTitle(t)
                    break

        if wa:
            w = wa[0]
            if w.isMinimized: w.restore()
            w.activate()
            time.sleep(0.5)
            # Click near center-left where the search bar typically is
            cx = w.left + w.width // 4
            cy = max(w.top + 150, w.top + w.height // 4)
            pyautogui.click(cx, cy)
            time.sleep(0.5)
            log_info(f"[ACTION] Click-focused WhatsApp at ({cx},{cy})")
            return True
    except Exception:
        pass
    return False

def whatsapp_automation(contact: str, message: str = None) -> str:
    """Use the Node.js headless bridge to send a WhatsApp message securely and instantly."""
    from server.platforms.whatsapp.core import send_whatsapp_message
    
    # Mizune runs on Master's own WhatsApp, so "Master"/"Rushi"/"me" all mean send-to-self.
    if contact.lower().strip() in ["me", "myself", "self", "master", "rushi", "rushikesh", "master rushi"]:
        target = None # Default to self
        contact = "yourself"
    else:
        target = contact
        
    # Attempt to resolve name from contacts.json
    try:
        import json, os
        contacts_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contacts.json")
        if os.path.exists(contacts_file):
            with open(contacts_file, "r", encoding="utf-8", errors="replace") as f:
                contacts_db = json.load(f)
                # lowercase match
                for name, number in contacts_db.items():
                    if name.lower() in contact.lower() or contact.lower() in name.lower():
                        target = number
                        log_info(f"[ACTION] Resolved contact '{contact}' to number {target}")
                        break
    except Exception as e:
        log_info(f"[ACTION] Contact resolution error: {e}")

    # If it's a phone number, use headless Baileys!
    if target is None or any(char.isdigit() for char in target):
        log_info(f"[ACTION] Sending headless WhatsApp message to '{contact}'")
        from server.platforms.whatsapp.core import send_whatsapp_message
        success = send_whatsapp_message(message, target)
        if success:
            return f"Done! Headless message successfully sent to {contact}!"
        else:
            return f"Failed to send message! The WhatsApp bridge is not connected."

    # If target is still just a name, it means it wasn't found in contacts.json
    error_msg = f"I cannot send the message because '{contact}' is not in your contacts dot JSON file. Please add their phone number so I can send it instantly in the background!"
    log_info(f"[ACTION] Failed to resolve contact: {error_msg}")
    return error_msg
def close_app(target: str):
    exe = COMMON_APPS.get(target, target)
    if _is_url_or_protocol(exe):
        return 

    if not exe.endswith(".exe"):
        exe += ".exe"

    log_info(f"[ACTION] Closing: {exe}")
    if not _is_safe_app_name(exe):
        log_info(f"[ACTION] Blocked unsafe close target: {exe}")
        return

    try:
        subprocess.Popen(["taskkill", "/IM", exe, "/F"])
    except Exception as e:
        log_info(f"[ACTION] Failed to close '{exe}': {e}")

def execute_python_code(code: str) -> str:
    """Safely execute Python code generated by the LLM in a subprocess and return output."""
    import tempfile
    import os
    import sys
    
    from server.security import SecurityScanner
    is_safe, reason = SecurityScanner.scan_code(code)
    if not is_safe:
        return f"Error: Code blocked due to security filter. {reason}"
            
    # Write code to a temp file
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(code)
            
        log_info(f"[ACTION] Executing generated Python script...")
        
        # Run it with a timeout of 15 seconds so the LLM doesn't hang the system with infinite loops
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        output = result.stdout.strip()
        err = result.stderr.strip()
        
        if result.returncode == 0:
            return f"Success. Output:\n{output}" if output else "Success. No output."
        else:
            return f"Error (Exit Code {result.returncode}).\nStdout: {output}\nStderr: {err}"
            
    except subprocess.TimeoutExpired:
        return "Error: Script execution timed out after 15 seconds."
    except Exception as e:
        return f"Error running script: {str(e)}"
    finally:
        # Cleanup
        try:
            os.remove(path)
        except Exception:
            pass

def get_system_info(category: str = "all") -> str:
    """Get real system information. Returns formatted string."""
    import psutil
    
    info_parts = []
    
    try:
        if category in ("all", "cpu"):
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            freq_str = f"{cpu_freq.current:.0f}MHz" if cpu_freq else "N/A"
            info_parts.append(f"CPU: {cpu_percent}% usage | {cpu_count} cores | {freq_str}")
        
        if category in ("all", "ram"):
            mem = psutil.virtual_memory()
            info_parts.append(f"RAM: {mem.percent}% used | {mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB")
        
        if category in ("all", "gpu"):
            # Try nvidia-smi for GPU info
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split(", ")
                    if len(parts) >= 5:
                        info_parts.append(f"GPU: {parts[0]} | {parts[2]}% load | {parts[1]}°C | VRAM: {parts[3]}MB / {parts[4]}MB")
                    else:
                        info_parts.append(f"GPU: {result.stdout.strip()}")
                else:
                    info_parts.append("GPU: nvidia-smi not available or no NVIDIA GPU detected")
            except FileNotFoundError:
                info_parts.append("GPU: nvidia-smi not found (no NVIDIA GPU or drivers not installed)")
            except Exception as e:
                info_parts.append(f"GPU: Error reading GPU info: {e}")
        
        if category in ("all", "disk"):
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info_parts.append(f"Disk {partition.device}: {usage.percent}% used | {usage.free // (1024**3)}GB free / {usage.total // (1024**3)}GB total")
                except PermissionError:
                    pass
        
        if category in ("all", "battery"):
            battery = psutil.sensors_battery()
            if battery:
                plug_status = "Plugged In" if battery.power_plugged else "On Battery"
                info_parts.append(f"Battery: {battery.percent}% | {plug_status}")
            else:
                info_parts.append("Battery: No battery detected (desktop PC)")
        
        if category in ("all", "processes"):
            # Top 5 by CPU usage
            procs = []
            for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                try:
                    procs.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            top5 = procs[:5]
            proc_str = ", ".join([f"{p['name']}({p.get('cpu_percent', 0):.1f}%)" for p in top5])
            info_parts.append(f"Top Processes by CPU: {proc_str}")
    
    except Exception as e:
        info_parts.append(f"Error reading system info: {e}")
    
    return "\n".join(info_parts) if info_parts else "Could not retrieve system information."

