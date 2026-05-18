# Design Document: Mizune AI Desktop Application Completion

## Overview

Mizune AI is a personal AI companion desktop application featuring an animated VRM chibi avatar with voice interaction, emotion-based animations, and productivity tool integrations. This design document covers the technical architecture and implementation strategy for completing Phases 2-6 of the application.

**Current Foundation (Phase 1 - Complete):**
- Tauri 2.0 desktop shell with frameless window
- Three.js + @pixiv/three-vrm for VRM avatar rendering
- Python FastAPI backend with WebSocket communication
- Basic chibi animations and idle state
- Existing agent architecture (ManagerAgent, SystemAgent, WebAgent, etc.)

**Target Architecture:**
A complete cross-platform desktop application with:
- Rich avatar animations with emotion-based expressions and lip-sync
- Voice interaction (TTS + wake word detection + speech recognition)
- OAuth 2.0 framework for third-party integrations
- Native desktop features (system tray, global hotkeys, auto-start)
- Professional packaging and auto-update system

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri Desktop Shell                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Frontend (Renderer Process)               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │  index.html  │  │ renderer.js  │  │  style.css  │ │  │
│  │  │  (UI Layer)  │  │ (Three.js +  │  │  (Styling)  │ │  │
│  │  │              │  │  VRM Avatar) │  │             │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  │         │                  │                  │        │  │
│  │         └──────────────────┴──────────────────┘        │  │
│  │                          │                              │  │
│  │                   WebSocket (ws://)                     │  │
│  └──────────────────────────┼──────────────────────────────┘  │
│                             │                                 │
│  ┌──────────────────────────┼──────────────────────────────┐  │
│  │              Tauri Core (main.rs)                       │  │
│  │  • System Tray Management                               │  │
│  │  • Window Lifecycle                                     │  │
│  │  • Global Hotkeys (via plugin)                          │  │
│  │  • Native Notifications                                 │  │
│  │  • Backend Process Management                           │  │
│  └──────────────────────────┼──────────────────────────────┘  │
└─────────────────────────────┼────────────────────────────────┘
                              │
                    Child Process (Python)
                              │
┌─────────────────────────────┼────────────────────────────────┐
│              Python Backend (server.py)                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  FastAPI Server                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │  WebSocket   │  │  Voice       │  │  Integration│ │  │
│  │  │  Handler     │  │  System      │  │  Framework  │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Agent Architecture                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │  Manager     │  │  System      │  │  Web        │ │  │
│  │  │  Agent       │  │  Agent       │  │  Agent      │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │  Memory      │  │  Vision      │  │  Task       │ │  │
│  │  │  Agent       │  │  Agent       │  │  Planner    │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Core Services                         │  │
│  │  • LLM Service (Gemini/OpenAI/Claude/Groq)            │  │
│  │  • Emotion Detection                                   │  │
│  │  • TTS (ElevenLabs/Edge TTS)                          │  │
│  │  • STT (Google/Faster-Whisper)                        │  │
│  │  • OAuth 2.0 Manager                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```


### Communication Flow

**Frontend → Backend:**
1. User types message in chat input
2. Frontend sends JSON via WebSocket: `{"type": "chat", "text": "..."}`
3. Backend processes with LLM and agents
4. Backend detects emotion from response text
5. Backend generates TTS audio
6. Backend sends response: `{"type": "speak", "text": "...", "emotion": "happy", "audio": "base64..."}`

**Backend → Frontend:**
1. Backend sends emotion updates: `{"type": "emotion", "emotion": "thinking"}`
2. Backend sends audio data: `{"type": "audio", "data": "base64..."}`
3. Backend sends status updates: `{"type": "status", "text": "Listening..."}`
4. Frontend updates avatar expression and plays audio with lip-sync

**Voice Flow:**
1. Wake word detected in backend (continuous listening)
2. Backend sends: `{"type": "listening", "active": true}`
3. Frontend shows visual indicator (pulsing status dot)
4. Backend records 6 seconds of audio
5. Backend transcribes with STT
6. Backend processes command → LLM → TTS
7. Backend sends response with audio
8. Frontend plays audio with lip-sync

## Components and Interfaces

### Frontend Components (renderer.js)

#### 1. Avatar System

**Responsibilities:**
- Load and render VRM model using Three.js
- Manage animation state machine
- Apply blend shape morphs for emotions
- Handle lip-sync with audio analysis
- Coordinate idle animations

**Key Classes/Functions:**
```javascript
// VRM Loading
function loadVRM(vrmPath: string): void
function initScene(): void

// Animation State Machine
class AnimationController {
  currentState: 'idle' | 'speaking' | 'listening' | 'thinking'
  transitionTo(newState: string, duration: number): void
  update(deltaTime: number): void
}

// Emotion System
function setEmotion(emotion: string, duration: number): void
function emotionToBlendShapes(emotion: string): BlendShapeMap
function updateEmotionBlends(deltaTime: number): void

// Lip Sync
function initAudioAnalyzer(audioElement: HTMLAudioElement): void
function updateLipSync(deltaTime: number): void
function analyzeAudioFrequency(): { low, mid, high, volume }
```


**Blend Shape Mapping:**
```javascript
const EMOTION_BLEND_SHAPES = {
  neutral: { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0.2 },
  happy: { happy: 1.0, sad: 0, angry: 0, surprised: 0, relaxed: 0 },
  blush: { happy: 0.6, sad: 0, angry: 0, surprised: 0, relaxed: 0, blush: 1.0 },
  smile: { happy: 0.7, sad: 0, angry: 0, surprised: 0, relaxed: 0.3 },
  sad: { happy: 0, sad: 0.8, angry: 0, surprised: 0, relaxed: 0 },
  angry: { happy: 0, sad: 0.2, angry: 0.5, surprised: 0, relaxed: 0 },
  surprised: { happy: 0, sad: 0, angry: 0, surprised: 1.0, relaxed: 0 },
  thinking: { happy: 0.15, sad: 0, angry: 0, surprised: 0, relaxed: 0.5 },
  sleepy: { happy: 0, sad: 0.15, angry: 0, surprised: 0, relaxed: 0.8 },
  excited: { happy: 1.0, sad: 0, angry: 0, surprised: 0.3, relaxed: 0 },
  shy: { happy: 0.4, sad: 0, angry: 0, surprised: 0, relaxed: 0, blush: 1.0 },
  pout: { happy: 0, sad: 0.25, angry: 0.2, surprised: 0, relaxed: 0 }
};
```

**Animation State Machine:**
```
┌─────────┐     speak event      ┌──────────┐
│  Idle   │ ──────────────────> │ Speaking │
│         │ <────────────────── │          │
└─────────┘   audio complete     └──────────┘
     │                                 │
     │ wake word                       │
     │ detected                        │
     ▼                                 ▼
┌─────────┐                      ┌──────────┐
│Listening│                      │ Thinking │
│         │ ──────────────────> │          │
└─────────┘   processing         └──────────┘
```

#### 2. WebSocket Client

**Responsibilities:**
- Maintain persistent connection to backend
- Handle reconnection with exponential backoff
- Parse and route incoming messages
- Send user input and events

**Interface:**
```javascript
class WebSocketClient {
  ws: WebSocket | null
  reconnectAttempts: number
  maxReconnectDelay: number
  
  connect(url: string): void
  disconnect(): void
  send(message: object): void
  onMessage(handler: (data: any) => void): void
  onError(handler: (error: Error) => void): void
  reconnect(): void
}

// Message Types
interface WSMessage {
  type: 'speak' | 'emotion' | 'audio' | 'status' | 'listening' | 'error'
  text?: string
  emotion?: string
  audio?: string  // base64 encoded
  data?: any
}
```

#### 3. Audio Playback System

**Responsibilities:**
- Decode base64 audio from backend
- Play audio through Web Audio API
- Provide real-time frequency analysis for lip-sync
- Manage audio queue for sequential responses

**Interface:**
```javascript
class AudioPlayer {
  audioContext: AudioContext
  analyser: AnalyserNode
  audioQueue: AudioBuffer[]
  isPlaying: boolean
  
  playAudio(base64Data: string): Promise<void>
  getFrequencyData(): Uint8Array
  stop(): void
  clearQueue(): void
}
```


### Backend Components (Python)

#### 1. Voice System (core/voice.py - NEW)

**Responsibilities:**
- Text-to-speech generation (ElevenLabs or Edge TTS)
- Wake word detection (continuous listening)
- Speech-to-text transcription
- Audio encoding for WebSocket transmission

**Interface:**
```python
class VoiceSystem:
    def __init__(self, config: dict):
        self.config = config
        self.tts_provider = self._init_tts_provider()
        self.recognizer = sr.Recognizer()
        self.wake_word_listener = None
        
    async def generate_speech(self, text: str, emotion: str = "neutral") -> bytes:
        """Generate TTS audio with emotion-based voice settings."""
        
    def start_wake_word_detection(self, callback: Callable):
        """Start continuous wake word listening in background thread."""
        
    async def transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Google STT or Faster-Whisper."""
        
    def _init_tts_provider(self) -> TTSProvider:
        """Initialize TTS provider based on config."""
```

**TTS Provider Interface:**
```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice_id: str, 
                        rate: int, pitch: int, style: str) -> bytes:
        """Synthesize speech from text."""

class ElevenLabsTTS(TTSProvider):
    async def synthesize(self, text: str, voice_id: str, 
                        rate: int, pitch: int, style: str) -> bytes:
        # Call ElevenLabs API
        
class EdgeTTS(TTSProvider):
    async def synthesize(self, text: str, voice_id: str, 
                        rate: int, pitch: int, style: str) -> bytes:
        # Use edge-tts library
```

**Wake Word Detection:**
```python
class WakeWordDetector:
    def __init__(self, wake_words: List[str], config: dict):
        self.wake_words = wake_words
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = config.get("wake_energy_threshold", 180)
        self.recognizer.dynamic_energy_threshold = config.get("wake_dynamic_energy", True)
        self.is_listening = False
        
    def listen_continuous(self, callback: Callable[[str], None]):
        """Listen for wake words in background thread."""
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=4.5)
                    text = self.recognizer.recognize_google(audio, language="en-IN")
                    if any(wake in text.lower() for wake in self.wake_words):
                        callback(text)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logging.error(f"Wake word detection error: {e}")
```


#### 2. Integration Framework (core/integrations.py - NEW)

**Responsibilities:**
- OAuth 2.0 authentication with PKCE
- Token storage in OS keychain
- Automatic token refresh
- API client management for each service

**OAuth 2.0 Manager:**
```python
class OAuth2Manager:
    def __init__(self):
        self.keyring_service = "MizuneAI"
        self.providers = {
            "google": GoogleOAuthProvider(),
            "github": GitHubOAuthProvider(),
            "spotify": SpotifyOAuthProvider(),
            "notion": NotionOAuthProvider()
        }
        
    async def authenticate(self, provider: str, scopes: List[str]) -> OAuthToken:
        """Initiate OAuth 2.0 flow with PKCE."""
        # 1. Generate code_verifier and code_challenge
        # 2. Open browser to authorization URL
        # 3. Start local callback server
        # 4. Exchange authorization code for tokens
        # 5. Store tokens in keychain
        
    async def get_token(self, provider: str) -> Optional[OAuthToken]:
        """Retrieve token from keychain."""
        
    async def refresh_token(self, provider: str) -> OAuthToken:
        """Refresh expired access token."""
        
    def store_token(self, provider: str, token: OAuthToken):
        """Store token securely in OS keychain."""
        import keyring
        keyring.set_password(self.keyring_service, f"{provider}_access", token.access_token)
        keyring.set_password(self.keyring_service, f"{provider}_refresh", token.refresh_token)
```

**OAuth Provider Interface:**
```python
class OAuthProvider(ABC):
    @property
    @abstractmethod
    def authorization_url(self) -> str:
        pass
        
    @property
    @abstractmethod
    def token_url(self) -> str:
        pass
        
    @abstractmethod
    def get_authorization_params(self, code_challenge: str, scopes: List[str]) -> dict:
        pass
        
    @abstractmethod
    async def exchange_code(self, code: str, code_verifier: str) -> OAuthToken:
        pass
```

**API Client Architecture:**
```python
class IntegrationClient(ABC):
    def __init__(self, oauth_manager: OAuth2Manager, provider: str):
        self.oauth_manager = oauth_manager
        self.provider = provider
        
    async def _get_headers(self) -> dict:
        """Get authorization headers with fresh token."""
        token = await self.oauth_manager.get_token(self.provider)
        if token.is_expired():
            token = await self.oauth_manager.refresh_token(self.provider)
        return {"Authorization": f"Bearer {token.access_token}"}

class GmailClient(IntegrationClient):
    async def get_unread_emails(self, max_results: int = 10) -> List[Email]:
        headers = await self._get_headers()
        # Call Gmail API
        
    async def send_email(self, to: str, subject: str, body: str):
        headers = await self._get_headers()
        # Call Gmail API

class CalendarClient(IntegrationClient):
    async def get_events(self, start_date: datetime, end_date: datetime) -> List[Event]:
        headers = await self._get_headers()
        # Call Calendar API
        
    async def create_event(self, title: str, start: datetime, duration: timedelta):
        headers = await self._get_headers()
        # Call Calendar API
```


#### 3. Enhanced WebSocket Handler (core/ws_handler.py - EXTEND)

**New Message Types:**
```python
class WSMessageType(Enum):
    CHAT = "chat"
    SPEAK = "speak"
    EMOTION = "emotion"
    AUDIO = "audio"
    STATUS = "status"
    LISTENING = "listening"
    ERROR = "error"
    WAKE_WORD_DETECTED = "wake_word_detected"
    SPEECH_COMPLETE = "speech_complete"

async def handle_message(websocket: WebSocket, message: dict):
    msg_type = message.get("type")
    
    if msg_type == WSMessageType.CHAT.value:
        await handle_chat_message(websocket, message)
    elif msg_type == WSMessageType.SPEECH_COMPLETE.value:
        # Frontend notifies backend that TTS playback finished
        await handle_speech_complete(websocket)
```

**Enhanced Broadcast Methods:**
```python
async def broadcast_emotion(emotion: str, duration: float = 5.0):
    await ws_handler.broadcast({
        "type": "emotion",
        "emotion": emotion,
        "duration": duration
    })

async def broadcast_audio(audio_data: bytes, text: str, emotion: str):
    import base64
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
    await ws_handler.broadcast({
        "type": "audio",
        "data": audio_b64,
        "text": text,
        "emotion": emotion
    })

async def broadcast_listening_state(active: bool):
    await ws_handler.broadcast({
        "type": "listening",
        "active": active
    })
```

### Tauri Components (Rust)

#### 1. System Tray (main.rs - EXTEND)

**Current Implementation:**
```rust
// Already implemented in main.rs
TrayIconBuilder::with_id("main-tray")
    .menu(&menu)
    .tooltip("Mizune AI - Click to show/hide")
    .on_menu_event(|app, event| { /* ... */ })
    .on_tray_icon_event(|tray, event| { /* ... */ })
    .build(app)?;
```

**Enhancements Needed:**
- Add "Status: Online/Offline" menu item that updates dynamically
- Add "Voice: Enabled/Disabled" toggle
- Add "Always on Top" toggle
- Update tooltip with backend status

#### 2. Global Hotkeys (NEW - via tauri-plugin-global-shortcut)

**Implementation:**
```rust
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

fn register_hotkeys(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // F2 to toggle window visibility
    let shortcut_f2 = Shortcut::new(Some(Modifiers::empty()), Code::F2)?;
    app.global_shortcut().register(shortcut_f2, move |app, _event| {
        toggle_window(app);
    })?;
    
    // Ctrl+Shift+M to activate voice input
    let shortcut_voice = Shortcut::new(
        Some(Modifiers::CONTROL | Modifiers::SHIFT), 
        Code::KeyM
    )?;
    app.global_shortcut().register(shortcut_voice, move |app, _event| {
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("activate-voice-input", ());
        }
    })?;
    
    Ok(())
}
```


#### 3. Backend Process Management (main.rs - EXTEND)

**Python Backend Lifecycle:**
```rust
use std::process::{Command, Child};
use std::sync::{Arc, Mutex};

struct BackendProcess {
    child: Option<Child>,
    port: u16,
}

impl BackendProcess {
    fn start(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        // Determine Python executable path
        let python_exe = if cfg!(windows) {
            ".venv\\Scripts\\python.exe"
        } else {
            ".venv/bin/python"
        };
        
        // Start server.py as child process
        let child = Command::new(python_exe)
            .arg("server.py")
            .spawn()?;
            
        self.child = Some(child);
        log::info!("Backend server started on port {}", self.port);
        Ok(())
    }
    
    fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            log::info!("Backend server stopped");
        }
    }
    
    fn is_running(&mut self) -> bool {
        if let Some(child) = &mut self.child {
            match child.try_wait() {
                Ok(Some(_)) => false,  // Process exited
                Ok(None) => true,      // Still running
                Err(_) => false,
            }
        } else {
            false
        }
    }
}

// In setup function:
fn setup(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    let backend = Arc::new(Mutex::new(BackendProcess {
        child: None,
        port: 8765,
    }));
    
    // Start backend
    backend.lock().unwrap().start()?;
    
    // Store backend handle in app state
    app.manage(backend.clone());
    
    // Monitor backend health
    let backend_clone = backend.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_secs(5));
            let mut backend = backend_clone.lock().unwrap();
            if !backend.is_running() {
                log::warn!("Backend crashed, restarting...");
                let _ = backend.start();
            }
        }
    });
    
    Ok(())
}
```

#### 4. Window Management (main.rs - EXTEND)

**Always-on-Top:**
```rust
#[tauri::command]
fn set_always_on_top(window: tauri::Window, enabled: bool) -> Result<(), String> {
    window.set_always_on_top(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn get_always_on_top(window: tauri::Window) -> Result<bool, String> {
    window.is_always_on_top()
        .map_err(|e| e.to_string())
}
```

**Multi-Monitor Support:**
```rust
use tauri::PhysicalPosition;

#[tauri::command]
fn save_window_position(window: tauri::Window) -> Result<(), String> {
    let position = window.outer_position()
        .map_err(|e| e.to_string())?;
    
    // Save to config.json
    let config_path = "config.json";
    // ... save position
    
    Ok(())
}

#[tauri::command]
fn restore_window_position(window: tauri::Window) -> Result<(), String> {
    // Load from config.json
    let config_path = "config.json";
    // ... load position
    
    let position = PhysicalPosition::new(x, y);
    window.set_position(position)
        .map_err(|e| e.to_string())
}
```


#### 5. Auto-Start Registration (NEW)

**Cross-Platform Auto-Start:**
```rust
use tauri_plugin_autostart::AutoLaunchManager;

#[tauri::command]
fn enable_auto_start(app: tauri::AppHandle) -> Result<(), String> {
    let auto_launch = AutoLaunchManager::new(
        "Mizune AI",
        &app.path().resource_dir()
            .map_err(|e| e.to_string())?
            .join("mizune.exe")
            .to_string_lossy()
    );
    
    auto_launch.enable()
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn disable_auto_start(app: tauri::AppHandle) -> Result<(), String> {
    let auto_launch = AutoLaunchManager::new(
        "Mizune AI",
        &app.path().resource_dir()
            .map_err(|e| e.to_string())?
            .join("mizune.exe")
            .to_string_lossy()
    );
    
    auto_launch.disable()
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn is_auto_start_enabled(app: tauri::AppHandle) -> Result<bool, String> {
    let auto_launch = AutoLaunchManager::new(
        "Mizune AI",
        &app.path().resource_dir()
            .map_err(|e| e.to_string())?
            .join("mizune.exe")
            .to_string_lossy()
    );
    
    auto_launch.is_enabled()
        .map_err(|e| e.to_string())
}
```

## Data Models

### Configuration (config.json)

**Extended Schema:**
```json
{
  "ai_model": "gemini",
  "gemini_api_key": "...",
  "openai_api_key": "...",
  "anthropic_api_key": "...",
  "groq_api_key": "...",
  
  "voice_id": "ja-JP-NanamiNeural",
  "edge_tts_voice": "ja-JP-NanamiNeural",
  "voice_style": "Cheerful",
  "voice_rate": -2,
  "voice_pitch": 6,
  
  "wake_words": ["mizune", "misune", "mizuna", "mizu", "missy"],
  "wake_language": "en-IN",
  "wake_energy_threshold": 180,
  "wake_dynamic_energy": true,
  "wake_phrase_time_limit": 4.5,
  "wake_timeout": 6.0,
  
  "mic_device_name": "Realtek(R) Audio",
  "mic_device_index": null,
  
  "character_name": "Mizune",
  "character_file": "character/5816025470716354497.vrm",
  "personality": "...",
  
  "memory_size": 30,
  "always_on_top": true,
  "window_scale": 1.0,
  
  "integrations": {
    "gmail": {
      "enabled": false,
      "scopes": ["gmail.readonly", "gmail.send"]
    },
    "calendar": {
      "enabled": false,
      "scopes": ["calendar.readonly", "calendar.events"]
    },
    "notion": {
      "enabled": false
    },
    "github": {
      "enabled": false,
      "scopes": ["repo", "read:user"]
    },
    "spotify": {
      "enabled": false,
      "scopes": ["user-read-playback-state", "user-modify-playback-state"]
    }
  },
  
  "system_settings": {
    "wake_key": "f2",
    "voice_hotkey": "ctrl+shift+m",
    "record_seconds": 6,
    "wake_cooldown": 3.0,
    "auto_start": false
  }
}
```


### OAuth Token Model

```python
@dataclass
class OAuthToken:
    access_token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = "Bearer"
    scope: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at - timedelta(minutes=5)
    
    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "token_type": self.token_type,
            "scope": self.scope
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OAuthToken':
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", [])
        )
```

### WebSocket Message Models

```python
@dataclass
class ChatMessage:
    type: str = "chat"
    text: str = ""

@dataclass
class SpeakMessage:
    type: str = "speak"
    text: str = ""
    emotion: str = "neutral"
    audio: Optional[str] = None  # base64 encoded

@dataclass
class EmotionMessage:
    type: str = "emotion"
    emotion: str = "neutral"
    duration: float = 5.0

@dataclass
class StatusMessage:
    type: str = "status"
    text: str = ""
    backend_online: bool = True

@dataclass
class ListeningMessage:
    type: str = "listening"
    active: bool = False
```

## Phase-by-Phase Design

### Phase 2: Avatar Enhancements

**Goal:** Implement rich avatar animations with emotion-based expressions.

**Animation System Architecture:**

```javascript
class AnimationStateMachine {
  constructor(vrm) {
    this.vrm = vrm;
    this.states = {
      idle: new IdleState(),
      speaking: new SpeakingState(),
      listening: new ListeningState(),
      thinking: new ThinkingState()
    };
    this.currentState = this.states.idle;
    this.transitionProgress = 0;
    this.transitionDuration = 0.3;
  }
  
  transitionTo(stateName, duration = 0.3) {
    if (this.currentState.name === stateName) return;
    
    this.previousState = this.currentState;
    this.currentState = this.states[stateName];
    this.transitionProgress = 0;
    this.transitionDuration = duration;
  }
  
  update(deltaTime) {
    // Blend between previous and current state during transition
    if (this.transitionProgress < this.transitionDuration) {
      this.transitionProgress += deltaTime;
      const t = Math.min(this.transitionProgress / this.transitionDuration, 1.0);
      this.blendStates(this.previousState, this.currentState, t);
    } else {
      this.currentState.update(deltaTime, this.vrm);
    }
  }
  
  blendStates(stateA, stateB, t) {
    // Interpolate bone rotations and blend shapes
    const humanoid = this.vrm.humanoid;
    // ... blend logic
  }
}
```


**Idle Animation State:**
```javascript
class IdleState {
  name = 'idle';
  
  update(deltaTime, vrm) {
    const time = performance.now() / 1000;
    const humanoid = vrm.humanoid;
    
    // Subtle breathing (chest movement)
    const breathCycle = Math.sin(time * 0.8) * 0.015;
    if (humanoid.getRawBoneNode('spine')) {
      humanoid.getRawBoneNode('spine').position.y += breathCycle;
    }
    
    // Head tilt (curious look)
    const headTilt = Math.sin(time * 0.3) * 0.08;
    if (humanoid.getRawBoneNode('head')) {
      humanoid.getRawBoneNode('head').rotation.z = headTilt;
    }
    
    // Ear wiggle (if model has ear bones)
    const earWiggle = Math.sin(time * 2.5) * 0.12;
    if (humanoid.getRawBoneNode('leftEar')) {
      humanoid.getRawBoneNode('leftEar').rotation.z = earWiggle;
    }
    if (humanoid.getRawBoneNode('rightEar')) {
      humanoid.getRawBoneNode('rightEar').rotation.z = -earWiggle;
    }
    
    // Tail swish (if model has tail bone)
    const tailSwish = Math.sin(time * 1.2) * 0.25;
    if (humanoid.getRawBoneNode('tail')) {
      humanoid.getRawBoneNode('tail').rotation.y = tailSwish;
    }
  }
}
```

**Bounce Animation (on user message):**
```javascript
function playBounceAnimation() {
  const duration = 0.15;
  const startY = vrm.scene.position.y;
  const bounceHeight = 0.05;
  
  gsap.to(vrm.scene.position, {
    y: startY + bounceHeight,
    duration: duration / 2,
    ease: "power2.out",
    onComplete: () => {
      gsap.to(vrm.scene.position, {
        y: startY,
        duration: duration / 2,
        ease: "bounce.out"
      });
    }
  });
}
```

**Emotion Transition Logic:**
```javascript
function updateEmotionBlends(deltaTime) {
  const blendSpeed = deltaTime * 3.0; // Smooth over ~0.33s
  
  for (const [key, targetValue] of Object.entries(targetBlends)) {
    currentBlends[key] = lerp(
      currentBlends[key], 
      targetValue, 
      Math.min(blendSpeed, 1.0)
    );
    
    // Apply to VRM expression manager
    vrm.expressionManager.setValue(key, currentBlends[key]);
  }
}
```

### Phase 3: Voice & Audio

**Goal:** Implement TTS, wake word detection, and lip-sync.

**TTS Integration (Backend):**

```python
# core/voice.py
class EdgeTTSProvider(TTSProvider):
    async def synthesize(self, text: str, voice_id: str, 
                        rate: int, pitch: int, style: str) -> bytes:
        import edge_tts
        
        # Build SSML with rate and pitch
        rate_str = f"{rate:+d}%"
        pitch_str = f"{pitch:+d}Hz"
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate_str,
            pitch=pitch_str
        )
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return audio_data

class ElevenLabsTTSProvider(TTSProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
    
    async def synthesize(self, text: str, voice_id: str, 
                        rate: int, pitch: int, style: str) -> bytes:
        import aiohttp
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # ElevenLabs uses stability/similarity_boost instead of rate/pitch
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    raise Exception(f"ElevenLabs API error: {resp.status}")
```


**Wake Word Detection (Backend):**

```python
# In server.py startup
voice_system = VoiceSystem(CFG)

def on_wake_word_detected(text: str):
    log_info(f"[WAKE] Wake word detected: {text}")
    asyncio.create_task(ws_handler.broadcast({
        "type": "listening",
        "active": True
    }))
    
    # Record user speech for 6 seconds
    audio_data, sample_rate = record_audio(seconds=6.0)
    
    # Transcribe
    transcription = asyncio.run(voice_system.transcribe_audio(audio_data))
    
    if transcription:
        log_info(f"[WAKE] Transcribed: {transcription}")
        # Process command
        response = process_command(transcription)
        
        # Generate TTS
        emotion = detect_emotion(response)
        audio = asyncio.run(voice_system.generate_speech(response, emotion))
        
        # Send to frontend
        asyncio.create_task(broadcast_audio(audio, response, emotion))
    else:
        asyncio.create_task(ws_handler.broadcast({
            "type": "speak",
            "text": "I didn't catch that, Master~",
            "emotion": "neutral"
        }))
    
    asyncio.create_task(ws_handler.broadcast({
        "type": "listening",
        "active": False
    }))

# Start wake word detection in background
voice_system.start_wake_word_detection(on_wake_word_detected)
```

**Lip-Sync with Web Audio API (Frontend):**

```javascript
class LipSyncAnalyzer {
  constructor(audioContext) {
    this.audioContext = audioContext;
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
  }
  
  connectAudio(audioElement) {
    const source = this.audioContext.createMediaElementSource(audioElement);
    source.connect(this.analyser);
    this.analyser.connect(this.audioContext.destination);
  }
  
  getFrequencyBands() {
    this.analyser.getByteFrequencyData(this.dataArray);
    
    // Split into frequency bands for different vowel shapes
    const len = this.dataArray.length;
    let lowSum = 0, midSum = 0, highSum = 0;
    
    // Low frequencies (0-300Hz) → "ah" sound
    for (let i = 1; i < 4; i++) lowSum += this.dataArray[i];
    
    // Mid frequencies (300-2000Hz) → "oh", "ih" sounds
    for (let i = 4; i < 10; i++) midSum += this.dataArray[i];
    
    // High frequencies (2000-8000Hz) → "ee" sound
    for (let i = 10; i < 20; i++) highSum += this.dataArray[i];
    
    return {
      low: lowSum / 3 / 255,
      mid: midSum / 6 / 255,
      high: highSum / 10 / 255,
      volume: (lowSum + midSum + highSum) / 19 / 255
    };
  }
}

function updateLipSync(deltaTime) {
  if (!audioAnalyzer || !isSpeaking) {
    // Close mouth smoothly
    smoothMouthA = lerp(smoothMouthA, 0, deltaTime * 14);
    smoothMouthOh = lerp(smoothMouthOh, 0, deltaTime * 14);
    smoothMouthIh = lerp(smoothMouthIh, 0, deltaTime * 14);
    smoothMouthEe = lerp(smoothMouthEe, 0, deltaTime * 14);
    
    vrm.expressionManager.setValue('aa', smoothMouthA);
    vrm.expressionManager.setValue('oh', smoothMouthOh);
    vrm.expressionManager.setValue('ih', smoothMouthIh);
    vrm.expressionManager.setValue('ee', smoothMouthEe);
    return;
  }
  
  const bands = audioAnalyzer.getFrequencyBands();
  
  // Map frequency bands to mouth shapes
  const targetA = Math.min(bands.low * 1.1, 0.45);
  const targetOh = Math.min(bands.low * 0.5 - bands.high * 0.2, 0.35);
  const targetIh = Math.min(bands.mid * 1.0 - bands.low * 0.3, 0.30);
  const targetEe = Math.min(bands.high * 1.2 - bands.low * 0.3, 0.35);
  
  // Smooth interpolation
  const lerpSpeed = deltaTime * 14.0;
  smoothMouthA = lerp(smoothMouthA, targetA, lerpSpeed);
  smoothMouthOh = lerp(smoothMouthOh, targetOh, lerpSpeed * 0.8);
  smoothMouthIh = lerp(smoothMouthIh, targetIh, lerpSpeed * 0.9);
  smoothMouthEe = lerp(smoothMouthEe, targetEe, lerpSpeed * 0.7);
  
  // Apply to VRM
  vrm.expressionManager.setValue('aa', smoothMouthA);
  vrm.expressionManager.setValue('oh', smoothMouthOh);
  vrm.expressionManager.setValue('ih', smoothMouthIh);
  vrm.expressionManager.setValue('ee', smoothMouthEe);
}
```


### Phase 4: Integrations

**Goal:** Implement OAuth 2.0 framework and API integrations.

**OAuth 2.0 PKCE Flow:**

```python
# core/integrations/oauth.py
import secrets
import hashlib
import base64
from urllib.parse import urlencode
import webbrowser
from aiohttp import web

class OAuth2Manager:
    def __init__(self):
        self.callback_port = 8080
        self.callback_server = None
        self.auth_code = None
        
    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate code_verifier and code_challenge for PKCE."""
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    async def authenticate(self, provider: str, scopes: List[str]) -> OAuthToken:
        """Initiate OAuth 2.0 flow with PKCE."""
        oauth_provider = self.providers[provider]
        code_verifier, code_challenge = self.generate_pkce_pair()
        
        # Build authorization URL
        params = oauth_provider.get_authorization_params(code_challenge, scopes)
        auth_url = f"{oauth_provider.authorization_url}?{urlencode(params)}"
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Start local callback server
        self.auth_code = None
        await self._start_callback_server()
        
        # Wait for callback (with timeout)
        timeout = 120  # 2 minutes
        start_time = time.time()
        while self.auth_code is None and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
        
        if self.auth_code is None:
            raise TimeoutError("OAuth authentication timed out")
        
        # Exchange code for tokens
        token = await oauth_provider.exchange_code(self.auth_code, code_verifier)
        
        # Store in keychain
        self.store_token(provider, token)
        
        return token
    
    async def _start_callback_server(self):
        """Start local HTTP server to receive OAuth callback."""
        async def handle_callback(request):
            self.auth_code = request.query.get('code')
            return web.Response(text="Authentication successful! You can close this window.")
        
        app = web.Application()
        app.router.add_get('/callback', handle_callback)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.callback_port)
        await site.start()
        
        self.callback_server = runner
