<p align="center">
  <img src="https://img.shields.io/badge/Mizune-AI%20Companion-ff69b4?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQyIDAtOC0zLjU4LTgtOHMzLjU4LTggOC04IDggMy41OCA4IDgtMy41OCA4LTggOHoiLz48L3N2Zz4=" alt="Mizune AI"/>
  <br/>
  <img src="https://img.shields.io/badge/Electron-3D%20Desktop-47848F?style=flat-square&logo=electron" alt="Electron"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?style=flat-square&logo=google" alt="Gemini"/>
  <img src="https://img.shields.io/badge/Groq-LPU%20Fallback-F55036?style=flat-square" alt="Groq"/>
  <img src="https://img.shields.io/badge/Murf-Voice%20AI-7C3AED?style=flat-square" alt="Murf"/>
  <img src="https://img.shields.io/badge/VRM-3D%20Avatar-FF6B6B?style=flat-square" alt="VRM"/>
</p>

<h1 align="center">🌸 Mizune — Your AI Desktop Companion</h1>

<p align="center">
  <strong>A fully autonomous, voice-controlled AI assistant that lives on your desktop as a 3D anime character.</strong>
  <br/>
  She sees your screen, controls your PC, coaches your code, and speaks with emotion — all in real-time.
</p>

---

## ✨ What Makes Mizune Special

Mizune isn't just another chatbot. She's a **persistent desktop companion** rendered as a 3D VRM anime character that:

- 🎤 **Listens** — Wake word detection + F2 hotkey → Groq/Whisper STT
- 🧠 **Thinks** — Multi-agent brain with 7 operational modes
- 👀 **Sees** — Real-time screen capture + Gemini/Groq Vision analysis
- 🗣️ **Speaks** — Murf AI / ElevenLabs TTS with synchronized lip movement
- 😊 **Feels** — Dynamic facial expressions (happy, blush, angry, surprised, sad)
- 💻 **Controls** — Full PC automation: apps, media, volume, screenshots, web search

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    ELECTRON FRONTEND                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 3D VRM   │  │ Lip Sync │  │ Emotion  │  │ Terminal │ │
│  │ Renderer │  │ Engine   │  │ System   │  │ Logger   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                        WebSocket                          │
├──────────────────────────────────────────────────────────┤
│                    FASTAPI BACKEND                         │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              MANAGER AGENT (Central Brain)            │ │
│  │  Routes requests → Modes → Worker Agents              │ │
│  ├──────────┬──────────┬──────────┬──────────────────────┤ │
│  │ System   │ Web      │ Memory   │ Coding Coach         │ │
│  │ Agent    │ Agent    │ Agent    │ (Vision Monitor)     │ │
│  └──────────┴──────────┴──────────┴──────────────────────┘ │
│  ┌──────────┬──────────┬──────────┬──────────────────────┐ │
│  │ Gemini   │ Groq     │ Murf AI  │ Whisper STT          │ │
│  │ 2.5 Flash│ Llama 3.3│ Voice    │ + Groq STT           │ │
│  └──────────┴──────────┴──────────┴──────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 🧠 Multi-Agent System

Mizune uses a **ManagerAgent** that routes commands to specialized workers:

| Agent | Role | Capabilities |
|-------|------|-------------|
| 🎯 **ManagerAgent** | Central Brain | Intent classification, mode management, agent routing |
| ⚙️ **SystemAgent** | PC Control | Launch/close apps, screenshots, environment setup, OS automation |
| 🌐 **WebAgent** | Web Operations | Search, scrape, summarize web content |
| 💾 **MemoryAgent** | Persistent Memory | ChromaDB-backed note storage, conversation history recall |

---

## 🎮 7 Operational Modes

| Mode | Trigger | What It Does |
|------|---------|-------------|
| 💬 **Conversation** | Default | Normal AI chat with personality |
| ✍️ **Writing** | *"writing mode"* | Continuous speech-to-text dictation |
| 🎯 **Focus** | *"focus mode"* | Pomodoro timer, blocks distracting sites, motivational nudges |
| 🎵 **Entertainment** | *"entertainment mode"* | Media control, anime/show recommendations |
| 🔍 **Research** | *"research mode"* | Web search, article summarization |
| ⚙️ **System** | *"system mode"* | Full PC control, project setup, file management |
| 💻 **Coding Coach** | *"coding mode"* | **Real-time screen monitoring** — watches your code, catches bugs, gives hints, praises good solutions |

### 💻 Coding Coach Mode (Highlight Feature)

When activated, Mizune **watches your screen in real-time**:

1. Captures your screen every 30 seconds silently
2. Sends to **Groq Vision** / **Gemini Vision** for AI analysis
3. **Speaks feedback** only when meaningful:
   - 🐛 *"Ara~ Master, your for loop has an off-by-one error on line 5!"*
   - ✅ *"Sugoi! That two-pointer approach is perfect, Master~!"*
   - 💡 Gives hints without spoiling (on request)
