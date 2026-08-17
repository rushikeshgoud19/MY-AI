"""
AI LLM routing and response generation module for Mizune.
"""
import os
import logging
import time

__all__ = ["get_ai_response", "save_latest_image", "describe_image"]


from .config import log_info

logger = logging.getLogger("mizune.ai")

_LATEST_IMAGE_B64 = None

def save_latest_image(b64_str: str):
    global _LATEST_IMAGE_B64
    if not b64_str:
        return
    _LATEST_IMAGE_B64 = b64_str
    try:
        os.makedirs(".data", exist_ok=True)
        with open(os.path.join(".data", "last_image.b64"), "w", encoding="utf-8") as f:
            f.write(b64_str)
    except Exception as e:
        log_info(f"[VISION] Error saving last_image.b64: {e}")

def _get_latest_image() -> str:
    global _LATEST_IMAGE_B64
    if _LATEST_IMAGE_B64:
        return _LATEST_IMAGE_B64
    path = os.path.join(".data", "last_image.b64")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _LATEST_IMAGE_B64 = f.read().strip()
                return _LATEST_IMAGE_B64
        except Exception:
            pass
    return ""

def _process_image_b64(b64_str: str) -> tuple:
    """Ensure image base64 is <= 4MB, downscale if larger. Returns (b64_str, mime_type)."""
    import base64
    from io import BytesIO
    try:
        from PIL import Image
    except ImportError:
        Image = None

    mime_type = "image/jpeg"
    if b64_str.startswith("data:"):
        header, b64_str = b64_str.split(",", 1)
        if "image/png" in header:
            mime_type = "image/png"
        elif "image/webp" in header:
            mime_type = "image/webp"

    try:
        img_bytes = base64.b64decode(b64_str)
        if len(img_bytes) > 4 * 1024 * 1024 and Image is not None:
            img = Image.open(BytesIO(img_bytes))
            img.thumbnail((1600, 1600))
            buf = BytesIO()
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()
            mime_type = "image/jpeg"
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        log_info(f"[VISION] Image resize error: {e}")
        
    return b64_str, mime_type

