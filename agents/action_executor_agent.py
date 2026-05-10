"""
ActionExecutorAgent — THE HANDS of Operation Angel Inside Devil
================================================================
Takes planned steps from TaskPlannerAgent and EXECUTES them on the
actual desktop using pyautogui, keyboard, and webbrowser.

This is where Mizune physically interacts with the computer.
"""

import os
import time
import json
import webbrowser
import subprocess
import logging
from typing import Any, Optional, Dict, List, Tuple
from PIL import Image

import pyautogui
import keyboard as kb

from agents.base_agent import BaseAgent

# Safety: prevent pyautogui from moving too fast
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # Move mouse to corner to abort


class ActionExecutorAgent(BaseAgent):
    """
    Executes atomic actions on the desktop.
    
    Supported actions:
      - open_url: Launch URL in default browser
      - click: Click at coordinates (from VisionPerceptionAgent)
      - type: Type text into focused element
      - hotkey: Press keyboard shortcut
      - scroll: Scroll up/down
      - wait: Pause execution
      - screenshot: Capture current screen
      - copy_text: Copy text from screen via Ctrl+C
      - save_note: Append to notes file
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._screen_width, self._screen_height = pyautogui.size()
        self._last_screenshot: Optional[Image.Image] = None
        self._action_count = 0
        self._max_actions_per_session = 100  # Hard safety limit
        self.log(f"ActionExecutorAgent initialized. Screen: {self._screen_width}x{self._screen_height}")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        """
        Execute a single action step.
        task_input: JSON string of the step to execute
        context: Must contain "vision_elements" from VisionPerceptionAgent
        """
        try:
            step = json.loads(task_input) if isinstance(task_input, str) else task_input
        except json.JSONDecodeError:
            return {"success": False, "error": f"Invalid step JSON: {task_input}"}

        return await self.execute_step(step, context)

    async def execute_step(self, step: Dict, context: Optional[Dict] = None) -> Dict:
        """Execute a single planned step and return result."""
        action = step.get("action", "")
        params = step.get("params", {})
        description = step.get("description", action)

        # Safety check
        self._action_count += 1
        if self._action_count > self._max_actions_per_session:
            self.log("SAFETY: Max actions per session reached!")
            return {"success": False, "error": "Safety limit: too many actions in one session", "abort": True}

        self.log(f"Executing [{self._action_count}]: {action} — {description}")

        # Capture before-screenshot for verification
        before_screenshot = pyautogui.screenshot()

        try:
            result = await self._dispatch_action(action, params, context)
            result["before_screenshot"] = before_screenshot
            result["after_screenshot"] = pyautogui.screenshot()
            result["action"] = action
            result["description"] = description
            return result
        except pyautogui.FailSafeException:
            self.log("FAILSAFE TRIGGERED — Mouse moved to corner. Aborting!")
            return {"success": False, "error": "Failsafe triggered — user moved mouse to corner", "abort": True}
        except Exception as e:
            self.log(f"Action '{action}' failed: {e}")
            return {"success": False, "error": str(e), "action": action}

    async def _dispatch_action(self, action: str, params: Dict, context: Optional[Dict]) -> Dict:
        """Route to the appropriate action handler."""
        handlers = {
            "open_url": self._action_open_url,
            "click": self._action_click,
            "type": self._action_type,
            "hotkey": self._action_hotkey,
            "scroll": self._action_scroll,
            "wait": self._action_wait,
            "screenshot": self._action_screenshot,
            "copy_text": self._action_copy_text,
            "save_note": self._action_save_note,
            "verify": self._action_verify,
            "report": self._action_report,
            "ask_confirmation": self._action_ask_confirmation,
            "run_terminal_command": self._action_run_terminal_command,
            "write_file": self._action_write_file,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}"}

        return await handler(params, context)

    # ─── Action Handlers ──────────────────────────────────────────────────────

    async def _action_open_url(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Open a URL in the default browser."""
        url = params.get("url", "")
        if not url:
            return {"success": False, "error": "No URL provided"}

        if not url.startswith("http"):
            url = "https://" + url

        self.log(f"Opening URL: {url}")
        webbrowser.open(url)
        time.sleep(2)  # Wait for browser to open
        return {"success": True, "message": f"Opened {url}"}

    async def _action_click(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Click on a UI element by target description."""
        target = params.get("target", "")
        
        # If pixel coordinates are directly provided
        if "x" in params and "y" in params:
            x, y = int(params["x"]), int(params["y"])
        elif "position" in params:
            x = int(params["position"][0] / 100 * self._screen_width)
            y = int(params["position"][1] / 100 * self._screen_height)
        else:
            # Look up target in vision elements from context
            elements = context.get("vision_elements", []) if context else []
            element = self._find_element_by_target(target, elements)
            if not element:
                return {"success": False, "error": f"Cannot find element: '{target}'", "needs_vision": True}
            
            pixel_pos = element.get("pixel_position", element.get("position", [0, 0]))
            x, y = int(pixel_pos[0]), int(pixel_pos[1])

        # Clamp to screen bounds
        x = max(5, min(x, self._screen_width - 5))
        y = max(5, min(y, self._screen_height - 5))

        self.log(f"Clicking at ({x}, {y}) — target: '{target}'")
        
        # Smooth mouse movement for natural appearance
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.1)
        pyautogui.click(x, y)
        time.sleep(0.5)

        return {"success": True, "message": f"Clicked '{target}' at ({x}, {y})", "position": [x, y]}

    async def _action_type(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Type text into the currently focused element."""
        text = params.get("text", "")
        if not text:
            return {"success": False, "error": "No text to type"}

        # Optional: clear existing text first
        if params.get("clear_first", False):
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)

        self.log(f"Typing: '{text[:50]}{'...' if len(text) > 50 else ''}'")

        # Use pyautogui.write for ASCII, pyperclip for unicode
        try:
            # For complex text (unicode, special chars), use clipboard
            if any(ord(c) > 127 for c in text):
                import pyperclip
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.typewrite(text, interval=0.03)
        except Exception:
            # Fallback: use keyboard module
            kb.write(text)

        # Press Enter if requested
        if params.get("press_enter", False):
            time.sleep(0.2)
            pyautogui.press("enter")

        time.sleep(0.3)
        return {"success": True, "message": f"Typed '{text[:50]}'"}

    async def _action_hotkey(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Press a keyboard shortcut."""
        keys = params.get("keys", [])
        if not keys:
            return {"success": False, "error": "No keys specified"}

        self.log(f"Pressing hotkey: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)
        time.sleep(0.3)
        return {"success": True, "message": f"Pressed {'+'.join(keys)}"}

    async def _action_scroll(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Scroll the page."""
        direction = params.get("direction", "down")
        amount = int(params.get("amount", 3))

        clicks = amount if direction == "up" else -amount
        self.log(f"Scrolling {direction} by {amount}")
        pyautogui.scroll(clicks)
        time.sleep(0.5)
        return {"success": True, "message": f"Scrolled {direction} by {amount}"}

    async def _action_wait(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Wait for a specified duration."""
        seconds = float(params.get("seconds", 2))
        seconds = min(seconds, 30)  # Max wait: 30 seconds
        self.log(f"Waiting {seconds}s...")
        time.sleep(seconds)
        return {"success": True, "message": f"Waited {seconds}s"}

    async def _action_screenshot(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Capture and return current screenshot."""
        screenshot = pyautogui.screenshot()
        self._last_screenshot = screenshot
        return {"success": True, "message": "Screenshot captured", "screenshot": screenshot}

    async def _action_copy_text(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Select and copy text from screen."""
        target = params.get("target", "")
        
        # If target specified, click it first
        if target and context:
            elements = context.get("vision_elements", [])
            element = self._find_element_by_target(target, elements)
            if element:
                pos = element.get("pixel_position", [0, 0])
                pyautogui.click(int(pos[0]), int(pos[1]))
                time.sleep(0.2)

        # Select all and copy
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)

        try:
            import pyperclip
            text = pyperclip.paste()
            return {"success": True, "message": f"Copied text ({len(text)} chars)", "text": text}
        except Exception:
            return {"success": True, "message": "Copied to clipboard (could not read)"}

    async def _action_save_note(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Save content to notes file on desktop."""
        content = params.get("content", "")
        if not content:
            return {"success": False, "error": "No content to save"}

        char_name = self.config.get("character_name", "mizune").lower()
        notes_file = os.path.join(os.path.expanduser("~"), "Desktop", f"{char_name}_notes.txt")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {content}\n")

        self.log(f"Note saved: {content[:50]}")
        return {"success": True, "message": f"Saved note to {notes_file}"}

    async def _action_verify(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Verify an expected condition (delegated to VisionPerceptionAgent)."""
        expect = params.get("expect", "")
        return {"success": True, "needs_verification": True, "expect": expect}

    async def _action_report(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Generate a spoken report for the user."""
        message = params.get("message", "Task completed!")
        return {"success": True, "report": True, "message": message}

    async def _action_ask_confirmation(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Request user confirmation before proceeding."""
        question = params.get("question", "Should I proceed?")
        return {"success": True, "needs_confirmation": True, "question": question}

    async def _action_run_terminal_command(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Execute a command in PowerShell/CMD."""
        command = params.get("command", "")
        if not command:
            return {"success": False, "error": "No command provided"}

        self.log(f"Running command: {command}")
        try:
            # We run asynchronously and wait for a brief timeout to capture initial output
            process = subprocess.Popen(
                ["powershell", "-Command", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Give it up to 5 seconds to finish, or just let it run in background
            try:
                stdout, stderr = process.communicate(timeout=5)
                return {
                    "success": process.returncode == 0,
                    "message": "Command executed",
                    "stdout": stdout[:500],
                    "stderr": stderr[:500]
                }
            except subprocess.TimeoutExpired:
                # Let it keep running
                return {"success": True, "message": "Command started in background"}
        except Exception as e:
            return {"success": False, "error": f"Failed to run command: {e}"}

    async def _action_write_file(self, params: Dict, context: Optional[Dict]) -> Dict:
        """Create or edit a file directly."""
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return {"success": False, "error": "No path provided"}

        self.log(f"Writing file: {path}")
        try:
            # Expand ~ if used
            expanded_path = os.path.expanduser(path)
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(os.path.abspath(expanded_path)), exist_ok=True)
            
            with open(expanded_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            return {"success": True, "message": f"Successfully wrote to {expanded_path}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to write file: {e}"}

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _find_element_by_target(self, target: str, elements: List[Dict]) -> Optional[Dict]:
        """Find a UI element from vision results by fuzzy label match."""
        if not elements or not target:
            return None

        target_lower = target.lower()

        # Exact match
        for elem in elements:
            if elem.get("label", "").lower() == target_lower:
                return elem

        # Contains match
        for elem in elements:
            label = elem.get("label", "").lower()
            desc = elem.get("description", "").lower()
            if target_lower in label or target_lower in desc:
                return elem
            if label in target_lower or desc in target_lower:
                return elem

        # Word overlap match (at least 2 words match)
        target_words = set(target_lower.split())
        best_match = None
        best_score = 0
        for elem in elements:
            label_words = set(elem.get("label", "").lower().split())
            desc_words = set(elem.get("description", "").lower().split())
            all_words = label_words | desc_words
            overlap = len(target_words & all_words)
            if overlap > best_score and overlap >= 2:
                best_score = overlap
                best_match = elem

        return best_match

    def reset_session(self):
        """Reset action counter for a new session."""
        self._action_count = 0
        self._last_screenshot = None
        self.log("Session reset")
