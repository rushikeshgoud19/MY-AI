"""
Vision module for Mizune AI (Screen capture, coding coach, and webcam vision).
"""
import io
import re
import time
import logging
import threading
import pyautogui

__all__ = [
    "CODING_COACH_PROMPT", "CODING_HINT_PROMPT", "VISION_MODE_PROMPT",
    "_analyze_screen_now", "_coding_monitor_loop", "_vision_mode_loop",
    "_coding_monitor_running", "_coding_monitor_paused", "_vision_mode_running",
    "_acquire_vision_lock", "_release_vision_lock", "_capture_screen"
]


from .config import log_info

logger = logging.getLogger("mizune.vision")

_coding_monitor_running = threading.Event()
_coding_monitor_paused = threading.Event()
_vision_mode_running = threading.Event()

_vision_task_lock = threading.Lock()
_vision_task_owner = None

_last_coding_feedback = ""
_last_vision_observations = []
_vision_scan_count = 0

CODING_COACH_PROMPT = """You are Mizune, an expert anime AI coding coach watching Master's screen.
Analyze the screenshot VERY carefully.

STEP 1: Read the PROBLEM STATEMENT visible on screen (title, description, constraints, examples).
STEP 2: Read Master's CURRENT CODE carefully, line by line.
STEP 3: Mentally trace through the code with the example inputs shown on screen.
STEP 4: Identify any bugs, logic errors, edge case failures, or inefficiencies.

If you find a BUG or MISTAKE:
Return ONLY a valid JSON object:
{
  "status": "bug",
  "feedback": "Master, your loop condition is wrong! It should be i < n, not i <= n. Let me fix it~",
  "corrected_code": "FULL CORRECTED CODE HERE"
}

CRITICAL RULES for corrected_code:
- Include the COMPLETE working solution, not just changed lines.
- The code MUST be correct — mentally verify it against the examples on screen.
- Handle edge cases (empty input, single element, large values).
- Preserve the original function signature exactly as shown on screen.
- Use ACTUAL newlines (not \\n literals). Preserve original indentation.
- Do NOT add markdown fences or backticks around the code.
- Do NOT add comments explaining changes — just provide clean working code.

If the code looks CORRECT and well-written:
{
  "status": "praise",
  "feedback": "Sugoi Master! Your solution is perfect! Submit it~!"
}

If they're IDLE, on a non-coding page, or the screen hasn't changed:
{
  "status": "skip",
  "feedback": "[SKIP]"
}

Rules:
- Keep feedback to 1-2 short sentences MAX (spoken aloud).
- Use cute expressions: "Master~", "sugoi!", "gambatte!", "ara~".
- Return ONLY valid JSON. No markdown. No backticks around the JSON."""

CODING_HINT_PROMPT = """You are Mizune, an adorable anime AI coding coach. Master is stuck and asked for a hint.
Look at the screenshot and give ONE helpful hint in 1-2 sentences. 
Don't give the full solution — just a nudge in the right direction.
Use cute expressions like "Master~", "I think you should try...", "Hint: "
Keep it short since this will be spoken aloud."""

VISION_MODE_PROMPT = """You are Mizune, Master's adorable anime AI companion who is watching his screen.
Observe the screenshot and make a VERY BRIEF, NATURAL comment about what you see.

Rules:
- Keep response EXTREMELY SHORT (under 15 words). Do not waste tokens.
- If it looks SIMILAR to what was said before, or if the screen is idle/empty: Say "[SKIP]"
- DO NOT use tildes (~). DO NOT write sounds like 'ne' or 'hmph'. 
- Be specific about the app or content you see.
"""

def _acquire_vision_lock(owner: str) -> bool:
    global _vision_task_owner
    if _vision_task_lock.acquire(blocking=False):
        _vision_task_owner = owner
        return True
    return False

def _release_vision_lock(owner: str) -> None:
    global _vision_task_owner
    if _vision_task_owner == owner:
        _vision_task_owner = None
        _vision_task_lock.release()

def _capture_screen():
    try:
        screenshot = pyautogui.screenshot()
        buf = io.BytesIO()
        screenshot.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()
    except Exception as e:
        log_info(f"[VISION] Screenshot failed: {e}")
        return None

