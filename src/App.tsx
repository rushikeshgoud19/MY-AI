import React, { useState, useEffect, useCallback } from 'react';

import { SlimeAvatar } from './components/SlimeAvatar';
import { SystemMonitor } from './components/SystemMonitor';
import { TraceRootInsights } from './components/TraceRootInsights';

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

export interface AgentTask {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
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
  const [activeTasks, setActiveTasks] = useState<AgentTask[]>([]);
  const wsRef = React.useRef<WebSocket | null>(null);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

      // WebSocket connection
  useEffect(() => {
    const connect = () => {
      const hostname = window.location.hostname;
      // @ts-ignore
      const isCapacitor = typeof Capacitor !== 'undefined' || !!window.Capacitor;
      
      let wsHost = '127.0.0.1';
      
      if (isCapacitor) {
        // Fallback for Android testing on same network
        wsHost = '192.168.0.7'; // Replace with actual dev machine IP if testing mobile
      } else if (hostname && hostname !== 'localhost' && hostname !== 'tauri.localhost' && hostname !== '127.0.0.1') {
        // Accessing from another device on LAN (e.g., 192.168.x.x)
        wsHost = hostname;
      }

      const ws = new WebSocket(`ws://${wsHost}:8001/ws`);
      
      ws.onopen = () => {
        setIsConnected(true);
        console.log('[Dashboard] Connected to Mizune');
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Check if trace context arrived
          if (data._trace_context) {
              console.log("🔍 Trace context RECEIVED on frontend:", data._trace_context.traceparent);
              console.log("❌ GAP CONFIRMED: No mechanism to extract/continue this trace in Tauri/JS");
          }

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
      if (window.__TAURI__ || window.__TAURI_IPC__) {
        try {
          const { register } = await import('@tauri-apps/plugin-global-shortcut');
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
      case 'task_list':
        setActiveTasks(data.tasks);
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
        // Only set isThinking to true for active statuses. Never set it to false here,
        // because we want it to stay thinking until the final 'speak' or 'error' message arrives.
        if (data.text !== 'Idle' && data.text !== 'Ready') {
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

  const sendMessage = (textOverride?: string) => {
    const text = textOverride || input;
    if (!text.trim() || !wsRef.current) return;
    
    setActiveTasks([]); // Clear old tasks on new command
    
    // Command Interception
    if (text.startsWith('/')) {
      const [cmd, ...args] = text.split(' ');
      const payload = args.join(' ');
      
      switch(cmd.toLowerCase()) {
        case '/dpr':
          wsRef.current.send(JSON.stringify({ type: 'command', command: 'research', query: payload }));
          break;
        case '/briefing':
          wsRef.current.send(JSON.stringify({ type: 'command', command: 'briefing' }));
          break;
        case '/wa':
          wsRef.current.send(JSON.stringify({ type: 'command', command: 'whatsapp', message: payload }));
          break;
        default:
          wsRef.current.send(JSON.stringify({ type: 'command', command: cmd.substring(1), args: payload }));
      }
    } else {
      // Normal Chat
      setMizuneState(prev => ({ ...prev, isThinking: true }));
      wsRef.current.send(JSON.stringify({ type: 'chat', text }));
    }
    
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
      platform: 'dashboard'
    }]);
    
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
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




  // Auto-scroll chat log
  useEffect(() => {
    if (showChatLog) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, showChatLog]);

  const handleWindowAction = async (action: 'minimize' | 'maximize' | 'close') => {
    // @ts-ignore
    if (window.__TAURI__ || window.__TAURI_IPC__) {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();
      if (action === 'minimize') win.minimize();
      if (action === 'maximize') win.toggleMaximize();
      if (action === 'close') win.close();
    }
  };

  // @ts-ignore
  const isDesktop = !!window.__TAURI__ || !!window.__TAURI_IPC__;

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
          
          {isDesktop && (
            <div className="window-controls" style={{ marginLeft: '16px', display: 'flex', gap: '8px' }}>
              <button onClick={() => handleWindowAction('minimize')} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>─</button>
              <button onClick={() => handleWindowAction('maximize')} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>□</button>
              <button onClick={() => handleWindowAction('close')} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>✕</button>
            </div>
          )}
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
                <div className="metric-bar-fill" style={{ width: `${((mizuneState.valence + 1) / 2) * 100}%`, height: '100%', background: getEmotionColor(mizuneState.valence), borderRadius: '10px' }} />
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

        {/* CENTER STAGE: Deep Research & Terminal Log */}
        <section className="center-stage glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          
          {/* Task Checklist Overlay */}
          {activeTasks.length > 0 && (
            <div className="task-tracker glass-panel" style={{ margin: '24px 24px 0 24px', padding: '20px', borderRadius: '16px', background: 'rgba(15, 23, 42, 0.85)', border: '1px solid rgba(139, 92, 246, 0.4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)' }}>
                  ⚙️ Active Tasks
                </h3>
                {activeTasks.every(t => t.status === 'completed') && (
                  <span style={{ color: 'var(--accent-success)', fontSize: '0.9rem', fontWeight: 600 }}>COMPLETED</span>
                )}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {activeTasks.map(t => (
                  <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', color: t.status === 'completed' ? 'var(--text-muted)' : 'white' }}>
                    <span style={{ fontSize: '1.2rem' }}>
                      {t.status === 'completed' ? '✅' : t.status === 'running' ? '🔄' : '⏳'}
                    </span>
                    <span style={{ textDecoration: t.status === 'completed' ? 'line-through' : 'none', fontSize: '0.95rem' }}>
                      {t.description}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Chat / Work Log */}
          <div className="chat-log-container" style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            
            {/* Removed TraceRoot SQL Analyst as requested */}
            {messages.map(msg => (
              <div key={msg.id} style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%'
              }}>
                <div style={{
                  background: msg.role === 'user' ? 'var(--accent-gradient)' : 'rgba(30, 41, 59, 0.8)',
                  padding: '12px 20px',
                  borderRadius: msg.role === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                  border: msg.role === 'assistant' ? '1px solid rgba(255,255,255,0.1)' : 'none',
                  color: 'white',
                  lineHeight: '1.5',
                  fontSize: '1rem',
                  whiteSpace: 'pre-wrap',
                  fontFamily: msg.role === 'assistant' && msg.content.includes('```') ? 'Consolas, monospace' : 'inherit'
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {messages.length === 0 && (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                <span style={{ fontSize: '3rem' }}>🔍</span>
                <p>Mizune Terminal Ready.</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', maxWidth: '400px' }}>
                  <code style={{ background: 'rgba(255,255,255,0.1)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>/dpr &lt;query&gt;</code>
                  <code style={{ background: 'rgba(255,255,255,0.1)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>/briefing</code>
                  <code style={{ background: 'rgba(255,255,255,0.1)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>/wa &lt;message&gt;</code>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          {/* Input Area */}
          <div className="input-area" style={{ display: 'flex', alignItems: 'center', padding: '16px 24px', background: 'rgba(15, 23, 42, 0.7)', borderTop: '1px solid rgba(255,255,255,0.05)', gap: '12px' }}>
            <input
              type="text"
              className="chat-input"
              style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', fontSize: '1.1rem', outline: 'none', padding: '12px 20px', borderRadius: '30px' }}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Run a command (/dpr) or chat normally... (F2 to speak)"
            />
            <button 
              className="btn-send"
              style={{ background: 'var(--accent-gradient)', border: 'none', width: '48px', height: '48px', borderRadius: '50%', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem', boxShadow: 'var(--shadow-glow)' }}
              onClick={() => sendMessage()}
              disabled={!input.trim() || mizuneState.isThinking}
            >
              ➤
            </button>
          </div>
        </section>

        {/* RIGHT COLUMN: Action Center & Avatar */}
        <aside className="sidebar-right" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '20px' }}>
          
          <div className="avatar-container">
            <SlimeAvatar state={mizuneState} size={280} />
            
            <div style={{ 
              marginTop: '20px', 
              background: 'rgba(15, 23, 42, 0.6)', 
              backdropFilter: 'blur(10px)', 
              padding: '12px 32px', 
              borderRadius: '30px', 
              border: '1px solid rgba(255,255,255,0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              boxShadow: 'var(--shadow-md)'
            }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: mizuneState.isThinking ? '#f59e0b' : mizuneState.isListening ? '#ec4899' : '#10b981', boxShadow: `0 0 12px ${mizuneState.isThinking ? '#f59e0b' : mizuneState.isListening ? '#ec4899' : '#10b981'}` }} />
              <span style={{ fontSize: '1rem', letterSpacing: '1px', fontWeight: 600 }}>
                {mizuneState.isThinking ? 'PROCESSING' : mizuneState.isListening ? 'LISTENING' : 'IDLE'}
              </span>
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

function getEmotionColor(valence: number): string {
  if (valence < -0.5) return '#6366f1';
  if (valence < 0) return '#8b5cf6';
  if (valence < 0.5) return '#a855f7';
  if (valence < 0.8) return '#d946ef';
  return '#f472b6';
}