```

**Google OAuth Provider:**

```python
class GoogleOAuthProvider(OAuthProvider):
    @property
    def authorization_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"
    
    @property
    def token_url(self) -> str:
        return "https://oauth2.googleapis.com/token"
    
    def get_authorization_params(self, code_challenge: str, scopes: List[str]) -> dict:
        return {
            "client_id": "YOUR_CLIENT_ID",
            "redirect_uri": "http://localhost:8080/callback",
            "response_type": "code",
            "scope": " ".join(scopes),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent"
        }
    
    async def exchange_code(self, code: str, code_verifier: str) -> OAuthToken:
        import aiohttp
        
        data = {
            "client_id": "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8080/callback"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.token_url, data=data) as resp:
                result = await resp.json()
                
                return OAuthToken(
                    access_token=result["access_token"],
                    refresh_token=result.get("refresh_token", ""),
                    expires_at=datetime.now() + timedelta(seconds=result["expires_in"]),
                    scope=result.get("scope", "").split()
                )
```


**Gmail Integration:**

```python
# core/integrations/gmail.py
class GmailClient(IntegrationClient):
    BASE_URL = "https://gmail.googleapis.com/gmail/v1"
    
    async def get_unread_emails(self, max_results: int = 10) -> List[dict]:
        """Fetch unread emails."""
        headers = await self._get_headers()
        
        async with aiohttp.ClientSession() as session:
            # Get message IDs
            url = f"{self.BASE_URL}/users/me/messages"
            params = {"q": "is:unread", "maxResults": max_results}
            
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                message_ids = [msg["id"] for msg in data.get("messages", [])]
            
            # Fetch full messages
            emails = []
            for msg_id in message_ids:
                url = f"{self.BASE_URL}/users/me/messages/{msg_id}"
                async with session.get(url, headers=headers) as resp:
                    msg_data = await resp.json()
                    emails.append(self._parse_email(msg_data))
            
            return emails
    
    def _parse_email(self, msg_data: dict) -> dict:
        """Parse Gmail API message format."""
        headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
        
        return {
            "id": msg_data["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": msg_data.get("snippet", "")
        }
    
    async def send_email(self, to: str, subject: str, body: str):
        """Send an email."""
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        headers = await self._get_headers()
        url = f"{self.BASE_URL}/users/me/messages/send"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"raw": raw}) as resp:
                return await resp.json()
