import re
import urllib.parse
from typing import Dict, Any, List

class TokenJuice:
    """
    Context compression engine.
    Squashes verbose tool outputs, HTML, and long URLs into token-efficient strings.
    """
    def __init__(self):
        # We can load custom regex patterns from config later
        self.patterns = []
        
    def compress(self, text: str) -> str:
        if not text: return ""
        
        compressed = text
        compressed = self._strip_html(compressed)
        compressed = self._shorten_urls(compressed)
        compressed = self._dedup_whitespace(compressed)
        compressed = self._truncate_base64(compressed)
        
        return compressed.strip()
        
    def _strip_html(self, text: str) -> str:
        # Very basic HTML stripping and formatting
        # If it doesn't look like it has HTML tags, skip
        if '<' not in text or '>' not in text:
            return text
            
        # Replace common structural tags with newlines
        text = re.sub(r'</?(div|p|br|li|tr|h[1-6])[^>]*>', '\n', text, flags=re.IGNORECASE)
        # Strip all other tags
        text = re.sub(r'<[^>]+>', ' ', text)
        return text

    def _shorten_urls(self, text: str) -> str:
        """Finds URLs and removes noisy query parameters."""
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        
        def replace_url(match):
            url = match.group(0)
            try:
                parsed = urllib.parse.urlparse(url)
                # Keep domain and path, drop query params if they are too long
                if len(parsed.query) > 20:
                    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?..."
                return url
            except Exception:
                return url
                
        return re.sub(url_pattern, replace_url, text)
        
    def _truncate_base64(self, text: str) -> str:
        """Truncates long base64 strings often found in scraped data."""
        # Matches base64 strings longer than 100 chars
        b64_pattern = r'(data:image/[^;]+;base64,)([A-Za-z0-9+/]{100,})={0,2}'
        return re.sub(b64_pattern, r'\1[BASE64_TRUNCATED]', text)
        
    def _dedup_whitespace(self, text: str) -> str:
        """Collapses multiple spaces and newlines."""
        # Replace 3+ newlines with 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Replace 2+ spaces with 1 space
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text
        
    def summarize_list(self, items: List[str], max_items: int = 5) -> str:
        """Compresses a list of items into a summary if it's too long."""
        if len(items) <= max_items:
            return ", ".join(items)
        
        visible = items[:max_items]
        hidden_count = len(items) - max_items
        return f"{', '.join(visible)} ... and {hidden_count} more items."

# Global instance
token_juice = TokenJuice()