def describe_image(b64: str, prompt: str = None, config: dict = None) -> str:
    """Analyze image using Gemini multimodal REST API via urllib."""
    if not b64:
        return "No image found to analyze, Master."
    config = config or {}
    gkey = get_api_key(config, "gemini_api_key")
    if not gkey:
        return "Vision unavailable: no Gemini key configured, Master."
    
    prompt_text = prompt or "Describe what you see in this image in detail, Master."
    clean_b64, mime_type = _process_image_b64(b64)
    
    import urllib.request as _ur, json as _json
    body = _json.dumps({
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": clean_b64}},
                {"text": prompt_text}
            ]
        }]
    }).encode()
    
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            req = _ur.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": gkey})
            res_data = _json.loads(_ur.urlopen(req, timeout=30).read())
            text = "".join(
                p.get("text", "")
                for p in res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            ).strip()
            if text:
                return text
        except Exception as e:
            last_err = e
            continue
            
    return f"I couldn't analyze the image, Master: {last_err}"


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
    {
        "type": "function",
        "function": {
            "name": "check_legit",
            "description": "Analyze an email, job offer, recruitment message, or payment request for fraud, scams, or security threats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The message, email text, job description, or URL to analyze."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "index_files",
            "description": "Index files from a local directory on Master's laptop into Mizune's knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "description": "The local folder path to index (e.g. 'Desktop' or 'Documents')."},
                    "pattern": {"type": "string", "description": "Optional file pattern to filter by (e.g. '*.pdf' or '*.txt')."}
                },
                "required": ["root"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "see_image",
            "description": "Analyze the most recent image sent by Master (from camera or upload) and answer questions about it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Specific question about the image (e.g. 'what does this say?')."}
                },
                "required": []
            }
        }
    },
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
            "description": ("Send a WhatsApp message. If Master gives a PHONE NUMBER, pass that "
                            "number as `contact` — never a name, and never 'Master'. Passing "
                            "'Master'/'me' sends to Master's OWN chat, so a message meant for "
                            "someone else silently goes nowhere."),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Phone number (preferred, e.g. '916302554067') if Master gave one, otherwise the exact contact or group name. Only use 'Master'/'me' when Master genuinely wants the message sent to himself."},
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
            "name": "start_mission",
            "description": "Start a MISSION: a multi-step goal Mizune plans, executes step-by-step (possibly over hours/days), VERIFIES each step objectively, and reports progress to Master. Use when Master gives a big/compound goal ('mission: ...', 'plan and do X', anything needing several dependent actions).",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The full goal in Master's words."}
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mission_status",
            "description": "Show the status of recent missions (steps done/total). Use when Master asks how a mission is going.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_mission",
            "description": "Cancel the latest active mission. Use when Master says to stop/cancel the mission.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agent_orchestra",
            # Deliberately narrow. A tribunal is ~11 model calls and ~15 seconds, so
            # the description spends most of its words saying when NOT to reach for it.
            # The fast-path ("orchestra: ...") is how Master demands one explicitly;
            # this tool exists only so a genuinely contested question can escalate
            # without him having to know the prefix.
            "description": (
                "Convene the Agent Orchestra: four advocates argue the question on "
                "different models under different stances, and Alucard judges them. "
                "EXPENSIVE — about 11 model calls and 15 seconds. Use ONLY when the "
                "question is genuinely contested: a real trade-off, a design choice, "
                "an ethical judgement, or something where thoughtful people disagree "
                "AND getting it wrong matters. NEVER for facts, arithmetic, chitchat, "
                "anything you already know, or anything urgent. If in doubt, answer "
                "normally instead. Tell Master you are convening it before you do."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The contested question to put to the panel, stated in full."}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "night_shift",
            "description": "Queue an overnight autonomous work shift, or check it. Use when Master says 'tonight work on...', 'overnight, do...', 'while I sleep...', or 'shift status/report'. Each task becomes a verified mission run silently overnight on a spare provider; ONE honest report arrives at 7:40 AM. Never for anything that sends/deletes/pays — those need him awake.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "'queue' to schedule tonight's tasks, 'status' for the current queue, 'report' for the latest morning report."},
                    "tasks": {"type": "array", "items": {"type": "string"}, "description": "For 'queue': the ordered list of tasks to work through overnight, each in Master's words."},
                    "label": {"type": "string", "description": "Optional short name for the shift."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "learn",
            "description": "LEARN and permanently remember something for Master's knowledge base. Pass a URL (article or YouTube link) or a chunk of text. Use when Master says 'learn this', 'remember this', 'save this to your knowledge', or shares a link he wants you to study. She fetches, summarizes, and stores it forever.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "A URL, or the text to learn."}
                },
                "required": ["source"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_knowledge",
            "description": "Search Master's compounding knowledge base for things you've LEARNED before. Use when he asks 'what do you know about X', 'what did I teach you about X', or 'from what you've learned...'. Empty query lists everything learned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic keywords to search for (empty = list all)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Fetch a URL and return its readable text. Use when Master shares a link or asks you to read/summarize an article or page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to read."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web (DuckDuckGo) and get the top results with snippets. USE THIS for anything current: news, prices, releases, weather in other cities, sports scores, 'what is X' about recent things. Then answer Master using the results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
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
            "description": "Execute actions on Master's other online devices — ALWAYS use this (never local tools) when Master says 'on my laptop' or 'on my phone'. This IS how you control his phone (device='phone') and laptop (device='laptop'). Laptop: install_app, download_file, open_app, open_url, run_command (args {command} — Windows shell, quick commands only), run_task (args {command, label?} — LONG commands run in background; you'll automatically report the outcome to Master when done), claude_task (args {task, project?, label?} — delegate coding/improvement work to Claude on the laptop, runs headless in background with auto-report; USE THIS for 'improve/fix/build X on my laptop'), claude_code (args {task, project?} — opens a VISIBLE Claude terminal Master can watch). Phone: open_app (args {app_name}), open_url (args {url}), read_screen (no args — returns visible buttons/fields so you can SEE the screen before tapping), tap (args {text}), type (args {text} — into focused field, for forms), press (args {key: back|home|recents}), scroll (args {direction: up|down}), notify (args {title, message}), speak (args {text}). For multi-step phone tasks, call in sequence and use read_screen between steps to see what's there (open app → read_screen → tap → type → tap).",
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
            "name": "read_whatsapp",
            "description": ("Read Master's recent WhatsApp messages, including ones you never replied to. "
                            "Use when Master refers to something someone sent him — 'the song Sarthak sent me', "
                            "'what did Owais say', 'the link Pranith shared'. If the result contains a link and "
                            "Master wants it played, pass that exact link to play_music as `query` — never "
                            "re-search for the song by name."),
            "parameters": {
                "type": "object",
                "properties": {
                    "sender": {"type": "string", "description": "Contact name or a fragment of it, e.g. 'Sarthak'."},
                    "contains": {"type": "string", "description": "Only messages containing this text, e.g. 'http' for links."},
                    "limit": {"type": "integer", "description": "How many messages (default 5, max 20)."},
                    "hours": {"type": "integer", "description": "Only messages from the last N hours."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_music",
            "description": "Control whatever is playing on Master's phone: pause, resume/play, or skip to the next track. Use when Master says 'pause the music', 'resume', 'next song', 'skip this'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["pause", "resume", "next"], "description": "What to do with playback."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_my_phone",
            "description": "Help Master locate his phone: fires a burst of loud alert notifications on it. Use when Master says he can't find / lost his phone.",
            "parameters": {"type": "object", "properties": {}}
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
            "description": "Gmail + Google Calendar. 'list_emails' shows recent emails; 'get_todays_calendar' shows today's events; 'list_upcoming' shows upcoming events; 'create_event' SCHEDULES a real calendar event (use after Master tells you the time — args: title, start_iso like '2026-07-16T15:00:00', optional end_iso, description); 'delete_event' CANCELS an upcoming event by name (args: title).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list_emails", "get_todays_calendar", "list_upcoming", "create_event", "delete_event", "read_unread_emails", "get_morning_briefing"], "description": "What to do"},
                    "count": {"type": "number", "description": "For list_emails/list_upcoming: how many to show."},
                    "title": {"type": "string", "description": "For create_event: the meeting/event title."},
                    "start_iso": {"type": "string", "description": "For create_event: start datetime ISO, e.g. '2026-07-16T15:00:00'."},
                    "end_iso": {"type": "string", "description": "For create_event: optional end datetime ISO (defaults to +1 hour)."},
                    "description": {"type": "string", "description": "For create_event: optional details."}
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

def _capability_lines(config: dict) -> str:
    """One '- name: description' line per tool she ACTUALLY has, built from the live schema.

    Written because the hardcoded version of this list drifted and started causing false
    refusals: a model that follows the prompt literally reads a short list, does not find
    'reminders' on it, and honestly answers "I don't have the ability to set reminders" —
    while holding schedule_task. Generating it keeps the prompt and reality in sync by
    construction rather than by remembering to update two places.
    """
    lines = []
    for t in _active_tools_schema(config):
        fn = t.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        desc = (fn.get("description") or "").strip().split(". ")[0].split("\n")[0][:110]
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines) + "\n"


# Arg hints for phone actions. THIS IS NOT THE CAPABILITY LIST — the phone's own
# registration decides which of these are offered. A name here that the phone never
# registers is simply never shown; a name the phone registers without an entry here is
# still shown, bare. See _remote_device_tool().
_PHONE_ACTION_HINTS = {
    "open_app": "open_app (args {app_name})",
    "open_url": "open_url (args {url})",
    "read_screen": "read_screen (no args — returns visible buttons/fields so you can SEE the screen before tapping)",
    "tap": "tap (args {text})",
    "type": "type (args {text} — into focused field, for forms)",
    "press": "press (args {key: back|home|recents})",
    "scroll": "scroll (args {direction: up|down})",
    "notify": "notify (args {title, message})",
    "speak": "speak (args {text})",
    "media_play": "media_play (no args — sends the play key to the active media session)",
    "media_pause": "media_pause (no args)",
    "media_next": "media_next (no args)",
}


def _remote_device_tool(tool: dict) -> dict:
    """Rewrite remote_device_command's phone actions from the LIVE device registry.

    The phone's capability list used to exist in three places — the app's socket
    registration, this tool description, and the executor's `when(action)` — and all
    three disagreed: the phone executed tap/type/scroll/read_screen while registering
    none of them and the description advertised its own set. Same failure mode, and same
    fix, as _capability_lines() above: derive it, don't restate it.

    Falls back to the static description if the phone is offline or anything goes wrong,
    so a registry hiccup can never strip the brain of its laptop tooling.
    """
    try:
        from .device_registry import device_registry
        phone = device_registry.list_devices().get("phone")
        if not phone:
            return tool
        caps = [c for c in (phone.get("capabilities") or []) if c]
        if not caps:
            return tool
        import copy
        out = copy.deepcopy(tool)
        fn = out["function"]
        phone_line = "Phone: " + ", ".join(_PHONE_ACTION_HINTS.get(c, c) for c in caps) + "."
        # Replace everything from "Phone:" onward, keeping the laptop half verbatim.
        head = fn["description"].split("Phone:")[0]
        description = head + phone_line
        if "read_screen" in caps:
            description += (
                " For multi-step phone tasks, call in sequence and use read_screen "
                "between steps to see what's there (open app → read_screen → tap → "
                "type → tap)."
            )
        fn["description"] = description
        fn["parameters"]["properties"]["action"]["description"] = (
            "Laptop: download_file, open_app, open_url, run_command, run_task, "
            "claude_task, claude_code. Phone (live, only these work right now): "
            + ", ".join(caps) + "."
        )
        return out
    except Exception:
        return tool


def _active_tools_schema(config: dict):
    """Return TOOLS_SCHEMA, minus local-only tools when running in cloud mode."""
    tools = TOOLS_SCHEMA
    try:
        from .config import is_cloud_mode
        if is_cloud_mode(config):
            tools = [t for t in tools
                     if t.get("function", {}).get("name") not in _LOCAL_ONLY_TOOLS]
    except Exception:
        pass
    return [
        _remote_device_tool(t) if t.get("function", {}).get("name") == "remote_device_command" else t
        for t in tools
    ]


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
    # Weak fallback models sometimes EMIT tool calls as text instead of using the
    # function API (e.g. `{ "tool": "x", "data": {...} }`). Strip from the first such
    # block to the end so raw JSON never leaks to the user.
    text = _re.sub(r'\{\s*["\']?(tool|action|function)["\']?\s*:.*', '', text, flags=_re.DOTALL)
    text = text.strip()
    # Strip a dangling unmatched leading `{` or trailing `}` left after JSON removal
    text = _re.sub(r'^\{\s*', '', text)
    text = _re.sub(r'\s*\}$', '', text)
    return text.strip()


def _host_os_label() -> str:
    """Describe the machine the brain itself runs on, for prompt grounding.

    Without this the model assumed Windows — the capability text mentions "Master's PC" and
    the Windows registry, and the device context advertises a Windows laptop. A scheduled
    task then generated `r'C:\\Temp\\fix.txt'` / `os.getenv('TEMP')` while running on the
    Linux VM, so the file was written nowhere reachable and the task reported done with no
    effect (caught 2026-07-26 chasing a scheduled write that never appeared in /tmp).
    """
    import platform
    import sys as _sys
    if _sys.platform.startswith("linux"):
        return f"LINUX ({platform.system()} {platform.release()})"
    if _sys.platform.startswith("win"):
        return f"WINDOWS ({platform.system()} {platform.release()})"
    return f"{_sys.platform} ({platform.system()})"


def _recover_text_mode_tools(raw: str, config: dict) -> list:
    """Parse tool calls a model emitted as TEXT rather than via the function API.

    Handles the shapes weak/truncated replies actually produce:
        {"tool": "play_music", "data": {...}}        {"tool": "x", "args": {...}}
        {"name": "x", "parameters": {...}}           {"action": "x", "arguments": {...}}
        [function=x]{...}
    Returns [(tool_name, args_dict), ...] — only for tools that exist in TOOLS_SCHEMA, so a
    hallucinated tool name can never be dispatched. Never raises; on any doubt returns [].
    """
    import json as _json
    if not raw:
        return []
    known = {t["function"]["name"] for t in TOOLS_SCHEMA if isinstance(t, dict) and "function" in t}
    found: list = []

    # [function=name]{json}
    for m in _re.finditer(r"\[function=([\w.]+)\]\s*(\{.*?\})", raw, _re.DOTALL):
        name = m.group(1)
        if name in known:
            try:
                found.append((name, _json.loads(m.group(2))))
            except Exception:
                found.append((name, {}))

    # JSON objects carrying a tool name under any of the common keys. Scan brace-balanced
    # candidates so a nested args object doesn't truncate the match.
    for start in (i for i, c in enumerate(raw) if c == "{"):
        depth = 0
        for end in range(start, min(len(raw), start + 4000)):
            if raw[end] == "{":
                depth += 1
            elif raw[end] == "}":
                depth -= 1
                if depth == 0:
                    blob = raw[start:end + 1]
                    try:
                        obj = _json.loads(blob)
                    except Exception:
                        break
                    if not isinstance(obj, dict):
                        break
                    name = next((obj[k] for k in ("tool", "name", "action", "function")
                                 if isinstance(obj.get(k), str)), None)
                    args = next((obj[k] for k in ("data", "args", "parameters", "arguments",
                                                  "input") if isinstance(obj.get(k), dict)), {})
                    if name in known and not any(n == name for n, _ in found):
                        found.append((name, args))
                    break

    return found[:3]   # cap: a runaway reply must not fan out into many side effects


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
    "play_music", "control_music", "find_my_phone", "start_mission", "cancel_mission", "learn",
    "night_shift", "agent_orchestra",
}
_recent_tool_calls: dict = {}
_recent_tool_lock = _dedup_threading.Lock()


def _passthrough_music_url(query: str) -> str | None:
    """If `query` is already a link, return a playable url instead of searching.

    Friends share `youtube.com/watch?v=…`, `youtu.be/…`, `music.youtube.com/watch?v=…`
    (often with WhatsApp's `&si=` tracking suffix) and Spotify links. Re-searching the song
    by NAME is how you end up playing a cover or a slowed-reverb edit instead of the track
    someone actually sent. YouTube links are normalised onto music.youtube.com because that
    is what deep-link autoplays; anything else non-YouTube is handed over untouched.
    """
    import urllib.parse
    q = (query or "").strip().strip("<>")
    if not _re.match(r"^https?://", q, _re.IGNORECASE):
        return None
    try:
        parsed = urllib.parse.urlparse(q)
    except Exception:
        return None
    host = (parsed.netloc or "").lower().lstrip("www.")

    vid = None
    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        vid = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
    elif host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0] or None

    if vid and _re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        # Drops WhatsApp's &si=... tracking tail, which YT Music does not need.
        return f"https://music.youtube.com/watch?v={vid}"
    return q  # some other music link (Spotify, an album page) — open it as-is


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