```

**Agent Integration Pattern:**

```python
# agents/gmail_agent.py
class GmailAgent(BaseAgent):
    def __init__(self, config: dict, oauth_manager: OAuth2Manager):
        super().__init__(config)
        self.gmail_client = GmailClient(oauth_manager, "google")
    
    async def handle_command(self, command: str) -> str:
        """Process Gmail-related commands."""
        command_lower = command.lower()
        
        if "read" in command_lower and "email" in command_lower:
            emails = await self.gmail_client.get_unread_emails(max_results=5)
            if not emails:
                return "You have no unread emails, Master!"
            
            response = f"You have {len(emails)} unread emails:\n"
            for email in emails:
                response += f"• From {email['from']}: {email['subject']}\n"
            return response
        
        elif "send email" in command_lower:
            # Parse email details from command using LLM
            details = self._parse_email_command(command)
            await self.gmail_client.send_email(
                to=details["to"],
                subject=details["subject"],
                body=details["body"]
            )
            return f"Email sent to {details['to']}, Master!"
        
        return "I'm not sure what you want me to do with Gmail, Master."
```

### Phase 5: Desktop Features

**Goal:** Implement system tray, global hotkeys, and window management.

**System Tray with Dynamic Status:**

```rust
// main.rs
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use std::sync::{Arc, Mutex};

