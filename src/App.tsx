import React, { useState, useEffect, useCallback } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';

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

interface EmailMessage {
  id: string;
  sender: string;
  subject: string;
  snippet: string;
  importance: number;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'skills' | 'whatsapp' | 'emails' | 'system' | 'kernel' | 'settings'>('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [whatsappMessages, setWhatsappMessages] = useState<WhatsAppMessage[]>([]);
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [kernelLogs, setKernelLogs] = useState<string[]>([]);
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
      case 'speak':
        const assistantTokens = Math.floor(data.text.length / 3); // rough estimate
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.text,
          timestamp: Date.now(),
          platform: 'dashboard'
        }]);
        setMizuneState(prev => ({ ...prev, isThinking: false, tokensToday: prev.tokensToday + assistantTokens }));
        break;
      case 'status':
        if (data.text === 'Thinking...') {
          setMizuneState(prev => ({ ...prev, isThinking: true }));
        } else {
          setMizuneState(prev => ({ ...prev, isThinking: false }));
        }
        break;
      case 'gmail_alert':
        setEmails(prev => [{
          id: Date.now().toString(),
          sender: data.sender,
          subject: data.subject,
          snippet: data.snippet,
          importance: data.importance
        }, ...prev]);
        break;
      case 'thinking':
        setMizuneState(prev => ({ ...prev, isThinking: data.payload }));
        break;
      case 'kernel_log':
        setKernelLogs(prev => {
          const updated = [...prev, data.payload];
          // Keep RAM low by capping at 100 lines
          if (updated.length > 100) return updated.slice(updated.length - 100);
          return updated;
        });
        break;
      case 'task_update':
        setMizuneState(prev => ({ ...prev, isThinking: true }));
        setKernelLogs(prev => [...prev, `[TASK] ${data.data}`]);
        break;
      case 'task_complete':
        setMizuneState(prev => ({ ...prev, isThinking: false }));
        setKernelLogs(prev => [...prev, `[TASK] ${data.data}`]);
        // Also send a chat notification
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `*Background task finished:* ${data.data}`,
          timestamp: Date.now(),
          platform: 'dashboard'
        }]);
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

  const sendMessage = useCallback((text?: string) => {
    const content = text || input;
    if (!content.trim() || !wsRef.current) return;
    
    const msg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content,
      timestamp: Date.now(),
      platform: 'dashboard'
    };
    
    setMessages(prev => [...prev, msg]);
    setInput('');
    
    const userTokens = Math.floor(content.length / 3);
    
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      text: content,
      payload: { message: content, device: 'dashboard' }
    }));
    
    setMizuneState(prev => ({ ...prev, isThinking: true, tokensToday: prev.tokensToday + userTokens }));
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
            {mizuneState.tokensToday < 1000 ? mizuneState.tokensToday : (mizuneState.tokensToday / 1000).toFixed(1) + 'k'} tokens
          </div>
          
          <div className="window-controls">
            <button onClick={() => getCurrentWindow().minimize()}>─</button>
            <button onClick={() => getCurrentWindow().toggleMaximize()}>□</button>
            <button onClick={() => getCurrentWindow().close()} className="close-btn">✕</button>
          </div>
        </div>
      </header>

      <div className="dashboard-body">
        {/* ─── LEFT SIDEBAR ─── */}
        <aside className="sidebar">
          {/* Slime Avatar */}
          <div className="avatar-container">
            <div className={`classic-blob-container ${mizuneState.isTalking || mizuneState.isThinking ? 'speaking' : ''}`}>
              <div id="mizune-blob" className={mizuneState.isTalking || mizuneState.isThinking ? 'speaking' : ''}>
                <div className="blob-eye left" />
                <div className="blob-eye right" />
              </div>
              <div className="blob-glow" />
            </div>
            
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
              className={`nav-tab ${activeTab === 'emails' ? 'active' : ''}`}
              onClick={() => setActiveTab('emails')}
            >
              <span className="tab-icon">📧</span>
              Emails
              {emails.length > 0 && (
                <span className="badge new">{emails.length}</span>
              )}
            </button>
            
            <button 
              className={`nav-tab ${activeTab === 'kernel' ? 'active' : ''}`}
              onClick={() => setActiveTab('kernel')}
            >
              <span className="tab-icon">🖥️</span>
              Kernel Stream
            </button>

            <button 
              className={`nav-tab ${activeTab === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveTab('settings')}
            >
              <span className="tab-icon">⚙️</span>
              Settings
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
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || mizuneState.isThinking}
                >
                  ➤
                </button>
              </div>
            </div>
          )}

          {activeTab === 'skills' && <SkillsPanel />}
          {activeTab === 'whatsapp' && <WhatsAppPanel messages={whatsappMessages} />}
          {activeTab === 'emails' && (
            <div className="emails-panel" style={{padding: '24px', height: '100%', overflowY: 'auto'}}>
              <div className="settings-card" style={{minHeight: '100%', display: 'flex', flexDirection: 'column'}}>
                <h3>Important Emails</h3>
                <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px'}}>
                  {emails.length === 0 ? (
                    <div style={{color: '#888', fontStyle: 'italic', textAlign: 'center', marginTop: '40px'}}>
                      No new important emails. (Make sure you connect Gmail in Settings)
                    </div>
                  ) : (
                    emails.map(email => (
                      <div key={email.id} className="email-card" style={{
                        background: 'var(--bg-secondary)', 
                        padding: '16px', 
                        borderRadius: '8px',
                        borderLeft: email.importance >= 8 ? '4px solid #ef4444' : '4px solid #3b82f6'
                      }}>
                        <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '8px'}}>
                          <span style={{fontWeight: 'bold', fontSize: '14px', color: 'var(--text-primary)'}}>{email.sender}</span>
                          <span style={{
                            background: email.importance >= 8 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                            color: email.importance >= 8 ? '#fca5a5' : '#93c5fd',
                            padding: '2px 8px', borderRadius: '12px', fontSize: '12px'
                          }}>
                            Importance: {email.importance}/10
                          </span>
                        </div>
                        <div style={{fontWeight: 'bold', marginBottom: '6px', color: 'var(--text-primary)'}}>{email.subject}</div>
                        <div style={{color: 'var(--text-muted)', fontSize: '13px', lineHeight: '1.4'}}>{email.snippet}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
          {activeTab === 'system' && (
            <SystemMonitor />
          )}

          {activeTab === 'kernel' && (
            <div className="kernel-terminal">
              {kernelLogs.map((log, i) => {
                let statusClass = '';
                if (log.toLowerCase().includes('error') || log.toLowerCase().includes('fail')) statusClass = 'error';
                else if (log.toLowerCase().includes('success') || log.toLowerCase().includes('done')) statusClass = 'success';
                
                return (
                  <div key={i} className={`kernel-log ${statusClass}`}>
                    <span style={{color: '#888', marginRight: '8px'}}>[{new Date().toLocaleTimeString()}]</span>
                    {log}
                  </div>
                );
              })}
              {kernelLogs.length === 0 && (
                <div style={{ color: '#888', fontStyle: 'italic' }}>Waiting for kernel logs...</div>
              )}
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="settings-panel">
              <div className="settings-card">
                <h3>Integrations</h3>
                <p style={{color: '#888', marginBottom: '16px', fontSize: '13px'}}>
                  Connect external services to give Mizune access to your data.
                </p>
                <div className="form-group">
                  <label>Google OAuth Token</label>
                  <button className="btn-primary" onClick={() => {
                    sendMessage('/nuke_cache');
                  }}>Check Token Status</button>
                  <p style={{marginTop: '8px', fontSize: '11px', color: '#666'}}>
                    Note: To connect Google, please run the <code>connect_gmail.py</code> script in your terminal!
                  </p>
                </div>
              </div>
            </div>
          )}
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
