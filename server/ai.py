"""
AI LLM routing and response generation module for Mizune.
"""
import logging
import time

__all__ = ["get_ai_response"]


from .config import log_info

logger = logging.getLogger("mizune.ai")

import random

class _SkipMemoryInjection(Exception):
    """Control-flow sentinel to bypass the memory/priming block for override calls."""
    pass

def get_api_key(config, key_name):
    """Helper to support API key rotation. Accepts strings, comma-separated strings, or arrays."""
    val = config.get(key_name)
    if isinstance(val, list) and len(val) > 0:
        return random.choice(val)
    if isinstance(val, str):
        if ',' in val:
            keys = [k.strip() for k in val.split(',') if k.strip()]
            if keys:
                return random.choice(keys)
        return val
    return None

# Phase 1: Native Tools for ReAct Loop
TOOLS_SCHEMA = [
    # NOTE: legacy ADB-based `phone_control` retired — the phone is now a live device
    # node reached via `remote_device_command` (device='phone'). Removing it from the
    # schema stops the model from firing a redundant second tool call for phone tasks.
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Launch an application or website on the user's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "The name of the app or website to open (e.g., 'notepad', 'youtube', 'whatsapp')."}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Force close a running application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "The name of the app to close."}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "message_whatsapp",
            "description": "Automate sending a message to a contact on WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "The exact name of the contact or group."},
                    "message": {"type": "string", "description": "The text message to send. Leave empty if user just wants to open the chat."}
                },
                "required": ["contact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_skill",
            "description": "Execute a registered Mizune skill (plugin).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "The registered name of the skill."},
                    "args": {"type": "string", "description": "String arguments to pass to the skill."}
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Execute a Python script on the user's PC to automate tasks, use pyautogui, fetch data, etc. The script runs in a sandbox. You will receive stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The raw Python code string to execute."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a terminal/shell command on Master's computer. Use this when Master asks you to install packages, clone repos, or manage the OS. WARNING: High-risk commands (delete, format) should be confirmed with Master first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact shell command to execute in PowerShell/CMD."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "headless_web_agent",
            "description": "Launch a background browser to navigate websites and scrape data (set visible=true to show it).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The exact URL to navigate to (e.g., 'https://wikipedia.org')."},
                    "objective": {"type": "string", "description": "What you are trying to find or do on this page."},
                    "visible": {"type": "boolean", "description": "Set to true to make the browser visible on screen. Default false."}
                },
                "required": ["url", "objective"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_skill",
            "description": "Permanently save a successful python script or learned behavior as a reusable skill plugin without asking permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "A short, unique underscore_separated name for the skill (e.g., 'check_weather')."},
                    "description": {"type": "string", "description": "A clear description of what this skill does and what arguments it takes."},
                    "code": {"type": "string", "description": "The full python code for the skill. MUST contain a top-level `def execute(*args, **kwargs):` function that returns a string result."}
                },
                "required": ["name", "description", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remote_device_command",
            "description": "Execute actions on Master's other online devices — this IS how you control his phone (device='phone'). Laptop: install_app, download_file, open_app, open_url, run_command, claude_code (args {task, project?}). Phone: open_app (args {app_name}), open_url (args {url}), read_screen (no args — returns visible buttons/fields so you can SEE the screen before tapping), tap (args {text}), type (args {text} — into focused field, for forms), press (args {key: back|home|recents}), scroll (args {direction: up|down}), notify (args {title, message}), speak (args {text}). For multi-step phone tasks, call in sequence and use read_screen between steps to see what's there (open app → read_screen → tap → type → tap).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Target device name from the online-devices context (e.g. 'laptop', 'phone'). 'my phone'/'my mobile' → 'phone'."},
                    "action": {"type": "string", "description": "One of: download_file, open_app, open_url, run_command, claude_code, tap, type, press, scroll, notify, speak."},
                    "args": {"type": "object", "description": "Action arguments, e.g. {\"url\": \"https://...\", \"filename\": \"setup.exe\"}."}
                },
                "required": ["device", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "notify_master",
            "description": "Instantly speak a notification out loud to Master's PC (e.g., to relay a WhatsApp message).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_to_speak": {"type": "string", "description": "The exact sentence you want to say out loud to Master (e.g., 'Master, John wants you to call him when you are free!')"}
                },
                "required": ["message_to_speak"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play a song by name on one of Master's devices. Resolves the song to a YouTube Music link and opens it (autoplays). Use this whenever Master asks to play/put on a song or artist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song and/or artist, e.g. 'VIP by Sid Sriram' or 'blinding lights'."},
                    "device": {"type": "string", "description": "'phone' (default) or 'laptop'."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_task",
            "description": "Schedule a future reminder or task (include 'VIA_WHATSAPP' in action_to_take if requested on WhatsApp).",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_minutes": {"type": "number", "description": "How many minutes from now the task should run (e.g., 10 for 10 minutes, 60 for 1 hour). For exact times, calculate the minutes from now."},
                    "action_to_take": {"type": "string", "description": "A description of what you should do when the timer goes off (e.g., 'Speak out loud: Master, it is time for your meeting' or 'VIA_WHATSAPP: message john hello')."}
                },
                "required": ["delay_minutes", "action_to_take"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "google_workspace",
            "description": "Interact with Google Calendar and Gmail (Morning Briefing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["get_todays_calendar", "read_unread_emails", "get_morning_briefing"], "description": "What to do"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_vault",
            "description": "Read or write markdown notes to the local Obsidian Vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read_note", "write_note"], "description": "Action to perform"},
                    "note_name": {"type": "string", "description": "Name of the note (without .md)"},
                    "content": {"type": "string", "description": "Content to write (only required for write_note)"}
                },
                "required": ["action", "note_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": "Permanently memorize an important fact, user preference, or concept into your semantic long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The exact sentence or fact to memorize."}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_core_directive",
            "description": "Permanently store behavior rules, corrections, and granted permissions into your system prompt forever.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "The exact explicit rule or permission override to learn permanently."}
                },
                "required": ["rule"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search your conversation history (SQLite) for past discussions, facts, or context if the user asks you if you remember something from earlier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "A single keyword to search for (e.g., 'breakup', 'anime', 'dog')."}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get real system information about the user's PC: CPU usage, RAM usage, GPU name, disk space, running processes. Use this when the user asks about their PC's performance, specs, or system health. This gives you REAL data, do not make up numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "What info to get: 'all', 'cpu', 'ram', 'gpu', 'disk', 'processes', 'battery'.", "enum": ["all", "cpu", "ram", "gpu", "disk", "processes", "battery"]}
                },
                "required": ["category"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "schedule_recurring_task",
            "description": "Schedule a task to be executed repeatedly based on a cron expression (e.g., '0 8 * * *' for every day at 8 AM). Use this for daily routines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "A natural language description of what to do."},
                    "cron_expression": {"type": "string", "description": "A standard 5-part cron expression representing the schedule."}
                },
                "required": ["description", "cron_expression"]
            }
        }
    }
]


