import re
import urllib.parse
from typing import List, Dict, Optional, Set

class TokenJuice:
    """
    TokenJuice Middleware Pipeline.
    Compresses strings and LLM context heavily to save tokens without losing meaning.
    """

    # Tunables
    VERBATIM_TURNS = 3
    MAX_HISTORY_TURNS = 20
    SUMMARY_MAX_TOKENS = 200

    @staticmethod
    def compress(text: str) -> str:
        """Run the full compression pipeline on a string."""
        if not text:
            return ""

        text = TokenJuice.strip_html(text)
        text = TokenJuice.compress_urls(text)
        text = TokenJuice.truncate_base64(text)
        text = TokenJuice.deduplicate_lines(text)
        text = TokenJuice.compress_whitespace(text)

        return text.strip()

    @staticmethod
    def truncate_base64(text: str) -> str:
        """Truncate long base64 blobs (e.g. inline images in scraped data)."""
        b64_pattern = r'(data:image/[^;]+;base64,)([A-Za-z0-9+/]{100,})={0,2}'
        return re.sub(b64_pattern, r'\1[BASE64_TRUNCATED]', text)

    @staticmethod
    def summarize_list(items: List[str], max_items: int = 5) -> str:
        """Compress a list of items into a short summary line."""
        if len(items) <= max_items:
            return ", ".join(items)
        visible = items[:max_items]
        hidden_count = len(items) - max_items
        return f"{', '.join(visible)} ... and {hidden_count} more items."

    @staticmethod
    def strip_html(text: str) -> str:
        """Strip non-semantic HTML tags, keeping just the text."""
        # Remove script and style tags completely
        text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', text, flags=re.IGNORECASE)

        # Remove HTML tags but keep their contents
        text = re.sub(r'<[^>]+>', ' ', text)
        return text

    @staticmethod
    def compress_urls(text: str) -> str:
        """Replace long URLs with domain paths to save tokens."""
        # Find all http/https URLs
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

        def replace_url(match):
            url = match.group(0)
            try:
                parsed = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
                domain = parsed.netloc.replace('www.', '')
                path = parsed.path
                if len(path) > 15:
                    path = path[:15] + "..."
                return f"[{domain}{path}]"
            except Exception:
                return "[url]"

        return re.sub(url_pattern, replace_url, text)

    @staticmethod
    def deduplicate_lines(text: str, max_repeats: int = 3) -> str:
        """Remove sequences of lines that repeat heavily (e.g. log files)."""
        lines = text.split('\n')
        if not lines:
            return text

        out_lines = []
        consecutive_count = 0
        last_line = None

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if line_stripped == last_line:
                consecutive_count += 1
                if consecutive_count < max_repeats:
                    out_lines.append(line)
                elif consecutive_count == max_repeats:
                    out_lines.append(f"... [repeated {line_stripped[:20]}...]")
            else:
                consecutive_count = 1
                last_line = line_stripped
                out_lines.append(line)

        return '\n'.join(out_lines)

    @staticmethod
    def compress_whitespace(text: str) -> str:
        """Compress multiple spaces and newlines."""
        # Replace 3 or more spaces with 2 spaces
        text = re.sub(r' {3,}', '  ', text)
        # Replace 3 or more newlines with 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    @staticmethod
    def compress_history(history: List[dict]) -> List[dict]:
        """Compress an entire conversation history dictionary list."""
        compressed = []
        for turn in history:
            new_turn = {"role": turn["role"], "parts": []}
            for part in turn.get("parts", []):
                if "text" in part:
                    new_turn["parts"].append({"text": TokenJuice.compress(part["text"])})
                else:
                    new_turn["parts"].append(part)
            compressed.append(new_turn)
        return compressed

    @staticmethod
    def _turn_text(turn: dict) -> str:
        """Extract text from a turn."""
        parts = turn.get("parts", [])
        if not parts:
            return ""
        return " ".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token for English text."""
        return max(1, len(text) // 4)

    @staticmethod
    def summarize_turns(turns: List[dict], max_tokens: int = SUMMARY_MAX_TOKENS) -> str:
        """Collapse older turns into a short summary."""
        if not turns:
            return ""
        combined = "\n".join(f"{t.get('role', 'user')}: {TokenJuice._turn_text(t)}" for t in turns)
        compressed = TokenJuice.compress(combined)
        # Hard truncation if still too long
        char_limit = max_tokens * 4
        if len(compressed) > char_limit:
            compressed = compressed[:char_limit - 3] + "..."
        return compressed

    @staticmethod
    def detect_topic_shift(current_text: str, recent_texts: List[str]) -> bool:
        """Detect if user shifted topic based on keyword overlap."""
        if not recent_texts:
            return False

        def keywords(text: str) -> Set[str]:
            return set(re.findall(r'\b[a-z]{4,}\b', text.lower()))

        current_kw = keywords(current_text)
        if not current_kw:
            return False

        # Compare against average overlap with recent turns
        overlaps = []
        for rt in recent_texts:
            rt_kw = keywords(rt)
            if not rt_kw:
                continue
            overlap = len(current_kw & rt_kw) / max(1, len(current_kw))
            overlaps.append(overlap)

        if not overlaps:
            return False

        avg_overlap = sum(overlaps) / len(overlaps)
        # If overlap is low (< 0.15), likely topic shift
        return avg_overlap < 0.15

    @staticmethod
    def compress_history_sliding_window(
        history: List[dict],
        user_text: str,
        memory_recall_fn=None
    ) -> List[dict]:
        """
        Smart context window:
        - Keep last N turns verbatim.
        - Summarize older turns into a single system context turn.
        - Detect topic shifts and archive old context.
        - Inject relevant memory facts if provided.
        """
        if not history:
            return []

        # Cap total turns
        capped = history[-TokenJuice.MAX_HISTORY_TURNS:]

        # Split into verbatim recent and older archive
        verbatim = capped[-TokenJuice.VERBATIM_TURNS:]
        older = capped[:-TokenJuice.VERBATIM_TURNS]

        recent_texts = [TokenJuice._turn_text(t) for t in verbatim]
        topic_shift = TokenJuice.detect_topic_shift(user_text, recent_texts)

        result = []

        # Build context prefix
        context_parts = []

        if older and not topic_shift:
            summary = TokenJuice.summarize_turns(older)
            if summary:
                context_parts.append(f"[Earlier conversation summary]\n{summary}")
        elif older and topic_shift:
            context_parts.append("[Topic shifted; older context archived.]")

        if memory_recall_fn:
            try:
                facts = memory_recall_fn(user_text)
                if facts:
                    if isinstance(facts, list):
                        facts = "\n".join(f"- {f}" for f in facts)
                    context_parts.append(f"[Relevant memory]\n{facts}")
            except Exception:
                pass

        if context_parts:
            result.append({
                "role": "system",
                "parts": [{"text": "\n\n".join(context_parts)}]
            })

        # Add verbatim turns compressed
        for turn in verbatim:
            new_turn = {"role": turn.get("role", "user"), "parts": []}
            for part in turn.get("parts", []):
                if isinstance(part, dict) and "text" in part:
                    new_turn["parts"].append({"text": TokenJuice.compress(part["text"])})
                else:
                    new_turn["parts"].append(part)
            result.append(new_turn)

        return result

# Shared singleton for callers that prefer an instance handle
token_juice = TokenJuice()
