// Mizune Voice Interface — glowing core + orbiting capability clusters.
// Talks to the Mizune server over the existing /ws websocket (chat in,
// status/speak events out). TTS audio is played by the server itself.

const $ = s => document.querySelector(s);

// ---------- capability map (what orbits the core) ----------
const CLUSTERS = [
  { name: 'Memory',  color: '#a78bfa', caps: ['memory tree', 'chromadb', 'obsidian sync', 'vault', 'sessions'] },
  { name: 'Comms',   color: '#f472b6', caps: ['whatsapp', 'gmail', 'notify', 'contacts'] },
  { name: 'Senses',  color: '#60a5fa', caps: ['vision', 'stt', 'wake word', 'noise cancel'] },
  { name: 'Mind',    color: '#fb923c', caps: ['emotion engine', 'subconscious', 'proactive', 'evolution', 'curator'] },
  { name: 'Skills',  color: '#34d399', caps: ['skills', 'agents', 'web agent', 'runbooks', 'scheduler'] },
  { name: 'Body',    color: '#e2e8f0', caps: ['tts', 'audio', 'device agent'] },
  { name: 'Ops',     color: '#22d3ee', caps: ['tracing', 'security', 'model router', 'tokenjuice'] },
];
const CAP_COUNT = CLUSTERS.reduce((n, c) => n + c.caps.length, 0);
$('#caps-label').textContent = `${CAP_COUNT} capabilities · ${CLUSTERS.length} clusters`;

const THEMES = {
  classic: { core: '#c6fff2', glow: '52,245,197' },
  aurora:  { core: '#d6ccff', glow: '167,139,250' },
  plasma:  { core: '#ffd6e0', glow: '244,114,182' },
};
let theme = THEMES.classic;
document.querySelectorAll('.mode').forEach(b => b.onclick = () => {
  document.querySelectorAll('.mode').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  theme = THEMES[b.dataset.theme] || THEMES.classic;
});

// ---------- state ----------
let state = 'idle';          // idle | listening | muted | thinking | speaking
let voiceOn = false;         // session started
let micLevel = 0;            // 0..1 from analyser
let ws = null, wsOk = false;

function setState(s) {
  state = s;
  const pill = $('#live-pill'), txt = $('#live-text');
  const map = { idle: 'TAP CORE TO START', listening: 'LIVE · LISTENING', muted: 'MUTED',
    thinking: 'THINKING…', speaking: 'SPEAKING' };
  txt.textContent = map[s] || s.toUpperCase();
  pill.classList.toggle('off', s === 'idle' || s === 'muted');
}

// ---------- websocket ----------
// Mizune's FastAPI runs on 8001 (local dev or cloud VM). When served from the
// Agentic OS dashboard, ask it which backend is actually alive; otherwise
// assume we're served by Mizune herself.
let MIZUNE_WS = location.port === '8001' ? `ws://${location.host}/ws` : null;

async function resolveWS() {
  if (MIZUNE_WS) return MIZUNE_WS;
  try {
    const st = await fetch('/api/mizune').then(r => r.json());
    if (st.online && st.ws) return MIZUNE_WS = st.ws;
  } catch {}
  return MIZUNE_WS = `ws://${location.hostname || 'localhost'}:8001/ws`;
}

async function connectWS() {
  const wsUrl = await resolveWS();
  ws = new WebSocket(wsUrl);
  ws.onopen = () => { wsOk = true; $('#status-chip').textContent = 'connected · ' + wsUrl.replace(/^ws:\/\//, '').replace('/ws', ''); $('#status-chip').classList.add('ok'); };
  ws.onclose = () => { wsOk = false; $('#status-chip').textContent = 'reconnecting…'; $('#status-chip').classList.remove('ok'); setTimeout(connectWS, 2000); };
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.type === 'user_input') $('#cap-user').textContent = '“' + m.text + '”';
    if (m.type === 'status') {
      if (/think/i.test(m.text || '')) setState('thinking');
      else if (voiceOn && state !== 'muted') setState('listening');
    }
    if (m.type === 'speak') {
      const clean = cleanReply(m.text);
      $('#cap-mizune').textContent = clean;
      setState('speaking');
      speak(clean);
      clearTimeout(setState._t);
      setState._t = setTimeout(() => { if (voiceOn && state === 'speaking') setState(muted ? 'muted' : 'listening'); },
        Math.min(20000, 1500 + clean.length * 55));
    }
  };
}
connectWS();

