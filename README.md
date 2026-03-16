# Lumina — Floating 3D AI Voice Assistant

A desktop application featuring a floating, transparent 3D anime character with voice-controlled desktop automation.

## Architecture

| Layer | Tech | Role |
|-------|------|------|
| **Backend** | Python + FastAPI | Voice recognition, desktop automation, Gemini AI |
| **Frontend** | Electron + Three.js + VRM | 3D character rendering, TTS, UI |
| **Communication** | WebSocket (`ws://localhost:8000/ws`) | Real-time bidirectional messaging |

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `PyAudio` may require additional system setup on Windows.  
> If `pip install PyAudio` fails, try: `pip install pipwin && pipwin install pyaudio`

### 2. Install Node Dependencies

```bash
npm install --legacy-peer-deps
```

### 3. Place Your VRM Model

Ensure your `.vrm` model is at:
```
character/5816025470716354497.vrm
```

## Running the Application

You need **two terminals** running simultaneously:

### Terminal 1: Python Backend

```bash
python server.py
```

> ⚠️ The `keyboard` library requires **Administrator/elevated** privileges on Windows to capture global hotkeys.

### Terminal 2: Electron Frontend

```bash
npm start
```

## Usage

| Action | Trigger |
|--------|---------|
| Talk to Lumina | Press **F2** or click the **Talk** button |
| Say "Hello" | Lumina replies: *"Hello senpai, need help?"* |
| Say "Play [song] on Spotify" | Opens Spotify and searches the song |
| Say "Search [query]" | Opens Google search in your browser |
| Any other question | Gemini AI responds as Lumina |

## Murf AI Integration

The TTS function in `renderer.js` is modular and documented. Search for `MURF AI INTEGRATION POINT` to find the exact injection point for the Murf AI REST API.