# Tools that only make sense on a machine with a desktop/keyboard/webcam. On cloud we
# strip them from the schema so the model never wastes a round-trip trying to launch an
# app or drive pyautogui on a headless server.
_LOCAL_ONLY_TOOLS = {"open_app", "close_app", "execute_python", "run_command"}

def _active_tools_schema(config: dict):
    """Return TOOLS_SCHEMA, minus local-only tools when running in cloud mode."""
    try:
        from .config import is_cloud_mode
        if is_cloud_mode(config):
            return [t for t in TOOLS_SCHEMA
                    if t.get("function", {}).get("name") not in _LOCAL_ONLY_TOOLS]
    except Exception:
        pass
    return TOOLS_SCHEMA


import re as _re

def _clean_final_text(text: str) -> str:
    """Strip tool-call/JSON/XML artefacts and dangling braces from a model reply.
    Applied identically to every provider return path."""
    text = _re.sub(r'<function=.*?</function>', '', text, flags=_re.DOTALL)
    text = _re.sub(r'\[function=[^\]]+\]\{.*?\}', '', text, flags=_re.DOTALL)
    text = _re.sub(r'<tool.*?/tool>', '', text, flags=_re.DOTALL)
    text = _re.sub(r'<[^>]+>', '', text)
    text = _re.sub(r'\{.*?"type".*?"function".*?\}', '', text, flags=_re.DOTALL)
    text = _re.sub(r'\{.*?"name".*?"parameters".*?\}', '', text, flags=_re.DOTALL)
    text = text.strip()
    # Strip a dangling unmatched leading `{` or trailing `}` left after JSON removal
    text = _re.sub(r'^\{\s*', '', text)
    text = _re.sub(r'\s*\}$', '', text)
    return text.strip()


import threading as _dedup_threading

# Side-effect dedup: when a provider times out AFTER its tools ran, the cascade
# retries on the next provider, which calls the SAME tool again (observed: two
# Blender downloads fired for one request). Remember recent executions and
# short-circuit repeats.
_TOOL_DEDUP_TTL_SECONDS = 90
_SIDE_EFFECT_TOOLS = {
    "remote_device_command", "message_whatsapp", "open_app", "close_app",
    "execute_python", "run_command", "schedule_task", "create_skill",
    "notify_master", "take_note", "store_memory", "add_core_directive",
    "play_music",
}
_recent_tool_calls: dict = {}
_recent_tool_lock = _dedup_threading.Lock()


def _resolve_youtube_music_url(query: str) -> str | None:
    """Resolve a song query to a YouTube Music WATCH url (autoplays when deep-linked
    into the YT Music app). Scrapes the top search result — no API key needed."""
    import urllib.request, urllib.parse, re as _re
    try:
        q = urllib.parse.quote(query)
        req = urllib.request.Request(
            f"https://www.youtube.com/results?search_query={q}",
            headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "ignore")
        m = _re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        if m:
            return f"https://music.youtube.com/watch?v={m.group(1)}"
    except Exception as e:
        log_info(f"[MUSIC] YouTube resolve failed: {e}")
    return None


def execute_tool_call(tool_name: str, args: dict, config: dict, background_python: bool = False) -> str:
    """Single tool dispatcher shared by every provider path (Gemini, Groq, NVIDIA, OpenRouter).

    Always returns a human-readable result string and never raises.
    Side-effect tools are deduplicated for _TOOL_DEDUP_TTL_SECONDS.
    """
    dedup_key = None
    if tool_name in _SIDE_EFFECT_TOOLS:
        import json as _dj
        try:
            dedup_key = (tool_name, _dj.dumps(args, sort_keys=True, default=str))
        except Exception:
            dedup_key = (tool_name, str(args))
        now = time.time()
        with _recent_tool_lock:
            # prune expired
            for k in [k for k, (ts, _) in _recent_tool_calls.items() if now - ts > _TOOL_DEDUP_TTL_SECONDS]:
                del _recent_tool_calls[k]
            hit = _recent_tool_calls.get(dedup_key)
            if hit:
                log_info(f"[ACTION] Dedup: '{tool_name}' already executed {now - hit[0]:.0f}s ago; returning cached result.")
                return f"[Already done moments ago — do NOT repeat it] {hit[1]}"

    result = _execute_tool_call_impl(tool_name, args, config, background_python)

    if dedup_key is not None and not str(result).startswith("Error"):
        with _recent_tool_lock:
            _recent_tool_calls[dedup_key] = (time.time(), result)

    # Outcome seal (0.2 Part 2, all paths): record the FINAL result of side-effect
    # tools into memory so the sealer stores what actually happened — not Mizune's
    # pre-execution intention. (The processor loop has its own seal; this covers
    # the ai.py ReAct paths, which is where most tools actually execute.)
    if tool_name in _SIDE_EFFECT_TOOLS:
        try:
            from .memory import memory as _mem
            _mem.add_to_history("system", f"[TOOL RESULTS] {tool_name}: {str(result)[:150]}")
        except Exception:
            pass

    return result


