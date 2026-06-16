import React, { useState, useEffect, useCallback } from 'react';
import { SlimeAvatar } from './components/SlimeAvatar';
import { MemoryGraph } from './components/MemoryGraph';
import { SkillsPanel } from './components/SkillsPanel';
import { WhatsAppPanel } from './components/WhatsAppPanel';
import { SystemMonitor } from './components/SystemMonitor';

interface MizuneState {
  valence: number;
  arousal: number;
  trust: number;
  isThinking: boolean;
  isListening: boolean;
  isTalking: boolean;
  currentApp: string;
  lastMessage: string;
  provider: string;
  tokensToday: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  platform: string;
  seen?: boolean;
}

interface WhatsAppMessage {
  id: string;
  sender: string;
  text: string;
  urgency: string;
  timestamp: number;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'memory' | 'skills' | 'whatsapp' | 'system'>('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [whatsappMessages, setWhatsappMessages] = useState<WhatsAppMessage[]>([]);
  const [input, setInput] = useState('');
  const [mizuneState, setMizuneState] = useState<MizuneState>({
    valence: 0,
    arousal: 0.2,
    trust: 0.5,
    isThinking: false,
    isListening: false,
    isTalking: false,
    currentApp: 'Desktop',
    lastMessage: '',
    provider: 'local',
    tokensToday: 0
  });
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = React.useRef<WebSocket | null>(null);

  // WebSocket connection
  useEffect(() => {
    const connect = () => {
      // Connect to the Python backend websocket port 8001
      const ws = new WebSocket('ws://localhost:8001/ws');
      
      ws.onopen = () => {
        setIsConnected(true);
        console.log('[Dashboard] Connected to Mizune');
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch (e) {
          console.error('[Dashboard] Error parsing WS message:', e);
        }
      };
      
      ws.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 3000);
      };
      
      wsRef.current = ws;
    };
    
    connect();
    return () => wsRef.current?.close();
  }, []);

  const handleServerMessage = useCallback((data: any) => {
    switch (data.type) {
      case 'state_update':
        setMizuneState(prev => ({ ...prev, ...data.payload }));
        break;
      case 'message':
        setMessages(prev => [...prev, data.payload]);
        break;
      case 'thinking':
        setMizuneState(prev => ({ ...prev, isThinking: data.payload }));
        break;
      case 'provider_switch':
        setMizuneState(prev => ({ ...prev, provider: data.payload }));
        break;
      case 'whatsapp_alert':
        setWhatsappMessages(prev => [{
          id: Date.now().toString(),
          sender: data.sender,
          text: data.message,
          urgency: data.urgency,
          timestamp: Date.now()
        }, ...prev]);
        break;
      default:
        console.log('[Dashboard] Unhandled message type:', data.type);
    }
  }, []);

  const sendMessage = useCallback(() => {
    if (!input.trim() || !wsRef.current) return;
    
    const msg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: Date.now(),
      platform: 'dashboard'
    };
    
    setMessages(prev => [...prev, msg]);
    setInput('');
    
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      payload: { message: input, device: 'dashboard' }
    }));
    
    setMizuneState(prev => ({ ...prev, isThinking: true }));
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="mizune-dashboard">
      {/* ─── HEADER ─── */}
      <header className="dashboard-header">
        <div className="brand" data-tauri-drag-region>
          <div className="brand-dot" data-tauri-drag-region />
          <h1 data-tauri-drag-region>Mizune OS</h1>
          <span className="version" data-tauri-drag-region>v6.0</span>
        </div>
        
        <div className="status-bar" data-tauri-drag-region>
          <div className={`connection-pill ${isConnected ? 'online' : 'offline'}`}>
            <span className="pulse" />
            {isConnected ? 'Connected' : 'Reconnecting...'}
          </div>
          
          <div className="provider-pill">
            <span className="provider-icon">🧠</span>
            {mizuneState.provider}
          </div>
          
          <div className="token-pill">
            <span className="token-icon">⚡</span>
            {(mizuneState.tokensToday / 1000).toFixed(1)}k tokens
          </div>
        </div>
      </header>

      <div className="dashboard-body">
        {/* ─── LEFT SIDEBAR ─── */}
        <aside className="sidebar">
          {/* Slime Avatar */}
          <div className="avatar-container">
            <SlimeAvatar 
              state={{
                valence: mizuneState.valence,
                arousal: mizuneState.arousal,
                trust: mizuneState.trust,
                isThinking: mizuneState.isThinking,
                isListening: mizuneState.isListening,
                isTalking: mizuneState.isTalking
              }}
              size={180}
            />
            
            <div className="emotion-badge" style={{
              background: getEmotionColor(mizuneState.valence, mizuneState.arousal)
            }}>
              {getEmotionLabel(mizuneState.valence, mizuneState.arousal)}
            </div>
            
            <div className="activity-indicator">
              {mizuneState.isThinking ? '💭 Thinking...' :
               mizuneState.isListening ? '👂 Listening...' :
               mizuneState.isTalking ? '💬 Speaking...' :
               `👀 Watching ${mizuneState.currentApp}`}
            </div>
          </div>

          {/* Navigation */}
          <nav className="nav-tabs">
            <button 
              className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <span className="tab-icon">💬</span>
              Chat
              {messages.filter(m => m.role === 'user' && !m.seen).length > 0 && (
                <span className="badge">{messages.filter(m => m.role === 'user' && !m.seen).length}</span>
              )}
            </button>
            
            <button 
              className={`nav-tab ${activeTab === 'memory' ? 'active' : ''}`}
              onClick={() => setActiveTab('memory')}
            >
              <span className="tab-icon">🧠</span>
              Memory Graph
            </button>
            
            <button 
              className={`nav-tab ${activeTab === 'skills' ? 'active' : ''}`}
              onClick={() => setActiveTab('skills')}
            >
              <span className="tab-icon">⚡</span>
              Skills & Tools
            </button>
            
            <button 
              className={`nav-tab ${activeTab === 'whatsapp' ? 'active' : ''}`}
              onClick={() => setActiveTab('whatsapp')}
            >
              <span className="tab-icon">📱</span>
              WhatsApp
              {whatsappMessages.length > 0 && (
                <span className="badge new">{whatsappMessages.length}</span>
              )}
            </button>
            
            <button 
              className={`nav-tab ${activeTab === 'system' ? 'active' : ''}`}
              onClick={() => setActiveTab('system')}
            >
              <span className="tab-icon">🔧</span>
              System
            </button>
          </nav>

          {/* Quick Stats */}
          <div className="quick-stats">
            <div className="stat-row">
              <span>Trust</span>
              <div className="stat-bar">
                <div className="stat-fill" style={{width: `${mizuneState.trust * 100}%`}} />
              </div>
            </div>
            <div className="stat-row">
              <span>Mood</span>
              <div className="stat-bar">
                <div className="stat-fill mood" style={{
                  width: `${((mizuneState.valence + 1) / 2) * 100}%`,
                  background: getEmotionColor(mizuneState.valence, 0)
                }} />
              </div>
            </div>
          </div>
        </aside>

        {/* ─── MAIN CONTENT ─── */}
        <main className="main-content">
          {activeTab === 'chat' && (
            <div className="chat-panel">
              <div className="messages-area">
                {messages.map(msg => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-bubble">
                      <p>{msg.content}</p>
                      <span className="message-meta">
                        {new Date(msg.timestamp).toLocaleTimeString()} · {msg.platform}
                      </span>
                    </div>
                  </div>
                ))}
                
                {mizuneState.isThinking && (
                  <div className="message assistant thinking">
                    <div className="message-bubble">
                      <div className="typing-dots">
                        <span /><span /><span />
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="input-area">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Message Mizune..."
                  rows={1}
                />
                <button 
                  className="send-btn"
                  onClick={sendMessage}
                  disabled={!input.trim() || mizuneState.isThinking}
                >
                  ➤
                </button>
              </div>
            </div>
          )}

          {activeTab === 'memory' && <MemoryGraph />}
          {activeTab === 'skills' && <SkillsPanel />}
          {activeTab === 'whatsapp' && <WhatsAppPanel messages={whatsappMessages} />}
          {activeTab === 'system' && <SystemMonitor />}
        </main>
      </div>
    </div>
  );
};

function getEmotionColor(valence: number, arousal: number): string {
  if (valence < -0.5) return '#6366f1';
  if (valence < 0) return '#8b5cf6';
  if (valence < 0.5) return '#a855f7';
  if (valence < 0.8) return '#d946ef';
  return '#f472b6';
}

function getEmotionLabel(valence: number, arousal: number): string {
  if (valence < -0.7) return 'Sad';
  if (valence < -0.3) return 'Down';
  if (valence < 0.3) return 'Neutral';
  if (valence < 0.7) return 'Happy';
  if (arousal > 0.7) return 'Excited';
  return 'Joyful';
}
