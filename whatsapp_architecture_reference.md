# HERMES AGENT WHATSAPP INTEGRATION — COMPLETE TECHNICAL DECONSTRUCTION

## 1. THE CORE ARCHITECTURE: Gateway-Adapter Pattern

Hermes does NOT run WhatsApp as a standalone bot. It uses a **unified gateway architecture** where all 22 messaging platforms flow through the same `AIAgent.run_conversation()` loop. The WhatsApp adapter is just one entry point among many (Telegram, Discord, Slack, Signal, etc.).

```
WhatsApp Message → Baileys WebSocket → Node.js Bridge → IPC → Python Gateway Adapter 
→ MessageEvent → GatewayRunner._handle_message() → authorize() → resolve_session_key() 
→ AIAgent.run_conversation() → response → adapter.deliver() → Node.js Bridge → Baileys 
→ WhatsApp Web Protocol → User
```

**Critical insight**: This is a **Python↔Node.js bridge**. The WhatsApp adapter is a thin wrapper around a separate Node.js process running the Baileys library. It is NOT pure Python.

---

## 2. THE BAILEYS BRIDGE (Node.js Layer)

### What is Baileys?
Baileys is an **unofficial** Node.js library that reverse-engineers the WhatsApp Web protocol. It connects via WebSocket to WhatsApp's servers and provides:
- Send/receive text, media, voice messages
- Group message reading
- Message reactions and receipts
- OGG/OPUS voice note handling

**Ban risk**: This is NOT the official WhatsApp Business API. Meta can detect and ban accounts using third-party bridges.

### Baileys Session Storage
The session lives at `~/.hermes/platforms/whatsapp/session/` and contains:
- `creds.json` — Authentication credentials (device keys, tokens)
- `pre-keys/` — Encryption pre-key bundles
- `sender-keys/` — Group encryption keys
- `session-*/` — Individual chat session keys

**Security warning**: This directory grants **FULL access** to the WhatsApp account. If compromised, an attacker can impersonate the bot completely. Never commit or share it.

### Connection Code (Simplified)
```javascript
import makeWASocket, { useMultiFileAuthState, fetchLatestBaileysVersion } from '@whiskeysockets/baileys'

async function startHermesBridge() {
  const { state, saveCreds } = await useMultiFileAuthState('~/.hermes/platforms/whatsapp/session')
  const { version } = await fetchLatestBaileysVersion()
  
  const sock = makeWASocket({ version, auth: state, printQRInTerminal: true })
  
  sock.ev.on('creds.update', saveCreds)  // Persist auth on every update
  
  sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
    if (connection === 'close') {
      const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== 401
      if (shouldReconnect) startHermesBridge()  // Auto-reconnect unless logged out
    }
  })
  
  // INCOMING MESSAGE INTERCEPTION
  sock.ev.on('messages.upsert', async ({ messages }) => {
    const msg = messages[0]
    await forwardToPythonGateway({
      id: msg.key.id,
      from: msg.key.remoteJid,
      text: msg.message?.conversation,
      type: msg.key.fromMe ? 'outgoing' : 'incoming',
      timestamp: msg.messageTimestamp,
    })
  })
}
```

---

## 3. THE PYTHON GATEWAY ADAPTER

### 3.1 MessageEvent Structure
When Node.js forwards a message to Python, it becomes a `WhatsAppMessageEvent`:

| Field | Description | Example |
|-------|-------------|---------|
| `message_id` | Baileys unique ID | `"3EB0...FA12"` |
| `sender_jid` | Sender's WhatsApp JID | `"1234567890@s.whatsapp.net"` |
| `sender_phone` | E.164 format | `"+1234567890"` |
| `chat_jid` | Chat identifier | Individual or group JID |
| `chat_type` | `"dm"` or `"group"` | — |
| `text` | Message content | `"Hello bot"` |
| `voice_note` | Is this a voice message? | `true/false` |
| `is_mention` | Was bot @-mentioned? | `true/false` |
| `quoted_message_id` | Reply-to message ID | `"3EB0...FA11"` |
| `raw_payload` | Full Baileys object | Complete message JSON |

### 3.2 Authorization: 5-Layer Hierarchy

```
LAYER 1: Global gateway kill-switch
    └─ whatsapp.enabled = false? → BLOCK

LAYER 2: Platform blocklist  
    └─ sender in blocked_users? → BLOCK

LAYER 3: Group routing
    ├─ Group not in allowed_groups? → BLOCK
    └─ require_mention=true and not mentioned? → BLOCK (DEFAULT)

LAYER 4: DM authorization
    ├─ allowed_users = '*'? → ALLOW
    ├─ sender in allowed_users? → ALLOW
    └─ unauthorized_dm_behavior:
        ├─ 'ignore' → SILENT BLOCK
        └─ 'pair' (default) → SEND PAIRING CODE, BLOCK

LAYER 5: Default → ALLOW
```

