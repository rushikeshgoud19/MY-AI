from agents.base_agent import BaseAgent
from typing import Any, Optional, Dict
import re
import logging

class ManagerAgent(BaseAgent):
    """
    The Central Brain of Mizune.
    Manages modes and routes requests to specialized worker agents.
    
    Modes:
      - conversation (default): Normal chat, defers to LLM
      - writing:    Continuous dictation / note-taking
      - focus:      Pomodoro timer, distraction blocking
      - entertainment: Media control, recommendations
      - research:   Web search, summarization
      - system:     PC control, environment setup
    """

    VALID_MODES = ["conversation", "writing", "focus", "entertainment", "research", "system", "coding", "vision"]

    def __init__(self, config: dict):
        super().__init__(config)
        self.workers: Dict[str, BaseAgent] = {}
        self.current_mode = "conversation"
        self._focus_timer = None
        self._focus_minutes = 25
        self.log("ManagerAgent initialized. Ready to route Master's commands.")

    async def execute(self, text: str, context: Optional[Dict] = None) -> Any:
        """
        1. Check for mode-switch commands
        2. If in a special mode, route to that mode's handler
        3. Otherwise return None to let the main LLM handle it
        """
        self.log(f"[Mode: {self.current_mode}] Routing: {text}")

        # ── 1. Mode switching ──
        mode_switch = self._detect_mode_switch(text)
        if mode_switch:
            old_mode = self.current_mode
            self.current_mode = mode_switch
            self.log(f"Mode changed: {old_mode} → {mode_switch}")
            return self._get_mode_greeting(mode_switch, old_mode)

        # ── 2. "What mode" / "current mode" query ──
        if re.search(r"\b(what mode|current mode|which mode|status)\b", text.lower()):
            return f"I'm currently in **{self.current_mode.capitalize()}** mode, Master~!"

        # ── 3. "Exit mode" / "normal mode" ──
        if re.search(r"\b(exit mode|normal mode|default mode|go back|leave mode|stop mode)\b", text.lower()):
            old = self.current_mode
            self.current_mode = "conversation"
            # Signal server to stop vision/coding if active
            prefix = ""
            if old == "vision":
                prefix = "[STOP_VISION] "
            elif old == "coding":
                prefix = "[STOP_CODING] "
            return f"{prefix}Exiting {old.capitalize()} mode! Back to normal conversation, Master~"

        # ── 4. Route based on current mode ──
        if self.current_mode == "writing":
            return await self._handle_writing(text, context)
        elif self.current_mode == "focus":
            return await self._handle_focus(text, context)
        elif self.current_mode == "entertainment":
            return await self._handle_entertainment(text, context)
        elif self.current_mode == "coding":
            return await self._handle_coding(text, context)
        elif self.current_mode == "research":
            return await self._handle_research(text, context)
        elif self.current_mode == "system":
            return await self._handle_system(text, context)
        elif self.current_mode == "vision":
            # Vision mode is handled by server.py's vision loop directly
            # But handle exit commands here
            if re.search(r"\b(stop watching|privacy mode|stop vision|exit vision|stop interactive)\b", text.lower()):
                self.current_mode = "conversation"
                return None  # Let server.py handle the actual stop
            return None  # Let LLM handle conversation while watching

        # ── 5. Conversation mode → return None for LLM ──
        return None

    # ─── Mode Detection ──────────────────────────────────────────────────────
    def _detect_mode_switch(self, text: str) -> Optional[str]:
        lower = text.lower()
        patterns = {
            "writing":       r"\b(writing mode|dictation mode|dictate|start writing|type for me)\b",
            "focus":         r"\b(focus mode|pomodoro|study mode|concentration|do not disturb)\b",
            "entertainment": r"\b(entertainment mode|fun mode|chill mode|relax mode|media mode)\b",
            "research":      r"\b(research mode|study|investigate|deep dive|look into)\b",
            "system":        r"\b(system mode|developer mode|dev mode|pc control|admin mode)\b",
            "coding":        r"\b(coding mode|code mode|leetcode mode|coding coach|watch me code|pair program|code review mode|code with me)\b",
            "vision":        r"\b(vision mode|interactive mode|companion mode|watch me|start watching)\b",
            "conversation":  r"\b(conversation mode|chat mode|talk mode|normal mode)\b",
        }
        for mode, pattern in patterns.items():
            if re.search(pattern, lower):
                return mode
        return None

    def _get_mode_greeting(self, new_mode: str, old_mode: str) -> str:
        greetings = {
            "writing": "✍️ Writing Mode activated! I'll transcribe everything you say, Master. Just speak naturally and I'll type it all out~ Say 'exit mode' when you're done!",
            "focus": f"🎯 Focus Mode activated! Starting a {self._focus_minutes}-minute Pomodoro session. I'll keep distractions away, Master~ Say 'exit mode' or 'take a break' when ready!",
            "entertainment": "🎵 Entertainment Mode activated! I can control your music, suggest anime, or find something fun~ What shall we do, Master?",
            "research": "🔍 Research Mode activated! I'll search the web, summarize articles, and gather info for you, Master~ What topic shall I investigate?",
            "system": "⚙️ System Mode activated! Full PC control unlocked. I can set up projects, analyze code, manage files, and more~ What do you need, Master?",
            "coding": "💻 Coding Coach Mode activated! I'm watching your screen now, Master~ I'll analyze your code every 20 seconds, catch mistakes, suggest improvements, and cheer you on! Ganbatte~! Say 'exit mode' when done!",
            "vision": "👁️ Interactive Vision Mode activated! I'm watching everything on your screen now, Master~ I'll comment on what I see! Say 'stop watching' or 'exit mode' for privacy!",
            "conversation": "💬 Back to Conversation Mode! Just chatting normally now, Master~",
        }
        return greetings.get(new_mode, f"Switched to {new_mode.capitalize()} mode!")

    # ─── Mode Handlers ───────────────────────────────────────────────────────
    async def _handle_writing(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Writing mode: save spoken text as notes."""
        lower = text.lower()

        # Commands within writing mode
        if re.search(r"\b(save|done|finish writing|stop writing)\b", lower):
            self.current_mode = "conversation"
            return "✍️ Writing session saved! Returning to conversation mode, Master~"

        if re.search(r"\b(new line|next line|paragraph|new paragraph)\b", lower):
            return "[WRITING_NEWLINE]"  # Signal to the note system

        if re.search(r"\b(read back|read it back|what did i say)\b", lower):
            return None  # Let LLM handle with context

        # In writing mode, everything else gets saved as a note
        # Return None to let the main process_command handle it via LLM
        # but prefix with writing context
        return None

    async def _handle_focus(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Focus mode: Pomodoro timer, motivational nudges."""
        lower = text.lower()

        if re.search(r"\b(take a break|break time|rest)\b", lower):
            self.current_mode = "conversation"
            return "☕ Break time! You've earned it, Master~ Take 5 minutes to relax. Say 'focus mode' when you're ready to go again!"

        if re.search(r"\b(how long|time left|how much time|timer)\b", lower):
            return f"You're in focus mode with a {self._focus_minutes}-minute session, Master! Stay strong~ 💪"

        if re.search(r"\b(set timer|set pomodoro|(\d+)\s*min)", lower):
            mins_match = re.search(r"(\d+)\s*min", lower)
            if mins_match:
                self._focus_minutes = int(mins_match.group(1))
                return f"🎯 Timer set to {self._focus_minutes} minutes! Let's do this, Master~"

        # In focus mode, redirect non-work queries
        if re.search(r"\b(youtube|netflix|anime|game|reddit|twitter|instagram|tiktok)\b", lower):
            return "Ehh?! Master, you're in Focus Mode! No distractions allowed~ 😤 Stay focused, you can do it! Ganbatte~!"

        # For work-related queries, let LLM handle
        return None

    async def _handle_entertainment(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Entertainment mode: media control, suggestions."""
        lower = text.lower()

        if re.search(r"\b(suggest|recommend)\b", lower) and re.search(r"\b(anime|show|movie|music|song)\b", lower):
            # Let LLM handle recommendations with its personality
            return None

        # Media controls are handled by process_command's built-in handlers
        return None

    async def _handle_research(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Research mode: web search and summarization."""
        if "web" in self.workers:
            try:
                result = await self.workers["web"].execute(text, context)
                return result
            except Exception as e:
                self.log(f"WebAgent failed: {e}")

        # Fall through to LLM for research queries
        return None

    async def _handle_system(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """System mode: PC control, environment setup."""
        if "system" in self.workers:
            try:
                result = await self.workers["system"].execute(text, context)
                return result
            except Exception as e:
                self.log(f"SystemAgent failed: {e}")

        # Fall through to built-in handlers or LLM
        return None

    async def _handle_coding(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Coding coach mode: screen monitoring + code review.
        In this mode, most queries about code trigger screen analysis, NOT app launching."""
        lower = text.lower()

        if re.search(r"\b(pause monitoring|stop watching|pause screen)\b", lower):
            return "[CODING_PAUSE] Got it, Master! I'll stop watching your screen for now~ Say 'resume monitoring' when you want me back!"

        if re.search(r"\b(resume monitoring|start watching|watch again|resume screen)\b", lower):
            return "[CODING_RESUME] Hai~! I'm watching your screen again, Master! Let's keep coding~!"

        # Broad screen review triggers — anything asking about code/screen
        if re.search(r"\b(how is|how's|is this|is it|am i|what do you think|look at|check|review|analyze|rate|evaluate|correct|wrong|right|good|bad|okay)\b", lower) and \
           re.search(r"\b(code|this|it|screen|solution|approach|logic|doing|going|progress|work|working)\b", lower):
            return "[CODING_REVIEW_NOW] Let me take a look at your screen right now, Master~!"

        # Direct questions about the code
        if re.search(r"\b(what'?s wrong|any error|any mistake|any bug|see anything|spot anything|find anything)\b", lower):
            return "[CODING_REVIEW_NOW] Let me check for issues, Master~!"

        # Asking for help/hints
        if re.search(r"\b(hint|help|stuck|don'?t know|no idea|confused|lost|what should i|how do i|how should|what next|next step)\b", lower):
            return "[CODING_HINT] Let me check your screen and give you a hint, Master~!"

        # Prevent "open code/editor/terminal" from falling through to app launcher
        if re.search(r"\b(open|launch|start)\b", lower) and re.search(r"\b(code|editor|terminal|vscode|vs code)\b", lower):
            return "Master, we're in Coding Coach mode! I'm watching your screen, not opening apps. Say 'exit mode' first if you want to open something~"

        # Everything else in coding mode → let LLM handle BUT with screen context
        # Don't let random phrases trigger app launching
        return None
