"""
VisionPerceptionAgent — THE EYES of Operation Angel Inside Devil
================================================================
Captures the screen, sends to Gemini/Groq Vision, and returns a structured
map of all interactive UI elements with their approximate positions.

This is the foundation of autonomous computer-use: Mizune must SEE
before she can ACT.
"""

import os
import io
import re
import json
import time
import base64
import hashlib
import logging
from typing import Any, Optional, Dict, List, Tuple
from PIL import Image
import pyautogui

from agents.base_agent import BaseAgent

# Vision API imports — multi-provider fallback
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


class VisionPerceptionAgent(BaseAgent):
    """
    Autonomous vision system that perceives the desktop screen.
    
    Capabilities:
      - Capture full screen or region
      - Identify all interactive UI elements (buttons, inputs, links, tabs)
      - Return structured element map with approximate coordinates
      - Diff-based frame skipping to save API calls
      - Multi-provider fallback: Gemini Vision → Groq Vision
    """

    # Structured prompt for UI element extraction
    PERCEPTION_PROMPT = """You are a computer vision system analyzing a desktop screenshot.

TASK: Identify ALL interactive UI elements visible on the screen.

For EACH element, return a JSON object with:
- "label": Human-readable name (e.g., "Search button", "URL bar", "Close tab X")
- "type": One of: button, text_input, link, tab, dropdown, checkbox, radio, slider, menu_item, icon, image
- "position": [x_percent, y_percent] — approximate CENTER position as percentage of screen width/height (0-100)
- "description": Brief description of what this element does
- "interactable": true/false — whether it can be clicked/typed into right now

Also include:
- "page_context": What application/website is currently active
- "page_state": Brief description of current screen state

Return ONLY valid JSON in this exact format:
{
  "page_context": "Google Chrome - Amazon.in search results",
  "page_state": "Showing laptop search results, 48 items found",
  "elements": [
    {"label": "Search bar", "type": "text_input", "position": [50, 5], "description": "Amazon search input", "interactable": true},
    {"label": "Add to Cart", "type": "button", "position": [80, 45], "description": "Add first item to cart", "interactable": true}
  ]
}

IMPORTANT:
- Position is percentage-based: [0,0] = top-left, [100,100] = bottom-right
- Only include elements that are VISIBLE on screen right now
- Include the Windows taskbar elements if visible
- Be precise with positions — they will be used for mouse clicks
- Return valid JSON only, no markdown formatting"""

    # Prompt for targeted element finding
    FIND_ELEMENT_PROMPT = """You are a computer vision system. I need you to find a SPECIFIC element on this screen.

TARGET ELEMENT: "{target}"

Look at the screenshot and find the element that best matches this description.

Return ONLY valid JSON:
{{
  "found": true/false,
  "label": "exact element name",
  "position": [x_percent, y_percent],
  "confidence": 0.0-1.0,
  "alternatives": [
    {{"label": "similar element", "position": [x, y], "reason": "why this might be what you want"}}
  ]
}}

Position is percentage of screen: [0,0]=top-left, [100,100]=bottom-right.
Return valid JSON only."""

    # Prompt for verifying action success
    VERIFY_PROMPT = """Compare these two screenshots (BEFORE and AFTER an action).

The intended action was: "{action}"

Analyze what changed between the two screenshots and determine:
1. Did the intended action succeed?
2. What changed on the screen?
3. Is there an error message or unexpected popup?
4. What should be done next?

Return ONLY valid JSON:
{{
  "success": true/false,
  "changes": "description of what changed",
  "error_detected": true/false,
  "error_message": "text of any error if visible",
  "suggestion": "what to do next",
  "new_page_context": "what app/page is now showing"
}}"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._last_frame_hash: Optional[str] = None
        self._last_elements: List[Dict] = []
        self._screen_width, self._screen_height = pyautogui.size()
        self._gemini_client = None
        self._groq_client = None
        self._setup_clients()
        self.log(f"VisionPerceptionAgent initialized. Screen: {self._screen_width}x{self._screen_height}")

    def _setup_clients(self):
        """Initialize vision API clients."""
        gemini_key = self.config.get("gemini_api_key", "")
        groq_key = self.config.get("groq_api_key", "")

        if HAS_GEMINI and gemini_key:
            try:
                self._gemini_client = genai.Client(api_key=gemini_key)
                self.log("Gemini Vision client ready")
            except Exception as e:
                self.log(f"Gemini Vision init failed: {e}")

        if HAS_GROQ and groq_key:
            try:
                self._groq_client = Groq(api_key=groq_key)
                self.log("Groq Vision client ready")
            except Exception as e:
                self.log(f"Groq Vision init failed: {e}")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        """
        Main entry point. Supports multiple actions:
          - "perceive": Full screen scan → return all UI elements
          - "find:<target>": Find a specific element on screen
          - "verify:<action>": Compare before/after screenshots
        """
        if task_input.startswith("find:"):
            target = task_input[5:].strip()
            return await self.find_element(target)
        elif task_input.startswith("verify:"):
            action = task_input[7:].strip()
            before = context.get("before_screenshot") if context else None
            after = context.get("after_screenshot") if context else None
            return await self.verify_action(action, before, after)
        else:
            return await self.perceive_screen()

    # ─── Core Perception ─────────────────────────────────────────────────────

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Capture full screen or a specific region."""
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        return screenshot

    def _image_to_base64(self, image: Image.Image, max_size: int = 1280) -> str:
        """Convert PIL Image to base64, resized for API efficiency."""
        # Resize to save API tokens while keeping enough detail
        w, h = image.size
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _image_hash(self, image: Image.Image) -> str:
        """Generate a perceptual hash for frame diffing."""
        # Downsample to 16x16 grayscale for fast comparison
        small = image.resize((16, 16)).convert("L")
        pixels = list(small.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p > avg else "0" for p in pixels)
        return hashlib.md5(bits.encode()).hexdigest()

    def _has_screen_changed(self, image: Image.Image, threshold: float = 0.15) -> bool:
        """Check if screen content changed significantly since last capture."""
        current_hash = self._image_hash(image)
        if self._last_frame_hash is None:
            self._last_frame_hash = current_hash
            return True
        
        # Simple: if hash is different, screen changed
        changed = current_hash != self._last_frame_hash
        self._last_frame_hash = current_hash
        return changed

    async def perceive_screen(self, force: bool = False) -> Dict:
        """
        Capture screen and identify all UI elements.
        Returns cached result if screen hasn't changed (unless force=True).
        """
        screenshot = self.capture_screen()

        # Skip if screen hasn't changed (saves API calls)
        if not force and not self._has_screen_changed(screenshot):
            self.log("Screen unchanged — returning cached elements")
            return {
                "cached": True,
                "page_context": self._last_elements.get("page_context", "unknown") if isinstance(self._last_elements, dict) else "unknown",
                "elements": self._last_elements.get("elements", []) if isinstance(self._last_elements, dict) else self._last_elements,
            }

        self.log("Screen changed — running vision perception...")
        result = await self._analyze_screenshot(screenshot, self.PERCEPTION_PROMPT)

        if result:
            # Convert percentage positions to absolute pixel coordinates
            if "elements" in result:
                for elem in result["elements"]:
                    if "position" in elem:
                        px = elem["position"][0]
                        py = elem["position"][1]
                        elem["pixel_position"] = [
                            int(px / 100 * self._screen_width),
                            int(py / 100 * self._screen_height),
                        ]
            self._last_elements = result

        return result or {"error": "Vision perception failed", "elements": []}

    async def find_element(self, target: str) -> Dict:
        """Find a specific UI element on screen by description."""
        self.log(f"Finding element: '{target}'")
        screenshot = self.capture_screen()
        prompt = self.FIND_ELEMENT_PROMPT.format(target=target)
        result = await self._analyze_screenshot(screenshot, prompt)

        if result and result.get("found"):
            pos = result.get("position", [50, 50])
            result["pixel_position"] = [
                int(pos[0] / 100 * self._screen_width),
                int(pos[1] / 100 * self._screen_height),
            ]
            self.log(f"Found '{target}' at pixel {result['pixel_position']}")
        else:
            self.log(f"Element '{target}' NOT found on screen")

        return result or {"found": False, "reason": "Vision API failed"}

    async def verify_action(self, action: str,
                            before: Optional[Image.Image] = None,
                            after: Optional[Image.Image] = None) -> Dict:
        """Compare before/after screenshots to verify an action succeeded."""
        if after is None:
            after = self.capture_screen()
        if before is None:
            self.log("No 'before' screenshot — capturing current as 'after' only")
            return {"success": None, "reason": "No before screenshot for comparison"}

        self.log(f"Verifying action: '{action}'")
        prompt = self.VERIFY_PROMPT.format(action=action)

        # Send both images to vision API
        result = await self._analyze_dual_screenshots(before, after, prompt)
        return result or {"success": None, "reason": "Verification API failed"}

    # ─── Vision API Calls ─────────────────────────────────────────────────────

    async def _analyze_screenshot(self, image: Image.Image, prompt: str) -> Optional[Dict]:
        """Send screenshot to vision API and parse JSON response."""
        # Try Gemini first, then Groq
        result = None

        if self._gemini_client:
            result = await self._gemini_vision(image, prompt)

        if result is None and self._groq_client:
            result = await self._groq_vision(image, prompt)

        return result

    async def _analyze_dual_screenshots(self, before: Image.Image, after: Image.Image, prompt: str) -> Optional[Dict]:
        """Send two screenshots for comparison analysis."""
        if self._gemini_client:
            return await self._gemini_vision_dual(before, after, prompt)
        if self._groq_client:
            # Groq doesn't support multi-image well — combine into one
            combined = self._combine_images(before, after)
            return await self._groq_vision(combined, prompt)
        return None

    async def _gemini_vision(self, image: Image.Image, prompt: str) -> Optional[Dict]:
        """Call Gemini Vision API."""
        try:
            b64 = self._image_to_base64(image)
            model = self.config.get("gemini_model", "gemini-2.0-flash")

            from google.genai import types
            safety_settings = [
                types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.BLOCK_NONE)
                for c in [
                    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                ]
            ]

            response = self._gemini_client.models.generate_content(
                model=model,
                contents=[
                    {
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                        ]
                    }
                ],
                config=types.GenerateContentConfig(safety_settings=safety_settings)
            )
            return self._parse_json_response(response.text)
        except Exception as e:
            self.log(f"Gemini Vision error: {e}")
            return None

    async def _gemini_vision_dual(self, before: Image.Image, after: Image.Image, prompt: str) -> Optional[Dict]:
        """Call Gemini Vision with two images (before/after comparison)."""
        try:
            b64_before = self._image_to_base64(before)
            b64_after = self._image_to_base64(after)
            model = self.config.get("gemini_model", "gemini-2.0-flash")

            from google.genai import types
            safety_settings = [
                types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.BLOCK_NONE)
                for c in [
                    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                ]
            ]

            response = self._gemini_client.models.generate_content(
                model=model,
                contents=[
                    {
                        "parts": [
                            {"text": prompt},
                            {"text": "BEFORE screenshot:"},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_before}},
                            {"text": "AFTER screenshot:"},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_after}},
                        ]
                    }
                ],
                config=types.GenerateContentConfig(safety_settings=safety_settings)
            )
            return self._parse_json_response(response.text)
        except Exception as e:
            self.log(f"Gemini dual-vision error: {e}")
            return None

    async def _groq_vision(self, image: Image.Image, prompt: str) -> Optional[Dict]:
        """Call Groq Vision API as fallback."""
        try:
            b64 = self._image_to_base64(image)
            response = self._groq_client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=2048,
                temperature=0.1,
            )
            return self._parse_json_response(response.choices[0].message.content)
        except Exception as e:
            self.log(f"Groq Vision error: {e}")
            return None

    def _combine_images(self, img1: Image.Image, img2: Image.Image) -> Image.Image:
        """Combine two images side-by-side for single-image APIs."""
        w1, h1 = img1.size
        w2, h2 = img2.size
        combined = Image.new("RGB", (w1 + w2 + 20, max(h1, h2)), (30, 30, 30))
        combined.paste(img1, (0, 0))
        combined.paste(img2, (w1 + 20, 0))
        return combined

    def _parse_json_response(self, raw_text: str) -> Optional[Dict]:
        """Extract and parse JSON from LLM response text."""
        if not raw_text:
            return None
        # Strip markdown code fences
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON object from mixed text
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            self.log(f"Failed to parse JSON from vision response: {cleaned[:200]}...")
            return None

    # ─── Utility ──────────────────────────────────────────────────────────────

    def get_element_at_label(self, elements: List[Dict], label: str) -> Optional[Dict]:
        """Find an element by label (fuzzy match)."""
        label_lower = label.lower()
        # Exact match first
        for elem in elements:
            if elem.get("label", "").lower() == label_lower:
                return elem
        # Partial match
        for elem in elements:
            if label_lower in elem.get("label", "").lower() or \
               label_lower in elem.get("description", "").lower():
                return elem
        return None

    def refresh_screen_size(self):
        """Update cached screen dimensions (call after resolution change)."""
        self._screen_width, self._screen_height = pyautogui.size()
        self.log(f"Screen size refreshed: {self._screen_width}x{self._screen_height}")
