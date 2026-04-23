# 🌸 Mizune — Autonomous AI Desktop Companion with Multi-Agent Brain

## Agentathon 2026 | Technical Project Documentation

---

## 1. Project Title

**Mizune — An Autonomous, Vision-Enabled AI Desktop Companion with Multi-Agent Architecture**

*A persistent 3D anime character that lives on your desktop, sees your screen, controls your PC, coaches your code, and speaks with emotion — powered by a modular multi-agent system with 7 operational modes.*

---

## 2. Team Composition

| Name | Role | Responsibilities |
|------|------|-----------------|
| Rushikesh Goud | Full-Stack AI Developer | Architecture design, backend (FastAPI + multi-agent system), frontend (Electron + 3D VRM), AI integration (Gemini, Groq), voice pipeline, coding coach vision system |

---

## 3. Problem Statement

### The Problem
Current desktop AI assistants (Siri, Cortana, Alexa) suffer from critical limitations:

1. **Blind** — They cannot see your screen. They have no awareness of what you're doing, making them useless for context-aware assistance like code review or workflow monitoring.

2. **Stateless** — They forget everything between sessions. Every interaction starts from zero — no persistent memory, no learning from past conversations.

3. **Single-Mode** — They treat every request the same way. Whether you're coding, studying, or relaxing, the assistant behaves identically with no contextual adaptation.

4. **Token-Wasteful** — Cloud AI assistants send every single request to expensive LLM APIs, even trivial commands like "what time is it" or "open Chrome" — burning tokens and adding latency.

5. **Disembodied** — They're invisible, lifeless text boxes or voice-only interfaces with no visual presence, no personality, and no emotional connection.

### The Opportunity
What if your AI assistant could **see your screen**, **remember your preferences**, **adapt its behavior** to your current task, **control your entire PC**, and do all of this while being a **charming 3D character** that lives permanently on your desktop?

---

## 4. Solution Overview

### What is Mizune?
Mizune is a **fully autonomous desktop AI companion** rendered as a 3D anime character (VRM model) that:

- **🎤 Listens** — Wake word detection ("Mizune") + F2 hotkey → Whisper/Groq STT
- **🧠 Thinks** — Multi-agent brain with a ManagerAgent that routes to specialized workers
- **👀 Sees** — Real-time screen capture → Groq Vision / Gemini Vision analysis
- **🗣️ Speaks** — Murf AI / ElevenLabs TTS with frequency-based 5-vowel lip synchronization
- **😊 Feels** — Dynamic facial expressions driven by real-time emotion detection
- **💻 Controls** — Full PC automation: launch/close apps, media control, volume, screenshots, web search
- **💾 Remembers** — ChromaDB vector database for persistent semantic memory across sessions

### Key Differentiators

| Feature | Siri/Cortana/Alexa | Mizune |
|---------|-------------------|--------|
| Screen Vision | ❌ | ✅ Groq/Gemini Vision every 30s |
| Persistent Memory | ❌ | ✅ ChromaDB vector store |
| Mode Switching | ❌ | ✅ 7 context-aware modes |
| Coding Coach | ❌ | ✅ Real-time bug detection |
| 3D Avatar | ❌ | ✅ VRM with lip sync + emotions |
| Token Economy | ❌ | ✅ 3-layer optimization |
| Never-Silent | ❌ | ✅ 4-tier model fallback |

---

## 5. Agent Architecture

