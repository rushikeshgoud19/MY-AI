import React, { useState, useEffect, useCallback } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { register } from '@tauri-apps/plugin-global-shortcut';

import { SlimeAvatar } from './components/SlimeAvatar';
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

export const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
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
  const [approvalRequest, setApprovalRequest] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [showChatLog, setShowChatLog] = useState(false);
  const [bubbleVisible, setBubbleVisible] = useState(false);
  const wsRef = React.useRef<WebSocket | null>(null);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

      // WebSocket connection
  useEffect(() => {
    const connect = () => {
      // @ts-ignore
      const isTauri = !!window.__TAURI__ || !!window.__TAURI_IPC__;
      let wsHost = '127.0.0.1';
      
      if (!isTauri && window.location.hostname === 'localhost') {
        // Fallback for Android testing on same network
        wsHost = '192.168.0.2';
      } else if (!isTauri && window.location.hostname !== 'localhost') {
        wsHost = window.location.hostname;
      }

      const ws = new WebSocket(`ws://${wsHost}:8001/ws`);
      
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

  // F2 Global Hotkey for Voice
  useEffect(() => {
    const setupHotkey = async () => {
      // @ts-ignore
      if (window.__TAURI__) {
        try {
          await register('F2', () => {
            console.log('F2 pressed - triggering voice listen');
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: 'trigger_listen' }));
            }
          });
        } catch (e) {
          console.error("Failed to register F2 hotkey", e);
        }
      } else {
        // Fallback for browser
        const handleKeyDown = (e: KeyboardEvent) => {
          if (e.key === 'F2') {
            e.preventDefault();
            console.log('F2 pressed - triggering voice listen');
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: 'trigger_listen' }));
            }
          }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
      }
    };
    setupHotkey();
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
        const assistantTokens = Math.floor(data.text.length / 3);
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
      case 'thinking':
        setMizuneState(prev => ({ ...prev, isThinking: data.payload }));
        break;
      case 'approval_required':
        setApprovalRequest(data.command);
        break;
    }
  }, []);

  const sendMessage = useCallback((overrideText?: string) => {
    const content = overrideText || input.trim();
    if (!content || mizuneState.isThinking || !isConnected) return;
    
    wsRef.current?.send(JSON.stringify({
      type: 'chat',
      text: content,
      payload: { message: content, device: 'dashboard' }
    }));
    
    const userTokens = Math.floor(content.length / 3);
    
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: content,
      timestamp: Date.now(),
      platform: 'dashboard'
    }]);
    
    if (!overrideText) setInput('');
    setMizuneState(prev => ({ ...prev, isThinking: true, tokensToday: prev.tokensToday + userTokens }));
  }, [input, mizuneState.isThinking, isConnected]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleQuickAction = (action: string) => {
    switch (action) {
      case 'briefing':
        sendMessage("Run my Morning Briefing. Check my emails and calendar.");
        break;
      case 'deep_work':
        sendMessage("Activate Deep Work Mode. Silence notifications and set a timer for 60 minutes.");
        break;
      case 'research':
        sendMessage("I need to do some Quick Research. Ask me what to search for.");
        break;
      case 'whatsapp':
        sendMessage("Who should we send a WhatsApp Blast to?");
        break;
      case 'sleep':
        sendMessage("Go to Sleep mode. Do not process background tasks until I wake you up.");
        break;
    }
  };

  const handleApprovalResponse = (approved: boolean) => {
    if (approved) {
      sendMessage(`Yes, I approve the execution of: ${approvalRequest}`);
    } else {
      sendMessage(`No, cancel the execution of: ${approvalRequest}`);
    }
    setApprovalRequest(null);
  };

  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');

  // Auto-hide the chat bubble after 8 seconds
  useEffect(() => {
    if (lastAssistantMessage) {
      setBubbleVisible(true);
      const timer = setTimeout(() => setBubbleVisible(false), 8000);
      return () => clearTimeout(timer);
    }
  }, [lastAssistantMessage]);

  // Auto-scroll chat log
  useEffect(() => {
    if (showChatLog) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, showChatLog]);

  return (
    <div className="mizune-dashboard">
      {/* ─── HEADER ─── */}
      <header className="dashboard-header glass-panel">
        <div className="brand" data-tauri-drag-region>
          <div className="brand-dot" data-tauri-drag-region />
          <h1 className="brand-text" data-tauri-drag-region>MIZUNE OS</h1>
        </div>
        
        <div className="status-bar" data-tauri-drag-region style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div className="provider-pill">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>CORE: </span>
            <span style={{ fontWeight: 600 }}>{mizuneState.provider.toUpperCase()}</span>
          </div>
          
          <div style={{ color: 'var(--text-muted)' }}>|</div>
          
          <div className={`connection-pill ${isConnected ? 'online' : 'offline'}`} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isConnected ? 'var(--accent-success, #10b981)' : 'var(--accent-danger, #ef4444)' }} />
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </div>
          
          <div className="window-controls" style={{ marginLeft: '16px', display: 'flex', gap: '8px' }}>
            <button onClick={() => getCurrentWindow().minimize()} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>─</button>
            <button onClick={() => getCurrentWindow().toggleMaximize()} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>□</button>
            <button onClick={() => getCurrentWindow().close()} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>✕</button>
          </div>
        </div>
      </header>

      {/* ─── MAIN CONTENT: 3-COLUMN MISSION CONTROL ─── */}
      <main className="main-content">
        
        {/* LEFT COLUMN: Metrics & State */}
        <aside className="sidebar-left glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div>
            <h2 className="panel-title" style={{ marginBottom: '16px', fontSize: '1rem', color: 'var(--text-muted)' }}>BIOMETRICS</h2>
            
            <div className="metric" style={{ marginBottom: '16px' }}>
              <div className="metric-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Trust Level</span>
                <span>{Math.round(mizuneState.trust * 100)}%</span>
              </div>
              <div className="metric-bar-bg" style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '10px' }}>
                <div className="metric-bar-fill" style={{ width: `${mizuneState.trust * 100}%`, height: '100%', background: 'var(--accent-gradient)', borderRadius: '10px' }} />
              </div>
            </div>
            
            <div className="metric" style={{ marginBottom: '16px' }}>
              <div className="metric-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Valence (Mood)</span>
                <span>{mizuneState.valence > 0 ? 'Happy' : mizuneState.valence < 0 ? 'Sad' : 'Neutral'}</span>
              </div>
              <div className="metric-bar-bg" style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '10px' }}>
                <div className="metric-bar-fill" style={{ width: `${((mizuneState.valence + 1) / 2) * 100}%`, height: '100%', background: getEmotionColor(mizuneState.valence, mizuneState.arousal), borderRadius: '10px' }} />
              </div>
            </div>
            
            <div className="metric" style={{ marginBottom: '16px' }}>
              <div className="metric-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Arousal (Energy)</span>
                <span>{Math.round(mizuneState.arousal * 100)}%</span>
              </div>
              <div className="metric-bar-bg" style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '10px' }}>
                <div className="metric-bar-fill" style={{ width: `${mizuneState.arousal * 100}%`, height: '100%', background: '#f59e0b', borderRadius: '10px' }} />
              </div>
            </div>
          </div>
          
          <div style={{ flex: 1 }}>
            <h2 className="panel-title" style={{ marginBottom: '16px', fontSize: '1rem', color: 'var(--text-muted)' }}>SYSTEM</h2>
            <SystemMonitor />
          </div>
        </aside>

        {/* CENTER STAGE: Huge Avatar & Chat */}
        <section className="center-stage" style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          
          <div className="avatar-container" style={{ transform: 'translateY(-40px)' }}>
            <SlimeAvatar state={mizuneState} size={300} />
            
            <div style={{ 
              position: 'absolute', 
              bottom: '-40px', 
              background: 'rgba(15, 23, 42, 0.6)', 
              backdropFilter: 'blur(10px)', 
              padding: '8px 24px', 
              borderRadius: '20px', 
              border: '1px solid rgba(255,255,255,0.1)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: mizuneState.isThinking ? '#f59e0b' : '#10b981', boxShadow: `0 0 10px ${mizuneState.isThinking ? '#f59e0b' : '#10b981'}` }} />
              <span style={{ fontSize: '0.9rem', letterSpacing: '1px' }}>
                {mizuneState.isThinking ? 'PROCESSING...' : mizuneState.isListening ? 'LISTENING...' : 'IDLE'}
              </span>
            </div>
          </div>
          
          {/* Chat Overlay floating at the bottom */}
          <div className="chat-overlay" style={{ position: 'absolute', bottom: '20px', width: '100%', maxWidth: '700px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            
            {lastAssistantMessage && !mizuneState.isThinking && bubbleVisible && (
              <div className="chat-bubble ai glass-panel" style={{ alignSelf: 'center', padding: '16px 24px', borderRadius: '24px', fontSize: '1.1rem', textAlign: 'center', background: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(139, 92, 246, 0.3)', position: 'relative' }}>
                <button 
                  onClick={() => setBubbleVisible(false)} 
                  style={{ position: 'absolute', top: '4px', right: '12px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
                >
                  ✕
                </button>
                {lastAssistantMessage.content}
              </div>
            )}
            
            {mizuneState.isThinking && (
              <div className="chat-bubble ai glass-panel" style={{ alignSelf: 'center', padding: '16px 24px', borderRadius: '24px' }}>
                <span style={{ opacity: 0.7 }}>Thinking...</span>
              </div>
            )}
            
            <div className="input-area glass-panel" style={{ display: 'flex', alignItems: 'center', padding: '8px 16px', borderRadius: '30px', background: 'rgba(15, 23, 42, 0.7)', width: '100%', gap: '8px' }}>
              <button
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem', padding: '4px' }}
                onClick={() => setShowChatLog(!showChatLog)}
                title="Toggle Chat Log"
              >
                📜
              </button>
              <input
                type="text"
                className="chat-input"
                style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', fontSize: '1rem', outline: 'none', padding: '8px' }}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Command Mizune... (or press F2 to speak)"
              />
              <button 
                className="btn-send"
                style={{ background: 'var(--accent-gradient)', border: 'none', width: '40px', height: '40px', borderRadius: '50%', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                onClick={() => sendMessage()}
                disabled={!input.trim() || mizuneState.isThinking}
              >
                ➤
              </button>
            </div>
          </div>
          
        </section>

        {/* RIGHT COLUMN: Action Center */}
        <aside className="sidebar-right glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div>
            <h2 className="panel-title" style={{ marginBottom: '16px', fontSize: '1rem', color: 'var(--text-muted)' }}>QUICK ACTIONS</h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button className="action-btn" onClick={() => handleQuickAction('briefing')}>
                <span style={{ fontSize: '1.2rem' }}>🌅</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontWeight: 600 }}>Morning Briefing</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Read Emails & Calendar</div>
                </div>
              </button>
              
              <button className="action-btn" onClick={() => handleQuickAction('deep_work')}>
                <span style={{ fontSize: '1.2rem' }}>🧠</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontWeight: 600 }}>Deep Work Mode</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Silence alerts, set timer</div>
                </div>
              </button>
              
              <button className="action-btn" onClick={() => handleQuickAction('research')}>
                <span style={{ fontSize: '1.2rem' }}>🔍</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontWeight: 600 }}>Quick Research</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Agent-Reach deep search</div>
                </div>
              </button>
              
              <button className="action-btn" onClick={() => handleQuickAction('whatsapp')}>
                <span style={{ fontSize: '1.2rem' }}>💬</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontWeight: 600 }}>WhatsApp Blast</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Draft & send messages</div>
                </div>
              </button>
              
              <button className="action-btn" onClick={() => handleQuickAction('sleep')}>
                <span style={{ fontSize: '1.2rem' }}>💤</span>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontWeight: 600 }}>Sleep / Wake</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Toggle background listening</div>
                </div>
              </button>
            </div>
          </div>
          
          <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: '16px', padding: '16px' }}>
            <h2 className="panel-title" style={{ marginBottom: '12px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>RECENT ALERTS</h2>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic', textAlign: 'center', marginTop: '40px' }}>
              No active alerts.
            </div>
          </div>
        </aside>

      </main>

      {/* ─── APPROVAL MODAL ─── */}
      {approvalRequest && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div className="glass-panel" style={{ padding: '32px', borderRadius: '24px', maxWidth: '500px', border: '2px solid var(--accent-danger, #ef4444)' }}>
            <h2 style={{ color: 'var(--accent-danger, #ef4444)', display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <span style={{ fontSize: '1.5rem' }}>⚠️</span> DANGEROUS ACTION
            </h2>
            <p style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              Mizune is attempting to execute a potentially destructive system command. Do you approve?
            </p>
            <div style={{ background: 'rgba(0,0,0,0.4)', padding: '16px', borderRadius: '8px', fontFamily: 'monospace', color: '#fca5a5', marginBottom: '32px', wordBreak: 'break-all' }}>
              {approvalRequest}
            </div>
            <div style={{ display: 'flex', gap: '16px', justifyContent: 'flex-end' }}>
              <button 
                onClick={() => handleApprovalResponse(false)}
                style={{ padding: '12px 24px', background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: 'white', borderRadius: '12px', cursor: 'pointer' }}
              >
                Deny & Cancel
              </button>
              <button 
                onClick={() => handleApprovalResponse(true)}
                style={{ padding: '12px 24px', background: 'var(--accent-danger, #ef4444)', border: 'none', color: 'white', borderRadius: '12px', cursor: 'pointer', fontWeight: 'bold' }}
              >
                Approve Execution
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── CHAT LOG MODAL ─── */}
      {showChatLog && (
        <div style={{ position: 'absolute', top: '80px', left: '20px', bottom: '20px', width: '400px', zIndex: 100, display: 'flex', flexDirection: 'column' }} className="glass-panel">
          <div style={{ padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Communication Log</h3>
            <button onClick={() => setShowChatLog(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {messages.map((msg, idx) => (
              <div key={idx} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px', textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                  {msg.role === 'user' ? 'You' : 'Mizune'} • {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div style={{ 
                  padding: '10px 14px', 
                  borderRadius: '16px', 
                  borderBottomRightRadius: msg.role === 'user' ? '4px' : '16px',
                  borderTopLeftRadius: msg.role === 'assistant' ? '4px' : '16px',
                  background: msg.role === 'user' ? 'var(--accent-gradient)' : 'rgba(30, 41, 59, 0.8)',
                  border: msg.role === 'assistant' ? '1px solid rgba(139, 92, 246, 0.3)' : 'none',
                  color: 'white',
                  fontSize: '0.9rem'
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {messages.length === 0 && <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '40px' }}>No messages yet.</div>}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

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