// ---------- Mizune voice output ----------
// Cloud is headless (no speakers) so the browser must voice her. Try server TTS
// (real edge-tts voice) first; fall back to the browser's own speech engine.
let mzVoice = null;
function pickVoice() {
  const vs = speechSynthesis.getVoices();
  mzVoice = vs.find(v => /female|zira|aria|jenny|natural/i.test(v.name) && /en/i.test(v.lang))
    || vs.find(v => /en-IN|en-GB|en-US/i.test(v.lang)) || vs[0] || null;
}
if ('speechSynthesis' in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

function cleanReply(t) {
  return String(t || '')
    .replace(/\[EMOTION:[^\]]*\]\s*/gi, '')   // strip [EMOTION: x]
    .replace(/^\s*[}\])]+\s*/g, '')            // stray leading brace/bracket
    .replace(/\s*[{[(]+\s*$/g, '')             // stray trailing brace
    .replace(/\(OpenRouter[^)]*\)/gi, '')       // provider error leak
    .trim();
}

function speak(text) {
  if (!text || muted) return;
  if (!('speechSynthesis' in window)) return;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    if (mzVoice) u.voice = mzVoice;
    u.rate = 1.02; u.pitch = 1.25;   // higher pitch = closer to Mizune's idol voice
    u.onend = () => { if (voiceOn && state === 'speaking') setState(muted ? 'muted' : 'listening'); };
    speechSynthesis.speak(u);
  } catch {}
}

function sendChat(text) {
  if (!text || !wsOk) return;
  ws.send(JSON.stringify({ type: 'chat', text }));
  $('#cap-user').textContent = '“' + text + '”';
}

$('#type-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.value.trim()) { sendChat(e.target.value.trim()); e.target.value = ''; }
});

// ---------- speech recognition + mic level ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, muted = false, audioCtx = null, analyser = null, micData = null;

function startRecognition() {
  if (!SR) { $('#cap-mizune').textContent = 'Speech recognition needs Chrome or Edge.'; return; }
  rec = new SR();
  rec.lang = 'en-IN';
  rec.continuous = true;
  rec.interimResults = true;
  rec.onresult = e => {
    let interim = '', final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      e.results[i].isFinal ? final += t : interim += t;
    }
    if (interim) $('#cap-user').textContent = interim;
    if (final.trim()) sendChat(final.trim());
  };
  rec.onend = () => { if (voiceOn && !muted) { try { rec.start(); } catch {} } };
  rec.onerror = ev => {
    if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
      $('#cap-mizune').textContent = 'Mic blocked here. Open this page in Edge or Chrome '
        + '(not Brave, not the embedded preview) → click the 🔒 padlock in the address bar → allow Microphone. '
        + 'Typing below still works!';
      endVoice();
    }
    if (ev.error === 'network') $('#cap-mizune').textContent = 'Speech service unreachable — this browser may block it (Brave does). Use Edge or Chrome.';
  };
  try { rec.start(); } catch {}
}

async function startMicMeter() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new AudioContext();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    micData = new Uint8Array(analyser.frequencyBinCount);
    startMicMeter._stream = stream;
  } catch { /* meter is optional */ }
}

function startVoice() {
  voiceOn = true; muted = false;
  $('#mute-btn').disabled = false; $('#end-btn').disabled = false;
  $('#mute-btn').textContent = '🎙 Mute';
  setState('listening');
  startRecognition();
  startMicMeter();
}

function endVoice() {
  voiceOn = false; muted = false;
  if (rec) { rec.onend = null; try { rec.stop(); } catch {} rec = null; }
  if (startMicMeter._stream) { startMicMeter._stream.getTracks().forEach(t => t.stop()); startMicMeter._stream = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; analyser = null; }
  $('#mute-btn').disabled = true; $('#end-btn').disabled = true;
  setState('idle');
}

$('#mute-btn').onclick = () => {
  muted = !muted;
  $('#mute-btn').textContent = muted ? '🔇 Unmute' : '🎙 Mute';
  if (muted) { try { rec && rec.stop(); } catch {} setState('muted'); }
  else { startRecognition(); setState('listening'); }
};
$('#end-btn').onclick = endVoice;

// ---------- cosmos canvas ----------
const canvas = $('#cosmos'), ctx = canvas.getContext('2d');
let W = 0, H = 0, CX = 0, CY = 0, DPR = 1;

function resize() {
  DPR = window.devicePixelRatio || 1;
  W = innerWidth; H = innerHeight;
  canvas.width = W * DPR; canvas.height = H * DPR;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  CX = W * 0.54; CY = H * 0.5;
}
addEventListener('resize', resize); resize();

// stars
const stars = Array.from({ length: 140 }, () => ({
  x: Math.random(), y: Math.random(), r: Math.random() * 1.1 + 0.2, tw: Math.random() * Math.PI * 2 }));

