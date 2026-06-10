"""
System commands and app launching logic for Mizune AI.
"""
import os
import subprocess
import webbrowser
import shlex
import time
import logging
import pyautogui

__all__ = ["launch_app", "close_app", "whatsapp_automation", "take_note", "search_memory", "COMMON_APPS"]


from .config import log_info

logger = logging.getLogger("mizune.commands")

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
    if exe.startswith("http") or exe.startswith("ms-") or "://" in exe:
        # Use built-in webbrowser to explicitly request a new tab instead of a new window
        webbrowser.open_new_tab(exe)
    else:
        try:
            safe_exe = shlex.quote(exe)
            subprocess.Popen(f"start {safe_exe}", shell=True)
            
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
    
    if contact.lower() in ["me", "myself", "self"]:
        target = None # Default to self
        contact = "yourself"
    else:
        # We pass the raw contact string directly to the headless bridge.
        # If it's pure digits, the bridge will use it as a number.
        # If it's letters (a name), the bridge will search the address book for that name.
        target = contact

    if message:
        log_info(f"[ACTION] Sending headless WhatsApp message to '{contact}'")
        success = send_whatsapp_message(message, target)
        if success:
            return f"Headless message successfully sent to {contact} on WhatsApp!"
        else:
            return "Failed to send message! The WhatsApp bridge is not connected."
    return f"Ready to message {contact}, Master! What should I say?"

def close_app(target: str):
    exe = COMMON_APPS.get(target, target)
    if exe.startswith("http") or exe.startswith("ms-"):
        return 

    if not exe.endswith(".exe"):
        exe += ".exe"

    log_info(f"[ACTION] Closing: {exe}")
    try:
        safe_exe = shlex.quote(exe)
        subprocess.Popen(f"taskkill /IM {safe_exe} /F", shell=True)
    except Exception as e:
        log_info(f"[ACTION] Failed to close '{exe}': {e}")

def execute_python_code(code: str) -> str:
    """Safely execute Python code generated by the LLM in a subprocess and return output."""
    import tempfile
    import os
    import sys
    
    # Security Filter
    dangerous_keywords = ["os.remove", "shutil.rmtree", "os.rmdir", "format", "del tree"]
    for keyword in dangerous_keywords:
        if keyword in code:
            return f"Error: Code blocked due to security filter. Contains dangerous keyword: {keyword}"
            
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