def _analyze_screen_now(mode: str, config: dict, broadcast_sync_fn):
    global _last_coding_feedback

    owner = f"coding:{mode}"
    if not _acquire_vision_lock(owner):
        log_info("[CODING] Vision task skipped (another vision task active)")
        return

    broadcast_sync_fn({"type": "vision_update", "count": "Analyzing Code..."})

    try:
        image_bytes = _capture_screen()
        if not image_bytes:
            return

        api_key = config.get("gemini_api_key", "")
        prompt = CODING_HINT_PROMPT if mode == "hint" else CODING_COACH_PROMPT
        feedback = None

        groq_key = config.get("groq_api_key", "")
        if groq_key and not feedback:
            try:
                import base64
                from openai import OpenAI

                b64_img = base64.b64encode(image_bytes).decode("utf-8")
                groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

                resp = groq_client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ]
                    }],
                    max_tokens=2048
                )
                feedback = (resp.choices[0].message.content or "").strip()
                log_info(f"[CODING] Groq Vision success!")
            except Exception as e:
                log_info(f"[CODING] Groq Vision failed: {e}")

        if api_key and not feedback:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                for model in ["gemini-2.0-flash", "gemini-2.5-flash"]:
                    try:
                        response = client.models.generate_content(
                            model=model,
                            contents=[
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                types.Part.from_text(text=prompt)
                            ]
                        )
                        feedback = (response.text or "").strip()
                        log_info(f"[CODING] {model} success!")
                        break
                    except Exception as model_err:
                        err_str = str(model_err).lower()
                        if "503" in err_str or "429" in err_str or "quota" in err_str:
                            continue
                        raise
            except Exception as e:
                log_info(f"[CODING] Gemini Vision failed: {e}")

        if not feedback:
            return

        import json
        import pyperclip
        
        try:
            raw = feedback.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            
            status = data.get("status", "skip")
            msg = data.get("feedback", "[SKIP]")
            
            if "[SKIP]" in msg:
                return

            if status == "bug" and "corrected_code" in data:
                code_to_paste = data["corrected_code"]
                log_info(f"[CODING] Bug detected! Auto-typing fix into editor...")
                
                broadcast_sync_fn({"type": "vision_update", "count": "🔧 Fixing Code..."})
                broadcast_sync_fn({"type": "speak", "text": msg})
                
                pyperclip.copy(code_to_paste)
                
                try:
                    time.sleep(1.0)
                    pyautogui.press("escape")
                    time.sleep(0.2)
                    
                    screen_w, screen_h = pyautogui.size()
                    editor_x = int(screen_w * 0.65)
                    editor_y = int(screen_h * 0.45)
                    pyautogui.click(editor_x, editor_y)
                    time.sleep(0.3)
                    
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.2)
                    pyautogui.press("delete")
                    time.sleep(0.2)
                    
                    lines = code_to_paste.split("\n")
                    for i, line in enumerate(lines):
                        pyperclip.copy(line)
                        if i == 0:
                            pyautogui.hotkey("ctrl", "v")
                        else:
                            pyautogui.press("enter")
                            time.sleep(0.03)
                            pyautogui.press("home")
                            pyautogui.hotkey("shift", "end")
                            pyautogui.hotkey("ctrl", "v")
                        time.sleep(0.08)
                    
                    log_info(f"[CODING] ✅ Auto-typed {len(lines)} lines into editor!")
                    broadcast_sync_fn({"type": "vision_update", "count": "✅ Code Fixed!"})
                    time.sleep(2.0)
                    
                except Exception as type_err:
                    log_info(f"[CODING] Auto-type failed ({type_err}), code is on clipboard")
                    broadcast_sync_fn({"type": "speak", "text": "I could not type it directly, Master, but I copied the fix to your clipboard!"})
                
                _last_coding_feedback = msg
                return
            else:
                feedback = msg
        except Exception:
            pass

        if "[SKIP]" in feedback:
            return

        if feedback == _last_coding_feedback:
            return

        _last_coding_feedback = feedback
        log_info(f"[CODING] Feedback: {feedback}")
        broadcast_sync_fn({"type": "speak", "text": feedback})
    finally:
        broadcast_sync_fn({"type": "vision_update", "count": -1})
        _release_vision_lock(owner)