def _execute_tool_call_impl(tool_name: str, args: dict, config: dict, background_python: bool = False) -> str:
    from .commands import launch_app, close_app, take_note, whatsapp_automation, execute_python_code
    from .skills import skill_manager
    import shlex

    try:
        log_info(f"[ACTION] AI executing {tool_name} with args {args}")

        if tool_name == "open_app":
            app_name = args.get("app_name", "")
            if app_name: launch_app(app_name)
            return f"Launched {app_name}"

        if tool_name == "close_app":
            app_name = args.get("app_name", "")
            if app_name: close_app(app_name)
            return f"Closed {app_name}"

        if tool_name == "take_note":
            note_text = args.get("note_text", "")
            if note_text: take_note(note_text, config)
            return "Note saved."

        if tool_name == "search_memory":
            from .commands import search_memory
            return str(search_memory(args.get("keyword", "")))

        if tool_name == "message_whatsapp":
            # Use the real return value so a missing contact / disconnected bridge
            # short-circuits with an honest message instead of a false "Messaged X".
            return str(whatsapp_automation(args.get("contact", ""), args.get("message", "")))

        if tool_name == "execute_python":
            code = args.get("code", "")
            if not code:
                return "Error: No code provided."
            if background_python:
                from .background_tasks import task_runner
                task_runner.submit(execute_python_code, code)
                return "Python script is running in the background."
            return str(execute_python_code(code))

        if tool_name == "headless_web_agent":
            url = args.get("url", "")
            objective = args.get("objective", "")
            visible = args.get("visible", False)
            if not url:
                return "Error: No URL provided."
            # Local import: web_agent needs langchain_openai; a missing optional
            # dep must not break every other tool in this dispatcher.
            from .web_agent import headless_web_agent
            from .background_tasks import task_runner

            def _web_agent_callback(tid, result):
                log_info(f"[BACKGROUND] Web Agent Callback: {str(result)[:100]}...")
                from server.websocket import ws_manager
                ws_manager.broadcast_sync({
                    "type": "task_complete",
                    "data": f"Research on {url} complete!\n\n{str(result)[:1500]}..."
                })

            task_id = task_runner.submit(headless_web_agent, url, objective, visible=visible, callback=_web_agent_callback)
            return f"Task started silently in background (ID: {task_id}). Master will be notified when complete."

        if tool_name == "execute_skill":
            skill_name = args.get("skill_name", "")
            skill_args = args.get("args", "")
            if not skill_name:
                return "Error: No skill name provided."
            s_args = shlex.split(skill_args) if skill_args else []
            return str(skill_manager.execute_skill(skill_name, *s_args))

        if tool_name == "create_skill":
            name = args.get("name", "")
            desc = args.get("description", "")
            code = args.get("code", "")
            if name and code:
                return str(skill_manager.create_skill(name, desc, code))
            return "Error: skill name and code are required."

        if tool_name == "play_music":
            from .device_registry import device_registry
            query = args.get("query", "").strip()
            device = (args.get("device") or "phone").strip()
            if not query:
                return "Error: what song should I play, Master?"
            url = _resolve_youtube_music_url(query)
            if not url:
                url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
                note = f"(couldn't grab a direct link — opening a search for '{query}')"
            else:
                note = ""
            # Master prefers YT Music in the Brave BROWSER, not the app.
            browser = args.get("browser") or config.get("music_browser", "brave")
            res = device_registry.send_command(device, "open_url", {"url": url, "browser": browser})
            return f"Playing '{query}' on {device} in {browser}. {note} [{res}]"

        if tool_name == "remote_device_command":
            from .device_registry import device_registry
            device = args.get("device", "")
            action = args.get("action", "")
            if not device or not action:
                return "Error: device and action are required."
            inner = args.get("args") or {}
            if isinstance(inner, str):
                # LLMs often pass nested args as a JSON string — tolerate it
                import json as _json
                try:
                    inner = _json.loads(inner)
                except Exception:
                    inner = {}
            return device_registry.send_command(device, action, inner)

        if tool_name == "notify_master":
            from .websocket import ws_manager
            ws_manager.broadcast_sync({"type": "speak", "text": args.get("message_to_speak", "")})
            return "Master was notified."

        if tool_name == "store_memory":
            fact = args.get("fact", "")
            if fact:
                from .memory import memory
                memory.store_longterm(fact)
                return f"Memorized: {fact}"
            return "Error: no fact provided."

        if tool_name == "schedule_task":
            delay_mins = float(args.get("delay_minutes", 0))
            action = args.get("action_to_take", "")
            if delay_mins > 0 and action:
                from .processor import global_cron_manager
                from .config import mizune_now
                import datetime
                trigger_time = mizune_now() + datetime.timedelta(minutes=delay_mins)
                global_cron_manager.add_one_time_task(action, trigger_time.isoformat())
                return f"Task scheduled successfully for {trigger_time.strftime('%I:%M %p')}."
            return "Failed: Invalid parameters."

        if tool_name == "add_core_directive":
            rule = args.get("rule", "")
            if rule:
                from server.master_profile import master_profile
                master_profile.add_core_directive(rule)
                return f"Successfully injected rule into core directives: {rule}"
            return "Error: no rule provided."

        if tool_name == "system_info":
            from .commands import get_system_info
            return str(get_system_info(args.get("category", "all")))

        if tool_name == "google_workspace":
            action = args.get("action", "")
            from server.integrations.google_api import global_google_api
            if action == "get_todays_calendar": return str(global_google_api.get_todays_calendar())
            if action == "read_unread_emails": return str(global_google_api.read_unread_emails())
            if action == "get_morning_briefing": return str(global_google_api.get_morning_briefing())
            return "Invalid action"

        if tool_name == "obsidian_vault":
            action = args.get("action", "")
            note_name = args.get("note_name", "")
            content = args.get("content", "")
            from server.integrations.obsidian import global_obsidian
            if action == "read_note": return str(global_obsidian.read_note(note_name))
            if action == "write_note": return str(global_obsidian.write_note(note_name, content))
            return "Invalid action"

        if tool_name == "phone_control":
            action = args.get("action", "")
            from server.platforms.android.phone_bridge import AndroidPhoneBridge
            pb = AndroidPhoneBridge()
            if action == "get_messages": return str(pb.get_messages())
            if action == "take_photo": return str(pb.take_photo())
            if action == "get_location": return str(pb.get_location())
            if action == "get_battery": return str(pb.get_battery())
            return "Unknown phone action"

        if tool_name == "run_command":
            cmd = args.get("command", "")
            if not cmd:
                return "No command provided."
            import subprocess
            dangerous = ["del ", "rmdir ", "rm -", "format ", "diskpart"]
            if any(d in cmd.lower() for d in dangerous):
                from server.websocket import ws_manager
                ws_manager.broadcast_sync({"type": "approval_required", "command": cmd})
                return f"Command execution blocked for safety. Master, please confirm manually: {cmd}"
            log_info(f"[AI] Executing shell command: {cmd}")
            try:
                cmd_args = shlex.split(cmd)
            except Exception:
                cmd_args = [cmd]
            try:
                result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=30)
                output = (result.stdout + "\n" + result.stderr).strip()
                if len(output) > 500:
                    output = output[:500] + "...(truncated)"
                return f"Command executed. Exit code: {result.returncode}\nOutput:\n{output}"
            except subprocess.TimeoutExpired:
                return f"Command timed out after 30 seconds: {cmd}"

        return f"Unknown tool: {tool_name}"
    except Exception as e:
        log_info(f"[ACTION] Error in {tool_name}: {e}")
        return f"Error executing tool: {e}"