// build cluster geometry: hubs orbit the core, satellites orbit hubs
const hubs = CLUSTERS.map((c, i) => {
  const angle = (i / CLUSTERS.length) * Math.PI * 2 + Math.random() * 0.5;
  return {
    ...c,
    angle, dist: 0.28 + (i % 3) * 0.11 + Math.random() * 0.05,   // fraction of min(W,H)
    speed: (Math.random() * 0.04 + 0.02) * (i % 2 ? 1 : -1),
    size: 9 + Math.random() * 5, spin: Math.random() * Math.PI,
    sats: c.caps.map(() => ({
      a: Math.random() * Math.PI * 2, d: 26 + Math.random() * 52,
      s: (Math.random() * 0.5 + 0.25) * (Math.random() < 0.5 ? 1 : -1),
      r: 1.6 + Math.random() * 2.6,
    })),
  };
});

function drawDiamond(x, y, size, rot, color, alphaHalo) {
  ctx.save();
  ctx.translate(x, y); ctx.rotate(rot);
  ctx.globalAlpha = alphaHalo;
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(0, 0, size * 2.6, 0, Math.PI * 2); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.shadowColor = color; ctx.shadowBlur = 16;
  ctx.fillRect(-size / 2, -size / 2, size, size);
  ctx.restore();
}

let t0 = performance.now();
function frame(now) {
  const t = (now - t0) / 1000;

  // mic level (smoothed)
  if (analyser) {
    analyser.getByteFrequencyData(micData);
    let sum = 0; for (let i = 0; i < micData.length; i++) sum += micData[i];
    micLevel += ((sum / micData.length / 160) - micLevel) * 0.2;
  } else micLevel *= 0.95;

  ctx.clearRect(0, 0, W, H);

  // stars
  ctx.fillStyle = '#9fb8c8';
  for (const s of stars) {
    ctx.globalAlpha = 0.25 + 0.25 * Math.sin(t * 1.4 + s.tw);
    ctx.beginPath(); ctx.arc(s.x * W, s.y * H, s.r, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;

  const R = Math.min(W, H);

  // orbit rings
  ctx.strokeStyle = 'rgba(140,180,190,0.07)';
  for (const h of hubs) {
    ctx.beginPath(); ctx.ellipse(CX, CY, h.dist * R, h.dist * R * 0.86, 0.3, 0, Math.PI * 2); ctx.stroke();
  }

  // core pulse radius
  let pulse = 1 + Math.sin(t * 1.8) * 0.03;
  if (state === 'listening') pulse += micLevel * 0.5;
  if (state === 'speaking') pulse += Math.abs(Math.sin(t * 7)) * 0.22;
  if (state === 'thinking') pulse += Math.sin(t * 3.5) * 0.08;
  const coreR = R * 0.075 * pulse;

  // clusters
  for (const h of hubs) {
    h.angle += h.speed / 60;
    const hx = CX + Math.cos(h.angle) * h.dist * R;
    const hy = CY + Math.sin(h.angle) * h.dist * R * 0.86;

    // thread to core
    ctx.strokeStyle = 'rgba(150,200,205,0.10)';
    ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(CX, CY); ctx.stroke();

    // satellites
    for (const s of h.sats) {
      s.a += s.s / 60;
      const sx = hx + Math.cos(s.a) * s.d, sy = hy + Math.sin(s.a) * s.d * 0.8;
      ctx.strokeStyle = 'rgba(150,200,205,0.08)';
      ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(sx, sy); ctx.stroke();
      ctx.fillStyle = h.color;
      ctx.globalAlpha = 0.8;
      ctx.beginPath(); ctx.arc(sx, sy, s.r, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }

    drawDiamond(hx, hy, h.size, h.spin + t * 0.15, h.color, 0.10);
    ctx.fillStyle = 'rgba(190,220,225,0.55)';
    ctx.font = '9px "Segoe UI"'; ctx.textAlign = 'center';
    ctx.fillText(h.name.toUpperCase(), hx, hy + h.size * 2.6 + 12);
  }

  // core (drawn last, on top)
  const g = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR * 3.4);
  g.addColorStop(0, '#ffffff');
  g.addColorStop(0.25, theme.core);
  g.addColorStop(0.6, `rgba(${theme.glow},0.25)`);
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(CX, CY, coreR * 3.4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.shadowColor = theme.core; ctx.shadowBlur = 40;
  ctx.beginPath(); ctx.arc(CX, CY, coreR, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(5,20,20,0.85)';
  ctx.font = 'bold 10px "Segoe UI"'; ctx.textAlign = 'center';
  ctx.fillText('MIZUNE', CX, CY + 3);

  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// tap core (or anywhere near it) to start/stop
canvas.addEventListener('click', e => {
  const dx = e.clientX - CX, dy = e.clientY - CY;
  if (Math.hypot(dx, dy) < Math.min(W, H) * 0.14) voiceOn ? endVoice() : startVoice();
});

setState('idle');
