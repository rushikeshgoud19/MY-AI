import os
import json
import time

def log_info(msg):
    import logging
    logging.info(msg)
    print(msg)

class LLMService:
    @staticmethod
    def get_ai_response(text: str, history: list, system_prompt_override: str = None, cfg: dict = None) -> str:
        model_type = cfg.get("ai_model", "gemini")
        
        if system_prompt_override:
            system_prompt = system_prompt_override
        else:
            personality = cfg.get("personality", "")
            action_addendum = (
                " You have full control over Master's PC via action tags in your response. "
                "Use [ACTION: OPEN app_name] to open apps: Brave, Chrome, Firefox, Edge, VS Code, "
                "Terminal, Discord, Spotify, Telegram, WhatsApp, Steam, OBS, Blender, Figma, "
                "Excel, Word, PowerPoint, Outlook, Teams, Slack, Task Manager, Settings, "
                "Calculator, Paint, Notepad, File Explorer, YouTube, GitHub, Gmail, and more. "
                "Use [ACTION: CLOSE app_name] to close apps. "
                "Use [ACTION: SLEEP] to sleep the PC. "
                "Use [ACTION: NOTE text] ONLY if the user EXPLICITLY asks you to 'write this down', 'take a note', or 'remember this'. DO NOT use it for normal conversation. "
                "You can also take screenshots, lock the PC, and control volume — just say so. "
                "ALWAYS execute the requested action without asking for confirmation. "
                "Refer to yourself as " + cfg.get("character_name", "Mizune") + "."
            )
            system_prompt = personality + action_addendum

        if model_type == "gemini":
            return LLMService._gemini_response(text, history, system_prompt, cfg)
        elif model_type == "openai":
            return LLMService._openai_response(text, history, system_prompt, cfg)
        elif model_type == "anthropic":
            return LLMService._anthropic_response(text, history, system_prompt, cfg)
        elif model_type == "openrouter":
            return LLMService._openrouter_response(text, history, system_prompt, cfg)
        else:
            return LLMService._gemini_response(text, history, system_prompt, cfg)

    @staticmethod
    def _gemini_response(text: str, history: list, system_prompt: str, cfg: dict) -> str:
        api_key = cfg.get("gemini_api_key", "")
        if not api_key:
            return "No Gemini API key set! Please open Settings and add your key."
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        primary_model = cfg.get("gemini_model", "gemini-2.5-flash")
        fallback_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
        
        formatted_history = []
        for turn in history:
            role = turn.get("role", "user")
            if role == "assistant": role = "model"
            parts = []
            for p in turn.get("parts", []):
                if "text" in p:
                    parts.append(types.Part.from_text(text=p["text"]))
            formatted_history.append(types.Content(role=role, parts=parts))

        models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]
        
        skip_gemini = False
        for model in models_to_try:
            if skip_gemini:
                break
            for attempt in range(3):
                try:
                    log_info(f"[AI] Trying {model} (attempt {attempt + 1})...")
                    response = client.models.generate_content(
                        model=model,
                        contents=formatted_history,
                        config=types.GenerateContentConfig(system_instruction=system_prompt)
                    )
                    return response.text or "I'm speechless!"
                except Exception as e:
                    err_str = str(e).lower()
                    if "503" in err_str or "unavailable" in err_str or "overloaded" in err_str:
                        wait_time = (attempt + 1) * 1.5
                        log_info(f"[AI] {model} unavailable (503), retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    elif "429" in err_str or "quota" in err_str or "exhausted" in err_str or "api key not valid" in err_str or "api_key_invalid" in err_str:
                        log_info(f"[AI] Gemini API Key exhausted/invalid! Falling back directly to Groq...")
                        skip_gemini = True
                        break
                    else:
                        raise
            if not skip_gemini:
                log_info(f"[AI] {model} failed after retries, trying next fallback...")
        
        groq_key = cfg.get("groq_api_key", "")
        if groq_key:
            try:
                from openai import OpenAI
                log_info("[AI] All Gemini models exhausted, trying Groq...")
                groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                groq_messages = [{"role": "system", "content": system_prompt}]
                for turn in history:
                    role = turn.get("role", "user")
                    if role == "model": role = "assistant"
                    parts_text = " ".join(p.get("text", "") for p in turn.get("parts", []))
                    if parts_text:
                        groq_messages.append({"role": role, "content": parts_text})
                resp = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=groq_messages,
                    max_tokens=300
                )
                return resp.choices[0].message.content or "I'm speechless!"
            except Exception as e:
                log_info(f"[AI] Groq also failed: {e}")
        
        return "All my brain models are busy right now, Master! Please try again in a moment~"

    @staticmethod
    def _openai_response(text: str, history: list, system_prompt: str, cfg: dict) -> str:
        api_key = cfg.get("openai_api_key", "")
        if not api_key:
            return "No OpenAI API key set! Please open Settings and add your key."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            messages = [{"role": "system", "content": system_prompt}]
            for turn in history[:-1]:
                role = "assistant" if turn.get("role") == "model" else "user"
                parts_text = " ".join(p.get("text", "") for p in turn.get("parts", []))
                if parts_text:
                    messages.append({"role": role, "content": parts_text})
            messages.append({"role": "user", "content": text})
            resp = client.chat.completions.create(
                model=cfg.get("openai_model", "gpt-4o"),
                messages=messages
            )
            return resp.choices[0].message.content or "I'm speechless!"
        except Exception as e:
            return f"OpenAI error: {e}"

    @staticmethod
    def _anthropic_response(text: str, history: list, system_prompt: str, cfg: dict) -> str:
        api_key = cfg.get("anthropic_api_key", "")
        if not api_key:
            return "No Anthropic API key set! Please open Settings and add your key."
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            messages = []
            for turn in history[:-1]:
                role = "assistant" if turn.get("role") == "model" else "user"
                parts_text = " ".join(p.get("text", "") for p in turn.get("parts", []))
                if parts_text:
                    messages.append({"role": role, "content": parts_text})
            messages.append({"role": "user", "content": text})
            response = client.messages.create(
                model=cfg.get("anthropic_model", "claude-3-opus-20240229"),
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic error: {e}"

    @staticmethod
    def _openrouter_response(text: str, history: list, system_prompt: str, cfg: dict) -> str:
        api_key = cfg.get("openrouter_api_key", "")
        if not api_key:
            return "No OpenRouter API key set! Please open Settings and add your key."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            messages = [{"role": "system", "content": system_prompt}]
            for turn in history[:-1]:
                role = "assistant" if turn.get("role") == "model" else "user"
                parts_text = " ".join(p.get("text", "") for p in turn.get("parts", []))
                if parts_text:
                    messages.append({"role": role, "content": parts_text})
            messages.append({"role": "user", "content": text})
            resp = client.chat.completions.create(
                model=cfg.get("openrouter_model", "anthropic/claude-3-opus"),
                messages=messages
            )
            return resp.choices[0].message.content or "I'm speechless!"
        except Exception as e:
            return f"OpenRouter error: {e}"