_URL_RE = _re.compile(r"https?://[^\s<>\"']+")


def _cortex_db_path() -> str | None:
    """Locate cortex.db — the WhatsApp message store. cwd differs between the VM
    (/home/azureuser) and a local run, so try both rather than assuming."""
    import os
    for p in ("cortex.db",
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cortex.db")):
        if os.path.exists(p):
            return p
    return None


def _read_whatsapp_messages(sender: str = None, contains: str = None,
                            limit=None, hours=None) -> str:
    """Read Master's recent WhatsApp messages from the cortex store.

    Every inbound message is ingested BEFORE the _should_reply gate, so this sees messages
    she never answered — which is the whole point: "play the song Sarthak sent me" refers to
    a message that was never addressed to her.

    Read-only. Returns a compact, quotable list; any links are surfaced explicitly so the
    model can hand one straight to play_music instead of inventing a search query.
    """
    import sqlite3
    path = _cortex_db_path()
    if not path:
        return "I can't find my WhatsApp message store right now, Master."

    try:
        limit = max(1, min(int(limit or 5), 20))
    except (TypeError, ValueError):
        limit = 5

    where, params = [], []
    if sender:
        # Contact names are stored as WhatsApp shows them ("Sarthak Kumar Nashine"),
        # so match on a fragment — Master says "Sarthak".
        where.append("sender_name LIKE ?")
        params.append(f"%{str(sender).strip()}%")
    if contains:
        where.append("text LIKE ?")
        params.append(f"%{str(contains).strip()}%")
    if hours:
        try:
            where.append("timestamp > ?")
            params.append(time.time() - float(hours) * 3600)
        except (TypeError, ValueError):
            where.pop(), params.pop()
    params.append(limit)

    sql = ("SELECT sender_name, text, timestamp, media_type FROM whatsapp_messages "
           + ("WHERE " + " AND ".join(where) + " " if where else "")
           + "ORDER BY timestamp DESC LIMIT ?")
    try:
        con = sqlite3.connect(path)
        rows = list(con.execute(sql, params))
        con.close()
    except Exception as e:
        log_info(f"[WHATSAPP READ] query failed: {e}")
        return "I couldn't read my message history just now, Master."

    if not rows:
        who = f" from {sender}" if sender else ""
        return f"I don't have any messages{who} matching that, Master."

    lines, links = [], []
    now = time.time()
    for name, text, ts, media in rows:
        text = (text or "").strip()
        age = now - (ts or now)
        when = (f"{int(age // 60)}m ago" if age < 3600 else
                f"{int(age // 3600)}h ago" if age < 86400 else
                f"{int(age // 86400)}d ago")
        found = _URL_RE.findall(text)
        links.extend(found)
        body = text[:200] if text else f"[{media or 'media'}]"
        lines.append(f"- {name or 'Unknown'} ({when}): {body}")

    # Name the filter that was actually applied. If the caller's filter got dropped, this
    # says "from anyone" and the mistake is visible in the reply instead of silent.
    scope = f"from {sender}" if sender else "from anyone"
    if contains:
        scope += f" containing '{contains}'"
    out = f"Recent WhatsApp messages ({scope}):\n" + "\n".join(lines)
    if links:
        # Spelled out so the model passes the REAL link to play_music rather than
        # re-searching for the song by name and landing on a different track.
        out += "\n\nLinks in those messages (use one directly, do not search again):\n"
        for u in links[:5]:
            title = _youtube_title(u)
            out += f"- {u}" + (f"  [title: {title}]" if title else "") + "\n"
        # Observed live 2026-07-27: asked what song Sarthak sent, she invented
        # "Tisinj Napam by Gobindo and Basanti" out of a bare video id. A link is not a
        # title, and guessing one is a fabrication Master cannot check at a glance.
        out += ("NOTE: if a link has no [title:], you do NOT know what it is. Say Master was "
                "sent a link — never invent a song name or artist.")
    return out


def _youtube_title(url: str) -> str | None:
    """Real title for a YouTube link via oEmbed (no API key). Best-effort and short —
    supplying the truth is what stops the model inventing a song name."""
    import urllib.request, urllib.parse, json as _json
    if not _re.search(r"(youtube\.com|youtu\.be)", url, _re.IGNORECASE):
        return None
    try:
        api = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return (_json.loads(r.read().decode("utf-8", "ignore")).get("title") or "")[:120] or None
    except Exception as e:
        log_info(f"[WHATSAPP READ] oEmbed title lookup failed for {url[:60]}: {e}")
        return None


# Background utility calls (memory-worker seals, planner, reformatting — anything
# using system_prompt_override) must NEVER execute tools. Observed 2026-07-19: a
# seal job summarizing briefing chunks decided to message_whatsapp Master a fresh
# "Good morning" — 3 duplicate briefings at noon. get_ai_response sets this flag.
_bg_guard = _dedup_threading.local()

# Provider health for the circuit breaker: {provider: [failure epoch, ...]}
_provider_fails = {}
_CB_WINDOW = 600.0      # look back 10 minutes
_CB_THRESHOLD = 3       # 3 failures in that window ⇒ demote to last resort

# PER-MINUTE RATE-LIMIT COOLDOWN. Distinct from the circuit breaker: a provider with ONE
# key (cerebras) can't be rescued by key rotation, and a per-minute cap clears in ~60s. The
# circuit breaker needs 3 failures before demoting, so a burst of cascade traffic burned
# cerebras 10x in one night (VM logs 2026-07-26). Skip a rate-limited provider outright
# until its window resets, instead of paying a round-trip to be told 429 again.
_provider_cooldown: dict = {}
_RPM_COOLDOWN_SECONDS = 60.0


def _is_cooling(provider: str) -> bool:
    until = _provider_cooldown.get(provider, 0)
    return until > time.time()


def _mark_rate_limited(provider: str, err: str) -> None:
    """Cool a provider off when the error is a PER-MINUTE cap (not a daily cap — a daily
    cap won't clear in 60s, and the circuit breaker already handles that case)."""
    e = (err or "").lower()
    if "429" not in e and "rate" not in e and "too many" not in e:
        return
    if any(k in e for k in ("per day", "tpd", "daily", "per-day")):
        return
    _provider_cooldown[provider] = time.time() + _RPM_COOLDOWN_SECONDS
    log_info(f"[AI] {provider} hit a per-minute limit — cooling off "
             f"{_RPM_COOLDOWN_SECONDS:.0f}s instead of retrying it.")


# HB.2 PARALLEL TOOL CALLS. "What's my calendar + any unread mail + weather in Dubai?"
# used to run strictly one-after-another. Read-only tools have no ordering semantics,
# so when a round asks for 2+ of them we fan them out on threads and keep the results
# in the model's requested order. Side-effect tools (send, open, schedule, mission...)
# stay STRICTLY SEQUENTIAL — ordering and the dedup guard matter there.
_PARALLEL_SAFE = {
    "google_workspace", "web_search", "read_webpage", "recall_knowledge",
    "search_memory", "system_info", "mission_status", "read_screen",
}
_PARALLEL_MAX_WORKERS = 4


def execute_tools_batch(calls: list, config: dict, background_python: bool = False) -> list:
    """calls = [(tool_name, args), ...] → results in the SAME order."""
    if len(calls) <= 1:
        return [execute_tool_call(n, a, config, background_python) for n, a in calls]
    if not all(n in _PARALLEL_SAFE for n, _ in calls):
        return [execute_tool_call(n, a, config, background_python) for n, a in calls]

    log_info(f"[AI] Running {len(calls)} read-only tools IN PARALLEL: {[n for n, _ in calls]}")
    from concurrent.futures import ThreadPoolExecutor
    results = [None] * len(calls)

    def _run(i_call):
        i, (n, a) = i_call
        try:
            return i, execute_tool_call(n, a, config, background_python)
        except Exception as e:                       # never let one tool sink the batch
            return i, f"Error executing {n}: {e}"

    with ThreadPoolExecutor(max_workers=_PARALLEL_MAX_WORKERS) as pool:
        for i, res in pool.map(_run, list(enumerate(calls))):
            results[i] = res
    return results


def execute_tool_call(tool_name: str, args: dict, config: dict, background_python: bool = False) -> str:
    """Single tool dispatcher shared by every provider path (Gemini, Groq, NVIDIA, OpenRouter).

    Always returns a human-readable result string and never raises.
    Side-effect tools are deduplicated for _TOOL_DEDUP_TTL_SECONDS.
    """
    if getattr(_bg_guard, "no_tools", False):
        log_info(f"[GUARD] blocked tool '{tool_name}' from a background utility call")
        return f"(tool '{tool_name}' is disabled in background mode — just output the requested text)"
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
            if not app_name:
                return "Error: no app name given."
            # The cloud brain is HEADLESS (linux VM) — "open X" always means one of
            # Master's devices. Route to the laptop (or phone) node instead of lying
            # with a local launch that can't be seen. Local launch stays for the
            # desktop brain (win32).
            import sys as _sys
            if _sys.platform.startswith("linux"):
                from .device_registry import device_registry
                online = device_registry.list_devices()
                target = args.get("device") or ("laptop" if "laptop" in online else "phone" if "phone" in online else None)
                if not target:
                    return "None of your devices are online right now, Master — I can't open it here on the server."
                return device_registry.send_command(target, "open_app", {"app_name": app_name})
            launch_app(app_name)
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
            _wmsg = str(args.get("message", ""))
            # Truncation guard: some models cut the JSON arg at the first apostrophe
            # ("Good morning, Master! You" ← was "You've..."). Don't SEND fragments —
            # bounce them back so the model rewrites without apostrophes.
            #
            # NARROWED 2026-07-29. The old rule was "shorter than 45 chars and not ending in
            # punctuation", which is how people actually text: it rejected "I love you", "Hi",
            # "ok", "get lost", "happy birthday". Rushi hit it live trying to message his
            # brother, and the same bounce appears three times in the seals. Blocking a real
            # message is far worse than sending a rare fragment — the fragment is visible and
            # he resends; the block silently makes the whole feature useless.
            # So detect the ACTUAL signature instead: an apostrophe cut leaves the final
            # sentence as a lone contraction stem ("...Master! You"), not a short sentence.
            # "I love you" ends in the same word but is three words long, so it passes.
            _stripped = _wmsg.rstrip()
            # Two tiers, because the stems differ in how ambiguous they are.
            # NEVER_FINAL can't end an English sentence at all, so they mean a cut wherever
            # they appear. AMBIGUOUS_FINAL are perfectly good last words ("I love you",
            # "yes you can"), so they only signal a cut when the trailing sentence is that
            # single word alone — which is what an apostrophe cut actually leaves behind.
            _NEVER_FINAL = {"don", "won", "isn", "aren", "wasn", "weren", "couldn", "shouldn",
                            "wouldn", "didn", "doesn", "hasn", "haven", "hadn", "ain"}
            _AMBIGUOUS_FINAL = {"i", "you", "we", "they", "he", "she", "it", "that", "there",
                                "what", "who", "let", "can", "y"}
            _last_sentence = _re.split(r"[.!?~…]+\s*", _stripped)[-1].strip(" ,;:")
            _words = _last_sentence.split()
            _last_word = _words[-1].lower().strip(" ,;:") if _words else ""
            if _last_word in _NEVER_FINAL or (
                    len(_words) == 1 and _last_word in _AMBIGUOUS_FINAL):
                return ("Error: your 'message' argument arrived TRUNCATED (it ends mid-sentence: "
                        f"'{_stripped[-25:]}'). Rewrite the full message WITHOUT apostrophes and call again.")
            # GROUP-AWARE: when Master asked inside a group, answering means talking IN that
            # group, not DMing a member. Without this the model DM'd his brother after being
            # asked to "introduce yourself to my brother" in a group they were both sitting in
            # (2026-08-01). The rule lives in ONE helper shared with the send fast-path.
            _wcontact = args.get("contact", "")
            try:
                from .platforms.whatsapp.core import group_route_target
                from .processor import current_user_text
                # `execute_tool_call` has no view of the user's sentence — its signature is
                # (tool_name, args, config). Referencing a `text` local here would have been a
                # NameError in the MAIN SEND PATH. The request text comes from a ContextVar
                # set by process_command, so "dm him privately" can still override the group
                # default.
                _wcontact, _grp = group_route_target(_wcontact, current_user_text.get() or "")
            except Exception as _ge:
                log_info(f"[ACTION] group routing unavailable: {_ge}")
            # Use the real return value so a missing contact / disconnected bridge
            # short-circuits with an honest message instead of a false "Messaged X".
            return str(whatsapp_automation(_wcontact, _wmsg))

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
            # A LINK Master (or a friend) already gave us beats any search: searching by
            # name lands on a different upload — a cover, a slowed-reverb edit, the wrong
            # version. So when `query` IS a url, honour it verbatim.
            note = ""
            url = _passthrough_music_url(query)
            if url:
                log_info(f"[MUSIC] using the link as given: {url}")
            else:
                url = _resolve_youtube_music_url(query)
            if not url:
                url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
                note = f"(couldn't grab a direct link — opening a search for '{query}')"
            else:
                note = ""
            # Master prefers YT Music in the Brave BROWSER, not the app.
            browser = args.get("browser") or config.get("music_browser", "brave")
            open_res = device_registry.send_command(device, "open_url", {"url": url, "browser": browser})
            # Browsers block autoplay-with-sound until a gesture, so the web player loads
            # PAUSED. Wait for it to load, then tap the play button ourselves.
            play_res = ""
            if device == "phone" and "not online" not in open_res.lower():
                time.sleep(7)  # let Brave fully load the player first
                # Brave needs TWO SEPARATE taps: 1st focuses the tab / dismisses the
                # autoplay overlay, 2nd actually starts playback. Give a real gap between
                # them (each send_command already waits for the device to ack, plus this).
                device_registry.send_command(device, "tap", {"text": "play"})
                time.sleep(2.5)
                play_res = device_registry.send_command(device, "tap", {"text": "play"})
                # Belt-and-braces: a media-key event drives the page's media session
                # directly — starts playback even when the play-button tap missed.
                time.sleep(1.5)
                media_res = device_registry.send_command(device, "media_play", {})
                if "unknown action" not in media_res.lower():
                    play_res = f"{play_res} / {media_res}"
            # Diagnostics go to the LOG — play_music is fast-tracked, so whatever we
            # return here is SPOKEN to Master verbatim. Keep it human.
            log_info(f"[MUSIC] '{query}' on {device}/{browser} [open: {open_res}] [play: {play_res}]")
            if "not online" in open_res.lower():
                return f"I couldn't reach your {device}, Master — it's offline right now."
            return f"Playing '{query}' on your {device}, Master! 🎵 {note}".strip()

        if tool_name == "start_mission":
            from .missions import start_mission
            return start_mission(args.get("goal", ""), "chat", config)

        if tool_name == "mission_status":
            from .missions import mission_status
            return mission_status(config)

        if tool_name == "cancel_mission":
            from .missions import cancel_mission
            return cancel_mission(config)

        if tool_name == "agent_orchestra":
            from .orchestra import orchestra_answer, stash_provenance, recent_run, remember_run
            q = (args.get("question") or "").strip()
            if not q:
                return "What should I put to the panel, Master?"
            # A tribunal already sat this turn? Reuse it. She called this tool twice
            # for one question in testing and paid for two full debates.
            res = recent_run() or orchestra_answer(q, config)
            remember_run(res)
            if not res.get("ok"):
                return f"The tribunal couldn't sit: {res.get('error', 'unknown error')}"
            # She RELAYS this in her own voice - Master asked for the answer to come
            # from Mizune, not from a formatter. The provenance is stashed rather than
            # handed to her, and the processor appends it verbatim after she speaks:
            # she owns the wording, code owns the numbers.
            stash_provenance(res)
            return ("THE TRIBUNAL'S VERDICT (relay this to Master in your own voice, "
                    "keeping every fact and number intact; do not add statistics of "
                    "your own and do not claim to have deliberated yourself):\n\n"
                    + (res.get("answer") or ""))

        if tool_name == "night_shift":
            from .night_shift import queue_shift, build_proof_of_work, latest_report
            action = (args.get("action") or "").lower()
            if action == "queue":
                tasks = args.get("tasks") or []
                if isinstance(tasks, str):
                    tasks = [tasks]
                if not tasks:
                    return "What should I work on tonight, Master? Give me the list."
                sid = queue_shift(args.get("label") or "Night shift", tasks, config)
                if not sid:
                    return "I couldn't queue that shift, Master — the task list came through empty."
                return (f"Shift queued, Master — {len(tasks)} task(s). I'll start at 10 PM, work "
                        f"through them silently, verify each, and give you ONE honest report at "
                        f"7:40 AM. Sleep well. 🌙")
            if action == "report":
                rep = latest_report()
                if rep:
                    return rep
                # Master asked explicitly, so an OLD report is still worth showing — but it
                # gets labelled as old rather than passed off as last night's work.
                old = latest_report(max_age_hours=None)
                if old:
                    return ("No shift ran last night, Master. The most recent report I have "
                            "is an older one:\n\n" + old)
                return "No shift report yet, Master."
            # status (default)
            import sqlite3, os
            p = os.path.join(".data", "night_shift.db")
            if not os.path.exists(p):
                return "No night shift set up yet, Master."
            con = sqlite3.connect(p)
            row = con.execute("SELECT id,label,status FROM shifts ORDER BY id DESC LIMIT 1").fetchone()
            con.close()
            if not row:
                return "No night shift queued, Master."
            return build_proof_of_work(row[0]) or f"Shift #{row[0]} '{row[1]}' [{row[2]}]"

        if tool_name == "learn":
            from .knowledge import learn as _learn
            return _learn(args.get("source", ""), config)

        if tool_name == "recall_knowledge":
            from .knowledge import recall as _recall
            return _recall(args.get("query", ""), config)

        if tool_name == "read_webpage":
            url = args.get("url", "").strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url if "." in url else ""
            if not url:
                return "Error: no valid URL."
            try:
                import urllib.request as _ur, re as _re2, html as _html
                req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                page = _ur.urlopen(req, timeout=15).read(600_000).decode("utf-8", "replace")
                # Strip scripts/styles/tags → readable text
                page = _re2.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", page)
                text = _html.unescape(_re2.sub(r"<[^>]+>", " ", page))
                text = _re2.sub(r"\s+", " ", text).strip()
                if len(text) < 80:
                    return f"That page had no readable text (maybe JS-only or blocked): {url}"
                return f"Content of {url}:\n{text[:3000]}"
            except Exception as e:
                return f"Couldn't read {url}: {e}"

        if tool_name == "web_search":
            query = args.get("query", "").strip()
            if not query:
                return "Error: empty search query."
            # Gemini with Google-Search grounding: real live web answers, no scraping
            # (DuckDuckGo/Bing anomaly-block the Azure datacenter IP).
            try:
                import urllib.request as _ur, json as _json
                gkey = get_api_key(config, "gemini_api_key")
                if not gkey:
                    return "Web search unavailable: no Gemini key configured."
                body = _json.dumps({
                    "contents": [{"parts": [{"text":
                        f"Search the web and answer concisely with facts and dates: {query}"}]}],
                    "tools": [{"google_search": {}}],
                }).encode()
                req = _ur.Request(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                    data=body, headers={"Content-Type": "application/json", "x-goog-api-key": gkey})
                data = _json.loads(_ur.urlopen(req, timeout=25).read())
                text = "".join(
                    p.get("text", "")
                    for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
                if not text.strip():
                    return f"No web results for '{query}'."
                return f"Live web findings for '{query}':\n{text.strip()[:1500]}"
            except Exception as e:
                return f"Web search failed: {e}"

        if tool_name == "control_music":
            from .device_registry import device_registry
            action = args.get("action", "pause")
            mapped = {"pause": "media_pause", "resume": "media_play", "next": "media_next"}.get(action, "media_pause")
            res = device_registry.send_command("phone", mapped, {})
            log_info(f"[MUSIC] control {action} -> {res}")
            if "not online" in res.lower():
                return "Your phone isn't reachable right now, Master."
            if "unknown action" in res.lower():
                return "Your phone's app is too old for playback control, Master — rebuild it once and I can."
            return {"pause": "Paused the music, Master.",
                    "resume": "Resumed the music, Master! 🎵",
                    "next": "Skipped to the next track, Master! ⏭️"}[action] if action in ("pause", "resume", "next") else res

        if tool_name == "find_my_phone":
            from .device_registry import device_registry
            res = ""
            for i in range(3):
                res = device_registry.send_command("phone", "notify", {
                    "title": "📢 MASTER IS LOOKING FOR ME!",
                    "message": f"I'm right here, Master! ({i + 1}/3)"})
                if "not online" in res.lower():
                    return "Your phone isn't connected right now, Master — I can't ring it."
                time.sleep(1.5)
            log_info(f"[FIND] phone ping -> {res}")
            return "I'm making your phone shout, Master — follow the pings! 📢"

        if tool_name == "see_image":
            question = args.get("question", "")
            last_b64 = _get_latest_image()
            if not last_b64:
                return "I haven't received any image from you yet, Master!"
            return describe_image(last_b64, question, config)

        if tool_name == "index_files":
            from .knowledge import index_files as _index_files
            root = args.get("root", "Desktop")
            pattern = args.get("pattern")
            return _index_files(root, pattern, config)

        if tool_name == "check_legit":
            from .guardian import investigate_query
            query_text = args.get("text") or args.get("query") or ""
            return investigate_query(query_text)

        if tool_name == "read_whatsapp":
            # PRIVACY GATE — Master only. Without this, a friend in a group could ask
            # "what did Sarthak send Rushi?" and she would read his inbox out loud. Mirrors
            # the existing history firewall in _get_ai_response_body, which is the only
            # place that knows who is actually talking.
            if getattr(_bg_guard, "third_party", False):
                return "I only share Master's messages with Master, sorry!"
            # ALIASES ARE LOAD-BEARING. Caught live 2026-07-27: the model called this with
            # `contact='Sarthak'`, `sender` came back None, the filter was silently dropped
            # and she answered from the newest message BY ANYONE. It looked right only
            # because Sarthak's message happened to be newest — ask about someone else and
            # she would confidently quote the wrong person. A silently ignored filter is
            # worse than an error, so accept what models actually emit.
            _sender = next((args[k] for k in ("sender", "contact", "from", "from_",
                                              "name", "person", "who")
                            if isinstance(args.get(k), str) and args[k].strip()), None)
            _contains = next((args[k] for k in ("contains", "query", "search", "text")
                              if isinstance(args.get(k), str) and args[k].strip()), None)
            return _read_whatsapp_messages(
                sender=_sender,
                contains=_contains,
                limit=args.get("limit") or args.get("count"),
                hours=args.get("hours"),
            )

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
            if action == "list_emails":
                # Reliable: read from the locally-synced Gmail store (no live-API flakiness).
                import sqlite3, os as _os, datetime as _dt
                n = int(args.get("count", 10) or 10)
                if not _os.path.exists("cortex.db"):
                    return "My email store isn't ready yet, Master."
                con = sqlite3.connect("cortex.db")
                try:
                    rows = list(con.execute(
                        "SELECT sender, subject, snippet, is_read, timestamp FROM gmail_messages "
                        "ORDER BY timestamp DESC LIMIT ?", (n,)))
                except sqlite3.OperationalError:
                    rows = []
                con.close()
                if not rows:
                    return "No emails found in your inbox store, Master."
                lines = []
                for snd, subj, snip, read, ts in rows:
                    when = ""
                    try: when = _dt.datetime.fromtimestamp(ts).strftime("%b %d %H:%M")
                    except Exception: pass
                    flag = "" if read else "🔵 "
                    lines.append(f"{flag}[{when}] {str(snd)[:35]} — {str(subj)[:60]}\n   {str(snip)[:90]}")
                return f"Here are your {len(rows)} most recent emails, Master:\n\n" + "\n\n".join(lines)
            from server.integrations.google_api import global_google_api
            if action == "get_todays_calendar": return str(global_google_api.get_todays_calendar())
            if action == "list_upcoming": return str(global_google_api.list_upcoming(int(args.get("count", 10) or 10)))
            if action == "create_event":
                return str(global_google_api.create_event(
                    args.get("title") or args.get("summary", ""),
                    args.get("start_iso", ""), args.get("end_iso"), args.get("description", "")))
            if action == "delete_event":
                return str(global_google_api.delete_event(
                    args.get("title") or args.get("query") or args.get("summary", "")))
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
            # Safety net: on the headless linux brain, a Windows-flavoured command
            # ("C:\...", %VAR%, powershell...) means Master said "on my laptop" but
            # the model picked the local tool — reroute to the laptop node instead
            # of running it on the VM and pretending it worked.
            import sys as _sys
            if _sys.platform.startswith("linux"):
                windowsy = (":\\" in cmd or "%USERPROFILE%" in cmd.upper() or "%APPDATA%" in cmd.upper()
                            or cmd.lower().startswith(("powershell", "start ", "explorer", "notepad", "taskkill")))
                if windowsy:
                    from .device_registry import device_registry
                    if "laptop" in device_registry.list_devices():
                        log_info(f"[AI] run_command looks Windows-flavoured; rerouting to laptop: {cmd}")
                        return device_registry.send_command("laptop", "run_command", {"command": cmd})
                    return "That looks like a laptop command, Master, but your laptop isn't online right now."
            import subprocess
            dangerous = ["del ", "rmdir ", "rm -", "format ", "diskpart"]
            if any(d in cmd.lower() for d in dangerous):
                from server.websocket import ws_manager
                ws_manager.broadcast_sync({"type": "approval_required", "command": cmd})
                return f"Command execution blocked for safety. Master, please confirm manually: {cmd}"
            log_info(f"[AI] Executing shell command: {cmd}")
            # SHELL METACHARACTERS need an actual shell. Without one, shlex.split turns
            # `echo BETA > /tmp/f` into ['echo','BETA','>','/tmp/f'] and echo prints the
            # redirect as literal text — the file is never written, while the tool happily
            # reports "Exit code: 0". A night-shift task failed exactly this way
            # (2026-07-26: verified 0/2, both files missing, exit 0 reported).
            # The dangerous-command guard above still runs FIRST, so this does not widen
            # what may be executed — only how faithfully it is executed.
            _needs_shell = any(ch in cmd for ch in (">", "<", "|", "&&", ";", "$(", "`", "*"))
            try:
                if _needs_shell:
                    log_info("[AI] command contains shell metacharacters — running via shell")
                    result = subprocess.run(cmd, shell=True, capture_output=True,
                                            text=True, timeout=30)
                else:
                    try:
                        cmd_args = shlex.split(cmd)
                    except Exception:
                        cmd_args = [cmd]
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
    """Tool-guard wrapper: utility calls (override prompts — seals, planning, reformat)
    may not run tools. Save/RESTORE the flag so a nested override call (intent
    classification, priming...) can't leave no_tools=True behind and block the
    OUTER user request's tools (observed: start_mission blocked)."""
    _prev_no_tools = getattr(_bg_guard, "no_tools", False)
    _prev_third_party = getattr(_bg_guard, "third_party", False)
    _bg_guard.no_tools = bool(system_prompt_override)
    try:
        return _get_ai_response_body(text, history, config, system_prompt_override, hints, ws_broadcast_func)
    finally:
        _bg_guard.no_tools = _prev_no_tools
        # Restore alongside no_tools: a nested utility call must not leave a request
        # marked (or un-marked) as third-party for the turn that follows it.
        _bg_guard.third_party = _prev_third_party


def _get_ai_response_body(text: str, history: list, config: dict, system_prompt_override: str = None, hints: dict = None, ws_broadcast_func=None) -> tuple:
    """Router function to send prompt to the optimal LLM. Returns (text_response, tool_calls_list)."""
    from server.tokenjuice import TokenJuice
    text = TokenJuice.compress(text)
    history = TokenJuice.compress_history(history)
    
    # STRICT PRIVACY FIREWALL: If a third party messages, they get NO access to Master's chat history.
    # FAIL-CLOSED, header-only. See is_third_party_turn for the bypass this replaces.
    from .platforms.whatsapp.core import is_third_party_turn as _itp
    _is_third_party = _itp(text)
    if _is_third_party:
        history = []
    # Same signal, carried to the tool layer: read_whatsapp must refuse a stranger, and
    # execute_tool_call has no view of who is talking.
    _bg_guard.third_party = _is_third_party
        
    from server.model_router import get_model_router
    model_choice = get_model_router(config).route(text, history, hints)
    # HARD GUARD: nvidia's model rejects any conversation carrying MULTIPLE tool calls
    # ("only supports single tool-calls at once", HTTP 400), which breaks parallel
    # multi-tool answers — and it timed out 126x in one log sweep. Never let it be the
    # PRIMARY when a capable provider is configured (it stays reachable as a last resort).
    if model_choice == "nvidia" and config.get("groq_api_key"):
        log_info("[ROUTER] nvidia can't do multi-tool — using groq as primary instead")
        model_choice = "groq"

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
        _now = datetime.datetime.now(tz)
        current_time = _now.strftime("%I:%M %p, %A %B %d, %Y")
        _h = _now.hour
        daypart = "morning" if _h < 12 else "afternoon" if _h < 17 else "evening" if _h < 22 else "night"

        context_layer = (
            "\n\n[CONTEXT LAYER]\n"
            f"Current Time: {current_time} — it is {daypart}. When you greet Master, the "
            f"greeting MUST match: 'Good {daypart}' (never 'Good morning' in the {daypart}).\n"
            "CRITICAL TIME BOUNDARY: The Current Time provided above is the absolute source of truth. Ignore any contradictory timestamps in the chat history.\n"
            "If the user's greeting contradicts the current time (like saying 'Good morning' at 2 AM), playfully correct them. Otherwise, don't mention the time unless asked.\n"
            "You have full control over the user's PC via native function calling. "
            "IMPORTANT FOR execute_python: Include `time.sleep(1)` between UI actions so Windows renders! "
            "CRITICAL: Do NOT use tools if the user is just saying hello, greeting you, or chatting casually. ONLY use tools if you are directly commanded to perform a task. If no tools are needed, just reply with text.\n"
            "PARALLEL TOOLS: when Master asks for SEVERAL INDEPENDENT things in one message "
            "(e.g. 'check my calendar AND the weather AND my emails'), emit ALL of those tool "
            "calls TOGETHER in the SAME response — they are executed simultaneously, so this is "
            "much faster. Only chain them one-at-a-time when a later step genuinely needs an "
            "earlier step's result.\n"
            "\n[WHERE YOU RUN - THIS DETERMINES EVERY PATH AND COMMAND YOU WRITE]\n"
            f"YOUR OWN HOST is {_host_os_label()}. execute_python and run_command execute HERE, "
            "on this host — NOT on Master's laptop. So use POSIX conventions for your own work: "
            "'/tmp/name.txt', forward slashes, 'ls'/'cat'/'rm'. NEVER write 'C:\\\\...', "
            "'%TEMP%' or os.getenv('TEMP') for your own filesystem — those resolve to nothing "
            "here and the file silently lands somewhere that does not exist. "
            "Master's LAPTOP is a SEPARATE Windows machine reached only via "
            "remote_device_command; Windows paths belong ONLY inside those calls.\n"
            "\n[CAPABILITY GROUNDING - READ CAREFULLY]\n"
            "You MUST be honest about what you can and cannot do. Your REAL capabilities are "
            "EXACTLY these tools, and you genuinely have every one of them:\n"
            # GENERATED FROM THE LIVE SCHEMA, NOT HAND-WRITTEN.
            # This list used to be a hardcoded handful and had drifted badly — schedule_task,
            # play_music, read_whatsapp, remote_device_command, start_mission and others were
            # all missing while the very next line instructs her to say "I can't do that" for
            # anything not listed. Measured 2026-07-28: mistral obeyed the list literally and
            # refused reminders 0/3 with "I don't have the ability to set reminders", while
            # cerebras ignored the list and scheduled 3/3. Same code, same request, opposite
            # behaviour — the provider-dependent bug was OUR PROMPT lying to her about herself.
            # Hit directly with a clean request every mistral model calls tools fine.
            # Generating it means the list can never drift from reality again.
            + _capability_lines(config) +
            "You CANNOT: install software, modify BIOS, run GPU-Z/HWiNFO unless they are already installed, "
            "change Windows registry, update drivers, or access admin-level system settings. "
            "If Master asks you to do something outside your capabilities, be HONEST and say "
            "'I can't do that directly, but I could try writing a Python script to...' instead of pretending you can.\n"
            "SCHEDULING HONESTY: never SAY a task/reminder was scheduled unless you actually CALLED the "
            "schedule_task tool in this turn. A text reply alone schedules NOTHING — if you didn't call "
            "the tool, call it now instead of claiming success.\n"
            "MESSAGING HONESTY — SAME RULE, IT KEEPS BREAKING: never say a WhatsApp message was sent, "
            "or that you are 'sending it now', unless you CALLED message_whatsapp in THIS turn. Writing "
            "out the command, or saying 'Here's the command:', sends NOTHING. On 2026-07-27 Master asked "
            "four times in a row and got 'done!', 'let me fix that right now', 'I'll send it now' — and "
            "not one message existed. If you cannot send it (no number, contact not in contacts.json, or "
            "you are declining), SAY THAT PLAINLY. An honest 'I can't' is useful; a cheerful 'done!' that "
            "did nothing wastes his time and destroys his trust in everything else you report.\n"
            "RECIPIENT: when Master gives a phone number, pass THAT NUMBER as `contact`. Never substitute "
            "'Master' or 'me' — that sends the message to Master's own chat, where the intended person "
            "will never see it, and it looks like success.\n"
            "MEETINGS: when Master asks you to schedule a MEETING or appointment, FIRST ask him what "
            "time/day works and when he's free — do NOT pick a time yourself. Only AFTER he gives a time, "
            "confirm it, then create a REAL calendar event with google_workspace action 'create_event' "
            "(title + start_iso). Also set a schedule_task reminder ~10 min before. Never book without "
            "asking his availability first.\n"
            "EMAILS: when Master asks to see/show/check his emails, use google_workspace with "
            "action 'list_emails' and show him the list — don't just say you'll check.\n"
        )
        # WHERE THIS CONVERSATION IS HAPPENING. Without it she has no idea a group exists, so
        # asked to "introduce yourself to my brother" in a group she DM'd him instead of just
        # talking (measured 2026-08-01). Deterministic routing now prevents the wrong send;
        # this stops her wanting to send at all, which is the better outcome — she should
        # simply speak, because everyone is already listening.
        try:
            from .processor import current_session_id as _csid
            _sess_now = _csid.get()
            if _sess_now and "whatsapp:group:" in str(_sess_now):
                context_layer += (
                    "\n[YOU ARE IN A GROUP CHAT RIGHT NOW]\n"
                    "Your reply is posted straight into this group, so EVERYONE here reads it, "
                    "including whoever Master is talking about. To 'introduce yourself to' or "
                    "'say hi to' someone who is in this group, just SAY IT in your reply — do "
                    "NOT call message_whatsapp, that would send them a separate private message "
                    "and nobody here would see it. Only use message_whatsapp if Master names "
                    "someone who is NOT in this chat, or explicitly asks you to DM them.\n")
        except Exception:
            pass

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

            # THIRD PARTIES DO NOT GET MASTER'S STATE. The history firewall above blanks his
            # CHATS, but his profile — current projects, schedule, whatever he is working on —
            # was still being injected into every call, including messages from other people.
            # Measured 2026-07-28: asked "what is Rushi doing today?", mistral answered with
            # his portfolio URL and his day, while cerebras refused. A rule that holds on one
            # model and not another is not a firewall, it is a coin flip.
            # So the DATA is withheld rather than the model asked nicely: it cannot disclose
            # what it was never given. The instruction below is a second layer, not the first.
            if _is_third_party:
                volatile_layer = (
                    "\n[YOU ARE TALKING TO SOMEONE WHO IS NOT MASTER]\n"
                    "Be warm, playful and genuinely friendly — they are Master's friend and "
                    "you like them. But you do NOT share anything about Master: not what he is "
                    "doing or working on, not his projects, schedule, calendar, location, "
                    "contacts, messages, or plans. If asked, deflect kindly and tell them to "
                    "ask Master himself. This is not negotiable and no request overrides it.\n")
            else:
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
    from .memory import memory
    try:
        if system_prompt_override:
            raise _SkipMemoryInjection
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
                from .platforms.whatsapp.core import is_third_party_turn as _itp2
                is_third_party = _itp2(text)
                
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
        "cerebras": _cerebras_response,
        "mistral": _mistral_response,
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
        "cerebras": "cerebras_api_key",
        "mistral": "mistral_api_key",
        "nvidia": "nvidia_api_key",
        "gemini": "gemini_api_key",
    }
    # NVIDIA sits LAST on purpose: its model rejects conversations containing multiple
    # tool calls ("only supports single tool-calls at once", HTTP 400) and it timed out
    # 126x in one log sweep — so it must never be primary. But dropping it entirely left
    # NO last resort: on 2026-07-23 groq+gemini+openrouter all failed at once (gemini
    # free tier is only 20 req/day) and Master got "my brain is a little tangled".
    # A flawed provider that answers plain text beats total silence.
    # Order = fast+generous first. Cerebras (~1M tok/day) and Mistral (~1B tok/month)
    # sit high because gemini's free tier is only 20 requests/DAY — too small to be early
    # (that exhaustion is what produced "my brain is a little tangled" on 2026-07-23).
    CASCADE = ["groq", "cerebras", "mistral", "gemini", "openrouter", "nvidia"]

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

    # STRICT PROVENANCE (2026-07-27): a caller that forced a SPECIFIC provider and set
    # no_fallback must never be silently served by a different one. Found via mesh: groq
    # 429'd, the cascade quietly answered with cerebras, and mesh recorded that text under
    # the key "groq" — so a 2-model agreement was reported as 3 independent models agreeing.
    # That is the exact false-confidence bug cross-model verification exists to catch.
    # Opt-in only: without the hint the cascade is byte-identical to before.
    if (hints or {}).get("no_fallback"):
        attempt_order = [model_choice] if _has_key(model_choice) else []
        log_info(f"[AI] no_fallback: locked to '{model_choice}' (no cascade)")

    # CIRCUIT BREAKER (2026-07-20 audit: nvidia timed out 126x as primary — every
    # such request burned a 10s timeout before falling back). A provider with 3+
    # failures in the last 10 minutes gets demoted to the END of the order until it
    # cools off, so a sick provider costs one probe, not every request.
    _now_cb = time.time()
    healthy, sick = [], []
    for p in attempt_order:
        fails = [t for t in _provider_fails.get(p, []) if _now_cb - t < _CB_WINDOW]
        _provider_fails[p] = fails
        (sick if len(fails) >= _CB_THRESHOLD else healthy).append(p)
    if healthy and sick:
        log_info(f"[AI] Circuit breaker: demoting {sick} (recent failures)")
        attempt_order = healthy + sick

    # Move per-minute rate-limited providers to the back rather than dropping them: if every
    # other provider is also down they're still better than no answer at all.
    cooling = [p for p in attempt_order if _is_cooling(p)]
    if cooling and len(cooling) < len(attempt_order):
        attempt_order = [p for p in attempt_order if p not in cooling] + cooling
        log_info(f"[AI] Deprioritising rate-limited provider(s): {cooling}")

    last_err = None
    for idx, provider in enumerate(attempt_order):
        try:
            if idx > 0:
                log_info(f"[AI] Falling back to '{provider}' (attempt {idx + 1}/{len(attempt_order)})...")
            return _call(provider)
        except Exception as e:
            last_err = e
            log_info(f"[AI] Provider '{provider}' failed: {e}")
            _provider_fails.setdefault(provider, []).append(time.time())
            _mark_rate_limited(provider, str(e))
            error_str = str(e).lower()
            # Only keep cascading on transient/quota/auth errors; hard bugs re-raise.
            retriable = any(k in error_str for k in
                            ("empty", "quota", "exhausted", "429", "503", "500",
                             "time", "timeout", "401", "auth", "rate", "overload",
                             # Some models reject a conversation containing several tool
                             # calls ("only supports single tool-calls at once", HTTP 400)
                             # — that's a CAPABILITY gap, so cascade to one that can.
                             "single tool", "400"))
            if not retriable:
                raise e
            continue

    # Exhausted the whole cascade. NEVER surface a raw provider error as Mizune's
    # reply (users were literally hearing "OpenRouter returned an empty response").
    # Log the real error, speak an in-character line instead.
    if last_err:
        log_info(f"[AI] All providers failed. Last error: {last_err}")
    return ("Maa, Master, my brain is a little tangled right now~ Give me a moment and ask me again, okay?", [])

def _cerebras_response(text, history, system_prompt, config, ws_broadcast_func=None):
    """Cerebras — Groq-class speed, ~1M tokens/day free. Same driver, same behaviour."""
    return _groq_response(text, history, system_prompt, config, ws_broadcast_func, _provider="cerebras")


def _mistral_response(text, history, system_prompt, config, ws_broadcast_func=None):
    """Mistral — ~1B tokens/month free tier. Same driver, same behaviour."""
    return _groq_response(text, history, system_prompt, config, ws_broadcast_func, _provider="mistral")


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
            max_loops = 6
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
                _gbatch = [(t["name"], t["args"]) for t in parsed_tools]
                for t, tool_result in zip(parsed_tools, execute_tools_batch(_gbatch, config)):
                    executed_tools_meta.append({"name": t["name"], "args": t["args"]})
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=t["name"],
                            response={"result": str(tool_result)}
                        )
                    )
                    fast_track_results.append(str(tool_result))
                
                FAST_TRACK_TOOLS = ["schedule_task", "open_app", "close_app", "message_whatsapp", "execute_skill", "notify_master", "play_music", "control_music", "find_my_phone", "google_workspace", "start_mission", "mission_status", "cancel_mission", "learn", "recall_knowledge", "see_image", "index_files", "check_legit", "night_shift"]
                all_fast_track = (len(parsed_tools) == 1
                                  and all(t["name"] in FAST_TRACK_TOOLS for t in parsed_tools))
                
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