### 5.1 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ELECTRON FRONTEND                          │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 3D VRM    │  │ 5-Vowel   │  │ Emotion  │  │ Terminal  │  │
│  │ Renderer  │  │ Lip Sync  │  │ System   │  │ Logger    │  │
│  │ (Three.js)│  │ (FFT 256) │  │ (5 types)│  │ (Debug)   │  │
│  └───────────┘  └───────────┘  └──────────┘  └───────────┘  │
│                        ▲ WebSocket ▼                          │
├──────────────────────────────────────────────────────────────┤
│                    FASTAPI BACKEND                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              MANAGER AGENT (Central Brain)            │    │
│  │  Intent Classification → Mode Routing → Agent Dispatch│    │
│  ├────────────┬────────────┬────────────┬───────────────┤    │
│  │ System     │ Web        │ Memory     │ Coding Coach  │    │
│  │ Agent      │ Agent      │ Agent      │ (Vision Loop) │    │
│  │ ──────     │ ──────     │ ──────     │ ────────────  │    │
│  │ App launch │ Web search │ ChromaDB   │ Screen capture│    │
│  │ PC control │ Scraping   │ Notes      │ Groq Vision   │    │
│  │ Env setup  │ Summarize  │ Recall     │ Bug detection │    │
│  └────────────┴────────────┴────────────┴───────────────┘    │
│                                                              │
│  ┌────────────┬────────────┬────────────┬───────────────┐    │
│  │ Gemini     │ Groq       │ Murf AI    │ Whisper STT   │    │
│  │ 2.5 Flash  │ Llama 4    │ TTS Voice  │ + Google SR   │    │
│  │ (Primary)  │ (Fallback) │ (Primary)  │ (Fallback)    │    │
│  └────────────┴────────────┴────────────┴───────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Agent Descriptions

#### ManagerAgent (Central Brain)
The **ManagerAgent** acts as the central orchestrator. It:
- Classifies user intent using regex-based pattern matching
- Manages a finite state machine for 7 operational modes
- Routes requests to the appropriate worker agent
- Falls through to the built-in command router for zero-token operations
- Broadcasts mode changes to the frontend via WebSocket

#### SystemAgent (PC Control)
Handles all operating system interactions:
- **App Management**: Launch and close 30+ apps via COMMON_APPS dictionary
- **Environment Builder**: Scaffold projects (React, Tailwind) and open VS Code
- **Code Analyst**: Read clipboard code and detect common bug patterns
- **OS Automation**: Lock PC, sleep, screenshots, volume control via pyautogui/keyboard

#### WebAgent (Web Operations)
Handles web-related tasks:
- **Search**: Google search queries with result parsing
- **Scraping**: Extract and summarize web page content using Playwright
- **URL Navigation**: Smart URL construction for streaming services (Netflix, Crunchyroll, Prime Video, Spotify)

#### MemoryAgent (Persistent Storage)
Implements long-term memory using ChromaDB:
- **Save**: Vectorizes user notes and stores as embeddings
- **Recall**: Semantic similarity search across all stored memories
- **Session Logger**: Background transcription of meetings/coding sessions using faster-whisper
- **Summarize**: Auto-generate session summaries saved to Desktop

### 5.3 Seven Operational Modes

| Mode | Purpose | Trigger Phrase |
|------|---------|---------------|
| 💬 **Conversation** | Normal AI chat | Default mode |
| ✍️ **Writing** | Speech-to-text dictation | "writing mode" |
| 🎯 **Focus** | Pomodoro timer + distraction blocking | "focus mode" |
| 🎵 **Entertainment** | Media control, recommendations | "entertainment mode" |
| 🔍 **Research** | Web search + summarization | "research mode" |
| ⚙️ **System** | Full PC control | "system mode" |
| 💻 **Coding Coach** | Screen monitoring + code review | "coding mode" |

### 5.4 Coding Coach — The Highlight Feature

When "coding mode" is activated:

1. **Screen Capture**: `pyautogui.screenshot()` captures the screen silently every 30 seconds
2. **Vision Analysis**: Screenshot sent to **Groq Vision (Llama 4 Scout)** with a coaching prompt
3. **Smart Feedback**: AI responds with one of:
   - 🐛 Bug detection: *"Ara~ Master, your for loop has an off-by-one error on line 5!"*
   - ✅ Praise: *"Sugoi! That two-pointer approach is perfect, Master~!"*
   - 🤫 Skip: Stays silent when nothing meaningful to say (no spam)
4. **Hint Mode**: User can say "I'm stuck" for a nudge without spoilers
5. **Pause/Resume**: Voice-controlled monitoring control

---

