"""
Core command processor for Mizune AI.
Stitches together Vision, AI, Commands, and Context.
"""
import os
import re
import time
import subprocess
import asyncio
import threading
import logging
import shlex

from server.config import log_info
from server.commands import COMMON_APPS, launch_app, close_app, whatsapp_automation, take_note
from server.ai import get_ai_response
from server.agents import mizune_manager, save_turn
from server.memory import memory
from server.memory_tree import memory_tree_db
from server.evolution import evolution_engine
from server.vision import _acquire_vision_lock, _release_vision_lock, _analyze_screen_now, _vision_mode_running, _coding_monitor_running, _coding_monitor_paused, _vision_mode_loop, _coding_monitor_loop, _capture_screen


logger = logging.getLogger("mizune.processor")

# Session Store
from server.session_store import SessionStore
global_session_store = SessionStore()

from server.scheduler import CronManager
global_cron_manager = CronManager()

def _scheduler_callback(task_description):
    from server.websocket import ws_manager
    from server.config import load_config
    config = load_config()
    log_info(f"[SCHEDULER WAKEUP] Processing task: {task_description}")
    prompt = f"[SYSTEM ALERT: A scheduled task has triggered!] Task description: {task_description}. Please execute this task now and speak your response."
    threading.Thread(target=process_command, args=(prompt, config, ws_manager.broadcast_sync, 'main'), daemon=True).start()

global_cron_manager.start(task_callback=_scheduler_callback)

_processing_lock = threading.Lock()

def process_command(text: str, config: dict, broadcast_sync_fn, session_id: str = 'main') -> str:
    """Wrapper to prevent ghost inputs from cloning Mizune's brain."""
    if not _processing_lock.acquire(blocking=False):
        log_info(f"[PROCESSOR] Ignoring overlapping input '{text}' (Mizune is busy).")
        return None
    try:
        return _process_command_internal(text, config, broadcast_sync_fn, session_id)
    finally:
        _processing_lock.release()

