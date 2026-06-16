"""
Background Web Agent for Headless Browsing
Uses Playwright to navigate pages, extract text, and perform basic interactions.
"""
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger("mizune.web")

def headless_web_agent(url: str, objective: str, visible: bool = False) -> str:
    """
    Launch a Chromium browser to navigate a URL and fulfill the objective.
    Returns the extracted text or result.
    """
    if not url.startswith("http"):
        url = "https://" + url

    # Intercept Search Engine URLs to bypass aggressive bot detection (CAPTCHAs)
    if "google.com/search" in url or "duckduckgo.com" in url or "bing.com/search" in url:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        query = qs.get("q", [""])[0]
        
        if query:
            logger.info(f"[WEB AGENT] Intercepted search query, using DDGS to bypass bot detection: {query}")
            try:
                from ddgs import DDGS
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    results = list(DDGS().text(query, max_results=10))
                
                if results:
                    text_content = ""
                    for i, r in enumerate(results):
                        text_content += f"{i+1}. {r.get('title', '')}\nLink: {r.get('href', '')}\nDescription: {r.get('body', '')}\n\n"
                    return f"Successfully searched for: {query}\n\nObjective: {objective}\n\nSearch Results:\n{text_content}"
            except Exception as e:
                logger.error(f"[WEB AGENT] DDGS failed: {e}")
                # Fall back to standard playwright if DDGS fails
                
    try:
        with sync_playwright() as p:
            # Calculate the primary screen width to push the window to Screen 2
            import ctypes
            primary_width = ctypes.windll.user32.GetSystemMetrics(0)
            
            # Set headless=False if user wants to watch her work
            launch_args = []
            if visible:
                # Force the browser to open physically on Screen 2 (Primary Width + 50px offset)
                launch_args = [f"--window-position={primary_width + 50},50"]
                
            browser = p.chromium.launch(headless=not visible, args=launch_args)
            page = browser.new_page()
            
            logger.info(f"[WEB AGENT] Navigating to {url}")
            
            # Add a slight timeout for page loads
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Give JS a moment to render
            page.wait_for_timeout(2000)
            
            # We can extract all readable text
            text_content = page.evaluate('''() => {
                return document.body.innerText;
            }''')
            
            browser.close()
            
            # Since LLM contexts are limited, we should truncate massive text
            if len(text_content) > 5000:
                text_content = text_content[:5000] + "\n...[TRUNCATED FOR LENGTH]..."
                
            return f"Successfully loaded {url}.\n\nObjective: {objective}\n\nPage Content:\n{text_content}"
            
    except Exception as e:
        logger.error(f"[WEB AGENT] Error: {e}")
        return f"Error loading URL {url}: {e}"