## 6. Token Economy — 3-Layer Cost Optimization

### Layer 1: TTS Voice Cache (Frontend)
Common short phrases ("hai~", "yes master", "arigatou") are matched against a `CACHED_PHRASES` set and served via **free browser TTS** instead of calling Murf/ElevenLabs APIs. Saves ~40% of TTS API calls.

### Layer 2: Zero-Token Command Router (Backend)
20+ command categories (time, weather, app control, media, streaming search, system commands) are handled via **regex pattern matching + local APIs** with zero AI token cost. The AI is only called for novel, creative queries.

### Layer 3: Vector Memory Store (ChromaDB)
Instead of re-sending full conversation history, the MemoryAgent stores memories as vector embeddings and retrieves only semantically relevant context, reducing context window usage by ~60%.

### Cost Comparison

| Request Type | Traditional Approach | Mizune's Approach |
|-------------|---------------------|-------------------|
| "What time is it?" | 1 LLM call + 1 TTS call | 0 tokens (regex + local) |
| "Open Netflix" | 1 LLM call + 1 TTS call | 0 tokens (COMMON_APPS lookup) |
| "Weather Hyderabad" | 1 LLM call + 1 TTS call | 0 tokens (Open-Meteo API) |
| "Yes Master!" (TTS) | 1 TTS API call | 0 cost (browser TTS cache) |
| "Recall my notes" | Full history context | Vector similarity search |

---

## 7. AI Model Resilience — Never-Silent Architecture

### Text Generation Fallback Chain
```
Gemini 2.5 Flash (3 retries with exponential backoff)
    ↓ 503/429
Gemini 2.0 Flash (3 retries)
    ↓ 503/429  
Gemini 2.0 Flash-Lite (3 retries)
    ↓ exhausted
Groq Llama 3.3 70B Versatile (free tier, LPU inference)
    ↓ all failed
Graceful error message (never crashes)
```

### Vision Analysis Fallback Chain
```
Groq Llama 4 Scout 17B (free, multimodal)
    ↓ failed
Gemini 2.0 Flash Vision
    ↓ 503/429
Gemini 2.5 Flash Vision
    ↓ all failed
Silent skip (no spam)
```

### Voice Pipeline Fallback Chain
```
ElevenLabs Turbo v2.5 (ultra-low latency)
    ↓ failed
Murf AI (Japanese-accented, high quality)
    ↓ failed
Browser SpeechSynthesis (offline, zero cost)
```

---

## 8. Technical Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Electron, Three.js, @pixiv/three-vrm | Desktop window, 3D avatar rendering |
| **Backend** | FastAPI, Uvicorn, WebSockets | Real-time server + IPC |
| **Primary AI** | Google Gemini 2.5 Flash | Text generation |
| **Fallback AI** | Groq Llama 3.3 70B | Free-tier backup for text |
| **Vision AI** | Groq Llama 4 Scout 17B | Screen capture analysis |
| **TTS** | Murf AI, ElevenLabs, Browser TTS | Voice synthesis |
| **STT** | faster-whisper, Google Speech Recognition | Voice input |
| **Lip Sync** | Web Audio API (FFT 256) | 5-vowel mouth shapes from audio frequencies |
| **Memory** | ChromaDB | Persistent vector storage |
| **PC Control** | PyAutoGUI, keyboard, subprocess | App automation, hotkeys |
| **Weather** | Open-Meteo API (free, no key) | Real-time weather data |

---

## 9. Repository & Links

| Resource | Link |
|----------|------|
| **GitHub** | https://github.com/rushikeshgoud19/MY-AI |
| **Demo Video** | *(Add YouTube/Loom link here)* |

---

## 10. Future Roadmap

1. **Local LLM Support** — Ollama integration for fully offline operation
2. **Multi-Monitor Support** — Track specific windows/apps
3. **Proactive Suggestions** — Mizune initiates conversation based on context
4. **Plugin System** — Third-party mode/agent development
5. **Mobile Companion** — React Native app for remote control

---

*Built with 💜 for Agentathon 2026*