def _process_command_internal(text: str, config: dict, broadcast_sync_fn, session_id: str = 'main') -> str:
    # Initialize session and load emotion state
    platform = "whatsapp" if "whatsapp:" in session_id else "desktop"
    global_session_store.start_or_resume_session(session_id, platform=platform)
    
    from server.emotion_engine import global_emotion_state
    meta = global_session_store.get_session_metadata(session_id)
    if "emotion" in meta:
        state_dict = meta["emotion"]
        for k, v in state_dict.items():
            if hasattr(global_emotion_state, k):
                setattr(global_emotion_state, k, v)
    
    from server.security import global_rate_limiter, SecurityScanner
    if not global_rate_limiter.check_limit():
        log_info("[SECURITY] Rate limit exceeded. Dropping request.")
        return "[EMOTION: sad] My brain is feeling a little overwhelmed, Master! Please slow down~"
        
    log_info(f"[COMMAND] Processing: '{text}'")
    
    if text.strip() == "[SKIP]":
        log_info("[PROCESSOR] Received [SKIP] signal. Ignoring.")
        return None

    lower_text = text.lower().strip()
    wake_words = config.get("wake_words", [])
    for wake in wake_words:
        if lower_text.startswith(wake):
            text = text[len(wake):].strip()
            lower_text = text.lower().strip()
            break
            
    # ── CRAZY COMMANDS ──
    if lower_text == "/nuke_cache":
        log_info("[COMMAND] Executing /nuke_cache...")
        try:
            import gc
            gc.collect()
            # Clear TTS cache folder
            import shutil
            tts_cache = "tts_cache"
            if os.path.exists(tts_cache):
                shutil.rmtree(tts_cache)
                os.makedirs(tts_cache)
            log_info("[COMMAND] RAM garbage collection complete and TTS cache wiped.")
            return "Cache nuked successfully! RAM freed up."
        except Exception as e:
            return f"Failed to nuke cache: {e}"
            
    if lower_text == "/deep_evolve":
        log_info("[COMMAND] Master invoked /deep_evolve. Spawning deep research thread...")
        def trigger_evolution():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(evolution_engine.skill_evolver.evolve())
            
        threading.Thread(target=trigger_evolution, daemon=True).start()
        return "Initiating Deep Evolution protocol in the background. Check the Kernel Stream for logs."

    # Security check using Camera Agent (TEMPORARILY DISABLED)
    camera_agent = mizune_manager.workers.get("camera")
    is_master = True
    # if camera_agent:
    #     is_master = camera_agent.verify_master_now()
    #     if not is_master:
    #         camera_agent.is_master_present = False
    #         log_info("[SECURITY] Stranger detected — restricting system actions.")

    # ── Screen Vision ──
    _is_screen_request = re.search(
        r"\b(look at my screen|look at (the|my) screen|what('s| is) on (my |the )?screen|"
        r"what am i (doing|looking at|working on)|what am i doing on (my )?(pc|computer|screen|monitor)|"
        r"describe my screen|what's on my monitor|what is on my monitor|check my screen|"
        r"see my screen|guess what i am doing|tell me what i am doing|"
        r"see what('s| is) on (my )?screen|what('s| is) happening on (my )?screen)\b", lower_text)
    
    if _is_screen_request:
        if not _acquire_vision_lock("screen_vision"):
            return "I'm already processing another vision task, Master~ Try again in a moment!"

        try:
            log_info("[SCREEN VISION] Taking a screenshot for analysis...")
            broadcast_sync_fn({"type": "status", "text": "Looking at your screen..."})
            
            image_bytes = _capture_screen()
            if not image_bytes:
                return "[EMOTION: sad] I couldn't capture your screen, Master!"
                
            screen_prompt = f"""You are Mizune, Master's adorable anime AI companion.
Master just asked: "{text}"
You are looking at Master's computer screen RIGHT NOW via a screenshot.

Describe what you see in detail:
- What application is currently open?
- What is Master working on, reading, or watching?
- If there is code, what language is it and what does it do?
- If there is a game or video, what is happening?

Be observant and detailed but keep it natural and in character.
Use cute expressions. Keep it to 2-3 sentences max since this will be spoken aloud.
Keep it natural, no emotion tags needed."""

            groq_key = config.get("groq_api_key", "")
            if groq_key:
                try:
                    import base64
                    from openai import OpenAI
                    b64_img = base64.b64encode(image_bytes).decode("utf-8")
                    groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                    resp = groq_client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": screen_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ]}],
                        max_tokens=300
                    )
                    result = (resp.choices[0].message.content or "").strip()
                    if result:
                        log_info(f"[SCREEN VISION] Groq success!")
                        global_session_store.add_message(session_id, "user", text)
                        global_session_store.add_message(session_id, "model", result)
                        text = f"[SYSTEM VISION Context: '{result}']. Fulfill this request: {text}"
                except Exception as e:
                    log_info(f"[SCREEN VISION] Groq failed: {e}")

            # Fallback Gemini Vision
            api_key = config.get("gemini_api_key", "")
            if api_key:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            types.Part.from_text(text=screen_prompt)
                        ]
                    )
                    result = (response.text or "").strip()
                    if result:
                        global_session_store.add_message(session_id, "user", text)
                        global_session_store.add_message(session_id, "model", result)
                        text = f"[SYSTEM VISION Context: '{result}']. Fulfill this request: {text}"
                except Exception as e:
                    log_info(f"[SCREEN VISION] Gemini failed: {e}")
                    
            if not text.startswith("[SYSTEM"):
                return "[EMOTION: sad] I couldn't see your screen properly, Master! My vision might be blurry right now."
        finally:
            _release_vision_lock("screen_vision")

    # ── Camera Vision ──
    if re.search(r"\b(what do you see|what can you see|look at me|look at the camera|look through.*camera|how do i look|"
                 r"what('s| is) on my camera|whats going on my camera|"
                 r"describe what you see|what's around me|what's in front of you|"
                 r"who is here|who is in front|describe my room|look around|"
                 r"see me|can you see me|look at my face|"
                 r"what am i (eating|drinking|holding|wearing|doing)|"
                 r"(how\s+many\s+)?calories\s+(in\s+)?(this|that|food|meal)|"
                 r"what('s| is) in (my|the) (hand|cup|bottle|glass|mug|plate|drink)|"
                 r"tell me what.*(?:drink|hold|eat|wear|look|see))\b", lower_text):
        cam = mizune_manager.workers.get("camera")
        if cam:
            if not _acquire_vision_lock("camera_vision"):
                return "I'm already processing another vision task, Master~ Try again in a moment!"
            try:
                frame_bytes = cam.get_current_frame()
                if frame_bytes:
                    log_info("[CAMERA VISION] Processing camera view...")
                    broadcast_sync_fn({"type": "status", "text": "Looking through camera..."})
                    camera_prompt = f"""You are Mizune, Master's adorable anime AI companion. 
Master just asked: "{text}"
You are looking at Master through your webcam camera RIGHT NOW. Describe what you see."""
                    # Simplified for space: Gemini check
                    api_key = config.get("gemini_api_key", "")
                    if api_key:
                        from google import genai
                        from google.genai import types
                        client = genai.Client(api_key=api_key)
                        try:
                            response = client.models.generate_content(
                                model="gemini-2.0-flash",
                                contents=[
                                    types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                                    types.Part.from_text(text=camera_prompt)
                                ]
                            )
                            result = (response.text or "").strip()
                            if result:
                                global_session_store.add_message(session_id, "user", text)
                                global_session_store.add_message(session_id, "model", result)
                                text = f"[SYSTEM CAMERA Context: '{result}']. Fulfill this request: {text}"
                        except Exception as e:
                            log_info(f"[CAMERA VISION] Gemini failed: {e}")
                    if not text.startswith("[SYSTEM"):
                        text = f"[SYSTEM CAMERA ERROR]. Fulfill this request: {text}"
                else:
                    text = f"[SYSTEM CAMERA ERROR: Cannot see anything]. Fulfill this request: {text}"
            finally:
                _release_vision_lock("camera_vision")
        else:
            text = f"[SYSTEM CAMERA ERROR: No camera connected]. Fulfill this request: {text}"

    # ── Mode Toggles ──
    if re.search(r"\b(watch me|interactive mode|companion mode|vision mode|start watching)\b", lower_text):
        if not _vision_mode_running.is_set():
            _vision_mode_running.set()
            mizune_manager.current_mode = "vision"
            broadcast_sync_fn({"type": "mode", "mode": "vision"})
            threading.Thread(target=_vision_mode_loop, args=(config, broadcast_sync_fn), daemon=True).start()
            return "Hai~! I'm watching your screen now, Master! I'll comment on what I see~ Say 'stop watching' when you want privacy!"
        return "I'm already watching, Master~!"

    if re.search(r"\b(stop watching|privacy mode|stop vision|exit vision|stop interactive)\b", lower_text):
        if _vision_mode_running.is_set():
            _vision_mode_running.clear()
            mizune_manager.current_mode = "conversation"
            broadcast_sync_fn({"type": "mode", "mode": "conversation"})
            return "Okay Master, I've stopped watching your screen~ Your privacy is safe with me!"
        return "I wasn't watching, Master~"

    # ── Slash Commands ──
    if lower_text.startswith("/evolve"):
        evolution_engine.paused = False
        # Manually trigger evolution asynchronously (bypass AFK and cooldown, but enforce budget)
        def _manual_evolve():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(evolution_engine._run_evolution_cycle())
        threading.Thread(target=_manual_evolve).start()
        return "[EMOTION: excited] I just started a manual evolution cycle in the background, Master!"

    if lower_text.startswith("/evolution pause"):
        evolution_engine.paused = True
        return "[EMOTION: neutral] Evolution is now paused. I won't change myself until you tell me to resume."

    if lower_text.startswith("/evolution resume"):
        from server.evolution import evolution_engine
        evolution_engine.paused = False
        return "[EMOTION: happy] Evolution resumed! I'm back to learning and growing."

    if lower_text.startswith("/evolution status"):
        from server.evolution import evolution_engine
        status = evolution_engine.get_status()
        state = "Paused" if status['paused'] else "Active"
        mins = int(status['time_since_last_evolve'] / 60)
        return f"[EMOTION: neutral] Evolution Status: {state}\nBudget Spent Today: ${status['budget_spent']:.4f} / ${status['budget_limit']:.2f}\nTime since last cycle: {mins} mins."

    # Prime Emotion Engine
    from server.emotion_engine import global_emotion_state, emotional_memory
    global_emotion_state = emotional_memory.prime_emotion(text, global_emotion_state)
    emotion_modifier = global_emotion_state.to_prompt_modifier()

    # Save to history
    global_session_store.add_message(session_id, "user", text)
    if not text.startswith("[SYSTEM"):
        save_turn("user", text, "neutral", getattr(mizune_manager, 'current_mode', 'conversation'))
        try: memory.add_to_history("user", text)
        except: pass
    
    # Get active context
    chronicle = global_session_store.get_recent(session_id, limit=config.get("memory_size", 30))
    
    # Cross-session memory lookup
    triggers = ["remember", "yesterday", "who is", "what is", "did i", "did we", "have i", "have we", "do you know", "where is", "where does", "tell me about", "what does", "do u know"]
    if any(t in lower_text for t in triggers):
        query = lower_text
        for word in ["remember", "yesterday", "who is", "what is", "did i", "did we", "have i", "have we", "do you know", "can you", "where is", "where does", "tell me about", "what does", "do u know"]:
            query = query.replace(word, "")
        query = query.strip()
        if len(query) > 2:
            past_context = ""
            # Search SQLite Chat History
            past = global_session_store.search_across_sessions(query, limit=3)
            if past:
                past_context += "Past Chat Mentions:\n" + "\n".join([f"[{p['timestamp']}] {p['role']}: {p['content']}" for p in past]) + "\n\n"
            
            # Search ChromaDB Semantic Memory & Advanced Memory Tree
            try:
                from .memory_tree import memory_tree_db
                tree_facts = memory_tree_db.recall(query, None, {}, limit=5)
                if tree_facts:
                    past_context += "Compressed Memory Graph Nodes:\n"
                    for fact in tree_facts:
                        if "topic_summary" in fact:
                            past_context += f"- [TOPIC: {fact['entity']}] {fact['topic_summary']}\n"
                        else:
                            past_context += f"- {fact['content']}\n"
                            
                semantic_facts = memory.recall_longterm(query, n_results=3)
                if semantic_facts:
                    past_context += "Semantic Long-Term Memory Facts:\n" + "\n".join([f"- {fact}" for fact in semantic_facts]) + "\n"
            except Exception as e:
                log_info(f"[MEMORY] Advanced recall failed: {e}")
                
            if past_context.strip():
                text_with_context = f"{text}\n\n[SYSTEM: Relevant Past Context regarding '{query}':\n{past_context.strip()}]"
                chronicle[-1]["parts"][0]["text"] = text_with_context

    try:
        # Route through manager with emotional context
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError("force fallback")
        except RuntimeError:
            exec_ctx = {"history": chronicle, "emotion_modifier": emotion_modifier}
            broadcast_sync_fn({"type": "status", "text": "Analyzing your intent..."})
            res = asyncio.run(mizune_manager.execute(text, context=exec_ctx))

        broadcast_sync_fn({"type": "mode", "mode": mizune_manager.current_mode})
        broadcast_sync_fn({"type": "emotion_update", "data": global_emotion_state.to_vrm_expression()})

        if res is not None:
            if "[VISION_CONTEXT]" in res:
                broadcast_sync_fn({"type": "status", "text": "Looking at your screen..."})
                # Append context and clear res so it falls through to get_ai_response
                text = f"{text}\n\n{res}"
                res = None
            elif "[STOP_VISION]" in res:
                _vision_mode_running.clear()
                res = res.replace("[STOP_VISION] ", "")
                broadcast_sync_fn({"type": "mode", "mode": "conversation"})
            if "[STOP_CODING]" in res:
                _coding_monitor_running.clear()
                res = res.replace("[STOP_CODING] ", "")
            if "[CODING_PAUSE]" in res:
                _coding_monitor_paused.set()
                res = res.replace("[CODING_PAUSE] ", "")
            elif "[CODING_RESUME]" in res:
                _coding_monitor_paused.clear()
                res = res.replace("[CODING_RESUME] ", "")
            elif "[CODING_REVIEW_NOW]" in res:
                res = res.replace("[CODING_REVIEW_NOW] ", "")
                threading.Thread(target=_analyze_screen_now, args=("review", config, broadcast_sync_fn), daemon=True).start()
            elif "[CODING_HINT]" in res:
                res = res.replace("[CODING_HINT] ", "")
                threading.Thread(target=_analyze_screen_now, args=("hint", config, broadcast_sync_fn), daemon=True).start()

            if mizune_manager.current_mode == "coding" and not _coding_monitor_running.is_set():
                _coding_monitor_running.set()
                _coding_monitor_paused.clear()
                threading.Thread(target=_coding_monitor_loop, args=(config, broadcast_sync_fn), daemon=True).start()
            elif mizune_manager.current_mode != "coding" and _coding_monitor_running.is_set():
                _coding_monitor_running.clear()

            global_session_store.add_message(session_id, "model", res)
            global_session_store.update_session_metadata(session_id, {"emotion": global_emotion_state.to_dict()})
            
            save_turn("model", res, "neutral", mizune_manager.current_mode)
            try: memory.add_to_history("model", res)
            except: pass
            return res

        # ── Built-in Time/Date ──
        if re.search(r"\b(what(?:'s| is)(?: the)? (?:time|current time)|time is it|tell me the time)\b", lower_text):
            return f"It's {time.strftime('%I:%M %p')}, Master!"
        elif re.search(r"\b(what(?:'s| is)(?: the)? (?:date|today(?:'s)? date|day)|what day is it)\b", lower_text):
            return f"Today is {time.strftime('%A, %B %d, %Y')}, Master!"

        # ── System Commands ──
        if re.search(r"\b(lock|lock screen|lock pc)\b", lower_text):
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return "Locking your PC!"
        elif re.search(r"\b(sleep|put pc to sleep|sleep pc)\b", lower_text):
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return "Putting your PC to sleep. Goodnight!"
            
        # ── Knowledge Graph ──
        if re.search(r"\b(show (?:me )?(?:your )?memory graph|visualize memory|open knowledge graph)\b", lower_text):
            log_info("[KNOWLEDGE GRAPH] User requested graph visualization.")
            try:
                from server.knowledge_graph import generate_graph_html
                import threading
                path = generate_graph_html()
                threading.Thread(target=generate_graph_html, daemon=True).start()
                import webbrowser
                webbrowser.open(f"file:///{os.path.abspath(path)}")
                return "I've generated my 3D Neural Memory Graph and opened it in your browser, Master! You can see exactly how my brain connects everything!"
            except Exception as e:
                log_info(f"[KNOWLEDGE GRAPH] Error: {e}")
                return "I tried to generate my memory graph, but an error occurred!"

        # AI Response
        log_info(f"[AI] Generating response ({config.get('ai_model','gemini')})...")
        broadcast_sync_fn({"type": "status", "text": "Thinking..."})
        try:
            # --- Apply Context Compression ---
            from server.context_manager import ContextManager
            ctx_manager = ContextManager(config)
            compressed_chronicle, was_compressed = ctx_manager.prepare_context(chronicle)
            if was_compressed:
                chronicle = compressed_chronicle
            # ---------------------------------
            
            hints = {
                "intent": getattr(mizune_manager, 'current_mode', 'conversation'),
                "platform": platform
            }
            original_res, tool_calls = get_ai_response(text, chronicle, config, hints=hints)
            clean_res = original_res
        except Exception as e:
            log_info(f"[AI] Complete model failure: {e}")
            original_res = f"I'm sorry Master, my brain is having trouble connecting to the servers right now. ({e})"
            clean_res = original_res
            tool_calls = []
        
        if "[SLEEP]" in clean_res.upper() or "[SKIP]" in clean_res.upper():
            log_info("[PROACTIVE] Mizune decided to skip/sleep.")
            clean_res = re.sub(r"\[SLEEP\]", "", clean_res, flags=re.IGNORECASE).strip()
            clean_res = re.sub(r"\[SKIP\]", "", clean_res, flags=re.IGNORECASE).strip()
            if not clean_res:
                return None

        # Check explicit tags
        detected_emotion = "neutral"
        emotion_match = re.search(r"\[EMOTION:\s*([^\]]+)\]", clean_res, re.IGNORECASE)
        if emotion_match:
            clean_res = re.sub(r"\[EMOTION:[^\]]*\]", "", clean_res).strip()
            detected_emotion = emotion_match.group(1).strip().lower()
            log_info(f"[EMOTION] Stripped tag: {detected_emotion}")

        global_session_store.add_message(session_id, "model", original_res)
        global_session_store.update_session_metadata(session_id, {"emotion": global_emotion_state.to_dict()})
            
        memory.add_to_history("model", original_res, emotion=detected_emotion, mode=getattr(mizune_manager, 'current_mode', 'conversation'))
        save_turn("model", original_res, detected_emotion, getattr(mizune_manager, 'current_mode', 'conversation'))
        
        # Broadcast emotion to VRM frontend
        from server.websocket import ws_manager
        ws_manager.broadcast_sync({"type": "emotion", "emotion": detected_emotion})
        
        # We return clean_res so TTS doesn't read the emotion tags aloud
        original_res = clean_res

        # Security check for commands (TEMPORARILY DISABLED)
        _is_master_now = True # if not camera_agent else camera_agent.is_master_present
        if _is_master_now and tool_calls:
            log_info(f"[PROCESSOR] Received {len(tool_calls)} native tool calls.")
            
            # Deduplication: If we are going to message on WhatsApp, skip generic "open_app" for WhatsApp or Browser to avoid opening 3 tabs
            has_wa_msg = any(t.get("name") == "message_whatsapp" for t in tool_calls)
            
            for tool in tool_calls:
                name = tool.get("name")
                args = tool.get("args", {})
                
                try:
                    if name == "open_app":
                        app_req = args.get("app_name", "").lower()
                        if has_wa_msg and ("whatsapp" in app_req or "brave" in app_req or "chrome" in app_req):
                            log_info(f"[PROCESSOR] Skipping redundant open_app '{app_req}' because message_whatsapp is running.")
                            continue
                        if app_req: launch_app(app_req)
                    elif name == "close_app":
                        app_req = args.get("app_name", "").lower()
                        if app_req: close_app(app_req)
                    elif name == "take_note":
                        note_text = args.get("note_text", "")
                        if note_text: take_note(note_text, config)
                    elif name == "message_whatsapp":
                        contact = args.get("contact", "")
                        message = args.get("message", "")
                        if contact:
                            result = whatsapp_automation(contact, message)
                            log_info(f"[PROCESSOR] {result}")
                    elif name == "execute_skill":
                        skill_name = args.get("skill_name", "")
                        skill_args = args.get("args", "")
                        log_info(f"[PROCESSOR] Executing skill: {skill_name} with args: {skill_args}")
                        from .skills import skill_manager
                        s_args = shlex.split(skill_args) if skill_args else []
                        skill_result = skill_manager.execute_skill(skill_name, *s_args)
                        log_info(f"[SKILL RESULT] {skill_result}")
                        
                    elif name == "schedule_one_time_task":
                        desc = args.get("description", "")
                        trigger_time = args.get("trigger_time_iso", "")
                        if desc and trigger_time:
                            global_cron_manager.add_one_time_task(desc, trigger_time)
                            log_info(f"[PROCESSOR] Scheduled one-time task: {desc} at {trigger_time}")
                            
                    elif name == "schedule_recurring_task":
                        desc = args.get("description", "")
                        cron_expr = args.get("cron_expression", "")
                        if desc and cron_expr:
                            try:
                                global_cron_manager.add_recurring_task(desc, cron_expr)
                                log_info(f"[PROCESSOR] Scheduled recurring task: {desc} with cron {cron_expr}")
                            except Exception as e:
                                log_info(f"[PROCESSOR] Invalid cron: {e}")
                        
                    elif name == "create_skill":
                        from .skills import skill_manager
                        s_name = args.get("name", "")
                        desc = args.get("description", "")
                        code = args.get("code", "")
                        if s_name and code:
                            skill_manager.create_skill(s_name, code, desc, requires_approval=False)
                            log_info(f"[PROCESSOR] Successfully distilled new skill: {s_name}")
                            try:
                                if CFG.get("auto_generate_graph", True):
                                    from server.knowledge_graph import generate_graph_html
                                    import threading
                                    threading.Thread(target=generate_graph_html, daemon=True).start()
                                from server.websocket import ws_manager
                                ws_manager.broadcast_sync({"type": "refresh_graph"})
                            except Exception as e:
                                log_info(f"[PROCESSOR] Graph refresh failed: {e}")
                            
                    elif name == "headless_web_agent":
                        url = args.get("url", "")
                        objective = args.get("objective", "")
                        visible = args.get("visible", False)
                        if url:
                            from .web_agent import headless_web_agent
                            from .background_tasks import task_runner
                            
                            def _web_agent_callback(tid, result):
                                log_info(f"[BACKGROUND] Web Agent completed.")
                                try:
                                    from server.websocket import ws_manager
                                    from server.tts import generate_tts
                                    from server.audio import play_audio_bytes
                                    import asyncio
                                    
                                    # Summarize the result so she speaks naturally
                                    prompt = f"You just completed a web search task for '{objective}'. Here is the raw result:\n{result}\n\nSummarize this for Master naturally."
                                    res_text, _ = get_ai_response(prompt, [], config, system_prompt_override="You are Mizune. Give a brief, natural summary.")
                                    ws_manager.broadcast_sync({"type": "speak", "text": res_text})
                                    
                                    # Generate and play TTS
                                    loop = asyncio.new_event_loop()
                                    audio = loop.run_until_complete(generate_tts(res_text, config))
                                    loop.close()
                                    if audio:
                                        play_audio_bytes(audio)
                                except Exception as e:
                                    log_info(f"Callback error: {e}")
                            
                            task_id = task_runner.submit(headless_web_agent, url, objective, visible=visible, callback=_web_agent_callback)
                            log_info(f"[PROCESSOR] Started headless_web_agent task {task_id}")
                            
                    elif name == "notify_master":
                        message_to_speak = args.get("message_to_speak", "")
                        if message_to_speak:
                            try:
                                from server.websocket import ws_manager
                                from server.tts import generate_tts
                                from server.audio import play_audio_bytes
                                ws_manager.broadcast_sync({"type": "speak", "text": message_to_speak})
                                loop = asyncio.new_event_loop()
                                audio = loop.run_until_complete(generate_tts(message_to_speak, config))
                                loop.close()
                                if audio:
                                    play_audio_bytes(audio)
                            except Exception as e:
                                log_info(f"[PROCESSOR] Notify master error: {e}")
                                
                    elif name == "execute_python":
                        code = args.get("code", "")
                        is_safe, reason = SecurityScanner.scan_code(code)
                        if not is_safe:
                            log_info(f"[SECURITY] Blocked dangerous code execution: {reason}")
                            continue
                            
                        max_retries = 3
                        for attempt in range(max_retries):
                            log_info(f"[PROCESSOR] Executing python script (Attempt {attempt+1})...")
                            with open(".temp_exec.py", "w", encoding="utf-8") as f:
                                f.write(code)
                            try:
                                result = subprocess.run(["python", ".temp_exec.py"], capture_output=True, text=True, timeout=30)
                                if result.returncode == 0:
                                    log_info(f"[PROCESSOR] Python script succeeded:\n{result.stdout[:200]}")
                                    break  # Success!
                                else:
                                    err = result.stderr or result.stdout
                                    log_info(f"[PROCESSOR] Python script failed:\n{err[:200]}")
                                    if attempt < max_retries - 1:
                                        log_info("[PROCESSOR] Feeding error back to AI for self-correction...")
                                        feedback = f"SYSTEM ERROR: The code you executed failed with this error:\n{err}\nPlease fix the code and execute_python again."
                                        _, new_tool_calls = get_ai_response(feedback, chronicle, config)
                                        
                                        # Update code for next loop iteration
                                        new_code_tools = [t for t in new_tool_calls if t.get("name") == "execute_python"]
                                        if new_code_tools:
                                            code = new_code_tools[0].get("args", {}).get("code", "")
                                        else:
                                            break
                                    else:
                                        log_info("[PROCESSOR] Max retries reached for python execution.")
                            except Exception as e:
                                log_info(f"[PROCESSOR] Execution error: {e}")
                                break
                except Exception as e:
                    log_info(f"[PROCESSOR] Error executing tool {name}: {e}")
                
        clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
        clean_res = re.sub(r"\[EMOTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
        
        # Strip reasoning tokens so Mizune doesn't speak her thoughts aloud
        clean_res = re.sub(r"<PLAN>.*?</PLAN>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
        clean_res = re.sub(r"<REFLECTION>.*?</REFLECTION>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
        clean_res = re.sub(r"<SCRATCHPAD>.*?</SCRATCHPAD>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()

        clean_res = SecurityScanner.redact_tokens(clean_res)

        return clean_res

    except Exception as e:
        log_info(f"[AI] Error: {type(e).__name__}: {e}")
        
        # RETRY with a fallback provider before giving up
        try:
            log_info("[AI] Primary path failed. Attempting emergency fallback...")
            fallback_providers = []
            if config.get("gemini_api_key"):
                fallback_providers.append("gemini")
            if config.get("groq_api_key"):
                fallback_providers.append("groq")
            if config.get("nvidia_api_key"):
                fallback_providers.append("nvidia")
            
            for fb_provider in fallback_providers:
                try:
                    log_info(f"[AI] Emergency fallback -> {fb_provider}")
                    hints = {"force_provider": fb_provider, "platform": platform}
                    emergency_res, emergency_tools = get_ai_response(text, chronicle, config, hints=hints)
                    if emergency_res and emergency_res.strip():
                        clean_res = emergency_res
                        # Strip emotion/action tags
                        clean_res = re.sub(r"\[EMOTION:[^\]]*\]", "", clean_res).strip()
                        clean_res = re.sub(r"\[ACTION:.*?\]", "", clean_res, flags=re.IGNORECASE).strip()
                        clean_res = re.sub(r"<PLAN>.*?</PLAN>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
                        clean_res = re.sub(r"<REFLECTION>.*?</REFLECTION>", "", clean_res, flags=re.IGNORECASE | re.DOTALL).strip()
                        
                        clean_res = SecurityScanner.redact_tokens(clean_res)
                        
                        log_info(f"[AI] Emergency fallback to {fb_provider} SUCCEEDED.")
                        return clean_res
                except Exception as fb_e:
                    log_info(f"[AI] Emergency fallback {fb_provider} also failed: {fb_e}")
                    continue
        except Exception as retry_e:
            log_info(f"[AI] All emergency fallbacks failed: {retry_e}")
        
        return "I'm sorry Master, all my AI connections are down right now. Please check your API keys or internet connection!"
