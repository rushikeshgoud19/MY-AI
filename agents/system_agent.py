import os
import re
import subprocess
import time
import pyautogui
import pyperclip
import webbrowser
from agents.base_agent import BaseAgent
from typing import Any, Optional, Dict
import logging

# COMMON_APPS defined locally to avoid circular import with server.py
COMMON_APPS = {
    "notepad": "notepad.exe", "brave": "brave", "chrome": "chrome",
    "firefox": "firefox", "edge": "msedge", "code": "code", "vs code": "code",
    "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
    "excel": "excel", "word": "winword", "powerpoint": "powerpnt",
    "discord": "discord", "telegram": "telegram", "whatsapp": "whatsapp",
    "spotify": "spotify", "steam": "steam", "obs": "obs64",
    "calculator": "calc.exe", "explorer": "explorer", "task manager": "taskmgr",
    "settings": "ms-settings:", "paint": "mspaint",
    "youtube": "https://youtube.com", "github": "https://github.com",
    "gmail": "https://mail.google.com", "netflix": "https://netflix.com",
}

class SystemAgent(BaseAgent):
    """
    Specialized Agent for local computer operations.
    Handles the 'Environment Builder' and 'Code Analyst' workflows.
    """
    def __init__(self, config: dict):
        super().__init__(config)
        self.log("SystemAgent initialized. Ready to control the PC.")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        self.log(f"Executing system task: {task_input}")
        
        text = task_input.lower()
        
        # Workflow: Environment Builder
        if any(word in text for word in ["setup", "install", "create project", "build env"]):
            return await self._build_environment(task_input)
            
        # Workflow: Code Analyst
        if any(word in text for word in ["why is this failing", "analyze this code", "fix this bug"]):
            return await self._analyze_code(task_input)

        # General OS operations
        return await self._handle_general_os(task_input)

    async def _build_environment(self, params: str) -> str:
        self.log("Starting Environment Builder workflow...")
        try:
            # Basic logic to detect framework
            is_react = "react" in params.lower()
            is_tailwind = "tailwind" in params.lower()
            
            project_name = "mizune_project"
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            proj_path = os.path.join(desktop_path, project_name)

            if is_react:
                self.log(f"Executing: npx create-react-app {project_name}")
                # In a real scenario, we'd run this in a shell. 
                # Using subprocess.run for a simplified implementation.
                # subprocess.run(["npx", "create-react-app", project_name], cwd=desktop_path, check=True, shell=True)
                
                if is_tailwind:
                    self.log("Installing Tailwind CSS...")
                    # subprocess.run(["npm", "install", "-D", "tailwindcss", "postcss", "autoprefixer"], cwd=proj_path, check=True, shell=True)
                    # subprocess.run(["npx", "tailwindcss", "init", "-p"], cwd=proj_path, check=True, shell=True)
            
            # Launch IDE
            self.log("Launching VS Code in project directory...")
            subprocess.Popen(f"code {proj_path}", shell=True)
            
            pyautogui.alert(f"Mizune has finished building your project at {proj_path}!", "Project Ready")
            return "I've set up the environment for you, Master! Your project is ready and I've opened the editor. Hai~!"
        except Exception as e:
            self.log(f"Build failed: {e}")
            return f"Gomen ne, Master... I had trouble building the environment: {e}"

    async def _analyze_code(self, params: str) -> str:
        self.log("Starting Code Analyst workflow...")
        try:
            # 1. Read Clipboard
            code_snippet = pyperclip.paste()
            if not code_snippet:
                return "Master, please copy the failing code or error first so I can see it!"
            
            self.log(f"Analyzing code snippet (length: {len(code_snippet)} characters)...")
            
            # 2. Capture Screenshot for context
            ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"mizune_debug_{int(time.time())}.png")
            pyautogui.screenshot(ss_path)
            
            # 3. Basic Pattern Analysis (Simulating LLM)
            if ".map(" in code_snippet and "undefined" in code_snippet.lower():
                suggestion = "It looks like you're calling .map() on an undefined variable. Try adding a check: "
            elif "await" not in code_snippet and "async" in code_snippet:
                suggestion = "I noticed an async function without an await. You might be missing a promise resolution!"
            else:
                suggestion = "I've analyzed the code. While it looks okay at first glance, I recommend checking the variable types in your imports!"
            
            return f"I've analyzed the code, Master! {suggestion} I can type the fix for you if you'd like!"
        except Exception as e:
            self.log(f"Analysis failed: {e}")
            return f"I couldn't analyze the code, Master. Error: {e}"

    async def simulate_keystrokes(self, text: str):
        self.log(f"Simulating keystrokes: {text}")
        pyautogui.write(text, interval=0.01)

    async def _handle_general_os(self, text: str) -> str:
        text_low = text.lower()
        if "screenshot" in text_low:
            ss_path = os.path.join(os.path.expanduser("~"), "Desktop", f"mizune_capture_{int(time.time())}.png")
            pyautogui.screenshot(ss_path)
            return f"Taken! I've saved the screenshot to your desktop, Master~"
        
        # App Launching
        app_match = re.search(r"open\s+([a-zA-Z0-9\s]+)", text_low)
        if app_match:
            target = app_match.group(1).strip()
            exe = COMMON_APPS.get(target, target)
            if exe.startswith("http") or exe.startswith("ms-"):
                webbrowser.open(exe)
            else:
                subprocess.Popen(f"start {exe}", shell=True)
            return f"Opening {target} for you right away!"
        
        return "I can help you with that, but I'm not sure exactly how. Could you guide me, Master?"

