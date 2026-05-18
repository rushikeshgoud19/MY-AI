"""Research Agent for Mizune."""
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional


class ResearchAgent:
    """Agent for deep web research and information gathering."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_results = config.get("max_search_results", 5)

    def search_web(self, query: str, num_results: int = None) -> Dict[str, Any]:
        """Search the web for information."""
        if num_results is None:
            num_results = self.max_results

        try:
            # Use DuckDuckGo API (no key required)
            encoded_query = urllib.parse.quote(query)
            url = f"https://duckduckgo.com/html/?q={encoded_query}&b={num_results}"

            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')

            # Simple parsing - extract search result titles and snippets
            results = self._parse_search_results(html, num_results)

            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    def _parse_search_results(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse search results from HTML."""
        results = []
        import re

        # Simple regex to extract result snippets
        # Look for result blocks
        result_pattern = re.compile(r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?<a class="result__snippet"[^>]*>([^<]*)</a>', re.DOTALL)
        matches = result_pattern.findall(html)

        for match in matches[:limit]:
            url, title, snippet = match
            results.append({
                "title": title.strip(),
                "url": url,
                "snippet": snippet.strip() if snippet else ""
            })

        return results

    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from a URL."""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Simple content extraction - remove HTML tags
            import re
            # Remove script and style elements
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # Extract text
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            text = text[:5000]  # Limit to first 5000 chars

            return {
                "success": True,
                "url": url,
                "content": text.strip(),
                "length": len(text)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Generate a simple summary of text."""
        if not text:
            return "No content to summarize."

        # Simple extraction-based summarization
        sentences = text.split('.')
        if len(sentences) <= 2:
            return text[:max_length] + "..." if len(text) > max_length else text

        # Take first 2-3 sentences as summary
        summary = ". ".join(sentences[:2]).strip()
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary

    def compile_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Compile sources into formatted bibliography."""
        if not sources:
            return "No sources to compile."

        lines = ["## Sources\n"]
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Untitled")
            url = source.get("url", "")
            lines.append(f"{i}. [{title}]({url})")

        return "\n".join(lines)