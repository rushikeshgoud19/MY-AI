"""
ManagerAgent — THE BRAIN of Mizune AI
======================================
Intelligent intent-based routing system. NO explicit mode triggers needed.

The user simply speaks naturally:
  "Open Chrome"              → SystemAgent handles it
  "What's on my screen?"     → VisionPerceptionAgent handles it
  "Search for flights"       → Autonomous pipeline OR WebAgent
  "How's my code looking?"   → CodingCoach pipeline
  "Play some music"          → Entertainment handler
  "Just chatting"            → LLM conversation

The brain classifies intent from the text itself and routes silently.
The frontend never knows what "mode" is active — it just gets a response.
"""

from agents.base_agent import BaseAgent
from typing import Any, Optional, Dict, List
import re
import logging
import json


class ManagerAgent(BaseAgent):
    """
    The Central Brain of Mizune.
    
    Uses a 3-tier intent classification system:
      Tier 1: Zero-cost regex patterns for obvious intents (instant, free)
      Tier 2: Keyword scoring for ambiguous intents (instant, free)
      Tier 3: LLM classification for complex/uncertain intents (API call)
    
    Routes silently — no "mode activated!" messages. Just does the right thing.
    """

    # All capabilities Mizune has
    INTENTS = [
        "conversation",    # Normal chat, jokes, questions, personality
        "system",          # Open/close apps, screenshots, PC control
        "autonomous",      # Multi-step tasks requiring screen interaction
        "research",        # Web search, information lookup
        "entertainment",   # Music, anime, media, fun
        "coding",          # Code review, debugging, watching screen for code
        "vision",          # What's on screen, describe what you see
        "writing",         # Dictation, note-taking, type for me
        "focus",           # Pomodoro, concentration, distraction blocking
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.workers: Dict[str, BaseAgent] = {}
        self.current_mode = "conversation"  # Internal state — frontend doesn't see this
        self._focus_timer = None
        self._focus_minutes = 25
        self._autonomous_pending_confirm = False  # Waiting for user to confirm a plan
        self._pending_plan = None
        self.log("ManagerAgent Brain initialized. Silent intent routing active.")

    async def execute(self, text: str, context: Optional[Dict] = None) -> Any:
        """
        The Brain. Takes ANY user input and routes it to the right handler.
        No explicit mode triggers needed — intent is detected automatically.
        """
        lower = text.lower().strip()
        self.log(f"[Brain] Input: '{text[:80]}' | Background mode: {self.current_mode}")

        # ── 0. Handle pending autonomous confirmation ──
        if self._autonomous_pending_confirm:
            return await self._handle_autonomous_confirmation(text)

        # ── 1. Sticky mode commands (only if user explicitly asked for a mode before) ──
        # Writing/focus are "sticky" — they stay active until explicitly exited
        if self.current_mode == "writing":
            if re.search(r"\b(exit|stop writing|done writing|finish|quit)(\s+mode)?\b", lower):
                self.current_mode = "conversation"
                return "✍️ Writing session saved! What's next, Master~?"
            return await self._handle_writing(text, context)

        if self.current_mode == "focus":
            if re.search(r"\b(exit|stop focus|end focus|quit|take a break)(\s+mode)?\b", lower):
                self.current_mode = "conversation"
                return "☕ Break time! You've earned it, Master~"
            return await self._handle_focus(text, context)

        # ── 2. Explicit mode requests (user specifically wants a mode) ──
        explicit_mode = self._detect_explicit_mode(text)
        if explicit_mode:
            return await self._activate_mode(explicit_mode, text)

        # ── 3. THE BRAIN — Intent Classification ──
        intent = self._classify_intent(text)
        self.log(f"[Brain] Classified intent: {intent}")

        # ── 4. Route to handler based on intent ──
        return await self._route_by_intent(intent, text, context)

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 1: EXPLICIT MODE DETECTION (only when user ASKS for a mode)
    # ═══════════════════════════════════════════════════════════════════════════

    def _detect_explicit_mode(self, text: str) -> Optional[str]:
        """Only detect if user EXPLICITLY asks for a mode by name."""
        lower = text.lower()
        # Only match when user says the word "mode" explicitly
        explicit = {
            "writing":       r"\b(writing mode|dictation mode|start dictating)\b",
            "focus":         r"\b(focus mode|pomodoro mode|study mode|do not disturb)\b",
            "autonomous":    r"\b(autonomous mode|agent mode|autopilot mode|auto mode)\b",
            "coding":        r"\b(coding mode|code mode|coding coach mode|pair program mode)\b",
            "vision":        r"\b(vision mode|interactive mode)\b",
            "conversation":  r"\b(conversation mode|chat mode|normal mode|exit mode|default mode|go back|leave mode|stop mode)\b",
        }
        for mode, pattern in explicit.items():
            if re.search(pattern, lower):
                return mode
        return None

    async def _activate_mode(self, mode: str, text: str) -> str:
        """Activate a mode explicitly — this is the only time we announce it."""
        old = self.current_mode
        self.current_mode = mode

        if mode == "conversation" and old != "conversation":
            prefix = ""
            if old == "vision":
                prefix = "[STOP_VISION] "
            elif old == "coding":
                prefix = "[STOP_CODING] "
            return f"{prefix}Got it, Master~ Back to normal!"

        greetings = {
            "writing": "✍️ Writing mode! I'll type everything you say. Tell me when you're done!",
            "focus": f"🎯 Focus mode! {self._focus_minutes}-minute session starts now. Stay strong, Master~!",
            "autonomous": "⚡ Full autonomous mode! Tell me what to do and I'll handle everything myself~!",
            "coding": "💻 Coding coach! I'm watching your screen now. Let's write some clean code~!",
            "vision": "👁️ Vision active! I can see your screen now~!",
        }
        return greetings.get(mode, f"Switched to {mode}, Master!")

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 2: SMART INTENT CLASSIFICATION (regex + keyword scoring)
    # ═══════════════════════════════════════════════════════════════════════════

    def _classify_intent(self, text: str) -> str:
        """
        The core brain. Classifies user intent WITHOUT requiring trigger words.
        Uses prioritized pattern matching — first match wins.
        """
        lower = text.lower().strip()
        # Strip trailing punctuation only (keep apostrophes for contractions like what's, how's)
        clean = re.sub(r"[!?.,\"]+", "", lower).strip()

        # ── GUARD: Very short conversational inputs (1-2 words, no action words) ──
        word_count = len(clean.split())
        if word_count <= 2 and not re.search(
            r"\b(open|close|launch|start|kill|play|sing|search|screenshot|mute|unmute|"
            r"volume|lock|sleep|shutdown|restart|describe|review|check|debug|fix|watch|"
            r"pause|resume|remember|block|log|increase|decrease|brightness)\b", clean
        ):
            return "conversation"
        # ─── AUTONOMOUS: EXTREME COMPLEXITY GUARD (Runs first) ────────────
        # Brutal edge-case tasks orchestrating multiple apps or background tasks
        if re.search(r"\b(side\s*by\s*side|in\s+(the\s+)?background|second\s+monitor|main\s+one|while\s+it\s+plays|while\s+doing\s+that|while\s+(i|you|it)\s+|every\s+time)\b", clean):
            return "autonomous"

        # Action density heuristic for very long orchestrations
        if word_count >= 10:
            actions = re.findall(r"\b(open|launch|start|play|playing|search|find|mute|cut|sing|keep|snap|take|analyze|type|apply|block|checkout|go\s+to|copy|watch|load|navigate|turn)\b", clean)
            conjunctions = re.findall(r"\b(and|then|after\s+that)\b", clean)
            
            if len(set(actions)) >= 3:
                return "autonomous"
            if len(actions) >= 2 and len(conjunctions) >= 2:
                return "autonomous"

        # ─── SYSTEM: App control + PC commands ────────────────────────────

        app_names = (r"chrome|brave|firefox|edge|code|vs\s*code|terminal|discord|spotify|steam|"
                     r"notepad|excel|word|explorer|settings|calculator|obs|telegram|whatsapp|"
                     r"task\s*manager|powershell|cmd|browser|blender|figma|slack|teams|outlook|paint")

        if re.search(r"\b(open|launch|start|close|kill)\b", clean) and re.search(rf"\b({app_names})\b", clean):
            if re.search(r"\b(and\s+(go|navigate|search|find|then|also|do))\b", clean):
                return "autonomous"
            return "system"

        if re.search(r"\b(closing|opening|launching|starting)\b", clean) and re.search(rf"\b({app_names})\b", clean):
            return "system"

        if re.search(r"\b(take\s+(a\s+)?screenshot|screen\s*shot)\b", clean):
            return "system"
        if re.search(r"\b(lock\s+(the\s+|my\s+)?(pc|computer|screen)|"
                     r"shut\s*down(\s+(the\s+)?(pc|computer))?|"
                     r"restart(\s+(the\s+)?(pc|computer))?|"
                     r"(put|sleep)\s+.{0,10}(pc|computer)(\s+to\s+sleep)?|"
                     r"sleep\s+(the\s+)?(pc|computer)|"
                     r"log\s*off|log\s*out)\b", clean):
            return "system"
        if re.search(r"\b(volume\s*(up|down)|mute|unmute|"
                     r"(increase|decrease|turn\s+(up|down))\s*(the\s+)?(volume|brightness)|"
                     r"brightness)\b", clean):
            return "system"

        # ─── AUTONOMOUS: Multi-step tasks ─────────────────────────────────

        auto_pattern = (r"\b(search\s+for\s+.+\s+on\s+(amazon|flipkart|google|ebay|linkedin|indeed)|"
                        r"book\s+(a\s+)?(flight|hotel|ticket|cab|ride)|"
                        r"order\s+(a\s+|me\s+|food\s+|something\s+)?(from\s+)?|"
                        r"buy\s+(me\s+)?(a\s+)?|"
                        r"fill\s+(out\s+|in\s+)?(the\s+|this\s+|a\s+)?form|"
                        r"go\s+to\s+\S+\s+(and|then)\s+|"
                        r"navigate\s+to\s+.+\s+and\s+|"
                        r"go\s+to\s+(google\s+maps|amazon|flipkart|github|linkedin))\b")
        if re.search(auto_pattern, clean):
            return "autonomous"

        # Chain detection: action + "and" + follow-up action
        if re.search(r"\b(search|find|go|navigate|look)\b", clean) and \
           re.search(r"\b(and\s+(apply|save|sort|compare|add|buy|order|book|download|submit|click|then|filter|select))\b", clean):
            return "autonomous"

        if re.search(r"\b(do\s+it\s+(yourself|for\s+me)|do\s+this\s+for\s+me|"
                     r"handle\s+it(\s+yourself)?|take\s+control|operate\s+(my\s+)?pc|"
                     r"can\s+you\s+do\s+(it|this)\s+(for|by)\s+(me|yourself)|"
                     r"just\s+do\s+it\s+for\s+me|"
                     r"can\s+you\s+(order|book|buy|search|find)\s+.+\s+(online|for\s+me))\b", clean):
            return "autonomous"

        if re.search(r"\b(bruh|bro|yo|dude|fam)\b", clean) and \
           re.search(r"\b(do\s+it|handle\s+it|just\s+do|for\s+me)\b", clean):
            return "autonomous"

        # ─── VISION: What's on screen ─────────────────────────────────────

        if re.search(r"\b(what('s|\s+is)\s+(on\s+)?(my\s+)?(the\s+)?screen|"
                     r"what('s|\s+is)\s+happening\s+on\s+(my\s+)?screen|"
                     r"what\s+(do\s+you|can\s+you)\s+see|"
                     r"(can\s+you\s+)?see\s+my\s+screen|"
                     r"(look|looking)\s+at\s+(my\s+)?(screen|this)|"
                     r"describe\s+(my\s+)?(screen|what)|"
                     r"what('s|\s+is)\s+(this|that)\s+(on\s+)?(my\s+)?screen|"
                     r"read\s+(my\s+)?screen|read\s+what's\s+on|"
                     r"on\s+(the\s+)?screen\s+(right\s+)?now|"
                     r"what\s+am\s+i\s+(looking\s+at|doing|watching)|"
                     r"(see|check|lemme\s+see|let\s+me\s+see)\s+(whats|what's|what\s+is)\s+on\s+screen|"
                     r"look\s+at\s+my\s+screen\s+and)\b", clean):
            return "vision"

        # ─── CODING: Code review, debugging ───────────────────────────────

        if re.search(r"\b(check\s+(my\s+)?code|review\s+(my\s+)?code|"
                     r"checking\s+(my\s+)?code|"
                     r"how('s|\s+is)\s+my\s+code|any\s+(bug|error|mistake|issue)s?\s+(in\s+|with\s+)?(my\s+)?code|"
                     r"debug\s+(this|my)|fix\s+(this|my)\s+(code|error|bug)|"
                     r"watch\s+me\s+code|what('s|\s+is)\s+wrong\s+with\s+(my\s+)?code|"
                     r"code\s+review|explain\s+(this|my)\s+code|"
                     r"is\s+(this|my)\s+(code|solution)\s+(correct|right|wrong|good|bad|ok)|"
                     r"(think|thought)\s+about\s+(this\s+|my\s+)?code|"
                     r"help\s+me\s+(with\s+)?(this\s+)?(code|function|class|error|bug)|"
                     r"help\s+me\s+fix\s+(this\s+)?(bug|error|issue)|"
                     r"did\s+i\s+(do|code)\s+(it|this)?\s*(good|well|right|correct(ly)?)|"
                     r"make\s+(this|my)\s+code\s+better|improve\s+(this|my)\s+code|"
                     r"coding\s+question|"
                     r"can\s+you\s+check\s+(it|this|my))\b", clean):
            return "coding"

        # ─── RESEARCH: Information lookup ─────────────────────────────────

        if re.search(r"\b(search\s+for|look\s+up|google|"
                     r"research\s+(about|on|into)|"
                     r"find\s+(info|information|out)\s+(about|on))\b", clean):
            if not re.search(r"\b(and\s+(then|apply|save|sort|add|buy|order|book|also|filter))\b", clean):
                return "research"

        # "what is X" / "who is X" — exclude common non-research words
        non_research = r"(this|that|it|up|happening|going|wrong|good|bad|ok|2\+2|\d+\+\d+)"
        if re.search(rf"\b(what\s+is\s+(?!{non_research}\b)(a\s+|an\s+)?\w{{3,}}|" 
                     r"who\s+is\s+(?!this\b|that\b|it\b)\w{3,}|"
                     r"tell\s+me\s+about\s+\w{3,}|"
                     r"how\s+does\s+\w{3,}\s+work|"
                     r"best\s+\w+\s+of\s+\d{4}|"
                     rf"what\s+is\s+the\s+\w{{3,}}\s+of\s+\w{{3,}})\b", clean):
            return "research"

        # ─── ENTERTAINMENT: Music, media, anime ───────────────────────────

        if re.search(r"\b(play\s+(some\s+|a\s+|my\s+)?\w*\s*(music|song|songs|anime|video|movie|tunes|playlist)|"
                     r"sing\s+(a\s+)?song(\s+for\s+me)?|sing\s+for\s+me|^sing$|"
                     r"recommend\s+(an?\s+|me\s+)?(anime|movie|song|show)|"
                     r"suggest\s+(an?\s+|me\s+)?(a\s+)?(good\s+)?(anime|movie|song|show)|"
                     r"next\s+song|previous\s+song|pause\s+music|resume\s+music|"
                     r"put\s+on\s+(some\s+)?(music|anime|tunes)|"
                     r"watch\s+(something|anime|a\s+movie|movies?|netflix|youtube|crunchyroll)|"
                     r"(gimme|give\s+me)\s+(a\s+)?(song|music)\s*(recommendation|suggestion)?|"
                     r"what\s+(anime|movie|show|song)?\s*should\s+i\s+(watch|listen|play)|"
                     r"i\s+want\s+to\s+watch\s+(something|anime|a\s+movie)|"
                     r"play\s+something)\b", clean):
            return "entertainment"

        # ─── WRITING: Note-taking ─────────────────────────────────────────

        if re.search(r"\b(write\s+this\s+down|take\s+a\s+note|"
                     r"note\s+this|remember\s+this|save\s+this|"
                     r"type\s+(this|for\s+me)|start\s+dictating)\b", clean):
            return "writing"

        # ─── FOCUS: Productivity ──────────────────────────────────────────

        if re.search(r"\b(start\s+pomodoro|i\s+need\s+to\s+focus|"
                     r"help\s+me\s+(focus|concentrate)|block\s+distractions|"
                     r"do\s+not\s+disturb|"
                     r"set\s+(a\s+)?timer(\s+\d+\s*min)?|"
                     r"\d+\s*min(ute)?s?\s*(timer|pomodoro|focus))\b", clean):
            return "focus"


        # ─── FALLBACK: Conversation ───────────────────────────────────────
        return "conversation"

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 3: INTENT ROUTING (silent — no announcements)
    # ═══════════════════════════════════════════════════════════════════════════

    async def _route_by_intent(self, intent: str, text: str, context: Optional[Dict] = None) -> Any:
        """Route to the right handler based on classified intent. SILENTLY."""

        if intent == "system":
            self.current_mode = "system"
            if "system" in self.workers:
                try:
                    result = await self.workers["system"].execute(text, context)
                    if result:
                        return result
                except Exception as e:
                    self.log(f"SystemAgent error: {e}")
            return None  # Fall through to server.py built-in handlers

        elif intent == "autonomous":
            self.current_mode = "autonomous"
            return await self._handle_autonomous(text, context)

        elif intent == "vision":
            self.current_mode = "vision"
            return await self._handle_vision_query(text, context)

        elif intent == "coding":
            self.current_mode = "coding"
            return await self._handle_coding(text, context)

        elif intent == "research":
            self.current_mode = "research"
            return await self._handle_research(text, context)

        elif intent == "entertainment":
            self.current_mode = "entertainment"
            return None  # Let server.py's built-in media handlers catch it

        elif intent == "writing":
            self.current_mode = "writing"
            return await self._handle_writing(text, context)

        elif intent == "focus":
            self.current_mode = "focus"
            return f"🎯 Got it! {self._focus_minutes}-minute focus session started. Stay strong, Master~!"

        else:
            # Conversation — reset to default, let LLM handle
            self.current_mode = "conversation"
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # MODE HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    async def _handle_vision_query(self, text: str, context: Optional[Dict] = None) -> Optional[str]:
        """Handle one-shot vision queries without entering a persistent mode."""
        if "vision" in self.workers:
            try:
                perception = await self.workers["vision"].execute("perceive")
                page_ctx = perception.get("page_context", "unknown screen")
                elements = perception.get("elements", [])
                
                # Build a summary for the LLM to use
                elem_summary = ", ".join(
                    e.get("label", "?") for e in elements[:10]
                ) if elements else "no clear interactive elements"
                
                # Return context so server.py can feed it to the LLM
                return (f"[VISION_CONTEXT] I can see: {page_ctx}. "
                        f"Interactive elements: {elem_summary}. "
                        f"Let me describe what's on Master's screen~")
            except Exception as e:
                self.log(f"Vision query failed: {e}")
        # Fall through to server.py's existing vision handling
        return None

    async def _handle_writing(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Writing mode: save spoken text as notes."""
        lower = text.lower()
        if re.search(r"\b(save|done|finish writing|stop writing)(\s+mode)?\b", lower):
            self.current_mode = "conversation"
            return "✍️ Writing session saved! What's next, Master~?"
        if re.search(r"\b(new line|next line|paragraph|new paragraph)\b", lower):
            return "[WRITING_NEWLINE]"
        if re.search(r"\b(read back|read it back|what did i say)\b", lower):
            return None
        return None

    async def _handle_focus(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Focus mode: Pomodoro timer, motivational nudges."""
        lower = text.lower()
        if re.search(r"\b(take a break|break time|rest)\b", lower):
            self.current_mode = "conversation"
            return "☕ Break time! You've earned it, Master~ Take 5 minutes to relax!"
        if re.search(r"\b(how long|time left|how much time|timer)\b", lower):
            return f"You're in focus mode with a {self._focus_minutes}-minute session, Master! Stay strong~ 💪"
        if re.search(r"\b(set timer|set pomodoro|(\d+)\s*min)", lower):
            mins_match = re.search(r"(\d+)\s*min", lower)
            if mins_match:
                self._focus_minutes = int(mins_match.group(1))
                return f"🎯 Timer set to {self._focus_minutes} minutes!"
        # In focus mode, block entertainment
        if re.search(r"\b(youtube|netflix|anime|game|reddit|twitter|instagram|tiktok)\b", lower):
            return "Ehh?! Master, you're focusing! No distractions~ 😤 Ganbatte!"
        return None

    async def _handle_research(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Research: web search and summarization."""
        if "web" in self.workers:
            try:
                result = await self.workers["web"].execute(text, context)
                return result
            except Exception as e:
                self.log(f"WebAgent failed: {e}")
        return None

    async def _handle_coding(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Coding: screen monitoring + code review."""
        lower = text.lower()
        if re.search(r"\b(pause monitoring|stop watching|pause screen)\b", lower):
            return "[CODING_PAUSE] Got it! I'll stop watching for now~"
        if re.search(r"\b(resume monitoring|start watching|watch again)\b", lower):
            return "[CODING_RESUME] Watching your screen again~!"

        # Screen review triggers
        if re.search(r"\b(how is|how's|is this|is it|am i|what do you think|look at|check|review|"
                     r"analyze|rate|evaluate|correct|wrong|right|good|bad|okay|better|improve|"
                     r"did i|fix|debug)\b", lower):
            return "[CODING_REVIEW_NOW] Let me take a look at your code, Master~!"
        if re.search(r"\b(what's wrong|any error|any mistake|any bug|see anything|spot anything)\b", lower):
            return "[CODING_REVIEW_NOW] Let me check for bugs, Master~!"
        if re.search(r"\b(give me a hint|hint|stuck)\b", lower):
            return "[CODING_HINT] Hmm, let's see... I'll give you a small hint~"
        
        # If they asked a coding question and we are in coding mode, just review the screen by default.
        return "[CODING_REVIEW_NOW] Let me check your screen to answer that~!"

    # ─── Autonomous Mode ──────────────────────────────────────────────────────

    async def _handle_autonomous_confirmation(self, text: str) -> Optional[str]:
        """Handle user's response to an autonomous plan confirmation."""
        lower = text.lower()
        if re.search(r"\b(go ahead|proceed|yes|do it|confirm|approved|sure|okay|yep|yea)\b", lower):
            self._autonomous_pending_confirm = False
            if self._pending_plan:
                plan = self._pending_plan
                self._pending_plan = None
                return await self._execute_autonomous_plan(plan)
            return "I lost track of the plan, Master... Can you tell me again?"
        elif re.search(r"\b(cancel|no|stop|abort|don't|nah|nope|nevermind)\b", lower):
            self._autonomous_pending_confirm = False
            self._pending_plan = None
            self.current_mode = "conversation"
            return "Got it! Cancelled. What else can I do, Master?"
        else:
            return "I'm waiting for your confirmation, Master~ Say 'go ahead' or 'cancel'!"

    async def _handle_autonomous(self, text: str, context: Optional[Dict]) -> Optional[str]:
        """Autonomous mode: Mizune operates the computer herself."""
        lower = text.lower()

        # Stop/cancel
        if re.search(r"\b(stop|cancel|abort|halt|take back control)\b", lower):
            if "planner" in self.workers:
                self.workers["planner"].cancel_plan()
            if "executor" in self.workers:
                self.workers["executor"].reset_session()
            self.current_mode = "conversation"
            return "You're in control again, Master~"

        # Status check
        if re.search(r"\b(status|progress|where are you|what step|how far)\b", lower):
            if "planner" in self.workers:
                status = self.workers["planner"].get_plan_status()
                if status.get("active"):
                    return (f"Working on: {status['goal']}\n"
                            f"Progress: Step {status['completed_steps']}/{status['total_steps']} "
                            f"({status['progress_percent']}%)")
            return "No active task. Tell me what to do!"

        # ── New goal — run the full pipeline ──
        self.log(f"[Brain/Auto] New goal: {text}")

        # Step 1: PERCEIVE
        screen_context = "Desktop"
        if "vision" in self.workers:
            try:
                perception = await self.workers["vision"].execute("perceive")
                screen_context = perception.get("page_context", "Desktop")
            except Exception as e:
                self.log(f"[Brain/Auto] Vision failed: {e}")

        # Step 2: PLAN
        if "planner" not in self.workers:
            return "My planning brain isn't connected, Master..."

        plan = await self.workers["planner"].execute(
            f"plan:{text}",
            context={"screen_context": screen_context}
        )

        if not plan or "error" in plan:
            return f"I couldn't figure out how to do that... {plan.get('error', '')}"

        # Safety gate
        if plan.get("requires_confirmation"):
            self._autonomous_pending_confirm = True
            self._pending_plan = plan
            safety = plan.get('safety_level', 'unknown')
            step_count = len(plan.get('steps', []))
            return (f"I've planned {step_count} steps for: {plan.get('goal', text)}\n"
                    f"Safety: {safety.upper()}\n"
                    f"Say 'go ahead' to start or 'cancel' to abort!")

        # Step 3: EXECUTE
        return await self._execute_autonomous_plan(plan)

    async def _execute_autonomous_plan(self, plan: Dict) -> str:
        """Execute a full autonomous plan step by step."""
        planner = self.workers.get("planner")
        executor = self.workers.get("executor")
        vision = self.workers.get("vision")

        if not executor:
            return "ActionExecutorAgent not connected..."

        steps = plan.get("steps", [])
        results_log = []

        for i, step in enumerate(steps):
            action = step.get("action", "")
            self.log(f"[Brain/Auto] Step {i+1}/{len(steps)}: {action}")

            # Get fresh vision for interaction actions
            vision_elements = []
            if action in ("click", "type", "copy_text") and vision:
                try:
                    perception = await vision.execute("perceive", {})
                    vision_elements = perception.get("elements", [])
                except Exception:
                    pass

            # Execute
            import json as _json
            result = await executor.execute(
                _json.dumps(step),
                context={"vision_elements": vision_elements}
            )

            if result.get("abort"):
                return f"⚠️ Stopped at step {i+1}: {result.get('error', 'Safety limit')}"

            if result.get("needs_confirmation"):
                self._autonomous_pending_confirm = True
                self._pending_plan = {"steps": steps[i:], "goal": plan.get("goal", ""), "safety_level": plan.get("safety_level", "input")}
                return f"Step {i+1}: {result.get('question', 'Proceed?')}\nSay 'go ahead' or 'cancel'."

            if result.get("report"):
                return f"[EMOTION: happy] {result.get('message', 'Done!')}"

            if not result.get("success", False) and action not in ("verify", "screenshot"):
                error = result.get("error", "Unknown error")
                self.log(f"[Brain/Auto] Step failed: {error}")

                if planner and i < len(steps) - 1:
                    screen_ctx = "Unknown"
                    if vision:
                        try:
                            p = await vision.execute("perceive")
                            screen_ctx = p.get("page_context", "Unknown")
                        except Exception:
                            pass
                    new_plan = await planner.execute(
                        f"replan:{error}",
                        context={"screen_context": screen_ctx}
                    )
                    if new_plan and "steps" in new_plan:
                        return await self._execute_autonomous_plan(new_plan)

                return f"Step {i+1} failed: {error}. {step.get('on_failure', 'Could not complete task')}."

            results_log.append(f"✅ Step {i+1}: {step.get('description', action)}")

        # Reset to conversation after task completes
        self.current_mode = "conversation"
        return f"[EMOTION: happy] Done, Master~! All {len(steps)} steps completed!\n" + "\n".join(results_log[-3:])