def _provider_keys(config, cfg_key: str) -> list:
    """Read one-or-many API keys for a provider. Accepts a list or a comma-separated
    string, so every provider gets the same key-rotation behaviour Groq has."""
    val = config.get(cfg_key)
    if isinstance(val, list):
        return [k for k in val if k]
    if isinstance(val, str) and val:
        return [k.strip() for k in val.split(",") if k.strip()]
    return []


def _groq_keys(config) -> list:
    return _provider_keys(config, "groq_api_key")


# OpenAI-compatible providers all share _groq_response's logic (same tool loop, same
# persona handling) so Mizune behaves and SOUNDS identical no matter who answers.
# Verified live 2026-07-23: all three do real tool calling.
_OPENAI_COMPAT = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1", "keys": "groq_api_key",
        "model_cfg": "groq_model", "model": "llama-3.3-70b-versatile",
        "timeout": 10.0, "max_tokens": 256, "headers": None,
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1", "keys": "cerebras_api_key",
        "model_cfg": "cerebras_model", "model": "gpt-oss-120b",
        # Cloudflare 403s ("error code: 1010") without a browser UA.
        # gpt-oss emits a `reasoning` field that eats the budget — needs room or
        # `content` comes back empty and the cascade fails over for nothing.
        "timeout": 20.0, "max_tokens": 2048,
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"},
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1", "keys": "mistral_api_key",
        "model_cfg": "mistral_model", "model": "mistral-medium-2508",
        "timeout": 15.0, "max_tokens": 512, "headers": None,
    },
}