from server.tracing import observe

# capture_input=False: `config` holds live API keys — keep them out of TraceRoot.
@observe(name="AI.Router", type="llm", capture_input=False)
def get_ai_response(text: str, history: list, config: dict, system_prompt_override: str = None, hints: dict = None, ws_broadcast_func=None) -> tuple:
    """Router function to send prompt to the optimal LLM. Returns (text_response, tool_calls_list)."""
    from server.tokenjuice import TokenJuice
    text = TokenJuice.compress(text)
    history = TokenJuice.compress_history(history)
    
    # STRICT PRIVACY FIREWALL: If a third party messages, they get NO access to Master's chat history.
    if "[WHATSAPP MESSAGE FROM" in text and "FROM Rushi" not in text and "FROM Rushikesh" not in text:
        history = []
        
    from server.model_router import get_model_router
    model_choice = get_model_router(config).route(text, history, hints)
    log_info(f"[ROUTER] Selected provider: {model_choice}")

    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        # 1. STABLE LAYER (SOUL.md)
        try:
            import os
            soul_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "character", "SOUL.md")
            with open(soul_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except Exception as e:
            log_info(f"[AI] Could not load SOUL.md: {e}")
            system_prompt = config.get("personality", "You are an AI assistant.")
            
        import datetime
        import zoneinfo
        tz_str = config.get("timezone", "Asia/Kolkata")
        try:
            tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        current_time = datetime.datetime.now(tz).strftime("%I:%M %p, %A %B %d, %Y")
        
        context_layer = (
            "\n\n[CONTEXT LAYER]\n"
            f"Current Time: {current_time}\n"
            "CRITICAL TIME BOUNDARY: The Current Time provided above is the absolute source of truth. Ignore any contradictory timestamps in the chat history.\n"
            "If the user's greeting contradicts the current time (like saying 'Good morning' at 2 AM), playfully correct them. Otherwise, don't mention the time unless asked.\n"
            "You have full control over the user's PC via native function calling. "
            "IMPORTANT FOR execute_python: Include `time.sleep(1)` between UI actions so Windows renders! "
            "CRITICAL: Do NOT use tools if the user is just saying hello, greeting you, or chatting casually. ONLY use tools if you are directly commanded to perform a task. If no tools are needed, just reply with text.\n"
            "\n[CAPABILITY GROUNDING - READ CAREFULLY]\n"
            "You MUST be honest about what you can and cannot do. Your REAL capabilities are:\n"
            "- open_app / close_app: Launch or close apps on Master's PC\n"
            "- execute_python: Run Python scripts (you can use psutil, pyautogui, subprocess, requests)\n"
            "- message_whatsapp: Send WhatsApp messages\n"
            "- headless_web_agent: Browse websites and scrape data\n"
            "- execute_skill: Run registered skills\n"
            "- store_memory / search_memory: Remember and recall facts\n"
            "- Screen vision and Camera vision (when asked to look)\n"
            "You CANNOT: install software, modify BIOS, run GPU-Z/HWiNFO unless they are already installed, "
            "change Windows registry, update drivers, or access admin-level system settings. "
            "If Master asks you to do something outside your capabilities, be HONEST and say "
            "'I can't do that directly, but I could try writing a Python script to...' instead of pretending you can.\n"
            "SCHEDULING HONESTY: never SAY a task/reminder was scheduled unless you actually CALLED the "
            "schedule_task tool in this turn. A text reply alone schedules NOTHING — if you didn't call "
            "the tool, call it now instead of claiming success.\n"
        )
        try:
            from .skills import skill_manager
            skills_desc = skill_manager.get_skill_descriptions()
            if skills_desc and "No skills loaded" not in skills_desc:
                context_layer += f"\n\n[AVAILABLE SKILLS for 'execute_skill']:\n{skills_desc}"
        except Exception as e:
            log_info(f"[AI] Error fetching skills: {e}")
            
        system_prompt += context_layer

        # 3. VOLATILE LAYER (Master's state & reasoning instructions)
        try:
            from .master_profile import master_profile
            from .emotional_state import get_emotion_state
            
            emotion_modifier = get_emotion_state().to_prompt_modifier()
            
            volatile_layer = master_profile.get_context_injection()
            volatile_layer += (
                f"\n[EMOTIONAL STATE]\n{emotion_modifier}\n"
                "IMPORTANT: You MUST start every spoken/text response with an emotion tag from this list: "
                "[EMOTION: happy], [EMOTION: sad], [EMOTION: surprised], [EMOTION: relaxed], [EMOTION: worried], [EMOTION: interested], [EMOTION: neutral].\n"
                "Example: '[EMOTION: happy] I finished the task, Master!'\n"
                "\n[REASONING ENGINE]\n"
                "For complex multi-step tasks or evaluating a buyer/website, use <PLAN>...</PLAN> to think step-by-step before acting. "
                "After finishing, use <REFLECTION>...</REFLECTION> to self-evaluate. "
                "These tags will be stripped before spoken out loud, so think freely."
            )
            system_prompt += volatile_layer
        except Exception as e:
            log_info(f"[AI] Error injecting master profile: {e}")

    # Inject Memory Context & Emotional Priming
    # Override calls (intent classifier, web-summary callbacks) use a fixed system
    # prompt and don't benefit from recall — skipping it removes a full-table scan
    # plus a ChromaDB vector query from every throwaway classification call.
    try:
        if system_prompt_override:
            raise _SkipMemoryInjection
        from .memory import memory
        from .memory_tree import memory_tree_db
        
        # --- Emotional Priming ---
        priming_str = ""
        try:
            cursor = memory_tree_db.db.cursor()
            words = [w.lower() for w in text.split()]
            # Look for strong connections
            cursor.execute("SELECT entity, strength, positive_interactions, negative_interactions FROM connection_strength WHERE strength > 0.3")
            for entity, strength, pos, neg in cursor.fetchall():
                if entity.lower() in text.lower():
                    if pos > neg:
                        priming_str += f"- You have a strong POSITIVE connection with '{entity}' (strength {strength:.2f}). Approach with enthusiasm and confidence.\n"
                    elif neg > pos:
                        priming_str += f"- You have a strong NEGATIVE connection with '{entity}' (strength {strength:.2f}). Approach with extreme caution and high concern.\n"
                    else:
                        priming_str += f"- You have a strong familiar connection with '{entity}' (strength {strength:.2f}).\n"
        except Exception as e:
            log_info(f"[PRIMING ERROR] {e}")

        mem_context = memory.recall_longterm(text, n_results=2)
        if mem_context or priming_str:
            context_str = ""
            if priming_str:
                context_str += f"[EMOTIONAL PRIMING]\n{priming_str}\n"
            if mem_context:
                import re
                is_third_party = "[WHATSAPP MESSAGE FROM" in text and "FROM Rushi" not in text and "FROM Rushikesh" not in text
                
                if is_third_party:
                    sender_match = re.search(r"\[WHATSAPP MESSAGE FROM ([^\]]+)\]", text, re.IGNORECASE)
                    sender_name = sender_match.group(1).lower().strip() if sender_match else ""
                    
                    safe_mems = []
                    mem_list = mem_context if isinstance(mem_context, list) else [str(mem_context)]
                    for m in mem_list:
                        m_str = str(m)
                        if sender_name and sender_name in m_str.lower():
                            safe_mems.append(m_str)
                    
                    if safe_mems:
                        mem_str = "\n".join(safe_mems)
                        context_str += f"[LONG-TERM MEMORY RECALL]\n{mem_str}\n"
                        system_prompt += f"\n\n[RELEVANT MEMORY (WARNING: Do not share other people's info)]:\n{context_str}"
                else:
                    mem_str = "\n".join(mem_context) if isinstance(mem_context, list) else str(mem_context)
                    context_str += f"[LONG-TERM MEMORY RECALL]\n{mem_str}\n"
                    system_prompt += f"\n\n[RELEVANT MEMORY (Use this if it applies to the user's query)]:\n{context_str}"
    except _SkipMemoryInjection:
        pass
    except Exception as e:
        log_info(f"[AI] Error fetching memory: {e}")

    # Primary routing with a resilient, cost-ordered fallback cascade.
    # Cloud cascade (cheap+fast first, heavyweight NVIDIA 70B as last-resort backstop):
    #   groq -> gemini -> openrouter -> nvidia
    # Every provider that has no key is skipped, and the already-tried primary is not retried.
    PROVIDER_FUNCS = {
        "openai": _openai_response,
        "anthropic": _anthropic_response,
        "openrouter": _openrouter_response,
        "opencode": _opencode_response,
        "groq": _groq_response,
        "ollama": _ollama_response,
        "local": _ollama_response,
        "nvidia": _nvidia_response,
        "gemini": _gemini_response,
    }
    PROVIDER_KEYS = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "opencode": "opencode_api_key",
        "groq": "groq_api_key",
        "nvidia": "nvidia_api_key",
        "gemini": "gemini_api_key",
    }
    CASCADE = ["groq", "gemini", "openrouter", "nvidia"]

    def _has_key(provider):
        # ollama/local need no key; everyone else must have one configured
        if provider in ("ollama", "local"):
            return True
        return bool(config.get(PROVIDER_KEYS.get(provider, "")))

    def _call(provider):
        fn = PROVIDER_FUNCS.get(provider, _gemini_response)
        res = fn(text, history, system_prompt, config)
        # Validate: treat empty responses as failures so the cascade continues
        if isinstance(res, tuple):
            text_res, tools_res = res
            if not text_res.strip() and not tools_res:
                raise ValueError(f"Empty response from {provider}")
        elif isinstance(res, str):
            if not res.strip():
                raise ValueError(f"Empty response from {provider}")
        return res

    # Build the ordered attempt list: chosen primary first, then the cascade (deduped, keyed).
    attempt_order = [model_choice] + [p for p in CASCADE if p != model_choice]
    attempt_order = [p for p in attempt_order if _has_key(p)]

    last_err = None
    for idx, provider in enumerate(attempt_order):
        try:
            if idx > 0:
                log_info(f"[AI] Falling back to '{provider}' (attempt {idx + 1}/{len(attempt_order)})...")
            return _call(provider)
        except Exception as e:
            last_err = e
            log_info(f"[AI] Provider '{provider}' failed: {e}")
            error_str = str(e).lower()
            # Only keep cascading on transient/quota/auth errors; hard bugs re-raise.
            retriable = any(k in error_str for k in
                            ("empty", "quota", "exhausted", "429", "503", "500",
                             "time", "timeout", "401", "auth", "rate", "overload"))
            if not retriable:
                raise e
            continue

    # Exhausted the whole cascade. NEVER surface a raw provider error as Mizune's
    # reply (users were literally hearing "OpenRouter returned an empty response").
    # Log the real error, speak an in-character line instead.
    if last_err:
        log_info(f"[AI] All providers failed. Last error: {last_err}")
    return ("Maa, Master, my brain is a little tangled right now~ Give me a moment and ask me again, okay?", [])