**Default group behavior**: The bot is **silent unless explicitly invoked** (mention-only mode). This prevents group spam.

### 3.3 Session Resolution
Session keys follow the format: `agent:{agent_id}:whatsapp:{chat_type}:{jid}`

| Chat Type | Session Key Example |
|-----------|-------------------|
| DM | `agent:main:whatsapp:dm:1234567890@s.whatsapp.net` |
| Group | `agent:main:whatsapp:group:1234567890-123@g.us` |

**Why this matters**: DMs and groups have **completely separate conversation histories**. A `/verbose` command in a group does not affect your personal DM session.

---

## 4. CONVERSATION LOOP INTEGRATION

The WhatsApp adapter injects platform-specific hints into the system prompt:

```markdown
## PLATFORM: WHATSAPP
- Keep responses concise (mobile users read on small screens)
- Use WhatsApp-native formatting: *bold*, _italic_, ~strikethrough~
- Avoid long code blocks; use triple backticks sparingly
- For voice replies: keep under 2 minutes of TTS audio
- Group context: You are replying in the group "{group_name}". 
  Members: {member_list}. Address the specific sender.
- Mention-only mode: Only respond when explicitly tagged or replied to
```

Then it calls the **same** `AIAgent.run_conversation()` that the CLI uses. This is why slash commands work identically across all platforms.

---

## 5. RESPONSE DELIVERY: How Hermes Sends Answers Back

### 5.1 Text Delivery Pipeline

```python
class WhatsAppAdapter:
    async def deliver_response(self, response: str, event: WhatsAppMessageEvent):
        # STEP 1: Apply reply prefix (default: "⚕ Hermes Agent")
        prefix = self.config.get('whatsapp.reply_prefix', '⚕ **Hermes Agent**')
        if prefix:
            response = f"{prefix}\n\n{response}"
        
        # STEP 2: Convert Markdown → WhatsApp-native formatting
        response = self._convert_markdown_to_whatsapp(response)
        # **bold** → *bold*
        # ~~strike~~ → ~strike~
        # # Heading → *Heading* (bold, no native headings)
        # [link](url) → link text (url)
        
        # STEP 3: Chunk at 4096 characters (WhatsApp limit)
        chunks = self._chunk_response(response, max_length=4096)
        
        # STEP 4: Send sequentially with rate limiting
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.5)  # Rate limit between chunks
            
            await self._send_text(
                to_jid=event.chat_jid,
                text=chunk,
                quoted_message_id=event.message_id if i == 0 else None
            )
```

### 5.2 Chunking Algorithm
Long responses are split at:
- **Word boundaries** (never mid-word)
- **Paragraph breaks** (preferred split point)
- **Sentence boundaries** (fallback for oversized paragraphs)

### 5.3 Voice Replies (TTS)
If `reply_voice_messages: true`:
1. Synthesize text to MP3 via ElevenLabs/OpenAI TTS
2. Send as WhatsApp voice message (PTT = Push-to-Talk style)
3. Optionally also send text transcript

---

## 6. VOICE MESSAGE HANDLING (Incoming)

### STT Pipeline for Voice Notes
```python
async def handle_voice_message(event: WhatsAppMessageEvent):
    # 1. Download OGG/OPUS from WhatsApp servers (Baileys decrypts)
    ogg_bytes = await self.baileys_bridge.download_media(event.message_id)
    
    # 2. Route to STT provider
    stt_provider = self.config.get('tts_stt.stt_provider', 'whisper')
    
    # 3. Transcribe
    transcript = await self.stt_provider.transcribe(
        audio=ogg_bytes,
        language='auto',
        prompt='This is a voice message from WhatsApp'
    )
    
    # 4. Inject into conversation as: "[Voice message]: {transcript}"
    return f"[Voice message]: {transcript}"
```

**STT options**: Local `faster-whisper` (privacy-preserving), Groq Whisper, or OpenAI Whisper.

---

## 7. GROUP CHAT BEHAVIOR

### 7.1 Mention-Only Mode (Default)
The bot only responds when:
1. **@-mentioned** via WhatsApp's `mentionedJids` metadata
2. **Replying to a bot message** (quoted message detection)
3. **Wake prefix** detected: `hermes:` or `/hermes` at message start

### 7.2 Group Context Injection
When triggered in a group, the prompt includes:
```markdown
You are replying inside the WhatsApp group "Project Alpha".
Group members: Alice (+44...), Bob (+43...), Charlie (+1...)
Activation: trigger-only (you only respond when tagged)
Address the specific sender noted in the message context.

[Chat messages since your last reply - for context]
- Alice: "What about the deadline?"
- Bob: "I think we need more time"

[Current message - respond to this]
- Alice: "@Hermes what's the status?"
```

