import json
import logging
import hashlib
from typing import List, Dict, Any, Tuple
from .token_juice import token_juice
from .config import log_info

logger = logging.getLogger("mizune.context_manager")

class ContextManager:
    """
    Intelligently manages the LLM context window.
    Tracks tokens, compresses mid-conversation history, and prevents execution loops.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Estimate context window limits based on model
        self.model_name = config.get("ai_model", "nvidia").lower()
        if "gemini" in self.model_name or "claude-3" in self.model_name:
            self.max_tokens = 120000 # Leave some buffer
        else:
            # Llama 3 models
            self.max_tokens = 60000 
            
        self.compression_threshold = int(self.max_tokens * 0.85)
        
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation: ~4 chars per token."""
        return len(text) // 4
        
    def prepare_context(self, chronicle: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Takes the raw chronicle.
        Returns (compressed_chronicle, was_compressed)
        """
        if not chronicle:
            return [], False
            
        # 1. Apply TokenJuice to all raw entries first
        juiced_chronicle = []
        for entry in chronicle:
            role = entry["role"]
            content = entry["parts"][0]["text"] if "parts" in entry else entry.get("content", "")
            
            juiced_entry = {
                "role": role,
                "parts": [{"text": token_juice.compress(content)}]
            }
            juiced_chronicle.append(juiced_entry)
            
        # 2. Check for action loops (e.g., repeatedly failing on the same error)
        juiced_chronicle = self._detect_and_break_loops(juiced_chronicle)
            
        # 3. Estimate total tokens
        total_tokens = sum(self._estimate_tokens(e["parts"][0]["text"]) for e in juiced_chronicle)
        
        # 4. If under threshold, return as is
        if total_tokens < self.compression_threshold:
            return juiced_chronicle, False
            
        # 5. Compress the middle
        log_info(f"[CONTEXT] Window at {total_tokens} tokens (limit {self.compression_threshold}). Compressing...")
        return self._compress_middle(juiced_chronicle), True
        
    def _detect_and_break_loops(self, chronicle: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detects if the AI is repeating the exact same tool execution or getting the exact same error.
        If a loop of size 3 is detected, inject a system break message.
        """
        if len(chronicle) < 6: return chronicle
        
        # Look at the last few assistant/system pairs
        # We hash the content to easily compare
        recent = chronicle[-6:]
        hashes = [hashlib.md5(e["parts"][0]["text"].encode()).hexdigest() for e in recent]
        
        # If the sequence A-B-A-B-A-B is detected (loop of 2 turns repeated 3 times)
        if hashes[0] == hashes[2] == hashes[4] and hashes[1] == hashes[3] == hashes[5]:
            log_info("[CONTEXT] Execution loop detected. Injecting break message.")
            chronicle.append({
                "role": "model",
                "parts": [{"text": "[SYSTEM WARNING] You are stuck in a loop repeating the same actions and getting the same results. STOP doing what you are doing. Change your approach entirely or ask the user for help."}]
            })
            
        return chronicle

    def _compress_middle(self, chronicle: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Keeps the system prompt, the first 2 turns (context), and the last 5 turns (recent).
        Summarizes everything in between.
        """
        if len(chronicle) <= 10:
            return chronicle # Too short to safely compress, just let it clip or error
            
        # Keep index 0 (usually system prompt or initial user intent)
        # Keep last 5 (immediate working context)
        head = chronicle[:3]
        tail = chronicle[-5:]
        middle = chronicle[3:-5]
        
        middle_text = "\n".join([f"{e['role'].upper()}: {e['parts'][0]['text']}" for e in middle])
        
        # We can use get_ai_response here, but to avoid circular imports we do a simpler aggressive truncation
        # A true summarization would use a cheap model (e.g. flash-lite)
        compressed_middle = {
            "role": "model",
            "parts": [{"text": f"[SYSTEM: {len(middle)} intermediate turns were compressed] {token_juice.compress(middle_text)[:2000]}... [END COMPRESSION]"}]
        }
        
        return head + [compressed_middle] + tail
