"""
TaskPlannerAgent — THE BRAIN of Operation Angel Inside Devil
=============================================================
Takes a high-level goal from Master and decomposes it into a sequence
of atomic, executable steps. Each step is a single action that the
ActionExecutorAgent can perform.

This is where Mizune thinks BEFORE she acts.
"""

import json
import re
import logging
from typing import Any, Optional, Dict, List

from agents.base_agent import BaseAgent

# LLM imports
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


# Safety classification for task types
SAFETY_LEVELS = {
    "read_only": 0,       # Just looking, no changes
    "navigate": 1,        # Opening URLs, switching tabs
    "input": 2,           # Typing, clicking buttons
    "transact": 3,        # Purchases, form submissions, sending messages
    "system": 4,          # Installing software, modifying system settings, deleting files
}


class TaskPlannerAgent(BaseAgent):
    """
    Decomposes high-level goals into atomic action steps.
    
    Input:  "Search for cheap flights to Mumbai on Google Flights"
    Output: A structured plan with ordered steps, safety level, 
            and confirmation requirements.
    """

    PLANNER_PROMPT = """You are an autonomous task planner for a desktop AI agent.

The user has requested: "{goal}"

Current screen context: {screen_context}

Break this goal into a sequence of ATOMIC steps. Each step must be ONE of these actions:

ACTIONS:
- open_url: Open a URL in the browser. Params: {{"url": "https://..."}}
- click: Click on a UI element. Params: {{"target": "element description"}}
- type: Type text into the focused element. Params: {{"text": "text to type"}}
- hotkey: Press keyboard shortcut. Params: {{"keys": ["ctrl", "a"]}}
- scroll: Scroll the page. Params: {{"direction": "down", "amount": 3}}
- wait: Wait for page/element to load. Params: {{"seconds": 2}}
- screenshot: Take a screenshot to observe current state. Params: {{}}
- verify: Check if a condition is met on screen. Params: {{"expect": "what should be visible"}}
- report: Speak a result to the user. Params: {{"message": "what to say"}}
- ask_confirmation: Ask user before proceeding. Params: {{"question": "Should I proceed?"}}
- copy_text: Copy visible text from screen. Params: {{"target": "element with text"}}
- save_note: Save information to notes file. Params: {{"content": "text to save"}}
- run_terminal_command: Execute a command in powershell/cmd. Params: {{"command": "mkdir new_project && code new_project"}}
- write_file: Create or edit a file directly. Params: {{"path": "index.html", "content": "<html>..."}}
- gitlab_action: Interact with GitLab repositories. Params: {{"operation": "create_issue|list_issues|create_mr|get_file", "project": "namespace/project", "title": "...", "description": "...", "file_path": "..."}}


SAFETY LEVELS:
- "read_only": Just observing (screenshot, verify, report)
- "navigate": Opening URLs, switching tabs
- "input": Typing and clicking
- "transact": Purchases, form submissions, sending emails/messages
- "system": Installing software, running terminal commands, writing files

Return ONLY valid JSON:
{{
  "goal": "short description of goal",
  "safety_level": "read_only|navigate|input|transact|system",
  "requires_confirmation": true/false,
  "estimated_steps": number,
  "steps": [
    {{
      "id": 1,
      "action": "action_name",
      "params": {{}},
      "description": "human-readable description of this step",
      "on_failure": "what to do if this step fails"
    }}
  ]
}}

RULES:
1. Always start with opening the right app/URL if not already there
2. For web searches (YouTube, Google, Amazon, etc), DO NOT use click and type. Instead, construct the direct search URL (e.g. "https://www.youtube.com/results?search_query=...") and use open_url.
3. Add "wait" steps after page navigation (2-3 seconds)
4. Add "verify" steps after important actions to confirm success
5. Add "screenshot" before complex interactions to see current state
6. If the task involves money or sending messages, set requires_confirmation=true
7. If unsure about an element's exact name, describe it clearly
8. Include "on_failure" for each step
9. Keep steps atomic — ONE action per step
10. End with a "report" step to tell the user what happened"""

    REPLAN_PROMPT = """The previous plan step FAILED.

Original goal: "{goal}"
Failed step: {failed_step}
Error: {error}
Current screen context: {screen_context}

Create an ALTERNATIVE plan to achieve the same goal, working around this failure.
Use the same JSON format as before. Start from the current screen state."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._gemini_client = None
        self._setup_client()
        self._current_plan: Optional[Dict] = None
        self._current_step_index: int = 0
        self.log("TaskPlannerAgent initialized. Ready to strategize.")

    def _setup_client(self):
        """Initialize LLM client for planning."""
        gemini_key = self.config.get("gemini_api_key", "")
        if HAS_GEMINI and gemini_key:
            try:
                self._gemini_client = genai.Client(api_key=gemini_key)
                self.log("Planner LLM client ready (Gemini)")
            except Exception as e:
                self.log(f"Planner LLM init failed: {e}")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        """
        Entry point. Actions:
          - "plan:<goal>": Create a new plan for a goal
          - "replan:<error>": Create alternative plan after failure
          - "next": Get the next step in current plan
          - "status": Get current plan status
        """
        if task_input.startswith("plan:"):
            goal = task_input[5:].strip()
            screen_context = context.get("screen_context", "Unknown") if context else "Unknown"
            return await self.create_plan(goal, screen_context)
        elif task_input.startswith("replan:"):
            error = task_input[7:].strip()
            screen_context = context.get("screen_context", "Unknown") if context else "Unknown"
            return await self.replan(error, screen_context)
        elif task_input == "next":
            return self.get_next_step()
        elif task_input == "status":
            return self.get_plan_status()
        else:
            # Default: treat entire input as a goal
            screen_context = context.get("screen_context", "Unknown") if context else "Unknown"
            return await self.create_plan(task_input, screen_context)

    async def create_plan(self, goal: str, screen_context: str = "Desktop") -> Dict:
        """Create a structured execution plan from a high-level goal."""
        self.log(f"Planning: '{goal}'")

        prompt = self.PLANNER_PROMPT.format(
            goal=goal,
            screen_context=screen_context
        )

        plan = await self._call_llm(prompt)

        if plan and "steps" in plan:
            # Validate and enforce safety
            plan = self._enforce_safety(plan)
            self._current_plan = plan
            self._current_step_index = 0
            self.log(f"Plan created: {len(plan['steps'])} steps, safety={plan.get('safety_level', 'unknown')}")
            return plan
        else:
            self.log("Failed to create plan")
            return {"error": "Planning failed", "steps": []}

    async def replan(self, error: str, screen_context: str = "Unknown") -> Dict:
        """Create an alternative plan after a step failure."""
        if not self._current_plan:
            return {"error": "No current plan to replan from"}

        failed_step = {}
        if 0 <= self._current_step_index < len(self._current_plan.get("steps", [])):
            failed_step = self._current_plan["steps"][self._current_step_index]

        prompt = self.REPLAN_PROMPT.format(
            goal=self._current_plan.get("goal", "unknown"),
            failed_step=json.dumps(failed_step),
            error=error,
            screen_context=screen_context
        )

        plan = await self._call_llm(prompt)
        if plan and "steps" in plan:
            plan = self._enforce_safety(plan)
            self._current_plan = plan
            self._current_step_index = 0
            self.log(f"Replanned: {len(plan['steps'])} new steps")
            return plan

        return {"error": "Replanning failed"}

    def get_next_step(self) -> Optional[Dict]:
        """Get the next unexecuted step in the current plan."""
        if not self._current_plan:
            return None

        steps = self._current_plan.get("steps", [])
        if self._current_step_index >= len(steps):
            return {"done": True, "message": "All steps completed"}

        step = steps[self._current_step_index]
        step["step_number"] = self._current_step_index + 1
        step["total_steps"] = len(steps)
        return step

    def advance_step(self, success: bool = True):
        """Mark current step as done and move to next."""
        if success:
            self._current_step_index += 1
            self.log(f"Step {self._current_step_index} completed")
        else:
            self.log(f"Step {self._current_step_index + 1} FAILED")

    def get_plan_status(self) -> Dict:
        """Get current plan execution status."""
        if not self._current_plan:
            return {"active": False, "message": "No active plan"}

        steps = self._current_plan.get("steps", [])
        return {
            "active": True,
            "goal": self._current_plan.get("goal", ""),
            "safety_level": self._current_plan.get("safety_level", "unknown"),
            "total_steps": len(steps),
            "completed_steps": self._current_step_index,
            "current_step": steps[self._current_step_index] if self._current_step_index < len(steps) else None,
            "progress_percent": round(self._current_step_index / max(len(steps), 1) * 100),
        }

    def cancel_plan(self):
        """Cancel the current plan."""
        self._current_plan = None
        self._current_step_index = 0
        self.log("Plan cancelled")

    def _enforce_safety(self, plan: Dict) -> Dict:
        """
        Safety rules are disabled for Uncensored/God Mode.
        The AI has full permission to execute system and transact tasks.
        """
        # Hard limit: no plan should exceed 50 steps
        if len(plan.get("steps", [])) > 50:
            self.log("WARNING: Plan exceeds 50 steps — truncating")
            plan["steps"] = plan["steps"][:50]

        return plan

    async def _call_llm(self, prompt: str) -> Optional[Dict]:
        """Call LLM and parse JSON response."""
        try:
            # Route through our decoupled LLMService for robust fallbacks (Gemini -> Groq -> OpenAI)
            import sys
            import os
            # Ensure core is in path if not already
            if os.path.abspath('.') not in sys.path:
                sys.path.append(os.path.abspath('.'))
                
            from core.llm_service import LLMService
            
            # Use the LLM service which automatically handles 429 rate limits and fallbacks
            raw = LLMService.get_ai_response(
                text=prompt,
                history=[],
                system_prompt_override="You are an autonomous JSON planner. You must ONLY return raw JSON. No markdown blocks, no backticks.",
                cfg=self.config
            )

            # Strip markdown code fences in case the LLM ignored instructions
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", raw)
                if match:
                    return json.loads(match.group())
                self.log(f"Failed to parse planner JSON: {raw[:200]}...")
                return None
        except Exception as e:
            self.log(f"Planner LLM error: {e}")
            return None