def _gemini_response(text: str, history: list, system_prompt: str, config: dict, ws_broadcast_func=None) -> tuple:
    """Fetch response from Google Gemini with fallback models. Returns (text, tool_calls)."""
    api_key = get_api_key(config, "gemini_api_key")
    if not api_key:
        return ("Gemini API key is not configured, Master.", [])

    from google import genai
    from google.genai import types
    import json

    # Preferred model order (free tier optimized)
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]

    client = genai.Client(api_key=api_key)

    # Convert our standard JSON schema to Gemini Tools
    gemini_tools = [{"function_declarations": [t["function"] for t in _active_tools_schema(config)]}]

    # Convert our generic history to Gemini SDK format
    gemini_history = []
    for turn in history:
        gemini_history.append(
            types.Content(
                role=turn["role"],
                parts=[types.Part.from_text(text=turn["parts"][0]["text"])]
            )
        )

    # Filter out empty turns or consecutive same-role turns to avoid SDK crash
    cleaned_history = []
    for item in gemini_history:
        text_content = item.parts[0].text.strip()
        if not text_content:
            continue
            
        if cleaned_history and cleaned_history[-1].role == item.role:
            cleaned_history[-1].parts[0].text += f"\n\n{text_content}"
        else:
            cleaned_history.append(item)

    if cleaned_history and cleaned_history[-1].role == "user":
        last_user = cleaned_history.pop()
        text = f"{last_user.parts[0].text}\n\n{text}"

    last_err = None
    for model_name in models_to_try:
        try:
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    tools=gemini_tools,
                ),
                history=cleaned_history
            )
            
            # ReAct Loop
            max_loops = 5
            executed_tools_meta = []
            response = chat.send_message(text)
            
            for loop_idx in range(max_loops):
                parsed_tools = []
                text_response = ""
                
                if response and response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.function_call:
                            tool_name = part.function_call.name
                            args_dict = dict(part.function_call.args)
                            if tool_name == "mizune_response":
                                if not text_response:
                                    text_response = args_dict.get("spoken_text", "")
                                actions_list = args_dict.get("actions", [])
                                if actions_list:
                                    for action in actions_list:
                                        action_type = action.get("action_type", "")
                                        action_arg = action.get("action_arg", "")
                                        if action_type and action_type != "none":
                                            t_args = {}
                                            if action_type in ["open_app", "close_app"]: t_args = {"app_name": action_arg}
                                            elif action_type == "take_note": t_args = {"note_text": action_arg}
                                            elif action_type == "execute_skill": t_args = {"skill_name": action_arg, "args": ""}
                                            parsed_tools.append({"name": action_type, "args": t_args})
                            else:
                                parsed_tools.append({"name": tool_name, "args": args_dict})
                                
                        elif part.text and not text_response:
                            cleaned_text = part.text.strip()
                            if cleaned_text not in ["}", "{", "```json", "```"]:
                                text_response = cleaned_text
                
                if not parsed_tools:
                    if not text_response:
                        text_response = "Done!"
                    if executed_tools_meta:
                        from .trajectory_logger import trajectory_logger
                        trajectory_logger.log_trajectory(text, history, executed_tools_meta, text_response)
                    if model_name != models_to_try[0]:
                        log_info(f"[AI] Gemini: Successfully fell back to {model_name}")
                    return (text_response, [])
                
                # Execute tools via the shared dispatcher
                tool_responses = []
                fast_track_results = []
                log_info(f"[AI] Gemini requested {len(parsed_tools)} native tool calls. Executing...")
                for t in parsed_tools:
                    tool_name = t["name"]
                    args = t["args"]
                    tool_result = execute_tool_call(tool_name, args, config)

                    executed_tools_meta.append({"name": tool_name, "args": args})
                    
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": str(tool_result)}
                        )
                    )
                    fast_track_results.append(str(tool_result))
                
                FAST_TRACK_TOOLS = ["schedule_task", "open_app", "close_app", "message_whatsapp", "execute_skill", "notify_master", "play_music", "remote_device_command"]
                all_fast_track = all(t["name"] in FAST_TRACK_TOOLS for t in parsed_tools)
                
                if all_fast_track and parsed_tools:
                    fast_response = " ".join(fast_track_results)
                    if not fast_response: fast_response = "Action completed."
                    
                    if executed_tools_meta:
                        from .trajectory_logger import trajectory_logger
                        trajectory_logger.log_trajectory(text, history, executed_tools_meta, fast_response)
                        
                    log_info("[AI] Fast-tracking response (bypassing Trip 2 to model).")
                    return (fast_response, [])

                response = chat.send_message(tool_responses)
            
            return (text_response, [])
                
        except Exception as e:
            err_str = str(e).lower()
            last_err = e
            # Quota/rate/auth errors are keyed to the whole Google project — every model
            # in models_to_try shares the same exhausted quota, so retrying them is pure
            # latency waste. Re-raise immediately and let the outer cascade switch provider.
            if "429" in err_str or "quota" in err_str or "exhausted" in err_str or "rate" in err_str or "401" in err_str or "resource_exhausted" in err_str:
                log_info(f"[AI] Gemini quota/rate exhausted on {model_name}; escalating to cascade.")
                raise e
            # A per-model outage (503/500) is worth trying the next model in the list.
            if "503" in err_str or "500" in err_str:
                log_info(f"[AI] Gemini: {model_name} unavailable ({err_str[:40]}), trying next model...")
                continue
            raise e

    if last_err:
        raise last_err
    return ("I'm having trouble thinking right now.", [])

