import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("mizune.model_router")

class ModelRouter:
    """
    Dynamically routes AI requests to the optimal model based on complexity and hints.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def route(self, text: str, context: list, hints: Dict[str, Any] = None) -> str:
        """
        Returns the provider to use ("gemini", "openai", "groq", "nvidia", "ollama")
        based on the text, context length, and explicit hints.
        """
        hints = hints or {}
        
        # 1. Explicit Routing Hints (From ManagerAgent)
        forced_model = hints.get("force_provider")
        if forced_model:
            return forced_model
            
        intent = hints.get("intent", "conversation")
        
        # 2. Logic based on Intent and Task complexity
        task_keywords = ["open ", "close ", "search ", "find ", "research ", "code ", "write ", "create ", "note ", "play ", "youtube", "summarize", "analyze", "execute", "run ", "launch ", "calculate", "tell me what is love"]
        
        # Strip system prompts before checking keywords
        import re
        clean_text = re.sub(r"\[WHATSAPP MESSAGE FROM [^\]]+\]:\s*", "", text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\[MESSAGE FROM MASTER RUSHI[^\]]*\]:\s*", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\n*\(SYSTEM:[^\)]+\)\s*$", "", clean_text, flags=re.IGNORECASE)
        text_lower = clean_text.lower()
        
        is_task = intent in ("coding", "autonomous", "research", "task") or any(kw in text_lower for kw in task_keywords)

        # WhatsApp goes to a provider that can actually SERVE a full turn.
        #
        # This branch used to hard-return "groq" for every WhatsApp message, on the
        # reasoning that groq was "fastest + cheapest, sub-second llama-3.3-70b". Both
        # halves of that expired: Groq decommissioned llama-3.3-70b-versatile (404
        # model_not_found), and every tool-capable model left on its free tier caps at
        # 8,000 TPM — against a prompt whose STATIC floor is ~7,415 tokens and which is
        # observed at 9,297-9,386. So the fastest provider was also the one guaranteed to
        # 413, on the single path Master actually messages her from.
        #
        # This is the first half of why the 2026-08-16 "background check on Autter"
        # request was never answered: it arrived over WhatsApp, was pinned here to groq,
        # and what came back was a promise with no search behind it.
        #
        # Preference order is now by measured capacity, not by reputation for speed.
        if hints.get("platform") == "whatsapp":
            for provider in ("mistral", "nvidia", "gemini", "openrouter", "groq"):
                if self.config.get(f"{provider}_api_key"):
                    return provider
            return self.config.get("ai_model")
        
        if is_task:
            configured = self.config.get("ai_model")
            # "groq" was MISSING here, so setting ai_model=groq silently fell through
            # to openrouter for every task request (2026-07-20 parallel-tools work).
            if configured in ["nvidia", "openai", "anthropic", "gemini", "groq", "openrouter", "cerebras", "mistral"]:
                return configured
            if self.config.get("openrouter_api_key"):
                return "openrouter"
                
        # 3. Vision / Multimodal needs
        if "VISION" in text or "CAMERA" in text:
            if self.config.get("gemini_api_key"):
                return "gemini"
            if self.config.get("openai_api_key"):
                return "openai"
                
        # 4. Context Window Size Check
        # Fast estimation
        ctx_len = sum(len(str(m)) for m in context)
        if ctx_len > 30000:
            if self.config.get("gemini_api_key"):
                return "gemini" # 1M/2M context window
                
        # 5. Default Fallback Chain (Respect User's Configured Model First)
        configured_model = self.config.get("ai_model")
        if configured_model:
            return configured_model

        if self.config.get("gemini_api_key"):
            return "gemini"
        if self.config.get("groq_api_key"):
            return "groq"
        if self.config.get("ollama_host"):
            return "ollama"
            
        # Absolute fallback
        return "gemini"

model_router = None

def get_model_router(config: Dict[str, Any]) -> ModelRouter:
    global model_router
    if not model_router:
        model_router = ModelRouter(config)
    return model_router
