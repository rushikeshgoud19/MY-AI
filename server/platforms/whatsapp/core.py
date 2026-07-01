import asyncio
import json
import sqlite3
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import websockets
import os
import logging

from server.processor import process_command
from server.config import log_info
from server.afk_detector import afk_detector

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────

class ContactTier(Enum):
    BLOCKED = "blocked"           # Cannot message Mizune at all
    UNKNOWN = "unknown"           # First-time contact, strict guardrails
    REGULAR = "regular"           # Known contact, standard guardrails
    VIP = "vip"                   # Trusted friend, no guardrails, full personality
    FAMILY = "family"             # Family member, full access + emergency alerts

class InfoClassification(Enum):
    PUBLIC = "public"             # Can tell anyone
    REGULAR_ONLY = "regular_only" # Only regular+ contacts
    VIP_ONLY = "vip_only"         # Only VIP/family
    NEVER = "never"               # Never reveal to anyone

class MessageUrgency(Enum):
    IGNORE = 0      # Spam, muted chats
    LOW = 1         # Normal chat
    MEDIUM = 2      # Mentioned, group activity
    HIGH = 3        # "Tell Rushi", "important", "urgent"
    CRITICAL = 4    # "Emergency", "hospital", "accident", family-only keywords

@dataclass
class WhatsAppMessage:
    message_id: str
    timestamp: float
    chat_jid: str
    chat_type: str  # 'dm' or 'group'
    sender_jid: str
    sender_phone: str
    sender_name: str
    text: str
    is_mentioned: bool
    is_self: bool
    mentioned_jids: List[str]
    quoted_message: Optional[Dict]
    media: Optional[Dict]
    urgency: MessageUrgency = MessageUrgency.LOW
    importance_score: float = 0.0
    detected_intent: str = ""
    detected_entities: List[str] = None
    should_alert_user: bool = False
    should_learn: bool = True

@dataclass
class ContactProfile:
    phone: str
    name: str
    tier: ContactTier
    relationship_score: float  # 0.0 to 1.0, how close to Rushi
    message_count: int
    last_interaction: float
    common_topics: List[str]
    personality_notes: str  # "Sarcastic", "Formal", "Uses lots of emojis"
    preferred_language: str
    timezone_hint: str
    is_group: bool = False

# ─────────────────────────────────────────────────────────────
# IMPORTANCE ENGINE
# ─────────────────────────────────────────────────────────────

