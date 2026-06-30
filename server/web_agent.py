"""
Background Web Agent for Headless Browsing
Uses Browser-Use to autonomously navigate pages, read content, and achieve objectives.
"""
import logging
import asyncio
import os
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

logger = logging.getLogger("mizune.web")

# We will cache the browser instance to avoid spinning it up repeatedly
_browser_instance = None

def get_browser(visible: bool = False):
    global _browser_instance
    if _browser_instance is None:
        launch_args = []
        if visible:
            # Attempt to pop open on second monitor
            primary_width = 1920
            if os.name == 'nt':
                try:
                    import ctypes
                    primary_width = ctypes.windll.user32.GetSystemMetrics(0)
                except Exception:
                    pass
            launch_args = [f"--window-position={primary_width + 50},50"]
            
        _browser_instance = Browser(
            headless=not visible,
            args=launch_args,
            disable_security=True
        )
    return _browser_instance

def headless_web_agent(url: str, objective: str, visible: bool = False) -> str:
    """
    Launch an autonomous browser-use agent to fulfill the objective on the given URL.
    This function is synchronous, but it wraps an asynchronous execution because it is 
    called via ThreadPoolExecutor from the main event loop.
    """
    if not url.startswith("http"):
        url = "https://" + url

    task_prompt = f"Navigate to {url}.\n\nYour Objective:\n{objective}"
    
    logger.info(f"[WEB AGENT] Starting autonomous web agent for {url}")

    async def run_agent():
        try:
            # We must configure Langchain with our OpenAI key
            llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY", ""))
            
            agent = Agent(
                task=task_prompt,
                llm=llm,
                browser=get_browser(visible=visible)
            )
            
            history = await agent.run(max_steps=5) # Limit steps so it doesn't run forever
            
            final_result = history.final_result()
            if final_result:
                return f"Web Agent Success:\n{final_result}"
            else:
                return f"Web Agent completed task, but provided no specific final result. See logs for steps."
                
        except Exception as e:
            logger.error(f"[WEB AGENT] Autonomous agent failed: {e}")
            return f"Web Agent Error: {str(e)}"
            
    # Run the async agent loop and wait for it
    try:
        # Check if there is already a running event loop in this thread
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(run_agent())
        else:
            return asyncio.run(run_agent())
            
    except Exception as e:
        logger.error(f"[WEB AGENT] Execution Wrapper Error: {e}")
        return f"Execution Wrapper Error: {str(e)}"