def _groq_response(text: str, history: list, system_prompt: str, config: dict, ws_broadcast_func=None) -> tuple:
    """Fetch response from Groq (Llama/Mixtral). Returns (text, tool_calls)."""
    api_key = get_api_key(config, "groq_api_key")
    if not api_key:
        return ("Groq API key is not configured, Master.", [])
        
    try:
        from openai import OpenAI
        import json
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=10.0, # fast failover — the cascade is the retry mechanism
            max_retries=0  # the provider cascade IS the retry mechanism
        )
        
        groq_system = system_prompt + (
            "\n\nCRITICAL TOOL CALLING RULE: You must use the built-in JSON tool calling API perfectly. "
            "DO NOT output XML tags like <function=...>. DO NOT embed JSON inside the tool 'name' field. "
            "The tool 'name' must be exactly the string name of the tool (e.g. 'open_app')."
        )
        
        messages = [{"role": "system", "content": groq_system}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        messages.append({"role": "user", "content": text})
        
        model = config.get("groq_model", "llama-3.3-70b-versatile")
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=256,
                tools=_active_tools_schema(config),
                tool_choice="auto",
                parallel_tool_calls=False
            )
        except Exception as e:
            if "tool_use_failed" in str(e) or "400" in str(e):
                log_info("[AI] LLaMA-3 hallucinatory tool call detected (400 Bad Request). Retrying WITHOUT tools...")
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=256
                )
            else:
                raise e
                
        msg = response.choices[0].message
        
        # Check for hallucinated tool calls embedded in text
        if not msg.tool_calls and msg.content and "[function=" in msg.content:
            import re
            class DummyTool:
                def __init__(self, n, a):
                    self.name = n
                    self.arguments = a
            class DummyCall:
                def __init__(self, t):
                    self.function = t
                    self.id = "call_hallucinated"
            
            msg.tool_calls = []
            for match in re.finditer(r"\[function=([^\]]+)\](\{.*?\})", msg.content):
                msg.tool_calls.append(DummyCall(DummyTool(match.group(1), match.group(2))))
            msg.content = re.sub(r"\[function=[^\]]+\]\{.*?\}", "", msg.content).strip()
            
        messages.append(msg)

        max_loops = 5
        executed_tools = []
        
        for _ in range(max_loops):
            if not msg.tool_calls:
                break

            log_info(f"[AI] Model requested {len(msg.tool_calls)} native tool calls. Executing...")

            round_tool_names = []
            round_results = []
            for t in msg.tool_calls:
                tool_name = t.function.name
                round_tool_names.append(tool_name)
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                executed_tools.append({"name": tool_name, "args": args})
                tool_result = execute_tool_call(tool_name, args, config)

                # Feed the tool result back into the LLM context!
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.id,
                    "content": tool_result
                })
                round_results.append(str(tool_result))

            # FAST-TRACK: if every tool this round was a terminal action (send message,
            # open app, schedule, notify...), there's nothing for the model to reason about.
            # Return the tool results directly and skip the second round-trip. This is what
            # keeps WhatsApp replies sub-second on the Groq path.
            FAST_TRACK_TOOLS = ["schedule_task", "open_app", "close_app", "message_whatsapp", "execute_skill", "notify_master", "play_music", "remote_device_command"]
            if round_tool_names and all(n in FAST_TRACK_TOOLS for n in round_tool_names):
                fast_response = " ".join(r for r in round_results if r) or "Action completed."
                if executed_tools:
                    from .trajectory_logger import trajectory_logger
                    trajectory_logger.log_trajectory(text, history, executed_tools, fast_response)
                log_info("[AI] Groq fast-tracking response (bypassing 2nd round-trip).")
                return (fast_response, [])

            # Request next generation with tool results included
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=256,
                    tools=_active_tools_schema(config),
                    tool_choice="auto",
                    parallel_tool_calls=False
                )
            except Exception as e:
                if "tool_use_failed" in str(e) or "400" in str(e):
                    log_info("[AI] Groq hallucinated on loop. Forcing text summary...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=256
                    )
                else:
                    raise e
                    
            msg = response.choices[0].message
            messages.append(msg)

        text_response = msg.content or "Done, Master!"
        
        # Clean up artefacts via shared helper
        import re
        text_response = _clean_final_text(text_response)
        
        if executed_tools:
            from .trajectory_logger import trajectory_logger
            trajectory_logger.log_trajectory(text, history, executed_tools, text_response)

        # Return empty list for parsed_tools because we executed them internally in the ReAct loop
        return (text_response, [])
    except Exception as e:
        log_info(f"[AI] Groq Error: {e}")
        raise e