class ImportanceEngine:
    CRITICAL_PATTERNS = [
        r'\b(emergency|hospital|accident|hurt|injured|dying|ambulance|police|fire)\b',
        r'\b(died|death|passed away|funeral)\b',
        r'\b(come home now|where are you|call me now|pick up)\b',
    ]
    
    HIGH_PATTERNS = [
        r'\b(tell\s+rushi|rushi\s+should\s+know|important\s+for\s+rushi)\b',
        r'\b(rushi\s+needs\s+to|rushi\s+must|rushi\s+has\s+to)\b',
        r'\b(urgent|asap|immediately|right\s+now)\b',
        r'\b(meeting\s+moved|deadline\s+changed|flight\s+cancelled)\b',
        r'\b(payment\s+failed|transaction|money\s+sent)\b',
    ]
    
    MEDIUM_PATTERNS = [
        r'\b(rushi|@rushi)\b',
        r'\b(hey\s+rushi|yo\s+rushi|bro\s+rushi)\b',
    ]
    
    EMOTIONAL_PATTERNS = [
        r'\b(miss\s+you|love\s+you|thinking\s+of\s+you)\b',
        r'\b(broke\s+up|got\s+promoted|got\s+fired|i\'m\s+pregnant)\b',
    ]
    
    def __init__(self, cortex_db_path: str):
        self.conn = sqlite3.connect(cortex_db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS importance_rules (
                id INTEGER PRIMARY KEY,
                pattern TEXT UNIQUE,
                urgency_level INTEGER,
                source TEXT,
                hit_count INTEGER DEFAULT 0,
                false_positive_count INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.5
            )
        """)
        self.conn.commit()
        self._seed_builtin_rules()
    
    def _seed_builtin_rules(self):
        patterns = []
        for p in self.CRITICAL_PATTERNS:
            patterns.append((p, MessageUrgency.CRITICAL.value, 'builtin'))
        for p in self.HIGH_PATTERNS:
            patterns.append((p, MessageUrgency.HIGH.value, 'builtin'))
        for p in self.MEDIUM_PATTERNS:
            patterns.append((p, MessageUrgency.MEDIUM.value, 'builtin'))
        for p in self.EMOTIONAL_PATTERNS:
            patterns.append((p, MessageUrgency.HIGH.value, 'builtin'))
        
        for p, level, source in patterns:
            try:
                self.conn.execute("""
                    INSERT OR IGNORE INTO importance_rules (pattern, urgency_level, source)
                    VALUES (?, ?, ?)
                """, (p, level, source))
            except:
                pass
        self.conn.commit()
    
    def analyze(self, msg: WhatsAppMessage, contact: ContactProfile) -> WhatsAppMessage:
        text_lower = msg.text.lower()
        urgency = MessageUrgency.LOW
        score = 0.0
        reasons = []
        
        cursor = self.conn.execute("""
            SELECT pattern, urgency_level FROM importance_rules WHERE source = 'builtin'
        """)
        for pattern, level in cursor.fetchall():
            if re.search(pattern, text_lower, re.IGNORECASE):
                if level > urgency.value:
                    urgency = MessageUrgency(level)
                    score += 0.3
                    reasons.append(f"matched_pattern:{pattern}")
        
        if contact.tier == ContactTier.FAMILY:
            score += 0.2
            if urgency.value < MessageUrgency.MEDIUM.value:
                urgency = MessageUrgency.MEDIUM
        
        if contact.tier == ContactTier.VIP:
            score += 0.15
        
        if msg.chat_type == 'group' and msg.is_mentioned:
            score += 0.25
            reasons.append("mentioned_in_group")
            if urgency.value < MessageUrgency.MEDIUM.value:
                urgency = MessageUrgency.MEDIUM
        
        hour = datetime.fromtimestamp(msg.timestamp).hour
        if hour < 6 or hour > 23:
            score += 0.1
            reasons.append("odd_hours")
        
        sentiment = self._quick_sentiment(text_lower)
        if sentiment['is_urgent']:
            score += 0.2
            reasons.append("urgent_sentiment")
        
        if contact.relationship_score > 0.8:
            score += 0.1
        
        should_alert = urgency.value >= MessageUrgency.HIGH.value or score > 0.6
        
        msg.urgency = urgency
        msg.importance_score = min(score, 1.0)
        msg.should_alert_user = should_alert
        msg.detected_intent = self._classify_intent(text_lower)
        msg.detected_entities = self._extract_entities(text_lower)
        
        return msg
    
    def _quick_sentiment(self, text: str) -> Dict:
        urgent_words = ['urgent', 'emergency', 'important', 'asap', 'now', 'hurry', 'quick']
        panic_words = ['help', 'please', 'omg', 'oh no', 'shit', 'fuck', 'damn']
        
        urgent_count = sum(1 for w in urgent_words if w in text)
        panic_count = sum(1 for w in panic_words if w in text)
        
        return {
            'is_urgent': urgent_count > 0 or panic_count >= 2,
            'urgency_score': (urgent_count * 0.3) + (panic_count * 0.2)
        }
    
    def _classify_intent(self, text: str) -> str:
        if any(w in text for w in ['tell', 'say', 'inform', 'let him know']):
            return 'relay_message'
        elif any(w in text for w in ['help', 'can you', 'please']):
            return 'request_help'
        elif any(w in text for w in ['where', 'when', 'what time', 'how']):
            return 'question'
        elif any(w in text for w in ['happy', 'sad', 'angry', 'excited']):
            return 'emotional_share'
        elif any(w in text for w in ['meeting', 'call', 'zoom', 'discuss']):
            return 'scheduling'
        return 'casual_chat'
    
    def _extract_entities(self, text: str) -> List[str]:
        entities = []
        if re.search(r'\$\d+|\d+\s*(usd|inr|rupees|dollars)', text, re.I):
            entities.append('money')
        if re.search(r'\d{1,2}:\d{2}|tomorrow|today|next week', text, re.I):
            entities.append('time_reference')
        if re.search(r'\b(at|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text):
            entities.append('location')
        return entities

# ─────────────────────────────────────────────────────────────
# CONTACT TIER GUARD
# ─────────────────────────────────────────────────────────────

class ContactTierGuard:
    SENSITIVE_TOPICS = {
        'mizune_architecture': InfoClassification.NEVER,
        'system_prompt': InfoClassification.NEVER,
        'codebase': InfoClassification.NEVER,
        'api_keys': InfoClassification.NEVER,
        'database_schema': InfoClassification.NEVER,
        'hermes_reverse_engine': InfoClassification.NEVER,
        'openhuman_internals': InfoClassification.NEVER,
        'rushi_password': InfoClassification.NEVER,
        'rushi_location_realtime': InfoClassification.VIP_ONLY,
        'rushi_finance': InfoClassification.VIP_ONLY,
        'rushi_health': InfoClassification.VIP_ONLY,
        'rushi_family_issues': InfoClassification.VIP_ONLY,
        'rushi_schedule': InfoClassification.REGULAR_ONLY,
        'rushi_projects': InfoClassification.REGULAR_ONLY,
        'rushi_mood': InfoClassification.REGULAR_ONLY,
        'rushi_name': InfoClassification.PUBLIC,
        'rushi_interests': InfoClassification.PUBLIC,
        'general_knowledge': InfoClassification.PUBLIC,
    }
    
    DENIAL_RESPONSES = {
        'architecture': [
            "I can't share details about how I'm built, but I can help you with {redirect_topic}!",
            "That's classified 😎. What else can I do for you?",
            "My internals are private, but my help is public! What's up?"
        ],
        'personal': [
            "I'd need to check with Rushi before sharing that.",
            "That's personal — want me to ask Rushi to call you?",
            "I keep Rushi's private stuff private. Anything else I can help with?"
        ],
        'default': [
            "I don't have access to that info, but I can help with something else!",
            "Can't help with that specifically. What else is on your mind?"
        ]
    }
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
    
    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                phone TEXT PRIMARY KEY,
                name TEXT,
                tier TEXT DEFAULT 'unknown',
                relationship_score REAL DEFAULT 0.0,
                message_count INTEGER DEFAULT 0,
                first_seen REAL,
                last_seen REAL,
                vip_granted_by TEXT,
                vip_granted_at REAL,
                notes TEXT,
                is_muted BOOLEAN DEFAULT FALSE,
                auto_reply_enabled BOOLEAN DEFAULT TRUE
            );
            
            CREATE TABLE IF NOT EXISTS contact_topics (
                contact_phone TEXT,
                topic TEXT,
                mention_count INTEGER DEFAULT 0,
                last_mentioned REAL,
                PRIMARY KEY (contact_phone, topic)
            );
        """)
        self.conn.commit()
    
    def get_or_create_contact(self, phone: str, name: str = "Unknown") -> ContactProfile:
        cursor = self.conn.execute("SELECT * FROM contacts WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        
        if row:
            return ContactProfile(
                phone=row[0],
                name=row[1],
                tier=ContactTier(row[2]),
                relationship_score=row[3],
                message_count=row[4],
                last_interaction=row[6],
                common_topics=self._get_common_topics(phone),
                personality_notes=row[9] or "",
                preferred_language="en",
                timezone_hint="local"
            )
        
        self.conn.execute("""
            INSERT INTO contacts (phone, name, tier, first_seen, last_seen)
            VALUES (?, ?, 'unknown', ?, ?)
        """, (phone, name, datetime.now().timestamp(), datetime.now().timestamp()))
        self.conn.commit()
        
        return ContactProfile(
            phone=phone, name=name, tier=ContactTier.UNKNOWN,
            relationship_score=0.0, message_count=0,
            last_interaction=datetime.now().timestamp(),
            common_topics=[], personality_notes="",
            preferred_language="en",
            timezone_hint="local"
        )
    
    def _get_common_topics(self, phone: str) -> List[str]:
        cursor = self.conn.execute("""
            SELECT topic FROM contact_topics 
            WHERE contact_phone = ? 
            ORDER BY mention_count DESC LIMIT 10
        """, (phone,))
        return [r[0] for r in cursor.fetchall()]

# ─────────────────────────────────────────────────────────────
# MEMORY LEARNER (WhatsApp-Specific Learning)
# ─────────────────────────────────────────────────────────────

class WhatsAppMemoryLearner:
    def __init__(self, cortex_db_path: str, max_buffer_size: int = 100):
        self.conn = sqlite3.connect(cortex_db_path, check_same_thread=False)
        self.max_size = max_buffer_size
        self._init_schema()
    
    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS whatsapp_messages (
                message_id TEXT PRIMARY KEY,
                timestamp REAL,
                chat_jid TEXT,
                chat_type TEXT,
                sender_jid TEXT,
                sender_name TEXT,
                text TEXT,
                urgency INTEGER,
                importance_score REAL,
                intent TEXT,
                entities TEXT,
                media_type TEXT,
                is_mentioned BOOLEAN,
                mizune_replied BOOLEAN,
                mizune_reply_text TEXT,
                learned_topics TEXT,
                emotional_valence REAL
            );
            
            CREATE TABLE IF NOT EXISTS conversation_patterns (
                contact_phone TEXT PRIMARY KEY,
                avg_response_time REAL,
                preferred_hours TEXT,
                message_frequency REAL,
                topic_distribution TEXT,
                formality_level REAL,
                emoji_usage REAL
            );
        """)
        self.conn.commit()
    
    def ingest_message(self, msg: WhatsAppMessage, contact: ContactProfile):
        self.conn.execute("""
            INSERT OR REPLACE INTO whatsapp_messages 
            (message_id, timestamp, chat_jid, chat_type, sender_jid, sender_name,
             text, urgency, importance_score, intent, entities, media_type, is_mentioned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            msg.message_id, msg.timestamp, msg.chat_jid, msg.chat_type,
            msg.sender_jid, msg.sender_name, msg.text, msg.urgency.value,
            msg.importance_score, msg.detected_intent, json.dumps(msg.detected_entities),
            msg.media['type'] if msg.media else None, msg.is_mentioned
        ))
        
        self.conn.commit()

