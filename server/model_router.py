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
        
        if hints.get("platform") == "whatsapp" and not is_task:
            # FORCE Gemini for WhatsApp because Nvidia is too slow (user complained)
            if self.config.get("gemini_api_key"):
                return "gemini"
            if self.config.get("groq_api_key"):
                return "groq"
            configured = self.config.get("ai_model")
            return configured
        
        if is_task:
            configured = self.config.get("ai_model")
            if configured in ["nvidia", "openai", "anthropic", "gemini"]:
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