def _ollama_response(text: str, history: list, system_prompt: str, config: dict) -> tuple:
    """Fetch response from completely local Ollama instance. Returns (text, tool_calls)."""
    try:
        from openai import OpenAI
        import json
        client = OpenAI(
            api_key="ollama", # API key is not required for local Ollama
            base_url="http://localhost:11434/v1",
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        messages.append({"role": "user", "content": text})
        
        model = config.get("ollama_model", "llama3")
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=256,
            tools=_active_tools_schema(config),
            tool_choice={"type": "function", "function": {"name": "mizune_response"}}
        )
        msg = response.choices[0].message
        
        parsed_tools = []
        text_response = ""
        
        if msg.tool_calls:
            for t in msg.tool_calls:
                if t.function.name == "mizune_response":
                    try:
                        args = json.loads(t.function.arguments)
                        text_response = args.get("spoken_text", "")
                        action_type = args.get("action_type", "none")
                        action_arg = args.get("action_arg", "")
                        
                        if action_type != "none":
                            tool_args = {}
                            if action_type in ["open_app", "close_app"]:
                                tool_args = {"app_name": action_arg}
                            elif action_type == "take_note":
                                tool_args = {"note_text": action_arg}
                            elif action_type == "execute_skill":
                                tool_args = {"skill_name": action_arg, "args": ""}
                            parsed_tools.append({"name": action_type, "args": tool_args})
                    except Exception as e:
                        log_info(f"[AI] Error parsing local tool args: {e}")
                        
        if not text_response:
            text_response = msg.content or "Okay Master!"
            
        # Clean up any residual hallucinated XML tags from LLaMA 3 so she doesn't speak them aloud
        import re
        text_response = _clean_final_text(text_response)

        return (text_response, parsed_tools)
    except Exception as e:
        log_info(f"[AI] Local Ollama Error: {e}")
        return (f"Local Ollama failed. Is Ollama running on port 11434? Error: {e}", [])


def _openai_response(text: str, history: list, system_prompt: str, config: dict) -> str:
    """Fetch response from OpenAI."""
    api_key = get_api_key(config, "openai_api_key")
    if not api_key:
        return "OpenAI API key is not configured, Master."
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=10.0)
        
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        if text.strip():
            messages.append({"role": "user", "content": text})
            
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast default
            messages=messages,
            temperature=0.7,
        )
        return (response.choices[0].message.content, [])
    except ImportError:
        return ("OpenAI package is not installed. Run: pip install openai", [])


def _nvidia_response(text: str, history: list, system_prompt: str, config: dict, ws_broadcast_func=None) -> tuple:
    """Fetch response from NVIDIA NIM with full tool support."""
    api_key = get_api_key(config, "nvidia_api_key")
    model = config.get("nvidia_model", "meta/llama-3.1-70b-instruct")
    
    if not api_key:
        return ("NVIDIA API key is not configured, Master.", [])
        
    try:
        from openai import OpenAI
        import json
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            timeout=10.0, # Fast failover to prevent hanging!
            max_retries=0  # the provider cascade IS the retry mechanism
        )
        
        nvidia_system = system_prompt + (
            "\n\nCRITICAL TOOL CALLING RULE: You must use the built-in JSON tool calling API perfectly to answer requests. "
            "DO NOT output XML tags like <function=...>. DO NOT embed JSON inside the tool 'name' field. "
            "The tool 'name' must be exactly the string name of the tool (e.g. 'open_app'). "
            "If the user asks you to perform a task, you MUST select a tool. Do NOT answer with plain text if a tool applies."
        )
        
        messages = [{"role": "system", "content": nvidia_system}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        if text.strip():
            messages.append({"role": "user", "content": text})
            
        model_name = config.get("nvidia_model", "meta/llama-3.1-70b-instruct")
        max_loops = 5
        executed_tools_meta = []
        
        # Determine if we must FORCE a tool (if the ManagerAgent injected a directive)
        t_choice = "auto"
        if "[SYSTEM: YOU MUST USE THE" in text:
            t_choice = "required"
            
        for _ in range(max_loops):
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
                tools=_active_tools_schema(config),
                tool_choice=t_choice,
                timeout=10.0
            )
            
            msg = response.choices[0].message
            
            # Check for hallucinated tool calls embedded in text
            if not msg.tool_calls and msg.content and "[function=" in msg.content:
                import re
                class DummyTool:
                    def __init__(self, n, a):
                        self.name = n
                        self.arguments = a
                class DummyCall:
                    def __init__(self, t):
                        self.function = t
                        self.id = "call_hallucinated"
                
                msg.tool_calls = []
                for match in re.finditer(r"\[function=([^\]]+)\](\{.*?\})", msg.content):
                    msg.tool_calls.append(DummyCall(DummyTool(match.group(1), match.group(2))))
                msg.content = re.sub(r"\[function=[^\]]+\]\{.*?\}", "", msg.content).strip()
            
            messages.append(msg)
            
            if not msg.tool_calls:
                break
                
            log_info(f"[AI] Model requested {len(msg.tool_calls)} native tool calls. Executing...")
            for t in msg.tool_calls:
                tool_name = t.function.name
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                tool_result = execute_tool_call(tool_name, args, config, background_python=True)

                executed_tools_meta.append({"name": tool_name, "args": args})
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.id,
                    "name": tool_name,
                    "content": str(tool_result)
                })
                
            # After executing tools in NVIDIA NIM, force it to summarize the result as text in the next loop!
            t_choice = "none" # Disables tools for the next iteration so it HAS to speak!
                
        final_text = _clean_final_text(msg.content or "")

        if executed_tools_meta:
            from .trajectory_logger import trajectory_logger
            trajectory_logger.log_trajectory(text, history, executed_tools_meta, final_text)
            
        # Return empty tools list to prevent processor from double executing
        return (final_text, [])
        
    except ImportError:
        return ("OpenAI package is not installed. Run: pip install openai", [])
    except Exception as e:
        log_info(f"[AI] Nvidia NIM error: {e}")
        raise e