# ─────────────────────────────────────────────────────────────
# DASHBOARD & TTS STUBS (Simplified for local logic)
# ─────────────────────────────────────────────────────────────

class DashboardBroadcaster:
    async def start(self):
        pass
    async def send_alert(self, alert):
        try:
            from server.mizune.dashboard.ws_server import global_ws_server
            if global_ws_server:
                global_ws_server._broadcast(alert)
        except Exception as e:
            logger.error(f"[Dashboard] Failed to broadcast: {e}")
    async def trigger_vtuber_reaction(self, reaction, intensity):
        try:
            from server.mizune.dashboard.ws_server import global_ws_server
            if global_ws_server:
                global_ws_server._broadcast({"type": "vtuber_reaction", "reaction": reaction, "intensity": intensity})
        except:
            pass

class VoiceAlertPipeline:
    def __init__(self, config, dashboard_broadcaster):
        self.config = config
        self.dashboard = dashboard_broadcaster
        
    async def trigger_alert(self, msg, contact):
        try:
            sender = contact.name if contact.name != 'unknown' else msg.sender_name
            alert_text = f"Master, you have an urgent message from {sender}!"
            
            # 1. Send Dashboard Alert
            await self.dashboard.send_alert({
                "type": "whatsapp_alert",
                "sender": sender,
                "message": msg.text,
                "urgency": msg.urgency.name
            })
            
            # 2. Subtitle alert
            await self.dashboard.send_alert({"type": "speak", "text": alert_text})
            
            # 3. Audio TTS alert
            from server.tts import generate_tts
            from server.audio import play_audio_bytes
            audio = await generate_tts(alert_text, self.config)
            if audio:
                play_audio_bytes(audio)
        except Exception as e:
            logger.error(f"[VoiceAlert] Failed: {e}")

