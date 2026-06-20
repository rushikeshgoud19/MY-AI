# ✨ Mizune OS — Your Autonomous AI Companion

Mizune is an advanced, autonomous operating system and digital companion that lives right on your desktop. She doesn't just chat—she can take over the mouse, keyboard, and terminal to execute complex workflows, run background scripts, and manage your digital life completely autonomously. 

Built to be a fully independent digital workforce, Mizune acts as your loyal secretary, researcher, and coding coach, ready to assist you 24/7.

## 🌟 What Mizune Can Do

### 1. **Autonomous Web Research**
Mizune features a **Headless Web Agent** that can silently browse the internet in the background. If you ask her to research the top startups, find a recipe, or summarize a news article, she will spin up a hidden browser, scrape the data, compile the results, and deliver the final answer right to your dashboard—all while you continue your work uninterrupted.

### 2. **WhatsApp Super-Secretary**
Mizune natively integrates with your WhatsApp! She runs a lightweight, invisible background bridge to act as your personal assistant.
- She can read your incoming messages and instantly notify you out loud if there's an emergency.
- You can text her from your phone when you are away from your PC to ask her questions, command her to run scripts, or start web research remotely.
- She learns your relationships and remembers conversations, distinguishing between VIPs, family, and unknown contacts.

### 3. **Seamless PC Automation**
Mizune has true root-level execution capabilities. She can:
- **Launch and Close Apps:** Tell her to open Notepad, close Spotify, or start your favorite game.
- **Run Python Scripts:** She can write, sandbox, and execute raw Python scripts to automate tasks, move files, or process data on your PC.
- **System Monitoring:** She can check your CPU, RAM, battery, and disk space to keep you updated on your PC's health.

### 4. **Smart Task Scheduling**
Never forget a task again. You can ask Mizune to schedule one-time reminders (e.g., "Remind me to drink water in 30 minutes") or recurring daily routines (e.g., "Give me a news briefing every morning at 8 AM"). She handles time management autonomously in the background.

### 5. **Flawless Memory & Evolving Personality**
Mizune possesses a ChromaDB-backed semantic long-term memory. She continuously learns about your preferences, remembers facts you tell her, and understands your workflow over time. She can recall context from weeks ago instantly, making her feel truly alive.

### 6. **Coding Coach & Screen Vision**
When she's not automating your job, she can watch you work! With Vision Mode enabled, she silently analyzes your screen, catches coding bugs, validates your logic, and provides dynamic feedback out loud to keep you focused and productive.

---

## ⚙️ The Technology Behind Her

Mizune bypasses standard AI limitations by utilizing a custom multi-agent architecture and a Zero-Latency Intent Brain:
- **Lightning Fast:** Uses a combination of edge-TTS and background queues to respond rapidly and fluidly.
- **Auto-Healing:** Built-in safeguards automatically recover from API limits, corrupted databases, and expired integration tokens without user intervention.
- **Token Efficient:** Smart caching and background summarization allow her to handle massive tasks without blowing up API usage.

## 🚀 Quick Start

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

Edit `config.json` and add your API keys (like OpenRouter, Gemini, or Groq).

### Run the System

```bash
# Terminal 1 — Start the Python Brain
.venv\Scripts\python.exe main.py

# Terminal 2 — Start the React Dashboard
npm run dev
```

---
*Engineered by [Rushikesh Goud](https://github.com/rushikeshgoud19)*