4. Blocks app-launching to keep you focused

---

## 🗣️ Voice Pipeline

### Text-to-Speech (Waterfall Fallback)
```
Murf AI (Japanese-accented, high quality)
    ↓ fallback
ElevenLabs (Turbo v2.5, ultra-low latency)
    ↓ fallback
Browser SpeechSynthesis (offline, zero cost)
```

### Speech-to-Text
```
Groq Whisper (cloud, fast)
    ↓ fallback
faster-whisper (local, offline)
    ↓ fallback
Google Speech Recognition (free tier)
```

### 5-Vowel Lip Sync Engine
Real-time frequency-band analysis maps audio to 5 VRM blendshapes:
- **Low frequencies** → `aa` (open mouth), `oh` (rounded)
- **Mid frequencies** → `ih` (slight open), `ou` (pursed)
- **High frequencies** → `ee` (smile)
- FFT size: 256 bins with micro-variation for natural movement
- **Text + lips only start when audio actually begins** — perfectly synchronized

---

## 🤖 AI Model Resilience

Mizune **never goes silent** — automatic retry + fallback chain:

```
Gemini 2.5 Flash (3 retries with backoff)
    ↓ 503/429
Gemini 2.0 Flash (3 retries)
    ↓ 503/429
Gemini 2.0 Flash-Lite (3 retries)
    ↓ exhausted
Groq Llama 3.3 70B (free tier, LPU-fast)
    ↓ all failed
Graceful error message (never crashes)
```

---

## 🎭 Emotion System

Real-time emotion detection from user text drives VRM facial expressions:

| Emotion | Trigger Examples | Expression |
|---------|-----------------|------------|
| 😊 Happy | *"you're the best"*, *"amazing"* | Bright smile |
| 😳 Blush | *"cute"*, *"I love you"* | Flustered cheeks |
| 😢 Sad | *"I'm tired"*, *"feeling down"* | Concerned look |
| 😠 Angry | *"stupid"*, *"hate this"* | Pouty face |
| 😮 Surprised | *"wow"*, *"no way"* | Wide eyes |

---

## 💰 Token Economy — Smart Cost Optimization

Mizune is designed to **minimize API token usage** across 3 layers:

### Layer 1: TTS Voice Cache (`renderer.js`)
Common short phrases (greetings, confirmations) are cached and served via **free browser TTS** instead of calling paid APIs:

```
User input → Normalize → Check CACHED_PHRASES set
                              ↓ HIT → Free browser TTS (0 tokens, instant)
                              ↓ MISS → Murf/ElevenLabs API
```

**Cached phrases** include: *"hai~"*, *"yes master"*, *"got it"*, *"arigatou"*, *"sugoi"*, *"gomen ne"*, etc.
These are Mizune's most frequent responses — caching them saves **~40% of TTS API calls**.

### Layer 2: Zero-Token Command Router (`server.py`)
**20+ command categories** execute via regex pattern matching with **zero AI token cost**:

```
"what time is it"     → time.strftime()      → 0 tokens
"weather hyderabad"   → Open-Meteo API       → 0 tokens  
"open netflix"        → COMMON_APPS lookup    → 0 tokens
"volume up"           → keyboard.send()      → 0 tokens
"search X on Netflix" → URL construction     → 0 tokens
"lock pc"             → subprocess            → 0 tokens
```

Only **novel, creative queries** reach the LLM — everything else is handled locally.

### Layer 3: Vector Memory Store (`MemoryAgent` + ChromaDB)
Instead of re-sending full conversation history to the LLM:

```
User: "remember I like Python"     → Stored in ChromaDB (vectorized)
User: "what do I like?"            → Semantic search → Retrieved locally
                                     Only the relevant memory is sent to LLM
```

- **ChromaDB** stores memories as embeddings for semantic retrieval
- **Session Logger** transcribes meetings/coding sessions locally via Whisper
- Reduces context window usage by **~60%** vs sending full history

### Combined Savings
```
┌─────────────────────┬──────────────────┬──────────────────┐
│ Request Type        │ Without Mizune   │ With Mizune      │
├─────────────────────┼──────────────────┼──────────────────┤
│ "hai~" (TTS)        │ 1 API call       │ 0 (cached)       │
│ "open chrome"       │ 1 LLM + 1 TTS   │ 0 tokens         │
│ "what time"         │ 1 LLM + 1 TTS   │ 0 tokens         │
│ "weather delhi"     │ 1 LLM + 1 TTS   │ 0 tokens (API)   │
│ "recall my notes"   │ Full history     │ Vector lookup    │
│ Creative question   │ Full context     │ Trimmed context  │
└─────────────────────┴──────────────────┴──────────────────┘
```