**Key design**: Only "pending" messages (not yet processed) are injected. Already-seen messages are NOT re-injected to avoid duplication.

---

## 8. CONFIGURATION OPTIONS

### Environment Variables (.env)
```bash
WHATSAPP_ENABLED=true
WHATSAPP_MODE=bot                    # "bot" or "self-chat"
WHATSAPP_ALLOWED_USERS=15551234567   # Comma-separated E.164, no +
# WHATSAPP_ALLOWED_USERS=*            # Allow all
WHATSAPP_DEBUG=true                  # Log raw Baileys events
```

### Config YAML (config.yaml)
```yaml
gateway:
  platforms:
    whatsapp:
      enabled: true
      unauthorized_dm_behavior: pair   # "pair" | "ignore"
      allowed_users: []
      allowed_groups: []
      require_mention: true            # Group mention-only (DEFAULT)
      wake_prefixes: ["hermes:", "/hermes"]
      reply_prefix: "⚕ **Hermes Agent"
      reply_voice_messages: false
      text_batch_delay_seconds: 5.0    # Debounce rapid messages
      max_messages_per_minute: 20
```

---

## 9. SESSION REPAIR & TROUBLESHOOTING

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| QR code not scanning | Terminal < 60 columns | Widen terminal |
| QR code expires | ~20 second timeout | Restart `hermes whatsapp` |
| Session not persisting | `session/` not writable | Check permissions |
| Logged out unexpectedly | Phone offline > 24h | Re-pair; keep phone on network |
| Bridge crashes | WhatsApp protocol update | `hermes update` then re-pair |
| Messages not received | Sender not in allowlist | Add to `WHATSAPP_ALLOWED_USERS` |
| Bot replies to strangers | `pair` mode default | Set `unauthorized_dm_behavior: ignore` |
| No voice transcription | STT not configured | `hermes config set tts_stt.stt_provider whisper` |

**Re-pairing command**:
```bash
hermes gateway stop
rm -rf ~/.hermes/platforms/whatsapp/session/
hermes whatsapp  # Generate new QR
hermes gateway start
```

---

## 10. COMPARISON: HERMES vs. OPENCLAW vs. MIZUNE (WhatsApp)

| Feature | Hermes | OpenClaw | Mizune (Current) |
|---------|--------|----------|-----------------|
| Bridge library | Baileys (Node.js) | Baileys (Node.js) | **None** |
| Session persistence | `~/.hermes/platforms/whatsapp/session/` | `~/.openclaw/whatsapp/session/` | **N/A** |
| Group mention-only | ✅ Default | ✅ Default | ❌ **Not implemented** |
| Voice transcription | ✅ OGG→STT | ✅ OGG→STT | ❌ **Not implemented** |
| Voice replies (TTS) | ✅ MP3/OGG out | ✅ MP3/OGG out | ❌ **Not implemented** |
| Message chunking (4096) | ✅ | ✅ | ❌ **Not implemented** |
| Cross-platform sessions | ✅ Same memory | ✅ Same memory | ❌ **No gateway** |
| Rate limiting | ✅ Built-in | ✅ Built-in | ❌ **Not implemented** |
| Message debounce (5s) | ✅ | ✅ Configurable | ❌ **Not implemented** |
| Reply prefix | ✅ Customizable | ✅ Customizable | ❌ **Not implemented** |
| Wake prefixes | ✅ `hermes:` `/hermes` | ✅ Configurable | ❌ **Not implemented** |

---

## 11. WHAT YOU NEED TO BUILD FOR MIZUNE

To match Hermes' WhatsApp capabilities, you need these 10 components:

1. **Baileys Node.js bridge** (or `whatsapp-web.js` alternative)
2. **Python↔Node.js IPC** (HTTP localhost, WebSocket, or stdio)
3. **MessageEvent dataclass** with WhatsApp-specific fields (JIDs, mention metadata)
4. **Authorization layer** (5-layer hierarchy: global → blocklist → group → DM → default)
5. **Session resolution** (separate DM/group keys: `agent:id:whatsapp:dm:{jid}`)
6. **Response formatter** (Markdown→WhatsApp native, chunking at 4096 chars)
7. **Voice pipeline** (OGG download→STT→text injection; TTS→MP3/OGG send)
8. **Group mention detection** (parse `mentionedJids`, reply-to-bot, wake prefixes)
9. **Session persistence** (SQLite for conversations, disk for Baileys auth)
10. **Auto-reconnect logic** (handle WhatsApp protocol changes gracefully)

**Your killer advantage**: When WhatsApp says "Export the Figma file," you can **literally click the Export button** via your VisionAgent. Hermes can only reply with text instructions.
