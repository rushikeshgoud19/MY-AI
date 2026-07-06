"""
Multi-step Task Planner for Mizune.
Decomposes complex requests into ordered sub-tasks, executes them,
passes output between steps, and reports progress.
"""

import json
import traceback
from typing import List, Dict, Callable, Optional
from server.ai import get_ai_response
from server.config import log_info

SYSTEM_PROMPT_PLAN = """You are Mizune's task planner. Break the user's request into a JSON list of ordered sub-tasks.
Each sub-task must be executable by an AI assistant with these tools:
- open_app, close_app, execute_python, headless_web_agent, message_whatsapp, execute_skill,
- store_memory, search_memory, take_note, schedule_task, system_info.

Rules:
1. Output ONLY valid JSON. No markdown, no explanation.
2. Each item: {"id": 1, "description": "what to do", "tool": "tool_name", "tool_args": {...}, "depends_on": [ids]}
3. Use "depends_on" to enforce order.
4. Keep steps concrete and small.
5. If a step needs output from a previous step, reference it in description/tool_args using placeholder {{step_N_output}}.

Example:
[
  {"id": 1, "description": "Research React vs Vue", "tool": "headless_web_agent", "tool_args": {"url": "https://duckduckgo.com/?q=React+vs+Vue+2024", "objective": "Compare React and Vue"}, "depends_on": []},
  {"id": 2, "description": "Write summary", "tool": "execute_python", "tool_args": {"code": "print('Summary based on:', {{step_1_output}})"}, "depends_on": [1]},
  {"id": 3, "description": "Send summary to Tanmay on WhatsApp", "tool": "message_whatsapp", "tool_args": {"contact": "Tanmay", "message": "{{step_2_output}}"}, "depends_on": [2]}
]
"""

SYSTEM_PROMPT_STEP = """You are Mizune executing one sub-task. Use exactly ONE tool call to complete the task.
You have access to: open_app, close_app, execute_python, headless_web_agent, message_whatsapp, execute_skill, store_memory, search_memory, take_note, schedule_task, system_info.

Rules:
1. Use the provided context from previous steps.
2. Output ONLY a JSON object: {{"tool": "name", "args": {{...}}}}
3. If the task is already done by context, output {{"tool": "none", "args": {{}}}} and include the result in a "result" field.

Task: {task_description}
Context from previous steps:
{context}
"""


def _execute_tool(tool_name: str, args: Dict, config: Dict) -> str:
    """Execute a single tool by name."""
    try:
        if tool_name == "open_app":
            from server.commands import launch_app
            launch_app(args.get("app_name", ""))
            return f"Launched {args.get('app_name', '')}"
        elif tool_name == "close_app":
            from server.commands import close_app
            close_app(args.get("app_name", ""))
            return f"Closed {args.get('app_name', '')}"
        elif tool_name == "execute_python":
            from server.commands import execute_python_code
            return str(execute_python_code(args.get("code", "")))
        elif tool_name == "headless_web_agent":
            from server.web_agent import headless_web_agent
            from server.background_tasks import task_runner
            def _cb(tid, result):
                log_info(f"[TASK PLANNER] Web agent task {tid} done")
            tid = task_runner.submit(headless_web_agent, args.get("url", ""), args.get("objective", ""), visible=args.get("visible", False), callback=_cb)
            return f"Background web task started: {tid}"
        elif tool_name == "message_whatsapp":
            from server.commands import whatsapp_automation
            return str(whatsapp_automation(args.get("contact", ""), args.get("message", "")))
        elif tool_name == "execute_skill":
            from server.skills import skill_manager
            import shlex
            s_args = shlex.split(args.get("args", "")) if args.get("args") else []
            return str(skill_manager.execute_skill(args.get("skill_name", ""), *s_args))
        elif tool_name == "store_memory":
            from server.memory import memory
            memory.store_longterm(args.get("fact", ""))
            return f"Stored: {args.get('fact', '')}"
        elif tool_name == "search_memory":
            from server.commands import search_memory
            return str(search_memory(args.get("keyword", "")))
        elif tool_name == "take_note":
            from server.commands import take_note
            take_note(args.get("note_text", ""), config)
            return "Note saved"
        elif tool_name == "schedule_task":
            from server.processor import global_cron_manager
            import datetime
            delay = float(args.get("delay_minutes", 0))
            action = args.get("action_to_take", "")
            trigger_time = datetime.datetime.now() + datetime.timedelta(minutes=delay)
            global_cron_manager.add_one_time_task(action, trigger_time.isoformat())
            return f"Scheduled at {trigger_time.strftime('%I:%M %p')}"
        elif tool_name == "system_info":
            from server.commands import get_system_info
            return str(get_system_info(args.get("category", "all")))
        elif tool_name == "none":
            return args.get("result", "Done")
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        log_info(f"[TASK PLANNER] Tool {tool_name} failed: {e}")
        return f"Error: {e}"