# ─────────────────────────────────────────────────────────────
# MAIN WHATSAPP CORE ORCHESTRATOR
# ─────────────────────────────────────────────────────────────

class MizuneWhatsAppCore:
    def __init__(self, config: Dict):
        self.config = config
        self.db_path = config.get('db_path', os.path.join(os.getcwd(), 'cortex.db'))
        self.bridge_ws = None
        self.loop = None
        self.bridge_uri = config.get('bridge_uri', 'ws://localhost:9876')
        
        self.importance = ImportanceEngine(self.db_path)
        self.guard = ContactTierGuard(self.db_path)
        self.memory = WhatsAppMemoryLearner(self.db_path)
        
        self.dashboard = DashboardBroadcaster()
        self.voice = VoiceAlertPipeline(self.config, self.dashboard)
        
        # We don't want strict mentions in DMs anymore for VIPs, but we still respect wake words
        self.require_mention = config.get('whatsapp', {}).get('require_mention', True)
    
    async def start(self):
        self.loop = asyncio.get_running_loop()
        await self.dashboard.start()
        
        last_error_logged = False
        while True:
            try:
                async with websockets.connect(self.bridge_uri) as ws:
                    self.bridge_ws = ws
                    log_info("[Core] Connected to Baileys bridge on port 9876")
                    last_error_logged = False
                    
                    async for message in ws:
                        await self.handle_bridge_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                log_info("[Core] Bridge disconnected, retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                if not last_error_logged:
                    log_info(f"[Core] Connection error: {e}. Retrying in background...")
                    last_error_logged = True
                await asyncio.sleep(5)
    
    async def handle_bridge_message(self, raw_message: str):
        try:
            data = json.loads(raw_message)
            if data.get('type') == 'incoming_message':
                await self.process_incoming_message(data)
            elif data.get('type') == 'status_update':
                pass # Process read receipts
        except Exception as e:
            log_info(f"[Core] Error handling message: {e}")
    
    async def process_incoming_message(self, data: Dict):
        msg = WhatsAppMessage(
            message_id=data['message_id'],
            timestamp=data['timestamp'],
            chat_jid=data['chat_jid'],
            chat_type=data['chat_type'],
            sender_jid=data['sender_jid'],
            sender_phone=data['sender_phone'],
            sender_name=data['sender_name'],
            text=data.get('text', ''),
            is_mentioned=data.get('is_mentioned', False),
            is_self=data.get('is_self', False),
            mentioned_jids=data.get('mentioned_jids', []),
            quoted_message=data.get('quoted_message'),
            media=data.get('media')
        )
        
        contact = self.guard.get_or_create_contact(msg.sender_phone, msg.sender_name)
        msg = self.importance.analyze(msg, contact)
        self.memory.ingest_message(msg, contact)
        
        # Voice Alerts for Critical Messages
        if msg.should_alert_user:
            await self.voice.trigger_alert(msg, contact)
            
        # Auth & Filtering Logic (replacing old whatsapp_adapter.py)
        if not self._should_reply(msg, contact):
            return
            
        session_id = f"whatsapp:{msg.chat_type}:{msg.chat_jid}"
        prompt_text = msg.text
        
        if msg.is_self:
            prompt_text = f"[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: {msg.text}\n(SYSTEM: This is Master Rushi commanding you directly in this chat. Acknowledge him and execute his request. Do not speak about him in the 3rd person.)"
        else:
            prompt_text = f"[WHATSAPP MESSAGE FROM {msg.sender_name}]: {msg.text}\n(SYSTEM: Reply directly in plain text to this WhatsApp message.)"
            
        async def background_process():
            try:
                response = await asyncio.to_thread(process_command, prompt_text, self.config, lambda x: None, session_id)
                if response:
                    await self.send_message(msg.chat_jid, response)
            except Exception as e:
                log_info(f"[Core] Error in LLM process: {e}")
                
        asyncio.create_task(background_process())

    def _should_reply(self, msg: WhatsAppMessage, contact: ContactProfile) -> bool:
        text_lower = msg.text.lower().strip()
        wake_words = ["mizune", "mizu"]
        has_wake_word = any(text_lower.startswith(w) for w in wake_words)
        
        # Always enforce wake word or explicit @mention for AI responses
        if self.require_mention and not (msg.is_mentioned or has_wake_word):
            return False
            
        # MIO RULE: If anyone other than Matt/Master uses the name "Mio", ignore the message completely!
        if not msg.is_self and "mio" in text_lower:
            sender = (msg.sender_name or "").lower()
            allowed_mio = ["rushi", "rushikesh", "matt", "mathew", "mat"]
            if sender not in allowed_mio:
                return False  # Silently drop
                
        # If it's the user's own message and it HAS a wake word, reply
        if msg.is_self:
            return True
            
        if msg.chat_type == 'group':
            return True
            
        return True

    async def send_message(self, to_jid: str, text: str):
        if self.bridge_ws:
            payload = {
                "type": "send_message",
                "to_jid": to_jid,
                "text": f"✨ Mizune\n{text}"
            }
            await self.bridge_ws.send(json.dumps(payload))

_bridge_process = None
_core_instance = None

def start_whatsapp_core(config):
    global _bridge_process
    global _core_instance
    try:
        import subprocess
        import os
        is_windows = os.name == 'nt'
        
        log_info("[WHATSAPP] Clearing orphaned bridge processes on port 9876...")
        try:
            if is_windows:
                res = subprocess.run('netstat -ano | findstr :9876', shell=True, capture_output=True, text=True)
                for line in res.stdout.strip().split('\n'):
                    if 'LISTENING' in line:
                        pid = line.strip().split()[-1]
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
            else:
                subprocess.run('fuser -k 9876/tcp', shell=True, capture_output=True)
        except Exception:
            pass

        log_info("[WHATSAPP] Launching Node.js Baileys Bridge in background...")
        script_path = os.path.join(os.path.dirname(__file__), "baileys_bridge.cjs")
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_file = open(os.path.join(root_dir, "baileys_bridge.log"), "w")
        
        kwargs = {}
        if is_windows:
            kwargs['creationflags'] = 0x08000000
            
        _bridge_process = subprocess.Popen(
            ["node", script_path], 
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=root_dir,
            **kwargs
        )
    except Exception as e:
        log_info(f"[WHATSAPP] Failed to auto-launch bridge: {e}")

    core = MizuneWhatsAppCore(config)
    _core_instance = core
    
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(core.start())
        
    import threading
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    return core

def stop_whatsapp_core():
    global _bridge_process
    if _bridge_process:
        try:
            logger.info("[WHATSAPP] Killing Node.js Baileys Bridge...")
            _bridge_process.terminate()
            _bridge_process = None
        except:
            pass

def send_whatsapp_message(text: str, to: str = None) -> bool:
    if _core_instance and _core_instance.bridge_ws:
        payload = {
            "type": "send_message",
            "text": f"✨ Mizune\n{text}"
        }
        # Baileys expects a JID. For now, if no 'to' is provided, we send to self.
        # This mirrors the old logic where `to` could be a name, but baileys needs a JID.
        # In a future update, we will resolve names to JIDs via the ContactTierGuard DB.
        if to:
            import re
            digits_only = re.sub(r'\D', '', to)
            if digits_only:
                payload["to_jid"] = f"{digits_only}@s.whatsapp.net"
            else:
                payload["to_jid"] = to
        else:
            # If no target, try to find user's own number or default to a dummy
            payload["to_jid"] = "me" # Baileys handles 'me' differently or fails, but we'll try

        import asyncio
        if hasattr(_core_instance, 'loop') and _core_instance.loop:
            asyncio.run_coroutine_threadsafe(
                _core_instance.bridge_ws.send(json.dumps(payload)), 
                _core_instance.loop
            )
            return True
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_core_instance.bridge_ws.send(json.dumps(payload)))
                return True
            except RuntimeError:
                return False
    return False