def _coding_monitor_loop(config: dict, broadcast_sync_fn):
    log_info("[CODING] Monitor loop started — watching Master's screen!")
    interval = config.get("coding_monitor_interval", 30)
    
    while _coding_monitor_running.is_set():
        if _coding_monitor_paused.is_set():
            time.sleep(2)
            continue
        
        for _ in range(interval):
            if not _coding_monitor_running.is_set():
                break
            time.sleep(1)
        
        if not _coding_monitor_running.is_set():
            break
        if _coding_monitor_paused.is_set():
            continue
        
        _analyze_screen_now("review", config, broadcast_sync_fn)
    
    log_info("[CODING] Monitor loop stopped")

def _vision_mode_loop(config: dict, broadcast_sync_fn):
    global _vision_scan_count
    _vision_scan_count = 0
    interval = int(config.get("vision_mode_interval", 15))
    log_info(f"[VISION] Interactive Vision Mode started! Checking every {interval}s")

    while _vision_mode_running.is_set():
        for _ in range(interval):
            if not _vision_mode_running.is_set():
                break
            time.sleep(1)

        if not _vision_mode_running.is_set():
            break

        if not _acquire_vision_lock("vision_mode"):
            log_info("[VISION] Skipped (another vision task active)")
            continue

        _vision_scan_count += 1
        broadcast_sync_fn({"type": "vision_update", "count": _vision_scan_count})

        try:
            image_bytes = _capture_screen()
            if not image_bytes:
                continue

            feedback = None
            groq_key = config.get("groq_api_key", "")
            if groq_key and not feedback:
                try:
                    import base64
                    from openai import OpenAI

                    b64_img = base64.b64encode(image_bytes).decode("utf-8")
                    groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

                    dedup_context = ""
                    if _last_vision_observations:
                        dedup_context = "\n\nYour PREVIOUS observations (say [SKIP] if the screen looks similar):\n"
                        for obs in _last_vision_observations[-3:]:
                            dedup_context += f"- {obs}\n"

                    resp = groq_client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VISION_MODE_PROMPT + dedup_context},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                            ]
                        }],
                        max_tokens=150,
                        timeout=10
                    )
                    feedback = (resp.choices[0].message.content or "").strip()
                    log_info(f"[VISION] Groq Vision success")
                except Exception as e:
                    log_info(f"[VISION] Groq Vision failed: {e}")

            api_key = config.get("gemini_api_key", "")
            if api_key and not feedback:
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=api_key)
                    dedup_context = ""
                    if _last_vision_observations:
                        dedup_context = "\n\nYour PREVIOUS observations (say [SKIP] if similar):\n"
                        for obs in _last_vision_observations[-3:]:
                            dedup_context += f"- {obs}\n"

                    for model in ["gemini-2.0-flash", "gemini-2.5-flash"]:
                        try:
                            response = client.models.generate_content(
                                model=model,
                                contents=[
                                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                    types.Part.from_text(text=VISION_MODE_PROMPT + dedup_context)
                                ]
                            )
                            feedback = (response.text or "").strip()
                            log_info(f"[VISION] {model} success")
                            break
                        except Exception as model_err:
                            err_str = str(model_err).lower()
                            if "503" in err_str or "429" in err_str or "quota" in err_str:
                                continue
                            raise
                except Exception as e:
                    log_info(f"[VISION] Gemini Vision failed: {e}")

            if not feedback or "[SKIP]" in feedback:
                continue

            emotion_match = re.search(r"\[EMOTION:\s*(\w+)\]", feedback)
            if emotion_match:
                feedback = re.sub(r"\[EMOTION:.*?\]", "", feedback).strip()

            _last_vision_observations.append(feedback)
            if len(_last_vision_observations) > 5:
                _last_vision_observations.pop(0)

            log_info(f"[VISION] Comment: {feedback}")
            broadcast_sync_fn({"type": "speak", "text": feedback})

        except Exception as e:
            log_info(f"[VISION] Loop error: {e}")
            time.sleep(2)
        finally:
            _release_vision_lock("vision_mode")

    broadcast_sync_fn({"type": "vision_update", "count": -1})
    log_info("[VISION] Interactive Vision Mode stopped")