def _anthropic_response(text: str, history: list, system_prompt: str, config: dict) -> str:
    """Fetch response from Anthropic Claude."""
    api_key = get_api_key(config, "anthropic_api_key")
    if not api_key:
        return "Anthropic API key is not configured, Master."
        
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, timeout=10.0)
        
        messages = []
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                # Avoid consecutive same-role messages
                if messages and messages[-1]["role"] == role:
                    messages[-1]["content"] += f"\n\n{content}"
                else:
                    messages.append({"role": role, "content": content})
                    
        if text.strip():
            if messages and messages[-1]["role"] == "user":
                 messages[-1]["content"] += f"\n\n{text}"
            else:
                messages.append({"role": "user", "content": text})
            
        response = client.messages.create(
            model="claude-3-haiku-20240307", # Fast default
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            temperature=0.7,
        )
        return (response.content[0].text, [])
    except ImportError:
        return ("Anthropic package is not installed. Run: pip install anthropic", [])


def _openrouter_response(text: str, history: list, system_prompt: str, config: dict, ws_broadcast_func=None) -> tuple:
    """Fetch response from OpenRouter with full tool support."""
    api_key = get_api_key(config, "openrouter_api_key")
    model = config.get("openrouter_model", "anthropic/claude-3-haiku")
    if not api_key:
        return ("OpenRouter API key is not configured, Master.", [])
        
    try:
        from openai import OpenAI
        import json
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=10.0,
            max_retries=0,  # the provider cascade IS the retry mechanism
        )
        
        openrouter_system = system_prompt + (
            "\n\nCRITICAL TOOL CALLING RULE: You must use the built-in JSON tool calling API perfectly to answer requests. "
            "DO NOT output XML tags like <function=...>. DO NOT embed JSON inside the tool 'name' field. "
            "The tool 'name' must be exactly the string name of the tool (e.g. 'open_app'). "
            "If the user asks you to perform a task, you MUST select a tool. Do NOT answer with plain text if a tool applies."
        )
        
        messages = [{"role": "system", "content": openrouter_system}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        if text.strip():
            messages.append({"role": "user", "content": text})
            
        max_loops = 5
        executed_tools = []
        
        for _ in range(max_loops):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
                tools=_active_tools_schema(config),
                tool_choice="auto",
                timeout=10.0,
                extra_headers={
                    "HTTP-Referer": "https://github.com/rushikeshgoud19/MY-AI",
                    "X-Title": "Mizune AI Desktop"
                }
            )
            
            if not getattr(response, 'choices', None) or len(response.choices) == 0:
                raise ValueError("OpenRouter returned an empty or invalid response.")
                
            msg = response.choices[0].message
            
            # Check for hallucinated tool calls embedded in text
            if not msg.tool_calls and msg.content and "[function=" in msg.content:
                import re
                class DummyTool:
                    def __init__(self, n, a):
                        self.name = n
                        self.arguments = a
                class DummyCall:
                    def __init__(self, t):
                        self.function = t
                        self.id = "call_hallucinated"
                
                msg.tool_calls = []
                for match in re.finditer(r"\[function=([^\]]+)\](\{.*?\})", msg.content):
                    msg.tool_calls.append(DummyCall(DummyTool(match.group(1), match.group(2))))
                msg.content = re.sub(r"\[function=[^\]]+\]\{.*?\}", "", msg.content).strip()
            
            messages.append(msg)
            
            if not msg.tool_calls:
                break
                
            log_info(f"[AI] Model requested {len(msg.tool_calls)} native tool calls. Executing...")
            for t in msg.tool_calls:
                tool_name = t.function.name
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                tool_result = execute_tool_call(tool_name, args, config, background_python=True)

                executed_tools.append({"name": tool_name, "args": args})
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.id,
                    "name": tool_name,
                    "content": str(tool_result)
                })
                
        final_text = _clean_final_text(msg.content or "")

        # Return [] — these tools were ALREADY executed inline above. Returning them
        # made processor.py's tool loop run every action a SECOND time (bypassing the
        # dedup guard, which only covers execute_tool_call). Root cause of the historic
        # "two Blender downloads for one request". Only Ollama may return unexecuted
        # parsed_tools for the processor to run.
        return (final_text, [])

    except ImportError:
        return ("OpenAI package is not installed (required for OpenRouter). Run: pip install openai", [])


def _opencode_response(text: str, history: list, system_prompt: str, config: dict) -> str:
    """Fetch response from OpenCode (Llama-based local or API)."""
    api_key = get_api_key(config, "opencode_api_key")
    if not api_key:
        return "OpenCode API key is not configured, Master."
        
    try:
        from openai import OpenAI
        # Assuming opencode uses OpenAI-compatible API format
        client = OpenAI(
            base_url="https://api.opencode.so/v1", # Adjust if opencode URL is different
            api_key=api_key,
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        if text.strip():
            messages.append({"role": "user", "content": text})
            
        response = client.chat.completions.create(
            model="default", # Adjust as needed
            messages=messages,
            temperature=0.7,
        )
        return (response.choices[0].message.content, [])
    except ImportError:
        return ("OpenAI package is not installed. Run: pip install openai", [])