#[derive(Clone)]
struct AppState {
    backend_online: Arc<Mutex<bool>>,
    voice_enabled: Arc<Mutex<bool>>,
    always_on_top: Arc<Mutex<bool>>,
}

fn build_tray_menu(app: &AppHandle, state: &AppState) -> Result<Menu<Wry>, Box<dyn std::error::Error>> {
    let show_item = MenuItem::with_id(app, "show", "Show/Hide", true, None::<&str>)?;
    let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    
    let backend_status = if *state.backend_online.lock().unwrap() {
        "Status: Online"
    } else {
        "Status: Offline"
    };
    let status_item = MenuItem::with_id(app, "status", backend_status, false, None::<&str>)?;
    
    let voice_label = if *state.voice_enabled.lock().unwrap() {
        "Voice: Enabled ✓"
    } else {
        "Voice: Disabled"
    };
    let voice_item = MenuItem::with_id(app, "toggle_voice", voice_label, true, None::<&str>)?;
    
    let always_on_top_label = if *state.always_on_top.lock().unwrap() {
        "Always on Top ✓"
    } else {
        "Always on Top"
    };
    let always_on_top_item = MenuItem::with_id(app, "toggle_always_on_top", always_on_top_label, true, None::<&str>)?;
    
    let separator = PredefinedMenuItem::separator(app)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    
    Menu::with_items(app, &[
        &show_item,
        &settings_item,
        &separator,
        &status_item,
        &voice_item,
        &always_on_top_item,
        &separator,
        &quit_item
    ])
}
```


**Desktop Notifications:**

```rust
use tauri_plugin_notification::NotificationExt;

#[tauri::command]
fn send_notification(app: AppHandle, title: String, body: String) -> Result<(), String> {
    app.notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|e| e.to_string())
}

// In Python backend:
async def send_desktop_notification(title: str, body: str):
    """Send notification via Tauri."""
    # This would be called via a Tauri command or WebSocket message
    await ws_handler.broadcast({
        "type": "notification",
        "title": title,
        "body": body
    })
```

**Window Position Persistence:**

```rust
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Serialize, Deserialize)]
struct WindowState {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
    always_on_top: bool,
}

fn save_window_state(window: &Window) -> Result<(), Box<dyn std::error::Error>> {
    let position = window.outer_position()?;
    let size = window.outer_size()?;
    let always_on_top = window.is_always_on_top()?;
    
    let state = WindowState {
        x: position.x,
        y: position.y,
        width: size.width,
        height: size.height,
        always_on_top,
    };
    
    let json = serde_json::to_string_pretty(&state)?;
    fs::write("window_state.json", json)?;
    
    Ok(())
}

fn restore_window_state(window: &Window) -> Result<(), Box<dyn std::error::Error>> {
    let json = fs::read_to_string("window_state.json")?;
    let state: WindowState = serde_json::from_str(&json)?;
    
    window.set_position(PhysicalPosition::new(state.x, state.y))?;
    window.set_size(PhysicalSize::new(state.width, state.height))?;
    window.set_always_on_top(state.always_on_top)?;
    
    Ok(())
}
```

### Phase 6: Packaging

**Goal:** Build installers and implement auto-update system.

**Tauri Configuration (tauri.conf.json):**

```json
{
  "build": {
    "beforeDevCommand": "",
    "beforeBuildCommand": "",
    "devPath": ".",
    "distDir": "."
  },
  "package": {
    "productName": "Mizune AI",
    "version": "1.0.0"
  },
  "tauri": {
    "bundle": {
      "active": true,
      "targets": ["nsis", "msi", "dmg", "appimage"],
      "identifier": "com.mizune.ai",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "resources": [
        "character/*.vrm",
        "config.example.json",
        ".venv/**/*",
        "server.py",
        "agents/**/*.py",
        "core/**/*.py"
      ],
      "externalBin": [
        ".venv/Scripts/python.exe"
      ],
      "windows": {
        "certificateThumbprint": null,
        "digestAlgorithm": "sha256",
        "timestampUrl": ""
      },
      "macOS": {
        "entitlements": null,
        "exceptionDomain": "",
        "frameworks": [],
        "providerShortName": null,
        "signingIdentity": null
      }
    },
    "updater": {
      "active": true,
      "endpoints": [
        "https://releases.mizune.ai/{{target}}/{{current_version}}"
      ],
      "dialog": true,
      "pubkey": "YOUR_PUBLIC_KEY_HERE"
    }
  }
}
```


**Python Backend Bundling:**

```bash
# Build script (build.sh / build.bat)

# 1. Create virtual environment with all dependencies
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Bundle Python backend with PyInstaller (optional - for single executable)
pyinstaller --onefile \
  --add-data "agents:agents" \
  --add-data "core:core" \
  --add-data "character:character" \
  --hidden-import=google.genai \
  --hidden-import=edge_tts \
  --hidden-import=faster_whisper \
  server.py

# 3. Build Tauri app
cd src-tauri
cargo tauri build --target x86_64-pc-windows-msvc  # Windows
# cargo tauri build --target x86_64-apple-darwin    # macOS Intel
# cargo tauri build --target aarch64-apple-darwin   # macOS Apple Silicon
# cargo tauri build --target x86_64-unknown-linux-gnu  # Linux
```

**Auto-Update Implementation:**

```rust
// main.rs
use tauri_plugin_updater::UpdaterExt;

async fn check_for_updates(app: AppHandle) {
    match app.updater().check().await {
        Ok(Some(update)) => {
            log::info!("Update available: {}", update.version);
            
            // Show notification
            let _ = app.notification()
                .builder()
                .title("Update Available")
                .body(format!("Version {} is available. Click to install.", update.version))
                .show();
            
            // Download and install
            match update.download_and_install().await {
                Ok(_) => {
                    log::info!("Update installed successfully");
                    // Prompt user to restart
                    let _ = app.notification()
                        .builder()
                        .title("Update Ready")
                        .body("Restart Mizune AI to apply the update.")
                        .show();
                }
                Err(e) => {
                    log::error!("Update installation failed: {}", e);
                }
            }
        }
        Ok(None) => {
            log::info!("No updates available");
        }
        Err(e) => {
            log::error!("Update check failed: {}", e);
        }
    }
}

// Check for updates on startup
fn setup(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle().clone();
    tauri::async_runtime::spawn(async move {
        check_for_updates(app_handle).await;
    });
    
    Ok(())
}
```

**Update Server (Simple Static Hosting):**

```
releases.mizune.ai/
├── windows/
│   ├── 1.0.0/
│   │   ├── Mizune-AI_1.0.0_x64_en-US.msi
│   │   └── Mizune-AI_1.0.0_x64_en-US.msi.sig
│   └── latest.json
├── darwin/
│   ├── 1.0.0/
│   │   ├── Mizune-AI_1.0.0_x64.dmg
│   │   └── Mizune-AI_1.0.0_x64.dmg.sig
│   └── latest.json
└── linux/
    ├── 1.0.0/
    │   ├── mizune-ai_1.0.0_amd64.AppImage
    │   └── mizune-ai_1.0.0_amd64.AppImage.sig
    └── latest.json
