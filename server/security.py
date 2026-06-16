import os
import re
import time
from typing import Tuple, Dict

import logging
logger = logging.getLogger("mizune.security")

class SecurityScanner:
    """
    Scans AI-generated code and outputs for security threats.
    """
    DANGEROUS_PATTERNS = [
        r"os\.remove", r"shutil\.rmtree", r"os\.system\(['\"]rm\s+-rf", 
        r"format\s+[A-Za-z]:", r"subprocess\.run\(['\"]del",
        r"urllib\.request", r"requests\.post", r"socket\."
    ]

    @classmethod
    def scan_code(cls, code: str) -> Tuple[bool, str]:
        """Returns (is_safe, reason)."""
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Code contains dangerous pattern: {pattern}"
        return True, "Safe"

    @classmethod
    def redact_tokens(cls, text: str) -> str:
        """Redacts things that look like API keys or secrets."""
        if not text:
            return text
        # Basic regex for standard Bearer tokens / API keys
        redacted = re.sub(r"(?:sk-[a-zA-Z0-9]{32,}|Bearer\s+[a-zA-Z0-9_\-\.]+)", "[REDACTED_TOKEN]", text)
        return redacted

class RateLimiter:
    """
    Prevents the AI from making too many loops or API calls.
    """
    def __init__(self, max_calls_per_min: int = 20):
        self.max_calls = max_calls_per_min
        self.calls = []

    def check_limit(self) -> bool:
        now = time.time()
        # Keep only calls from the last 60 seconds
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.max_calls:
            return False
        self.calls.append(now)
        return True

global_rate_limiter = RateLimiter()

def validate_api_keys(config: Dict[str, str]) -> bool:
    """Verifies that at least one provider has keys on startup."""
    keys = ["gemini_api_key", "openai_api_key", "anthropic_api_key", "groq_api_key", "nvidia_api_key"]
    has_key = any(config.get(k) for k in keys)
    if not has_key:
        logger.warning("[SECURITY] ⚠️ No API keys found! Mizune will not be able to think!")
    return has_key