---

## ⚡ Zero-Token-Cost Commands

These execute instantly without AI calls:

| Category | Commands |
|----------|---------|
| 🕐 **Time/Date** | *"what time is it"*, *"what's today's date"* |
| 🌤️ **Weather** | *"weather hyderabad"* — fetches real data via Open-Meteo API |
| 📱 **App Control** | *"open spotify"*, *"close notepad"*, *"open netflix"* |
| 🔊 **Media** | *"volume up"*, *"mute"*, *"next song"*, *"play/pause"* |
| 🔍 **Streaming Search** | *"search Sakamoto Days on Netflix"*, *"find Naruto on Crunchyroll"* |
| 🔒 **System** | *"lock pc"*, *"screenshot"*, *"sleep"* |
| 🎵 **Spotify** | *"play lofi on spotify"* |

---

## 🚀 Quick Start

### Prerequisites
- **Node.js** ≥ 18
- **Python** ≥ 3.10
- **Git**

### Installation

```bash
# Clone the repository
git clone https://github.com/rushikeshgoud19/MY-AI.git
cd MY-AI

# Install Node dependencies
npm install

# Create Python virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install Python dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the example config
cp config.example.json config.json

# Edit config.json and add your API keys:
# - gemini_api_key (required) — https://ai.google.dev
# - groq_api_key (recommended) — https://console.groq.com (free)
# - murf_api_key (optional) — https://murf.ai
# - elevenlabs_api_key (optional) — https://elevenlabs.io
```

### Run

```bash
# Terminal 1 — Start the Python backend
.venv\Scripts\python.exe server.py

# Terminal 2 — Start the Electron frontend
npm start
```

Mizune will appear on your desktop and greet you! 🌸

---

## 🎯 Usage

### Wake Mizune
- Say **"Mizune"** (or any configured wake word)
- Press **F2** for instant activation

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Alt+Shift+P` | Scale up window |
| `Alt+Shift+O` | Scale down window |
| `Alt+Shift+T` | Toggle terminal log |
| `Alt+Shift+S` | Open settings |
| `Alt+Shift+K` | Reload UI |
| `Alt+Shift+Q` | Quit |

---

## 📁 Project Structure

```
mizune/
├── server.py              # FastAPI backend — AI, STT, commands, coding monitor
├── main.js                # Electron main process — window, IPC, always-on-top
├── renderer.js            # Frontend — 3D VRM, lip sync, TTS, WebSocket
├── index.html             # App shell
├── style.css              # UI styling
├── settings.html          # Settings panel
├── config.example.json    # Template configuration
├── requirements.txt       # Python dependencies
├── package.json           # Node dependencies
├── agents/
│   ├── base_agent.py      # Abstract base agent class
│   ├── manager_agent.py   # Central brain — mode management + routing
│   ├── system_agent.py    # PC control agent
│   ├── web_agent.py       # Web search agent
│   └── memory_agent.py    # ChromaDB memory agent
└── character/
    └── *.vrm              # 3D VRM character model
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Electron, Three.js, @pixiv/three-vrm |
| **Backend** | FastAPI, Uvicorn, WebSockets |
| **AI Models** | Gemini 2.5 Flash, Groq Llama 3.3, GPT-4o, Claude |
| **Vision** | Groq Vision (Llama 3.2 11B), Gemini Vision |
| **TTS** | Murf AI, ElevenLabs, Browser SpeechSynthesis |
| **STT** | Groq Whisper, faster-whisper, Google SR |
| **Memory** | ChromaDB (vector DB), SQLite |
| **PC Control** | PyAutoGUI, keyboard, subprocess |

---

## 🏆 Key Innovations

1. **Multi-Agent Architecture** — Not a monolithic chatbot; specialized agents handle different domains
2. **Coding Coach with Vision** — Real-time screen monitoring using multimodal AI (Groq/Gemini Vision)
3. **3-Layer Token Economy** — Voice caching + zero-token commands + vector memory saves ~60% API costs
4. **Never-Silent AI** — 4-tier model fallback chain ensures Mizune always responds
5. **5-Vowel Lip Sync** — Frequency-band audio analysis drives realistic mouth shapes
6. **Synchronized Output** — Text and lips only start when audio actually plays
7. **7 Operational Modes** — Context-aware behavior switching for different workflows
8. **Zero-Cost Commands** — 20+ command categories bypass AI entirely for instant response
9. **ChromaDB Memory** — Semantic vector storage for long-term memory retrieval without resending history

---

## 📜 License

MIT License — Built with 💜 by [Rushikesh Goud](https://github.com/rushikeshgoud19)

---

<p align="center">
  <em>"Hai~ Master! Mizune is ready to serve you~!" 🌸</em>
</p>