```

**latest.json format:**
```json
{
  "version": "1.0.0",
  "notes": "Initial release with voice interaction and integrations",
  "pub_date": "2024-01-15T12:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "...",
      "url": "https://releases.mizune.ai/windows/1.0.0/Mizune-AI_1.0.0_x64_en-US.msi"
    },
    "darwin-x86_64": {
      "signature": "...",
      "url": "https://releases.mizune.ai/darwin/1.0.0/Mizune-AI_1.0.0_x64.dmg"
    },
    "linux-x86_64": {
      "signature": "...",
      "url": "https://releases.mizune.ai/linux/1.0.0/mizune-ai_1.0.0_amd64.AppImage"
    }
  }
}
```


## Error Handling

### Frontend Error Handling

**WebSocket Reconnection Strategy:**
```javascript
class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000; // Start with 1 second
    this.maxReconnectDelay = 30000; // Max 30 seconds
  }
  
  connect() {
    try {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.onConnected();
      };
      
      this.ws.onclose = () => {
        console.log('[WS] Disconnected');
        this.scheduleReconnect();
      };
      
      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error);
        this.onError(error);
      };
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.onMessage(data);
        } catch (e) {
          console.error('[WS] Failed to parse message:', e);
        }
      };
    } catch (error) {
      console.error('[WS] Connection failed:', error);
      this.scheduleReconnect();
    }
  }
  
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnection attempts reached');
      this.onMaxReconnectAttemptsReached();
      return;
    }
    
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );
    
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }
}
```

**Audio Playback Error Handling:**
```javascript
async function playAudio(base64Data) {
  try {
    // Decode base64
    const audioData = atob(base64Data);
    const arrayBuffer = new ArrayBuffer(audioData.length);
    const view = new Uint8Array(arrayBuffer);
    for (let i = 0; i < audioData.length; i++) {
      view[i] = audioData.charCodeAt(i);
    }
    
    // Decode audio
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    
    // Play audio
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    source.start(0);
    
    isSpeaking = true;
    
    source.onended = () => {
      isSpeaking = false;
      ws.send(JSON.stringify({ type: 'speech_complete' }));
    };
    
  } catch (error) {
    console.error('[AUDIO] Playback failed:', error);
    isSpeaking = false;
    
    // Show error to user
    showNotification('Audio Error', 'Failed to play audio response');
  }
}
```

### Backend Error Handling

**Voice System Error Handling:**
```python
class VoiceSystem:
    async def generate_speech(self, text: str, emotion: str = "neutral") -> Optional[bytes]:
        """Generate TTS audio with fallback providers."""
        try:
            return await self.tts_provider.synthesize(
                text=text,
                voice_id=self.config.get("voice_id"),
                rate=self.config.get("voice_rate", 0),
                pitch=self.config.get("voice_pitch", 0),
                style=self.config.get("voice_style", "Cheerful")
            )
        except Exception as e:
            log_info(f"[TTS] Primary provider failed: {e}")
            
            # Fallback to Edge TTS if ElevenLabs fails
            if isinstance(self.tts_provider, ElevenLabsTTSProvider):
                try:
                    log_info("[TTS] Falling back to Edge TTS")
                    fallback = EdgeTTSProvider()
                    return await fallback.synthesize(
                        text=text,
                        voice_id="ja-JP-NanamiNeural",
                        rate=0, pitch=0, style="Cheerful"
                    )
                except Exception as e2:
                    log_info(f"[TTS] Fallback also failed: {e2}")
            
            return None
    
    async def transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio with fallback methods."""
        # Try Google Speech Recognition first
        try:
            recognizer = sr.Recognizer()
            audio = sr.AudioData(audio_data, sample_rate=16000, sample_width=2)
            return recognizer.recognize_google(audio, language=self.config.get("wake_language", "en-IN"))
        except sr.UnknownValueError:
            log_info("[STT] Google STT could not understand audio")
        except sr.RequestError as e:
            log_info(f"[STT] Google STT request failed: {e}")
        except Exception as e:
            log_info(f"[STT] Google STT error: {e}")
        
        # Fallback to Faster-Whisper if available
        if HAS_WHISPER and WHISPER_MODEL:
            try:
                log_info("[STT] Falling back to Faster-Whisper")
                segments, _ = WHISPER_MODEL.transcribe(audio_data, language="en")
                return " ".join([seg.text for seg in segments])
            except Exception as e:
                log_info(f"[STT] Faster-Whisper failed: {e}")
        
        return None
```


**OAuth Error Handling:**
```python
class OAuth2Manager:
    async def get_token(self, provider: str) -> Optional[OAuthToken]:
        """Retrieve token with automatic refresh."""
        try:
            # Load from keychain
            token = self._load_token_from_keychain(provider)
            
            if token is None:
                log_info(f"[OAUTH] No token found for {provider}")
                return None
            
            # Check if expired
            if token.is_expired():
                log_info(f"[OAUTH] Token expired for {provider}, refreshing...")
                try:
                    token = await self.refresh_token(provider)
                except Exception as e:
                    log_info(f"[OAUTH] Token refresh failed: {e}")
                    # Token refresh failed, need to re-authenticate
                    return None
            
            return token
            
        except Exception as e:
            log_info(f"[OAUTH] Error getting token for {provider}: {e}")
            return None
    
    async def refresh_token(self, provider: str) -> OAuthToken:
        """Refresh expired access token."""
        oauth_provider = self.providers[provider]
        token = self._load_token_from_keychain(provider)
        
        if not token or not token.refresh_token:
            raise ValueError(f"No refresh token available for {provider}")
        
        try:
            new_token = await oauth_provider.refresh_access_token(token.refresh_token)
            self.store_token(provider, new_token)
            return new_token
        except Exception as e:
            log_info(f"[OAUTH] Token refresh failed for {provider}: {e}")
            # Clear invalid token
            self._clear_token_from_keychain(provider)
            raise
```

**Integration Client Error Handling:**
```python
class IntegrationClient(ABC):
    async def _make_request(self, method: str, url: str, **kwargs) -> dict:
        """Make API request with error handling and retries."""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                headers = await self._get_headers()
                headers.update(kwargs.pop('headers', {}))
                
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, headers=headers, **kwargs) as resp:
                        if resp.status == 401:
                            # Unauthorized - token may be invalid
                            log_info(f"[API] 401 Unauthorized for {self.provider}")
                            # Try to refresh token
                            await self.oauth_manager.refresh_token(self.provider)
                            # Retry with new token
                            continue
                        
                        elif resp.status == 429:
                            # Rate limited
                            retry_after = int(resp.headers.get('Retry-After', retry_delay))
                            log_info(f"[API] Rate limited, retrying after {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        elif resp.status >= 500:
                            # Server error - retry with backoff
                            log_info(f"[API] Server error {resp.status}, retrying...")
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        
                        elif resp.status >= 400:
                            # Client error - don't retry
                            error_text = await resp.text()
                            raise Exception(f"API error {resp.status}: {error_text}")
                        
                        return await resp.json()
                        
            except aiohttp.ClientError as e:
                log_info(f"[API] Request failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * (attempt + 1))
        
        raise Exception(f"Max retries exceeded for {url}")
```

### Tauri Error Handling

**Backend Process Monitoring:**
```rust
fn monitor_backend_health(backend: Arc<Mutex<BackendProcess>>, app: AppHandle) {
    std::thread::spawn(move || {
        let mut consecutive_failures = 0;
        let max_failures = 3;
        
        loop {
            std::thread::sleep(std::time::Duration::from_secs(5));
            
            let mut backend = backend.lock().unwrap();
            
            if !backend.is_running() {
                consecutive_failures += 1;
                log::warn!("Backend not running (failure {} of {})", 
                          consecutive_failures, max_failures);
                
                if consecutive_failures >= max_failures {
                    log::error!("Backend failed {} times, giving up", max_failures);
                    
                    // Notify user
                    let _ = app.notification()
                        .builder()
                        .title("Backend Error")
                        .body("The backend server has crashed. Please restart the application.")
                        .show();
                    
                    break;
                }
                
                // Try to restart
                match backend.start() {
                    Ok(_) => {
                        log::info!("Backend restarted successfully");
                        consecutive_failures = 0;
                    }
                    Err(e) => {
                        log::error!("Failed to restart backend: {}", e);
                    }
                }
            } else {
                consecutive_failures = 0;
            }
        }
    });
}
```


## Testing Strategy

### Unit Testing

**Frontend Unit Tests (Jest + Testing Library):**
```javascript
// tests/emotion.test.js
describe('Emotion System', () => {
  test('emotionToBlendShapes returns correct blend values', () => {
    const result = emotionToBlendShapes('happy');
    expect(result.blends.happy).toBe(1.0);
    expect(result.blends.sad).toBe(0);
  });
  
  test('emotion transitions smoothly', () => {
    const blends = { happy: 0, sad: 0 };
    const target = { happy: 1.0, sad: 0 };
    
    updateBlends(blends, target, 0.1);
    
    expect(blends.happy).toBeGreaterThan(0);
    expect(blends.happy).toBeLessThan(1.0);
  });
});

// tests/websocket.test.js
describe('WebSocket Client', () => {
  test('reconnects with exponential backoff', () => {
    const client = new WebSocketClient('ws://localhost:8765');
    
    expect(client.getReconnectDelay(1)).toBe(1000);
    expect(client.getReconnectDelay(2)).toBe(2000);
    expect(client.getReconnectDelay(3)).toBe(4000);
    expect(client.getReconnectDelay(10)).toBe(30000); // Max delay
  });
});
```

**Backend Unit Tests (pytest):**
```python
# tests/test_voice.py
import pytest
from core.voice import VoiceSystem, EdgeTTSProvider

@pytest.mark.asyncio
async def test_edge_tts_synthesis():
    provider = EdgeTTSProvider()
    audio = await provider.synthesize(
        text="Hello Master",
        voice_id="ja-JP-NanamiNeural",
        rate=0, pitch=0, style="Cheerful"
    )
    assert audio is not None
    assert len(audio) > 0

# tests/test_oauth.py
def test_pkce_generation():
    from core.integrations.oauth import OAuth2Manager
    
    manager = OAuth2Manager()
    verifier, challenge = manager.generate_pkce_pair()
    
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge

# tests/test_emotion.py
from core.emotion import detect_emotion

def test_emotion_detection():
    assert detect_emotion("I love you!") == "shy"
    assert detect_emotion("You're so cute!") == "blush"
    assert detect_emotion("I'm so happy!") == "happy"
    assert detect_emotion("I'm sad") == "sad"
    assert detect_emotion("What?!") == "surprise"
```

### Integration Testing

**WebSocket Communication Test:**
```python
# tests/integration/test_websocket.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from server import app

@pytest.mark.asyncio
async def test_websocket_chat_flow():
    client = TestClient(app)
    
    with client.websocket_connect("/ws") as websocket:
        # Send chat message
        websocket.send_json({
            "type": "chat",
            "text": "Hello Mizune"
        })
        
        # Receive response
        response = websocket.receive_json()
        
        assert response["type"] == "speak"
        assert "text" in response
        assert "emotion" in response
```

**OAuth Flow Test:**
```python
# tests/integration/test_oauth.py
@pytest.mark.asyncio
async def test_oauth_flow():
    from core.integrations.oauth import OAuth2Manager
    
    manager = OAuth2Manager()
    
    # Mock OAuth provider
    # ... test authentication flow
```

### End-to-End Testing

**Voice Interaction Test:**
```python
# tests/e2e/test_voice_interaction.py
@pytest.mark.asyncio
async def test_wake_word_to_response():
    """Test complete voice interaction flow."""
    # 1. Simulate wake word detection
    # 2. Simulate audio recording
    # 3. Verify transcription
    # 4. Verify LLM response
    # 5. Verify TTS generation
    # 6. Verify WebSocket broadcast
```

**Avatar Animation Test:**
```javascript
// tests/e2e/avatar.test.js
describe('Avatar Animation E2E', () => {
  test('avatar responds to emotion changes', async () => {
    // Load VRM
    await loadVRM('character/test.vrm');
    
    // Set emotion
    setEmotion('happy', 5.0);
    
    // Wait for transition
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Verify blend shapes
    const em = vrm.expressionManager;
    expect(em.getValue('happy')).toBeGreaterThan(0.5);
  });
});
```

### Performance Testing

**Avatar Rendering Performance:**
```javascript
// tests/performance/rendering.test.js
describe('Rendering Performance', () => {
  test('maintains 60 FPS with animations', () => {
    const frameTimings = [];
    let lastTime = performance.now();
    
    for (let i = 0; i < 600; i++) { // 10 seconds at 60 FPS
      animate();
      const now = performance.now();
      frameTimings.push(now - lastTime);
      lastTime = now;
    }
    
    const avgFrameTime = frameTimings.reduce((a, b) => a + b) / frameTimings.length;
    const fps = 1000 / avgFrameTime;
    
    expect(fps).toBeGreaterThanOrEqual(55); // Allow 5 FPS margin
  });
});
```

**Memory Usage Test:**
```python
# tests/performance/test_memory.py
import psutil
import pytest

def test_backend_memory_usage():
    """Ensure backend uses less than 500MB RAM when idle."""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    assert memory_mb < 500, f"Memory usage too high: {memory_mb}MB"
```


## Security Considerations

### API Key Management

**Configuration Security:**
- API keys stored in `config.json` (user-managed file)
- File permissions set to user-only read/write (chmod 600 on Unix)
- Never commit `config.json` to version control (use `config.example.json` template)
- Validate API keys on startup and warn if missing

**Best Practices:**
```python
# core/config.py
def load_config() -> dict:
    config = _load_config_file()
    
    # Validate sensitive fields
    sensitive_keys = ["gemini_api_key", "openai_api_key", "anthropic_api_key"]
    for key in sensitive_keys:
        if config.get(key) and len(config[key]) < 10:
            logging.warning(f"[CONFIG] {key} looks invalid (too short)")
    
    return config
```

### OAuth Token Storage

**Keychain Integration:**
```python
# core/integrations/oauth.py
import keyring

class OAuth2Manager:
    def store_token(self, provider: str, token: OAuthToken):
        """Store token securely in OS keychain."""
        service_name = "MizuneAI"
        
        # Store access token
        keyring.set_password(
            service_name,
            f"{provider}_access_token",
            token.access_token
        )
        
        # Store refresh token
        keyring.set_password(
            service_name,
            f"{provider}_refresh_token",
            token.refresh_token
        )
        
        # Store expiry (not sensitive, can be in config)
        # ... store in config.json
    
    def _load_token_from_keychain(self, provider: str) -> Optional[OAuthToken]:
        """Load token from OS keychain."""
        service_name = "MizuneAI"
        
        try:
            access_token = keyring.get_password(
                service_name,
                f"{provider}_access_token"
            )
            refresh_token = keyring.get_password(
                service_name,
                f"{provider}_refresh_token"
            )
            
            if not access_token:
                return None
            
            # Load expiry from config
            # ...
            
            return OAuthToken(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
        except Exception as e:
            logging.error(f"[OAUTH] Failed to load token from keychain: {e}")
            return None
```

**Platform-Specific Keychain:**
- **Windows:** Windows Credential Manager
- **macOS:** Keychain Access
- **Linux:** Secret Service API (GNOME Keyring, KWallet)

### WebSocket Security

**Local-Only Communication:**
```python
# server.py
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",  # Bind to localhost only
        port=8765,
        log_level="info"
    )
```

**Message Validation:**
```python
async def handle_websocket_message(websocket: WebSocket, message: str):
    try:
        msg = json.loads(message)
        
        # Validate message structure
        if "type" not in msg:
            raise ValueError("Message missing 'type' field")
        
        msg_type = msg["type"]
        
        # Validate message type
        valid_types = ["chat", "speech_complete", "emotion_update"]
        if msg_type not in valid_types:
            raise ValueError(f"Invalid message type: {msg_type}")
        
        # Process message
        # ...
        
    except json.JSONDecodeError:
        logging.error("[WS] Invalid JSON received")
    except ValueError as e:
        logging.error(f"[WS] Invalid message: {e}")
    except Exception as e:
        logging.error(f"[WS] Error processing message: {e}")
```

### Input Sanitization

**User Input Validation:**
```python
def sanitize_user_input(text: str) -> str:
    """Sanitize user input before processing."""
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    
    # Limit length
    max_length = 1000
    if len(text) > max_length:
        text = text[:max_length]
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text

async def handle_chat_message(websocket: WebSocket, message: dict):
    text = message.get("text", "")
    text = sanitize_user_input(text)
    
    if not text:
        return
    
    # Process sanitized input
    # ...
```

### Code Signing

**Windows Code Signing:**
```bash
# Sign executable with certificate
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com Mizune-AI.exe
```

**macOS Code Signing:**
```bash
# Sign app bundle
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" Mizune-AI.app

# Notarize with Apple
xcrun notarytool submit Mizune-AI.dmg --apple-id your@email.com --password app-specific-password --team-id TEAMID
```


## Cross-Platform Compatibility

### Platform-Specific Considerations

**Windows:**
- Use `\` for file paths (handled by Rust `std::path`)
- Python executable: `.venv\Scripts\python.exe`
- System tray icon format: `.ico`
- Auto-start: Task Scheduler or Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Keychain: Windows Credential Manager

**macOS:**
- Use `/` for file paths
- Python executable: `.venv/bin/python`
- System tray icon format: `.icns`
- Auto-start: Login Items (`~/Library/LaunchAgents`)
- Keychain: macOS Keychain Access
- Code signing and notarization required for distribution

**Linux:**
- Use `/` for file paths
- Python executable: `.venv/bin/python`
- System tray icon format: `.png`
- Auto-start: `.desktop` file in `~/.config/autostart/`
- Keychain: Secret Service API (GNOME Keyring, KWallet)
- AppImage requires FUSE or AppImage runtime

### Path Handling

**Cross-Platform Path Resolution:**
```rust
// main.rs
use std::path::PathBuf;

fn get_python_executable() -> PathBuf {
    let mut path = std::env::current_dir().unwrap();
    path.push(".venv");
    
    #[cfg(target_os = "windows")]
    path.push("Scripts");
    
    #[cfg(not(target_os = "windows"))]
    path.push("bin");
    
    #[cfg(target_os = "windows")]
    path.push("python.exe");
    
    #[cfg(not(target_os = "windows"))]
    path.push("python");
    
    path
}
```

**Python Path Handling:**
```python
import os
import sys
from pathlib import Path

# Get platform-specific paths
def get_config_dir() -> Path:
    """Get platform-specific config directory."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "MizuneAI"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MizuneAI"
    else:  # Linux
        return Path.home() / ".config" / "mizune-ai"

