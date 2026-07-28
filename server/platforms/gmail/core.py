import asyncio
import sqlite3
import json
import time
import logging
import urllib.request
from typing import Dict, Any

from server.config import log_info

# Cooldown for critical-email WhatsApp pings (epoch seconds of last ping).
_LAST_EMAIL_ALERT = 0.0
from server.ai import get_ai_response

logger = logging.getLogger(__name__)

class GmailCore:
    def __init__(self, db_path: str, dashboard_broadcaster):
        self.db_path = db_path
        self.dashboard_broadcaster = dashboard_broadcaster
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS gmail_messages (
                msg_id TEXT PRIMARY KEY,
                thread_id TEXT,
                timestamp REAL,
                sender TEXT,
                subject TEXT,
                snippet TEXT,
                body TEXT,
                is_read BOOLEAN,
                importance_score INTEGER
            );
        """)

    async def _analyze_importance(self, sender: str, subject: str, snippet: str) -> int:
        """Score 1-10. Was CALLING get_ai_response(prompt, provider='local') — a
        signature that never existed → TypeError → silent `return 3` for EVERY
        email (121/121 scored 3, which also made the >=8 critical alert dead code).
        Now: rule-based signals first (free, deterministic), LLM only for the
        ambiguous middle, and failures are LOGGED, never silent."""
        text = f"{sender} {subject} {snippet}".lower()

        # Obvious noise → low, obvious signal → high. Cheap and reliable.
        NOISE = ("unsubscribe", "newsletter", "digest", "promotion", "sale", "% off",
                 "no-reply@alerts", "notifications@", "job alert", "recommendation",
                 "webinar", "survey", "follow us", "deal", "offer expires")
        URGENT = ("urgent", "asap", "immediately", "action required", "final notice",
                  "payment failed", "suspended", "expiring", "expires today", "deadline",
                  "interview", "offer letter", "shortlisted", "selected", "otp",
                  "verify your", "security alert", "unauthorized", "invoice due",
                  "last date", "confirm your")
        if any(k in text for k in URGENT):
            base = 8
        elif any(k in text for k in NOISE):
            base = 2
        else:
            base = 0

        if base:
            return base
        try:
            from server.config import load_config
            resp, _ = get_ai_response(
                f"Sender: {sender}\nSubject: {subject}\nSnippet: {snippet[:300]}",
                [], load_config(),
                system_prompt_override=(
                    "Rate how urgently this email needs Master's PERSONAL attention, "
                    "1-10 (1=marketing/automated, 10=urgent personal/financial/deadline). "
                    "Reply with ONLY the integer."))
            import re as _re
            m = _re.search(r"\b(10|[1-9])\b", str(resp))
            if m:
                return min(max(int(m.group(1)), 1), 10)
            log_info(f"[GMAIL] importance parse failed for '{subject[:40]}': {str(resp)[:60]}")
        except Exception as e:
            log_info(f"[GMAIL] importance scoring failed: {e}")
        return 4

    async def poll_emails(self):
        try:
            from server.integrations import integrations
            token_data = integrations.load_token("google")
            if not token_data or "access_token" not in token_data:
                return

            access_token = token_data["access_token"]
            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5&q=is:unread"
            
            def make_request(token):
                req = urllib.request.Request(url)
                req.add_header("Authorization", f"Bearer {token}")
                return urllib.request.urlopen(req)
                
            try:
                response = make_request(access_token)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    log_info("[GMAIL] Token expired. Attempting auto-refresh...")
                    new_token = integrations.auto_refresh_google_token()
                    if new_token and "access_token" in new_token:
                        access_token = new_token["access_token"]
                        response = make_request(access_token)
                    else:
                        raise e
                else:
                    raise e

            with response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    messages = data.get("messages", [])
                    
                    for msg in messages:
                        msg_id = msg["id"]
                        
                        # Check if already processed
                        c = self.conn.cursor()
                        if c.execute("SELECT 1 FROM gmail_messages WHERE msg_id=?", (msg_id,)).fetchone():
                            continue

                        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                        detail_req = urllib.request.Request(detail_url)
                        detail_req.add_header("Authorization", f"Bearer {access_token}")

                        with urllib.request.urlopen(detail_req) as detail_resp:
                            if detail_resp.status == 200:
                                detail_data = json.loads(detail_resp.read().decode())
                                headers = detail_data.get("payload", {}).get("headers", [])
                                subject = "No Subject"
                                sender = "Unknown"
                                for h in headers:
                                    if h["name"].lower() == "subject":
                                        subject = h["value"]
                                    elif h["name"].lower() == "from":
                                        sender = h["value"]
                                        
                                snippet = detail_data.get("snippet", "")
                                thread_id = detail_data.get("threadId", "")
                                
                                importance = await self._analyze_importance(sender, subject, snippet)
                                
                                c.execute('''INSERT OR IGNORE INTO gmail_messages 
                                    (msg_id, thread_id, timestamp, sender, subject, snippet, body, is_read, importance_score)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                    (msg_id, thread_id, time.time(), sender, subject, snippet, "", False, importance))
                                self.conn.commit()

                                log_info(f"[GMAIL] Logged new email from {sender}. Importance: {importance}")

                                # Z1 Guardian Fraud Shield Scan (fail-safe)
                                try:
                                    from server.guardian import analyze_message
                                    analyze_message("gmail", sender, snippet, subject)
                                except Exception as e:
                                    log_info(f"[GMAIL] Guardian scan failed: {e}")

                                # Critical email (>=8) → instant WhatsApp ping, but never
                                # spammy: 60-min cooldown + IST quiet hours (23:00-08:00).
                                if importance >= 8:
                                    try:
                                        from server.config import mizune_now
                                        global _LAST_EMAIL_ALERT
                                        now_ist = mizune_now()
                                        in_quiet = now_ist.hour >= 23 or now_ist.hour < 8
                                        cooled = (time.time() - _LAST_EMAIL_ALERT) > 3600
                                        if not in_quiet and cooled:
                                            _LAST_EMAIL_ALERT = time.time()
                                            from server.commands import whatsapp_automation
                                            import asyncio as _aio
                                            ping = (f"📧 Master, important email ({importance}/10): "
                                                    f"{sender.split('<')[0].strip()[:40]} — {subject[:80]}")
                                            await _aio.to_thread(whatsapp_automation, "Master", ping)
                                            log_info(f"[GMAIL] Critical-email WhatsApp ping sent ({importance}/10).")
                                    except Exception as e:
                                        log_info(f"[GMAIL] Critical-email ping failed: {e}")

                                # Alert user if highly important
                                if importance >= 7 and self.dashboard_broadcaster:
                                    try:
                                        self.dashboard_broadcaster({
                                            "type": "gmail_alert",
                                            "sender": sender,
                                            "subject": subject,
                                            "snippet": snippet,
                                            "importance": importance
                                        })
                                    except Exception as e:
                                        log_info(f"[GMAIL] Failed to broadcast alert: {e}")
        except Exception as e:
            log_info(f"[GMAIL] Polling error: {e}")

    async def start(self):
        log_info("[GMAIL] Background poller started.")
        while True:
            await self.poll_emails()
            await asyncio.sleep(60)  # Poll every 60 seconds

def start_gmail_core(config, dashboard_broadcaster):
    core = GmailCore("cortex.db", dashboard_broadcaster)
    
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(core.start())
        
    import threading
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    return core
