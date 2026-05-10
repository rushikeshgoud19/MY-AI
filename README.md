# Mizune OS — Autonomous Desktop Agent

Mizune is an autonomous operating system that lives on your desktop. It doesn't just chat—it takes over the mouse, keyboard, and terminal to execute complex workflows completely autonomously.

## The Architecture

I built Mizune to be a fully independent digital workforce. It bypasses standard LLM limitations by splitting workloads across a localized brain and a multi-agent execution pipeline.

### Zero-Latency Intent Routing
Forget typing "mode switch" or using wake words for specific tasks. Mizune uses a custom-built, 3-tier heuristic intent classifier that processes natural language in <1ms with zero API cost.
- Tested on 860+ edge cases with 100% accuracy.
- Recognizes Hinglish, typos, slang, and deeply buried intents.
- Instantly routes requests silently to the correct backend agent without breaking conversation flow.

### Privileged Execution Engine
The system is designed for unconstrained automation. Standard AI limitations and content filters have been bypassed to enable true root-level execution.
- **High-Complexity Orchestration:** Automatically detects massive, multi-app prompts and scales execution limits dynamically.
- **Unrestricted Processing:** Default API safety filters are explicitly disabled to ensure uninterrupted processing of raw data and scripts.
- **Raw System Access:** The execution engine writes code directly to the local file system and executes background PowerShell scripts to build entire projects from scratch, rather than simulating human input.

## The Multi-Agent Hivemind

The system operates using a `ManagerAgent` that acts as the routing brain, delegating tasks to specialized, high-performance workers.

- **ManagerAgent:** 100% accurate intent routing, extreme complexity detection.
- **VisionAgent:** Captures the screen, diffs frames to save tokens, and maps UI elements to exact [x, y] coordinates for interaction.
- **TaskPlanner:** Breaks high-level goals into 50+ atomic steps. Generates terminal commands and file structures dynamically.
- **ActionExecutor:** The hands. Executes the plan by clicking, typing, writing files to disk, and running scripts.
- **MemoryAgent:** ChromaDB-backed semantic memory. Remembers project context without blowing up the token window.

## Coding Coach Mode

When she's not automating your job, she watches you work.
1. Silently captures your screen every 30 seconds.
2. Analyzes code using Groq Vision.
3. Speaks dynamic feedback (catches bugs, validates logic) and forcefully blocks distracting apps to keep you focused.

## The 7 Operational Modes

Mizune adapts to workflow requirements dynamically using 7 distinct execution modes:
- **Conversation:** Default interaction state.
- **Writing:** Continuous speech-to-text dictation.
- **Focus:** Applies Pomodoro limits, blocks distracting URLs, provides motivational oversight.
- **Entertainment:** Automates media playback and recommendations.
- **Research:** Autonomous web search, scraping, and content summarization.
- **System:** Root-level PC control, project setup, and file management.
- **Coding Coach:** Vision-based real-time IDE monitoring and bug catching.

## The V-Tuber Pipeline

Rendered as a 3D VRM character directly on your desktop.
- **5-Vowel Lip Sync Engine:** Real-time frequency-band analysis maps audio to VRM blendshapes (`aa`, `ee`, `ih`, `oh`, `ou`).
- **Synchronized Audio:** Text and lips only move when the audio actually plays.
- **Dynamic Emotion Engine:** Real-time text sentiment analysis maps user input directly to the VRM's facial expressions (Happy, Angry, Sad, Blush, Surprised).
- **Redundant TTS Pipeline:** Primary execution via Murf AI (Premium), with fallback to ElevenLabs (Turbo), and finally Browser SpeechSynthesis for zero-latency offline processing.
- **Multi-Layer STT:** Groq Whisper for cloud-speed transcription, backed by faster-whisper for offline local processing.

## Token Economy

Built to run heavy enterprise tasks without burning API bills.
1. **Vision Frame Diffing:** Hashes screenshots and compares them. If the screen hasn't changed, uses cached coordinates. (Saves ~80% on Vision tokens).
2. **TTS Phrase Caching:** Common responses are cached locally. (Saves ~40% on TTS APIs).
3. **Zero-Token Router:** Basic commands (weather, time, app launching) run purely on Python subprocesses using 0 tokens.

## Quick Start

### Prerequisites
- Node.js ≥ 18
- Python ≥ 3.10
- Git

### Installation

```bash
git clone https://github.com/rushikeshgoud19/MY-AI.git
cd MY-AI

npm install

python -m venv .venv
.venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Configuration

Edit `config.json` and add your API keys:
- `gemini_api_key` (Required for Planner & Vision)
- `groq_api_key` (Recommended for STT and Vision fallback)

### Run the System

```bash
# Terminal 1 — Start the Python Brain
.venv\Scripts\python.exe server.py

# Terminal 2 — Start the 3D Desktop Interface
npm start
```

## License

MIT License — Engineered by [Rushikesh Goud](https://github.com/rushikeshgoud19)