def get_data_dir() -> Path:
    """Get platform-specific data directory."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "MizuneAI"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MizuneAI"
    else:  # Linux
        return Path.home() / ".local" / "share" / "mizune-ai"
```

### Audio Device Handling

**Cross-Platform Microphone Access:**
```python
# core/audio.py
import sounddevice as sd
import platform

def get_default_audio_device():
    """Get default audio input device for the platform."""
    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        
        if platform.system() == "Windows":
            # Windows: Look for Realtek or default
            for idx, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = dev['name'].lower()
                    if 'realtek' in name or 'microphone' in name:
                        return idx
        
        elif platform.system() == "Darwin":
            # macOS: Use default input
            return default_input
        
        else:  # Linux
            # Linux: Use PulseAudio default
            return default_input
            
    except Exception as e:
        logging.error(f"[AUDIO] Failed to get default device: {e}")
        return None
```

### Font Rendering

**Cross-Platform Font Support:**
```css
/* style.css */
body {
  font-family: 
    -apple-system,           /* macOS */
    BlinkMacSystemFont,      /* macOS */
    "Segoe UI",              /* Windows */
    Roboto,                  /* Android */
    "Helvetica Neue",        /* macOS fallback */
    Arial,                   /* Universal fallback */
    sans-serif;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Idle Animation Continuity

*For any* VRM model with the required bones (head, spine, ears, tail), when the avatar is in idle state, the animation system SHALL continuously update bone rotations within expected ranges (head tilt: ±0.08 rad, ear wiggle: ±0.12 rad, tail swish: ±0.25 rad) at each frame.

**Validates: Requirements 1.1**

### Property 2: Bounce Animation Timing

*For any* user message input, the bounce animation SHALL trigger, complete within 0.15s ±0.05s, and return the avatar's Y position to within 0.01 units of the original position.

**Validates: Requirements 1.2**

### Property 3: Animation Transition Blending

*For any* two distinct animation states, transitioning between them SHALL take 0.3s ±0.05s and blend shape values SHALL interpolate monotonically (no oscillation) from source to target values.

**Validates: Requirements 1.3**

### Property 4: Emotion State Persistence

*For any* emotion state, once set, the corresponding blend shape values SHALL remain stable (within ±0.05 tolerance) until a new emotion is explicitly triggered.

**Validates: Requirements 1.4**

### Property 5: Emotion Transition Timing

*For any* emotion change, the blend shape values SHALL reach at least 90% of their target values within 0.2s of the emotion being set.

**Validates: Requirements 2.1**

### Property 6: Emotion Timeout Reset

*For any* emotion state other than neutral, if no new emotion triggers occur for 5.0s ±0.5s, the blend shape values SHALL return to neutral emotion values (within ±0.1 tolerance).

**Validates: Requirements 2.4**

### Property 7: Audio Analysis Continuity

*For any* audio playback, the audio analyzer SHALL produce non-zero frequency data at approximately 60Hz (55-65 Hz) throughout the duration of the audio.

**Validates: Requirements 3.1**

### Property 8: Amplitude-to-Mouth Proportionality

*For any* audio amplitude value, the mouth blend shape SHALL be proportional: when amplitude > 0.1, mouth blend shape > 0; when amplitude ≤ 0.1, mouth blend shape SHALL approach 0 within 0.1s.

**Validates: Requirements 3.2, 3.3**

### Property 9: Mouth Closure After Audio

*For any* audio completion or silence period, the mouth blend shape SHALL reach 0.0 ±0.05 within 0.2s.

**Validates: Requirements 3.5**

### Property 10: TTS Text-to-Audio Conversion

*For any* non-empty text string (length > 0), the TTS provider SHALL return audio data with byte length > 0, or return null if generation fails (graceful failure).

**Validates: Requirements 4.1**

### Property 11: STT Audio-to-Text Conversion

*For any* valid audio input (sample rate 16kHz, duration > 0.5s), the STT system SHALL return either a non-empty transcription string or null (if audio is unclear), but SHALL NOT throw unhandled exceptions.

**Validates: Requirements 6.1**

### Property 12: Audio Decoding Validity

*For any* valid base64-encoded audio data, decoding SHALL produce an AudioBuffer with duration > 0 and sample rate > 0, or throw a specific decoding error (not a generic error).

**Validates: Requirements 7.1**

### Property 13: Audio Queue Sequential Playback

*For any* sequence of N audio clips (N ≥ 2), they SHALL play in the order they were queued, with no overlap (clip N+1 starts only after clip N completes), and all clips SHALL complete playback.

**Validates: Requirements 7.5**

### Property 14: PKCE Code Generation Validity

*For any* OAuth 2.0 PKCE flow, the generated code_verifier SHALL be at least 43 characters, and the code_challenge SHALL equal the base64url-encoded SHA256 hash of the code_verifier.

**Validates: Requirements 9.1**

### Property 15: Token Refresh on Expiry

*For any* expired OAuth token with a valid refresh_token, calling the token refresh method SHALL either return a new OAuthToken with a different access_token and future expires_at, or throw a specific authentication error.

**Validates: Requirements 9.3**

### Property 16: Boolean State Toggle Idempotence

*For any* boolean state (window visibility, always-on-top), toggling the state twice SHALL return it to the original value (toggle is its own inverse).

**Validates: Requirements 17.3, 20.3**

### Property 17: Always-On-Top Persistence

*For any* always-on-top setting value (true or false), after saving to config and restarting the application, the window's always-on-top state SHALL match the saved value.

**Validates: Requirements 20.5**

### Property 18: Window Position Persistence

*For any* window position (x, y, monitor_id), after saving to config and restarting the application, the window SHALL restore to within ±10 pixels of the saved position on the same monitor (or primary monitor if saved monitor is unavailable).

**Validates: Requirements 21.2**

### Property 19: Settings Persistence Round-Trip

*For any* valid settings change (AI model, voice settings, wake words, etc.), saving to config.json and then reloading SHALL produce settings values equal to the saved values (round-trip identity).

**Validates: Requirements 28.3**

### Property 20: Settings Validation Rejection

*For any* invalid settings input (negative numbers for positive-only fields, empty strings for required fields, invalid enum values), the validation SHALL reject the input and display an error message, and the config.json SHALL remain unchanged.

**Validates: Requirements 28.5**

### Property 21: WebSocket Message Format Validity

*For any* WebSocket message sent by the backend, it SHALL be valid JSON with a "type" field containing one of the supported message types (speak, emotion, audio, status, listening, error).

**Validates: Requirements 29.1**

### Property 22: WebSocket Reconnection Timing

*For any* WebSocket connection drop, reconnection attempts SHALL occur at intervals of 3s ±0.5s until connection is re-established or maximum attempts are reached.

**Validates: Requirements 29.3**

## Performance Optimization

### Frontend Optimization

**VRM Model Optimization:**
```javascript
// Optimize VRM rendering
function optimizeVRM(vrm) {
  // Reduce polygon count for chibi mode (already scaled to 0.55)
  vrm.scene.traverse((object) => {
    if (object.isMesh) {
      // Enable frustum culling
      object.frustumCulled = true;
      
      // Optimize materials
      if (object.material) {
        object.material.precision = 'mediump';
      }
    }
  });
  
  // Disable shadows for performance
  vrm.scene.traverse((object) => {
    object.castShadow = false;
    object.receiveShadow = false;
  });
}
```

**Animation Frame Rate Limiting:**
```javascript
// Limit to 30 FPS for better performance
let fpsInterval = 1000 / 30;
let lastFrameTime = performance.now();

function animate() {
  requestAnimationFrame(animate);
  
  const now = performance.now();
  const elapsed = now - lastFrameTime;
  
  if (elapsed < fpsInterval) return;
  
  lastFrameTime = now - (elapsed % fpsInterval);
  
  // Update and render
  const deltaTime = clock.getDelta();
  if (currentVrm) {
    currentVrm.update(deltaTime);
    updateAnimations(deltaTime);
  }
  renderer.render(scene, camera);
}
```

### Backend Optimization

**LLM Response Caching:**
```python
from functools import lru_cache
import hashlib

class LLMCache:
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
    
    def get_cache_key(self, text: str, history: List[dict]) -> str:
        """Generate cache key from input."""
        history_str = json.dumps(history[-5:])  # Last 5 turns
        combined = f"{text}:{history_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[str]:
        return self.cache.get(key)
    
    def set(self, key: str, value: str):
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = value

llm_cache = LLMCache()

def get_ai_response(text: str, history: List[dict]) -> str:
    cache_key = llm_cache.get_cache_key(text, history)
    cached = llm_cache.get(cache_key)
    
    if cached:
        log_info("[LLM] Using cached response")
        return cached
    
    response = _call_llm(text, history)
    llm_cache.set(cache_key, response)
    return response
```

**Audio Streaming:**
```python
# Stream TTS audio in chunks instead of waiting for complete generation
async def stream_tts_audio(text: str, voice_id: str):
    """Stream TTS audio in real-time."""
    import edge_tts
    
    communicate = edge_tts.Communicate(text=text, voice=voice_id)
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            # Send chunk immediately via WebSocket
            await broadcast_audio_chunk(chunk["data"])
```

## Testing Strategy

### Overview

The Mizune AI desktop application requires a comprehensive testing strategy that combines:
- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property-based tests**: Verify universal properties across all inputs (22 properties defined above)
- **Integration tests**: Verify external service interactions and cross-component communication
- **End-to-end tests**: Verify complete user workflows

### Property-Based Testing

**Framework Selection:**
- **Frontend (JavaScript)**: `fast-check` library for property-based testing
- **Backend (Python)**: `hypothesis` library for property-based testing

**Configuration:**
- Minimum 100 iterations per property test (due to randomization)
- Each property test MUST reference its design document property number
- Tag format: `Feature: mizune-desktop-completion, Property {number}: {property_text}`

**Example Property Test (Frontend):**
```javascript
// tests/properties/animation.test.js
import fc from 'fast-check';
import { setEmotion, getBlendShapeValues } from '../src/emotion';

describe('Property 4: Emotion State Persistence', () => {
  test('emotion blend shapes remain stable until changed', () => {
    // Feature: mizune-desktop-completion, Property 4: Emotion State Persistence
    fc.assert(
      fc.property(
        fc.constantFrom('happy', 'sad', 'angry', 'surprised', 'thinking', 'sleepy', 'excited'),
        fc.integer({ min: 10, max: 100 }), // number of frames to wait
        (emotion, frameCount) => {
          // Set emotion
          setEmotion(emotion, 5.0);
          
          // Wait for transition to complete
          for (let i = 0; i < 30; i++) {
            updateEmotionBlends(1/60); // 60 FPS
          }
          
          // Capture initial blend values
          const initialBlends = { ...getBlendShapeValues() };
          
          // Update for N frames without new emotion
          for (let i = 0; i < frameCount; i++) {
            updateEmotionBlends(1/60);
          }
          
          // Verify blend values remain stable (within tolerance)
          const currentBlends = getBlendShapeValues();
          for (const key in initialBlends) {
            const diff = Math.abs(currentBlends[key] - initialBlends[key]);
            if (diff > 0.05) {
              return false; // Blend shape changed too much
            }
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});
```

**Example Property Test (Backend):**
```python
# tests/properties/test_oauth.py
from hypothesis import given, strategies as st
from core.integrations.oauth import OAuth2Manager
import hashlib
import base64

class TestOAuthProperties:
    @given(st.binary(min_size=32, max_size=64))
    def test_property_14_pkce_code_generation_validity(self, random_bytes):
        """
        Feature: mizune-desktop-completion, Property 14: PKCE Code Generation Validity
        
        For any OAuth 2.0 PKCE flow, the generated code_verifier shall be at least 
        43 characters, and the code_challenge shall equal the base64url-encoded 
        SHA256 hash of the code_verifier.
        """
        manager = OAuth2Manager()
        code_verifier, code_challenge = manager.generate_pkce_pair()
        
        # Verify code_verifier length
        assert len(code_verifier) >= 43, f"code_verifier too short: {len(code_verifier)}"
        
        # Verify code_challenge is correct SHA256 hash
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        assert code_challenge == expected_challenge, \
            f"code_challenge mismatch: {code_challenge} != {expected_challenge}"
```

### Unit Testing

**Frontend Unit Tests (Jest + Testing Library):**
```javascript
// tests/unit/emotion.test.js
describe('Emotion System Unit Tests', () => {
  test('emotionToBlendShapes returns correct blend values for happy', () => {
    const result = emotionToBlendShapes('happy');
    expect(result.happy).toBe(1.0);
    expect(result.sad).toBe(0);
  });
  
  test('emotionToBlendShapes returns correct blend values for sad', () => {
    const result = emotionToBlendShapes('sad');
    expect(result.sad).toBe(0.8);
    expect(result.happy).toBe(0);
  });
  
  test('emotion transitions smoothly over time', () => {
    const blends = { happy: 0, sad: 0 };
    const target = { happy: 1.0, sad: 0 };
    
    updateBlends(blends, target, 0.1);
    
    expect(blends.happy).toBeGreaterThan(0);
    expect(blends.happy).toBeLessThan(1.0);
  });
});

// tests/unit/websocket.test.js
describe('WebSocket Client Unit Tests', () => {
  test('calculates exponential backoff correctly', () => {
    const client = new WebSocketClient('ws://localhost:8765');
    
    expect(client.getReconnectDelay(1)).toBe(1000);
    expect(client.getReconnectDelay(2)).toBe(2000);
    expect(client.getReconnectDelay(3)).toBe(4000);
    expect(client.getReconnectDelay(10)).toBe(30000); // Max delay
  });
  
  test('parses valid WebSocket messages', () => {
    const message = '{"type": "speak", "text": "Hello", "emotion": "happy"}';
    const parsed = parseWSMessage(message);
    
    expect(parsed.type).toBe('speak');
    expect(parsed.text).toBe('Hello');
    expect(parsed.emotion).toBe('happy');
  });
  
  test('handles invalid WebSocket messages gracefully', () => {
    const message = 'invalid json';
    expect(() => parseWSMessage(message)).toThrow();
  });
});
```

**Backend Unit Tests (pytest):**
```python
# tests/unit/test_voice.py
import pytest
from core.voice import VoiceSystem, EdgeTTSProvider

@pytest.mark.asyncio
async def test_edge_tts_synthesis_returns_audio():
    provider = EdgeTTSProvider()
    audio = await provider.synthesize(
        text="Hello Master",
        voice_id="ja-JP-NanamiNeural",
        rate=0, pitch=0, style="Cheerful"
    )
    assert audio is not None
    assert len(audio) > 0
    assert isinstance(audio, bytes)

@pytest.mark.asyncio
async def test_edge_tts_handles_empty_text():
    provider = EdgeTTSProvider()
    audio = await provider.synthesize(
        text="",
        voice_id="ja-JP-NanamiNeural",
        rate=0, pitch=0, style="Cheerful"
    )
    # Should return empty or minimal audio
    assert audio is not None

# tests/unit/test_emotion.py
from core.emotion import detect_emotion

def test_emotion_detection_happy():
    assert detect_emotion("I love you!") in ["shy", "blush", "happy"]
    assert detect_emotion("You're so cute!") in ["blush", "shy"]
    assert detect_emotion("I'm so happy!") == "happy"

def test_emotion_detection_sad():
    assert detect_emotion("I'm sad") == "sad"
    assert detect_emotion("I'm feeling down") == "sad"

def test_emotion_detection_surprise():
    assert detect_emotion("What?!") == "surprise"
    assert detect_emotion("Oh my!") == "surprise"

def test_emotion_detection_neutral():
    assert detect_emotion("The weather is nice") == "neutral"
    assert detect_emotion("What time is it?") == "neutral"

# tests/unit/test_config.py
def test_config_loading():
    from core.config import load_config
    config = load_config()
    
    assert "ai_model" in config
    assert "voice_id" in config
    assert "wake_words" in config
    assert isinstance(config["wake_words"], list)

def test_config_validation():
    from core.config import validate_config
    
    valid_config = {
        "ai_model": "gemini",
        "voice_rate": 0,
        "voice_pitch": 0,
        "wake_energy_threshold": 180
    }
    assert validate_config(valid_config) == True
    
    invalid_config = {
        "ai_model": "invalid_model",
        "voice_rate": -100,  # Out of range
    }
    assert validate_config(invalid_config) == False
```

### Integration Testing

**WebSocket Communication Test:**
```python
# tests/integration/test_websocket.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from server import app

@pytest.mark.asyncio
async def test_websocket_chat_flow():
    """Test complete chat message flow through WebSocket."""
    client = TestClient(app)
    
    with client.websocket_connect("/ws") as websocket:
        # Send chat message
        websocket.send_json({
            "type": "chat",
            "text": "Hello Mizune"
        })
        
        # Receive response
        response = websocket.receive_json()
        
        assert response["type"] == "speak"
        assert "text" in response
        assert "emotion" in response
        assert len(response["text"]) > 0

@pytest.mark.asyncio
async def test_websocket_emotion_update():
    """Test emotion update message."""
    client = TestClient(app)
    
    with client.websocket_connect("/ws") as websocket:
        # Backend should send emotion updates
        # Trigger an action that causes emotion change
        websocket.send_json({
            "type": "chat",
            "text": "I love you!"
        })
        
        # May receive emotion update before or with response
        messages = []
        for _ in range(3):
            msg = websocket.receive_json()
            messages.append(msg)
        
        # Check if any message is an emotion update
        emotion_msgs = [m for m in messages if m["type"] == "emotion"]
        assert len(emotion_msgs) > 0
```

**OAuth Integration Test (with mocks):**
```python
# tests/integration/test_oauth.py
import pytest
from unittest.mock import Mock, patch
from core.integrations.oauth import OAuth2Manager, GoogleOAuthProvider

@pytest.mark.asyncio
async def test_oauth_authentication_flow():
    """Test OAuth 2.0 authentication flow with mocked HTTP calls."""
    manager = OAuth2Manager()
    
    with patch('webbrowser.open') as mock_browser:
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock token exchange response
            mock_response = Mock()
            mock_response.json = asyncio.coroutine(lambda: {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
                "scope": "gmail.readonly gmail.send"
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Simulate callback with authorization code
            manager.auth_code = "test_auth_code"
            
            # Test token exchange
            provider = GoogleOAuthProvider()
            token = await provider.exchange_code("test_auth_code", "test_verifier")
            
            assert token.access_token == "test_access_token"
            assert token.refresh_token == "test_refresh_token"
            assert len(token.scope) > 0
```

**Gmail Integration Test (with mocks):**
```python
# tests/integration/test_gmail.py
import pytest
from unittest.mock import Mock, patch
from core.integrations.gmail import GmailClient

@pytest.mark.asyncio
async def test_gmail_get_unread_emails():
    """Test fetching unread emails with mocked Gmail API."""
    mock_oauth_manager = Mock()
    mock_oauth_manager.get_token = asyncio.coroutine(lambda x: Mock(
        access_token="test_token",
        is_expired=lambda: False
    ))
    
    client = GmailClient(mock_oauth_manager, "google")
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Mock Gmail API responses
        mock_response = Mock()
        mock_response.json = asyncio.coroutine(lambda: {
            "messages": [
                {"id": "msg1"},
                {"id": "msg2"}
            ]
        })
        mock_get.return_value.__aenter__.return_value = mock_response
        
        emails = await client.get_unread_emails(max_results=10)
        
        assert len(emails) == 2
```

### End-to-End Testing

**Voice Interaction E2E Test:**
```python
# tests/e2e/test_voice_interaction.py
import pytest
import asyncio
from unittest.mock import Mock, patch

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_voice_interaction_flow():
    """
    Test complete voice interaction flow:
    1. Wake word detection
    2. Audio recording
    3. Speech transcription
    4. LLM processing
    5. TTS generation
    6. WebSocket broadcast
    """
    from core.voice import VoiceSystem
    from core.ws_handler import WSHandler
    
    # Initialize systems
    voice_system = VoiceSystem(config)
    ws_handler = WSHandler()
    
    # Mock wake word detection
    with patch.object(voice_system, 'start_wake_word_detection') as mock_wake:
        # Simulate wake word detected
        callback = None
        def capture_callback(cb):
            nonlocal callback
            callback = cb
        mock_wake.side_effect = capture_callback
        
        voice_system.start_wake_word_detection(lambda text: None)
        
        # Trigger wake word
        await callback("mizune")
        
        # Verify listening state broadcast
        # ... verify WebSocket message sent
        
        # Mock audio recording and transcription
        with patch.object(voice_system, 'transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = "What's the weather?"
            
            # Process command
            # ... verify LLM called
            # ... verify TTS generated
            # ... verify audio broadcast
```

**Avatar Animation E2E Test:**
```javascript
// tests/e2e/avatar.test.js
describe('Avatar Animation E2E', () => {
  let vrm, scene, renderer;
  
  beforeEach(async () => {
    // Load VRM model
    vrm = await loadVRM('character/test.vrm');
    scene = initScene();
    renderer = initRenderer();
  });
  
  test('avatar responds to emotion changes with smooth transitions', async () => {
    // Set initial emotion
    setEmotion('neutral', 5.0);
    
    // Wait for transition
    await waitForFrames(30); // 0.5 seconds at 60 FPS
    
    // Verify neutral blend shapes
    const em = vrm.expressionManager;
    expect(em.getValue('happy')).toBeLessThan(0.1);
    expect(em.getValue('sad')).toBeLessThan(0.1);
    
    // Change to happy
    setEmotion('happy', 5.0);
    
    // Wait for transition (0.2s)
    await waitForFrames(12);
    
    // Verify happy blend shape increased
    expect(em.getValue('happy')).toBeGreaterThan(0.5);
  });
  
  test('avatar plays bounce animation on user message', async () => {
    const initialY = vrm.scene.position.y;
    
    // Trigger bounce
    playBounceAnimation();
    
    // Wait for animation (0.15s)
    await waitForFrames(9);
    
    // Verify returned to original position
    expect(Math.abs(vrm.scene.position.y - initialY)).toBeLessThan(0.01);
  });
});
```

### Performance Testing

**Avatar Rendering Performance:**
```javascript
// tests/performance/rendering.test.js
describe('Rendering Performance', () => {
  test('maintains 60 FPS with animations', () => {
    const frameTimings = [];
    let lastTime = performance.now();
    
    for (let i = 0; i < 600; i++) { // 10 seconds at 60 FPS
      animate();
      const now = performance.now();
      frameTimings.push(now - lastTime);
      lastTime = now;
    }
    
    const avgFrameTime = frameTimings.reduce((a, b) => a + b) / frameTimings.length;
    const fps = 1000 / avgFrameTime;
    
    expect(fps).toBeGreaterThanOrEqual(55); // Allow 5 FPS margin
  });
  
  test('memory usage remains stable during long session', () => {
    const initialMemory = performance.memory.usedJSHeapSize;
    
    // Run animations for 1000 frames
    for (let i = 0; i < 1000; i++) {
      animate();
    }
    
    const finalMemory = performance.memory.usedJSHeapSize;
    const memoryIncrease = (finalMemory - initialMemory) / 1024 / 1024; // MB
    
    // Memory should not increase by more than 50MB
    expect(memoryIncrease).toBeLessThan(50);
  });
});
```

**Backend Memory Usage Test:**
```python
# tests/performance/test_memory.py
import psutil
import pytest

def test_backend_memory_usage_idle():
    """Ensure backend uses less than 500MB RAM when idle."""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    assert memory_mb < 500, f"Memory usage too high: {memory_mb}MB"

def test_backend_cpu_usage_idle():
    """Ensure backend uses less than 5% CPU when idle."""
    process = psutil.Process()
    cpu_percent = process.cpu_percent(interval=1.0)
    
    assert cpu_percent < 5.0, f"CPU usage too high: {cpu_percent}%"
```

### Test Coverage Goals

**Frontend:**
- Unit test coverage: ≥80% for core modules (emotion, animation, websocket)
- Property test coverage: All 22 properties implemented
- Integration test coverage: All WebSocket message types
- E2E test coverage: All major user workflows

**Backend:**
- Unit test coverage: ≥80% for core modules (voice, emotion, config, integrations)
- Property test coverage: All 22 properties implemented
- Integration test coverage: All OAuth providers, all API integrations (with mocks)
- E2E test coverage: Complete voice interaction flow

**Continuous Integration:**
- Run all unit tests on every commit
- Run property tests (100 iterations) on every PR
- Run integration tests on every PR
- Run E2E tests nightly
- Run performance tests weekly

### Test Execution Commands

```bash
# Frontend tests
npm run test:unit          # Unit tests only
npm run test:properties    # Property-based tests (100 iterations)
npm run test:integration   # Integration tests
npm run test:e2e          # End-to-end tests
npm run test:all          # All tests

# Backend tests
pytest tests/unit/                    # Unit tests
pytest tests/properties/              # Property-based tests
pytest tests/integration/             # Integration tests
pytest tests/e2e/ -m e2e             # End-to-end tests
pytest tests/performance/             # Performance tests
pytest --cov=core --cov=agents       # Coverage report
```

