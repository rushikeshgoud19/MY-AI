"""
Intent Classifier Module
========================
High-performance zero-token intent classification for Mizune.
Uses prioritized pattern matching - first match wins.

This module classifies user input into intent categories WITHOUT requiring
trigger words. It uses regex patterns for fast, cost-free classification.
"""

import re
from typing import Dict, List, Optional, Set


class IntentClassifier:
    """
    Zero-token intent classifier using regex pattern matching.
    Designed for speed - no LLM calls needed for classification.
    """

    # Precompiled patterns for better performance
    _GUARD_SHORT_PATTERNS = re.compile(
        r"\b(open|close|launch|start|kill|play|sing|search|screenshot|mute|unmute|"
        r"volume|lock|sleep|shutdown|restart|describe|review|check|debug|fix|watch|"
        r"pause|resume|remember|block|log|increase|decrease|brightness)\b"
    )

    _AUTONOMOUS_EXTREME_PATTERNS = re.compile(
        r"\b(side\s*by\s*side|in\s+(the\s+)?background|second\s+monitor|main\s+one|"
        r"while\s+it\s+plays|while\s+doing\s+that|while\s+(i|you|it)\s+|every\s+time)\b"
    )

    _ACTION_PATTERNS = re.compile(
        r"\b(open|launch|start|play|playing|search|find|mute|cut|sing|keep|snap|take|"
        r"analyze|type|apply|block|checkout|go\s+to|copy|watch|load|navigate|turn)\b"
    )

    _CONJUNCTION_PATTERNS = re.compile(r"\b(and|then|after\s+that)\b")

    _APP_NAMES = (
        r"chrome|brave|firefox|edge|code|vs\s*code|terminal|discord|spotify|steam|"
        r"notepad|excel|word|explorer|settings|calculator|obs|telegram|whatsapp|"
        r"task\s*manager|powershell|cmd|browser|blender|figma|slack|teams|outlook|paint"
    )

    _SYSTEM_APP_PATTERNS = re.compile(
        rf"\b(open|launch|start|close|kill)\b.*\b({_APP_NAMES})\b|"rf"\b({_APP_NAMES})\b.*\b(open|launch|start|close|kill)\b"
    )

    _SYSTEM_SCREENSHOT = re.compile(r"\b(take\s+(a\s+)?screenshot|screen\s*shot)\b")

    _SYSTEM_LOCK_SHUTDOWN = re.compile(
        r"\b(lock\s+(the\s+|my\s+)?(pc|computer|screen)|"
        r"shut\s*down(\s+(the\s+)?(pc|computer))?|"
        r"restart(\s+(the\s+)?(pc|computer))?|"
        r"(put|sleep)\s+.{0,10}(pc|computer)(\s+to\s+sleep)?|"
        r"sleep\s+(the\s+)?(pc|computer)|"
        r"log\s*off|log\s*out)\b"
    )

    _SYSTEM_VOLUME = re.compile(
        r"\b(volume\s*(up|down)|mute|unmute|"
        r"(increase|decrease|turn\s+(up|down))\s*(the\s+)?(volume|brightness)|"
        r"brightness)\b"
    )

    _AUTONOMOUS_MULTI_STEP = re.compile(
        r"\b(search\s+for\s+.+\s+on\s+(amazon|flipkart|google|ebay|linkedin|indeed)|"
        r"book\s+(a\s+)?(flight|hotel|ticket|cab|ride)|"
        r"order\s+(a\s+|me\s+|food\s+|something\s+)?(from\s+)?|"
        r"buy\s+(me\s+)?(a\s+)?|"
        r"fill\s+(out\s+|in\s+)?(the\s+|this\s+|a\s+)?form|"
        r"go\s+to\s+\S+\s+(and|then)\s+|"
        r"navigate\s+to\s+.+\s+and\s+|"
        r"go\s+to\s+(google\s+maps|amazon|flipkart|github|linkedin))\b"
    )

    _AUTONOMOUS_CHAIN = re.compile(
        r"\b(search|find|go|navigate|look)\b.*\b(and\s+(apply|save|sort|compare|add|buy|order|book|download|submit|click|then|filter|select))\b"
    )

    _AUTONOMOUS_REQUEST = re.compile(
        r"\b(do\s+it\s+(yourself|for\s+me)|do\s+this\s+for\s+me|"
        r"handle\s+it(\s+yourself)?|take\s+control|operate\s+(my\s+)?pc|"
        r"can\s+you\s+do\s+(it|this)\s+(for|by)\s+(me|yourself)|"
        r"just\s+do\s+it\s+for\s+me|"
        r"can\s+you\s+(order|book|buy|search|find)\s+.+\s+(online|for\s+me))\b"
    )

    _AUTONOMOUS_SLANG = re.compile(r"\b(bruh|bro|yo|dude|fam)\b.*\b(do\s+it|handle\s+it|just\s+do|for\s+me)\b")

    _VISION_PATTERNS = re.compile(
        r"\b(what('s|\s+is)\s+(on\s+)?(my\s+)?(the\s+)?screen|"
        r"what('s|\s+is)\s+happening\s+on\s+(my\s+)?screen|"
        r"what\s+(do\s+you|can\s+you)\s+see|"
        r"(can\s+you\s+)?see\s+my\s+screen|"
        r"(look|looking)\s+at\s+(my\s+)?screen|"
        r"describe\s+(my\s+)?(screen|what)|"
        r"what('s|\s+is)\s+(this|that)\s+(on\s+)?(my\s+)?screen|"
        r"read\s+(my\s+)?screen|read\s+what's\s+on|"
        r"on\s+(the\s+)?screen\s+(right\s+)?now|"
        r"what\s+am\s+i\s+(looking\s+at|doing|watching)|"
        r"(see|check|lemme\s+see|let\s+me\s+see)\s+(whats|what's|what\s+is)\s+on\s+screen|"
        r"look\s+at\s+my\s+screen\s+and)\b"
    )

    _CODING_PATTERNS = re.compile(
        r"\b(check\s+(my\s+|the\s+)?code|review\s+(my\s+|the\s+)?code|"
        r"checking\s+(my\s+|the\s+)?code|"
        r"how('s|\s+is)\s+(my\s+|the\s+)?code|any\s+(bug|error|mistake|issue)s?\s+(in\s+|with\s+)?(my\s+|the\s+)?code|"
        r"debug\s+(this|my|the|it)|fix\s+(this|my|the)\s+(code|error|bug)|"
        r"watch\s+me\s+code|what('s|\s+is)\s+wrong\s+with\s+(my\s+|the\s+)?code|"
        r"code\s+review|explain\s+(this|my|the)\s+code|"
        r"is\s+(this|my|the)\s+(code|solution)\s+(correct|right|wrong|good|bad|ok)|"
        r"(think|thought)\s+about\s+(this\s+|my\s+|the\s+)?code|"
        r"help\s+me\s+(with\s+)?(this\s+)?(code|function|class|error|bug)|"
        r"help\s+me\s+fix\s+(this\s+)?(bug|error|issue)|"
        r"did\s+i\s+(do|code|get|solve)\s*(it|this|that)?\s*(good|well|right|correct(ly)?)?|"
        r"make\s+(this|my|the)?\s*(code)?\s*better|improve\s+(this|my|the)\s+code|"
        r"(code|solution)\s+(better|correct|wrong|right|good|bad)|"
        r"coding\s+question|"
        r"can\s+you\s+(check|look\s+at|review)\s+(it|this|my|the)|"
        r"(is|was)\s+(it|this|that)\s+(correct|right|wrong|good|bad))\b"
    )

    _RESEARCH_PATTERNS = re.compile(
        r"\b(search\s+for|look\s+up|google|"
        r"research\s+(about|on|into)|"
        r"find\s+(info|information|out)\s+(about|on))\b"
    )

    _RESEARCH_WHAT_WHO = re.compile(
        r"\b(what\s+is\s+(a\s+|an\s+)?\w{3,}|"
        r"who\s+is\s+\w{3,}|"
        r"tell\s+me\s+about\s+\w{3,}|"
        r"how\s+does\s+\w{3,}\s+work|"
        r"best\s+\w+\s+of\s+\d{4}|"
        r"what\s+is\s+the\s+\w{3,}\s+of\s+\w{3,})\b"
    )

    _ENTERTAINMENT_PATTERNS = re.compile(
        r"\b(play\s+(some\s+|a\s+|my\s+)?\w*\s*(music|song|songs|anime|video|movie|tunes|playlist)|"
        r"sing\s+(a\s+)?song(\s+for\s+me)?|sing\s+for\s+me|^sing$|"
        r"recommend\s+(me\s+)?(an?\s+)?(anime|movie|song|show)|"
        r"suggest\s+(an?\s+|me\s+)?(a\s+)?(good\s+)?(anime|movie|song|show)|"
        r"next\s+song|previous\s+song|pause\s+music|resume\s+music|"
        r"put\s+on\s+(some\s+)?(music|anime|tunes)|"
        r"watch\s+(something|anime|a\s+movie|movies?|netflix|youtube|crunchyroll)|"
        r"(gimme|give\s+me)\s+(a\s+)?(song|music)\s*(recommendation|suggestion)?|"
        r"what\s+(anime|movie|show|song)?\s*should\s+i\s+(watch|listen|play)|"
        r"i\s+want\s+to\s+watch\s+(something|anime|a\s+movie)|"
        r"play\s+something)\b"
    )

    _WRITING_PATTERNS = re.compile(
        r"\b(write\s+this\s+down|take\s+a\s+note|"
        r"note\s+this|remember\s+this|save\s+this|"
        r"type\s+(this|for\s+me)|start\s+dictating)\b"
    )

    _FOCUS_PATTERNS = re.compile(
        r"\b(start\s+pomodoro|i\s+need\s+to\s+focus|"
        r"help\s+me\s+(focus|concentrate)|block\s+distractions|"
        r"do\s+not\s+disturb|"
        r"set\s+(a\s+)?timer(\s+\d+\s*min)?|"
        r"\d+\s*min(ute)?s?\s*(timer|pomodoro|focus))\b"
    )

    @classmethod
    def classify(cls, text: str) -> str:
        """
        Classify user intent from text input.

        Args:
            text: The raw user input string

        Returns:
            One of: "conversation", "system", "autonomous", "vision",
                    "coding", "research", "entertainment", "writing", "focus"
        """
        lower = text.lower().strip()
        # Strip trailing punctuation only (keep apostrophes for contractions)
        clean = re.sub(r"[!?.,\"]+", "", lower).strip()

        # GUARD: Very short conversational inputs
        word_count = len(clean.split())
        if word_count <= 2 and not cls._GUARD_SHORT_PATTERNS.search(clean):
            return "conversation"

        # AUTONOMOUS: EXTREME COMPLEXITY GUARD
        if cls._AUTONOMOUS_EXTREME_PATTERNS.search(clean):
            return "autonomous"

        # Action density heuristic for very long orchestrations
        if word_count >= 10:
            actions = cls._ACTION_PATTERNS.findall(clean)
            conjunctions = cls._CONJUNCTION_PATTERNS.findall(clean)

            if len(set(actions)) >= 3:
                return "autonomous"
            if len(actions) >= 2 and len(conjunctions) >= 2:
                return "autonomous"

        # SYSTEM: App control + PC commands
        if cls._SYSTEM_APP_PATTERNS.search(clean):
            if re.search(r"\b(and\s+(go|navigate|search|find|then|also|do))\b", clean):
                return "autonomous"
            return "system"

        if re.search(rf"\b(closing|opening|launching|starting)\b.*\b({cls._APP_NAMES})\b", clean):
            return "system"

        if cls._SYSTEM_SCREENSHOT.search(clean):
            return "system"

        if cls._SYSTEM_LOCK_SHUTDOWN.search(clean):
            return "system"

        if cls._SYSTEM_VOLUME.search(clean):
            return "system"

        # AUTONOMOUS: Multi-step tasks
        if cls._AUTONOMOUS_MULTI_STEP.search(clean):
            return "autonomous"

        # Chain detection
        if cls._AUTONOMOUS_CHAIN.search(clean):
            return "autonomous"

        if cls._AUTONOMOUS_REQUEST.search(clean):
            return "autonomous"

        if cls._AUTONOMOUS_SLANG.search(clean):
            return "autonomous"

        # VISION: What's on screen
        if cls._VISION_PATTERNS.search(clean):
            return "vision"

        # CODING: Code review, debugging
        if cls._CODING_PATTERNS.search(clean):
            return "coding"

        # RESEARCH: Information lookup
        if cls._RESEARCH_PATTERNS.search(clean):
            if not re.search(r"\b(and\s+(then|apply|save|sort|add|buy|order|book|also|filter))\b", clean):
                return "research"

        # "what is X" / "who is X"
        non_research = r"(this|that|it|up|happening|going|wrong|good|bad|ok|2\+2|\d+\+\d+)"
        if re.search(rf"\b(what\s+is\s+(?!{non_research}\b)(a\s+|an\s+)?\w{{3,}}|"
                     rf"who\s+is\s+(?!this\b|that\b|it\b)\w{{3,}}|"
                     rf"tell\s+me\s+about\s+\w{{3,}}|"
                     rf"how\s+does\s+\w{{3,}}\s+work|"
                     rf"best\s+\w+\s+of\s+\d{{4}}|"
                     rf"what\s+is\s+the\s+\w{{3,}}\s+of\s+\w{{3,}})\b", clean):
            return "research"

        # ENTERTAINMENT: Music, media, anime
        if cls._ENTERTAINMENT_PATTERNS.search(clean):
            return "entertainment"

        # WRITING: Note-taking
        if cls._WRITING_PATTERNS.search(clean):
            return "writing"

        # FOCUS: Productivity
        if cls._FOCUS_PATTERNS.search(clean):
            return "focus"

        # FALLBACK: Conversation
        return "conversation"

    @classmethod
    def get_intent_description(cls, intent: str) -> str:
        """Get a human-readable description for an intent."""
        descriptions = {
            "conversation": "General chat and conversation",
            "system": "PC and application control",
            "autonomous": "Multi-step automation tasks",
            "vision": "Screen analysis and description",
            "coding": "Code review and debugging",
            "research": "Information lookup and research",
            "entertainment": "Music, anime, and media",
            "writing": "Note-taking and dictation",
            "focus": "Productivity and focus mode",
        }
        return descriptions.get(intent, "Unknown intent")