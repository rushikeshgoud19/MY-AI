import os
import re
import asyncio
import logging
from typing import Any, Optional, Dict
from agents.base_agent import BaseAgent

# Playwright is optional — fall back to requests-based scraping
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class WebAgent(BaseAgent):
    """
    Specialized Agent for internet research and data extraction.
    Searches Google and extracts real snippets from results.
    """
    def __init__(self, config: dict):
        super().__init__(config)
        self.log("WebAgent initialized. Ready to scour the web for Master!")

    async def execute(self, task_input: str, context: Optional[Dict] = None) -> Any:
        self.log(f"Performing web research: {task_input}")
        
        try:
            return await self._research(task_input)
        except Exception as e:
            self.log(f"Web research failed: {e}")
            return f"Gomen ne, Master... I tried to search the web but something went wrong: {e}"

    async def _research(self, query: str) -> str:
        """Search Google and extract top result snippets."""
        self.log(f"Searching for: {query}")

        # Try Playwright first for JS-rendered pages
        if HAS_PLAYWRIGHT:
            try:
                return await self._search_with_playwright(query)
            except Exception as e:
                self.log(f"Playwright search failed: {e}, trying requests fallback...")

        # Fallback: use requests + basic HTML parsing
        return await self._search_with_requests(query)

    async def _search_with_playwright(self, query: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            await page.goto(search_url, timeout=10000)
            
            # Extract search result snippets
            snippets = await page.query_selector_all('.VwiC3b, .IsZvec, .s3v9rd')
            results = []
            for i, snippet in enumerate(snippets[:5]):
                text = await snippet.inner_text()
                if text and len(text.strip()) > 20:
                    results.append(text.strip())
            
            await browser.close()
            
            if results:
                combined = "\n".join(f"• {r}" for r in results[:3])
                return f"Here's what I found about '{query}', Master!\n\n{combined}"
            
            return f"I searched for '{query}' but couldn't extract clear results. Try asking more specifically, Master!"

    async def _search_with_requests(self, query: str) -> str:
        """Lightweight fallback using requests (no browser needed)."""
        import requests
        import urllib.parse

        encoded = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                # Extract text snippets from Google's HTML
                text = resp.text
                # Find snippet divs
                snippet_pattern = re.compile(r'<span class="[^"]*">([^<]{40,300})</span>', re.DOTALL)
                matches = snippet_pattern.findall(text)
                
                # Clean HTML entities
                clean = []
                for m in matches[:5]:
                    cleaned = re.sub(r'<[^>]+>', '', m).strip()
                    cleaned = cleaned.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
                    if len(cleaned) > 30 and not cleaned.startswith('{'):
                        clean.append(cleaned)

                if clean:
                    combined = "\n".join(f"• {c}" for c in clean[:3])
                    return f"Here's what I found about '{query}', Master!\n\n{combined}"

            return f"I searched for '{query}' but the results were unclear. Want me to open it in your browser instead, Master?"
        except Exception as e:
            self.log(f"Requests search failed: {e}")
            return f"I couldn't search right now, Master. Error: {e}"