class TaskPlanner:
    def __init__(self, config: Dict, broadcast_func: Optional[Callable] = None):
        self.config = config
        self.broadcast = broadcast_func or (lambda x: None)

    def _broadcast_task_list(self, tasks: List[Dict]):
        self.broadcast({"type": "task_list", "tasks": tasks})

    def _broadcast_status(self, text: str):
        self.broadcast({"type": "status", "text": text})

    def _broadcast_speak(self, text: str):
        self.broadcast({"type": "speak", "text": text})

    def plan(self, request: str) -> List[Dict]:
        """Ask LLM to break request into sub-tasks."""
        _, tool_calls = get_ai_response(
            request,
            history=[],
            config=self.config,
            system_prompt_override=SYSTEM_PROMPT_PLAN
        )

        # Try to parse JSON from text response if tool_calls empty
        text, _ = get_ai_response(
            f"Return ONLY the JSON task plan for: {request}",
            history=[],
            config=self.config,
            system_prompt_override=SYSTEM_PROMPT_PLAN
        )

        plan_text = text[0] if isinstance(text, tuple) else text
        try:
            # Strip markdown fences if any
            cleaned = plan_text.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:-1]).strip()
            plan = json.loads(cleaned)
            if isinstance(plan, dict) and "tasks" in plan:
                plan = plan["tasks"]
            if not isinstance(plan, list):
                return []
            # Validate fields
            for t in plan:
                t.setdefault("depends_on", [])
                t.setdefault("tool_args", {})
                t.setdefault("status", "pending")
            return plan
        except Exception as e:
            log_info(f"[TASK PLANNER] Failed to parse plan: {e}\n{plan_text}")
            return []

    def _resolve_placeholders(self, text: str, results: Dict[int, str]) -> str:
        for step_id, result in results.items():
            placeholder = f"{{{{step_{step_id}_output}}}}"
            text = text.replace(placeholder, str(result)[:2000])
        return text

    def execute(self, request: str) -> str:
        """Plan and execute multi-step request."""
        tasks = self.plan(request)
        if not tasks:
            return "[EMOTION: sad] I couldn't break that down into steps, Master."

        self._broadcast_speak("I'll handle that in steps, Master~")
        self._broadcast_task_list(tasks)

        results: Dict[int, str] = {}
        max_retries = 2

        for task in tasks:
            task_id = task["id"]
            self._broadcast_status(f"Step {task_id}: {task['description']}")
            task["status"] = "running"
            self._broadcast_task_list(tasks)

            # Resolve placeholders in tool args
            resolved_args = {}
            for k, v in task.get("tool_args", {}).items():
                if isinstance(v, str):
                    resolved_args[k] = self._resolve_placeholders(v, results)
                else:
                    resolved_args[k] = v

            context = "\n".join(f"Step {sid}: {res}" for sid, res in results.items())
            prompt = SYSTEM_PROMPT_STEP.format(
                task_description=task["description"],
                context=context
            )

            attempt = 0
            result = ""
            while attempt <= max_retries:
                try:
                    text, tool_calls = get_ai_response(
                        prompt,
                        history=[],
                        config=self.config,
                        system_prompt_override=prompt,
                        ws_broadcast_func=self.broadcast
                    )
                    if tool_calls:
                        tc = tool_calls[0]
                        tool_name = tc.get("name", task.get("tool", "none"))
                        tool_args = tc.get("args", resolved_args)
                        result = _execute_tool(tool_name, tool_args, self.config)
                    else:
                        result = text if isinstance(text, str) else str(text)
                    break
                except Exception as e:
                    attempt += 1
                    log_info(f"[TASK PLANNER] Step {task_id} attempt {attempt} failed: {e}")
                    if attempt > max_retries:
                        result = f"Failed after {max_retries} retries: {e}"
                        task["status"] = "failed"
                        break

            if task.get("status") != "failed":
                task["status"] = "completed"
            results[task_id] = result
            self._broadcast_task_list(tasks)

        # Final summary
        summary_lines = [f"Step {tid}: {results[tid]}" for tid in sorted(results)]
        summary = "\n".join(summary_lines)
        self._broadcast_status("Idle")
        self._broadcast_speak(f"All steps finished, Master! Here's what I did:\n{summary}")
        return summary


def is_multi_step_request(text: str) -> bool:
    """Heuristic to detect requests that need task planning.

    Word-boundary matching only: the old substring version matched "then" inside
    "authentic" and counted the "and" in "COMMANDING" — the WhatsApp system
    wrapper alone was enough to send EVERY message into the planner.
    """
    import re as _re
    t = text.lower()
    # Strip injected system wrapper lines before judging the user's actual request
    t = _re.sub(r'\(system:.*?\)', '', t, flags=_re.DOTALL)

    markers = [
        "and then", "after that", "followed by", "step by step", "multi-step",
        "research and", "find and", "write and", "compare and", "summarize and",
    ]
    if any(m in t for m in markers):
        return True
    # Several independent clauses joined by standalone "and"s
    return len(_re.findall(r'\band\b', t)) >= 3


# Global instance
_task_planner_instance: Optional[TaskPlanner] = None


def get_task_planner(config: Dict, broadcast_func: Optional[Callable] = None) -> TaskPlanner:
    global _task_planner_instance
    if _task_planner_instance is None:
        _task_planner_instance = TaskPlanner(config, broadcast_func)
    return _task_planner_instance
