import re
import urllib.parse
from typing import List

class TokenJuice:
    """
    TokenJuice Middleware Pipeline.
    Compresses strings and LLM context heavily to save tokens without losing meaning.
    """

    @staticmethod
    def compress(text: str) -> str:
        """Run the full compression pipeline on a string."""
        if not text:
            return ""
            
        text = TokenJuice.strip_html(text)
        text = TokenJuice.compress_urls(text)
        text = TokenJuice.deduplicate_lines(text)
        text = TokenJuice.compress_whitespace(text)
        
        return text.strip()

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