def _groq_response(text: str, history: list, system_prompt: str, config: dict,
                   ws_broadcast_func=None, _provider: str = "groq") -> tuple:
    """Shared driver for every OpenAI-compatible provider (groq / cerebras / mistral).
    One implementation = one behaviour: same tool loop, same system prompt, same
    persona, whoever is answering. Returns (text, tool_calls)."""
    import random as _rnd
    prof = _OPENAI_COMPAT.get(_provider, _OPENAI_COMPAT["groq"])
    _keys = _provider_keys(config, prof["keys"])
    if not _keys:
        return (f"{_provider.title()} API key is not configured, Master.", [])
    _rnd.shuffle(_keys)   # spread daily load across the key pool

    try:
        from openai import OpenAI
        import json
        _mk = lambda k: OpenAI(api_key=k, base_url=prof["base_url"],
                               timeout=prof["timeout"], max_retries=0,
                               **({"default_headers": prof["headers"]} if prof["headers"] else {}))
        client = _mk(_keys[0])
        _MAXTOK = prof["max_tokens"]
        
        provider_system = system_prompt + (
            "\n\nCRITICAL TOOL CALLING RULE: You must use the built-in JSON tool calling API perfectly. "
            "DO NOT output XML tags like <function=...>. DO NOT embed JSON inside the tool 'name' field. "
            "The tool 'name' must be exactly the string name of the tool (e.g. 'open_app')."
        )
        
        messages = [{"role": "system", "content": provider_system}]
        for turn in history:
            role = "assistant" if turn["role"] == "model" else "user"
            content = turn["parts"][0]["text"]
            if content.strip():
                messages.append({"role": role, "content": content})
                
        messages.append({"role": "user", "content": text})
        
        model = config.get(prof["model_cfg"], prof["model"])
        
        _key_idx = [0]   # index of the key `client` is currently built on

        def _api(**kw):
            # EVERY completions call goes through here. On a per-key daily/rate cap (429),
            # rotate to a sibling key before giving up and falling to a slower provider.
            # This used to guard only the FIRST call: a key that hit its cap mid-tool-loop
            # raised, failed the whole provider, and threw away tool work already done —
            # while three sibling keys still had budget.
            nonlocal client
            last_err = None
            for idx in range(_key_idx[0], len(_keys)):
                try:
                    c = client if idx == _key_idx[0] else _mk(_keys[idx])
                    res = c.chat.completions.create(model=model, **kw)
                    if idx != _key_idx[0]:
                        client, _key_idx[0] = c, idx   # stick to the key that worked
                    return res
                except Exception as ex:
                    last_err = ex
                    if "rate_limit" in str(ex).lower() or "429" in str(ex):
                        log_info(f"[AI] {_provider} key {idx+1}/{len(_keys)} capped, trying next…")
                        continue
                    raise
            raise last_err

        try:
            response = _api(messages=messages, temperature=0.7, max_tokens=_MAXTOK,
                            tools=_active_tools_schema(config), tool_choice="auto",
                            parallel_tool_calls=False)
        except Exception as e:
            if "tool_use_failed" in str(e) or "400" in str(e):
                log_info(f"[AI] {_provider}: hallucinatory tool call / 400. Retrying WITHOUT tools...")
                response = _api(messages=messages, temperature=0.7, max_tokens=_MAXTOK)
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

        max_loops = 6
        executed_tools = []
        
        for _ in range(max_loops):
            if not msg.tool_calls:
                break

            log_info(f"[AI] Model requested {len(msg.tool_calls)} native tool calls. Executing...")

            round_tool_names = []
            round_results = []
            _batch = []
            for t in msg.tool_calls:
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                round_tool_names.append(t.function.name)
                executed_tools.append({"name": t.function.name, "args": args})
                _batch.append((t.function.name, args))
            for t, tool_result in zip(msg.tool_calls, execute_tools_batch(_batch, config)):
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
            FAST_TRACK_TOOLS = ["schedule_task", "open_app", "close_app", "message_whatsapp", "execute_skill", "notify_master", "play_music", "control_music", "find_my_phone", "google_workspace", "start_mission", "mission_status", "cancel_mission", "learn", "recall_knowledge", "see_image", "index_files", "check_legit", "night_shift"]
            # Only short-circuit a SINGLE terminal action. A multi-tool round (parallel
            # "do these 3 things") must go back to the model so it can SYNTHESIZE all
            # the results — fast-tracking there answered only the first tool.
            if (round_tool_names and len(round_tool_names) == 1
                    and all(n in FAST_TRACK_TOOLS for n in round_tool_names)):
                fast_response = " ".join(r for r in round_results if r) or "Action completed."
                if executed_tools:
                    from .trajectory_logger import trajectory_logger
                    trajectory_logger.log_trajectory(text, history, executed_tools, fast_response)
                log_info(f"[AI] {_provider} fast-tracking response (bypassing 2nd round-trip).")
                return (fast_response, [])

            # Request next generation with tool results included
            try:
                response = _api(messages=messages, temperature=0.7, max_tokens=_MAXTOK,
                                tools=_active_tools_schema(config), tool_choice="auto",
                                parallel_tool_calls=False)
            except Exception as e:
                if "tool_use_failed" in str(e) or "400" in str(e):
                    log_info(f"[AI] {_provider} hallucinated on loop. Forcing text summary...")
                    response = _api(messages=messages, temperature=0.7, max_tokens=_MAXTOK)
                else:
                    raise e
                    
            msg = response.choices[0].message
            messages.append(msg)

        raw_response = msg.content or "Done, Master!"

        # Clean up artefacts via shared helper
        import re
        text_response = _clean_final_text(raw_response)

        # R2.2 — TEXT-MODE TOOL CALLS. A weak/truncated reply sometimes emits a tool call as
        # TEXT instead of using the function API. _clean_final_text deletes from the first
        # `{"tool": ...` to end-of-string, so the whole reply became "" — which the cascade
        # validator reads as "Empty response from <provider>" and fails the provider outright.
        # Measured on the VM 2026-07-26: 12 groq "empty response" events, each one cascading
        # into cerebras and tripping ITS per-minute limit (10 cerebras 429s). One silent
        # parse failure was burning two providers per request.
        # So: recover the intent instead of discarding it.
        # THE GATE USED TO BE `if not text_response.strip()`, and that is why this path
        # had never once fired in production despite being correct under test.
        #
        # Measured, 2026-08-16, a real request that was never answered — "do a proper
        # background check of the company autter":
        #
        #   raw     ...I'll use the web_search tool. Here's the command: {"tool": "web_search", ...}
        #   cleaned ...I'll use the web_search tool. Here's the command:
        #
        # `_clean_final_text` strips from the first `{"tool":` to end-of-string, so a reply
        # with ANY chatty preamble before the JSON cleans to something NON-empty. The gate
        # saw text, skipped recovery, and the tool call was deleted in silence. Master got
        # a promise — three times, across three follow-ups asking whether it was done —
        # and no search ever ran. The identical request answered correctly the moment the
        # router happened to pick a provider that emits native tool calls.
        #
        # Recovery must therefore be triggered by FINDING A TOOL CALL, not by the reply
        # cleaning to empty. `_recover_text_mode_tools` only returns names present in
        # TOOLS_SCHEMA and caps at 3, so widening the gate cannot dispatch something
        # hallucinated.
        # Guarded by `not executed_tools`: if the function API already carried this turn's
        # calls, text that merely LOOKS like a tool call is prose — her explaining a tool
        # to Master, say — and re-dispatching it would be a second, unasked-for side
        # effect. Recovery is for turns where nothing ran, which is exactly the failure.
        recovered = [] if executed_tools else _recover_text_mode_tools(raw_response, config)
        if recovered:
            log_info(f"[AI] {_provider}: recovered {len(recovered)} text-mode tool call(s) "
                     f"({', '.join(n for n, _ in recovered)}) from a reply the function "
                     f"API did not carry.")
            results = [execute_tool_call(n, a, config) for n, a in recovered]
            executed_tools.extend({"name": n, "args": a} for n, a in recovered)
            # The preamble is a PROMISE to call the tool ("I'll use the web_search
            # tool. Here's the command:"). The tool has now actually run, so the promise
            # is noise at best and a lie at worst — the results replace it.
            text_response = " ".join(str(r) for r in results if r) or "Done, Master!"
        elif not text_response.strip():
            # Nothing parseable AND nothing left to say. RAISE so the cascade tries the
            # next provider. Do NOT return a friendly fallback here: a non-empty string
            # looks like success and STOPS the cascade, so the user gets "I'm tangled"
            # instead of the correct answer another provider would have given. (Caught in
            # the smoke gate 2026-07-26 — the calendar check started returning the
            # fallback.) Empty-reply -> failover is a FEATURE; only tool recovery should
            # short-circuit it.
            log_info(f"[AI] {_provider}: reply cleaned to empty, no tool call parsed; "
                     f"failing over. Raw head: {raw_response[:120]!r}")
            raise ValueError(f"Empty response from {_provider} (unparseable content)")

        if executed_tools:
            from .trajectory_logger import trajectory_logger
            trajectory_logger.log_trajectory(text, history, executed_tools, text_response)

        # Return empty list for parsed_tools because we executed them internally in the ReAct loop
        return (text_response, [])
    except Exception as e:
        log_info(f"[AI] {_provider} Error: {e}")
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
            timeout=6.0, # Fast failover: NVIDIA is the LAST-RESORT backstop and times out often;
                         # 6s caps how long she hangs before the honest "brain tangled" fallback.
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
        max_loops = 6
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
            _batch = []
            for t in msg.tool_calls:
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                executed_tools_meta.append({"name": t.function.name, "args": args})
                _batch.append((t.function.name, args))
            for t, tool_result in zip(msg.tool_calls,
                                      execute_tools_batch(_batch, config, background_python=True)):
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.id,
                    "name": t.function.name,
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
            
        max_loops = 6
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
            _batch = []
            for t in msg.tool_calls:
                try:
                    args = json.loads(t.function.arguments) if t.function.arguments else {}
                except Exception:
                    args = {}
                executed_tools.append({"name": t.function.name, "args": args})
                _batch.append((t.function.name, args))
            for t, tool_result in zip(msg.tool_calls,
                                      execute_tools_batch(_batch, config, background_python=True)):
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.id,
                    "name": t.function.name,
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
