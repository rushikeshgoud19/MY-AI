/* Mizune PWA client.
 *
 * Honesty rule enforced throughout: connection state is derived ONLY from real
 * socket events. We never render "Connected" optimistically, and every failure
 * carries the reason we actually observed (close code, HTTP status, exception).
 *
 * Wire protocol (verified live against 40.123.215.32:8001 on 2026-08-01):
 *   send    {"type":"chat","text":"...","platform":"pwa"}
 *   receive {"type":"user_input","text","platform"}   echo of any client's input
 *           {"type":"status","text":"Thinking..."|"Idle"|...}
 *           {"type":"speak","text","emotion"}         her reply, one per sentence
 *           {"type":"state_update","payload":{valence,arousal}}
 *           {"type":"audio","b64","format":"mp3"}     ~250 KB, opt-in playback
 *           {"type":"mode"|"emotion_update"|"task_list"|...}
 * NOTE: the server BROADCASTS to every connected client, so traffic from his
 * laptop appears here too. We label anything not from this device.
 */
'use strict';

var BUILD = 'pwa-2026-08-01';
var DEFAULT_HOST = '40.123.215.32:8001';
var LS = { host: 'mizune_host', token: 'mizune_token', voice: 'mizune_voice' };
var PLATFORM = 'pwa';

/* ── element handles ─────────────────────────────────────────────────────── */
var $ = function (id) { return document.getElementById(id); };
var elLog = $('log'), elInput = $('input'), elSend = $('send');
var elDot = $('conn-dot'), elConn = $('conn-text'), elAct = $('activity');
var elBrain = $('v-brain'), elDevices = $('v-devices'), elProviders = $('v-providers');
var elVitalsReason = $('vitals-reason');
var elSheet = $('sheet'), elBackdrop = $('sheet-backdrop'), elResult = $('sheet-result');

/* ── settings ────────────────────────────────────────────────────────────── */
function host() {
  var saved = localStorage.getItem(LS.host);
  if (saved) return saved;
  // Served by the FastAPI backend itself? Then talk to our own origin.
  if (location.protocol.indexOf('http') === 0 &&
      location.hostname && location.hostname !== 'localhost' &&
      location.hostname !== '127.0.0.1') {
    return location.host;
  }
  return DEFAULT_HOST;
}
function token() { return (localStorage.getItem(LS.token) || '').trim(); }
function voiceOn() { return localStorage.getItem(LS.voice) === '1'; }
function secure() { return location.protocol === 'https:'; }
function httpBase() { return (secure() ? 'https://' : 'http://') + host(); }
function wsUrl() {
  var u = (secure() ? 'wss://' : 'ws://') + host() + '/ws';
  var t = token();
  return t ? u + '?key=' + encodeURIComponent(t) : u;
}

/* ── transcript ──────────────────────────────────────────────────────────── */
function looksPreformatted(t) {
  return /\n/.test(t) && (/ {3}/.test(t) || /\n\s{2}/.test(t));
}
function atBottom() {
  return elLog.scrollHeight - elLog.scrollTop - elLog.clientHeight < 90;
}
function bubble(cls, text, who) {
  var stick = atBottom();
  var d = document.createElement('div');
  d.className = 'msg ' + cls + (looksPreformatted(text) ? ' pre' : '');
  if (who) {
    var w = document.createElement('span');
    w.className = 'who'; w.textContent = who; d.appendChild(w);
  }
  d.appendChild(document.createTextNode(text));
  elLog.appendChild(d);
  if (stick) elLog.scrollTop = elLog.scrollHeight;
  return d;
}
function sysline(text, isErr) { bubble('sys' + (isErr ? ' err' : ''), text); }

/* ── connection state (single source of truth) ───────────────────────────── */
var ws = null;
var attempt = 0;              // consecutive failed connects
var retryTimer = null;
var gen = 0;                  // connection generation; stale sockets are ignored
var lastInboundAt = 0;
var hiddenSince = 0;
var awaitingReply = false;

var STATE = { DOWN: 'down', CONNECTING: 'mid', UP: 'up' };
function paint(state, text) {
  elDot.className = 'dot state-' + state;
  elConn.textContent = text;
  elConn.className = 'conn-text ' + (state === STATE.UP ? 'ok' : state === STATE.DOWN ? 'bad' : '');
  var live = state === STATE.UP;
  elSend.disabled = !live;
  var qs = document.querySelectorAll('.quick');
  for (var i = 0; i < qs.length; i++) qs[i].disabled = !live;
}
function activity(text) {
  if (!text) { elAct.hidden = true; elAct.textContent = ''; return; }
  elAct.hidden = false; elAct.textContent = text;
}

/* Human-readable cause for a socket close. 4001 is the server's auth reject. */
function closeReason(ev) {
  if (ev && ev.code === 4001) {
    return token()
      ? 'Rejected (4001): server refused this token. Check it in settings.'
      : 'Rejected (4001): server now requires a token. Add one in settings.';
  }
  if (ev && ev.code === 1006) return 'Dropped (1006): no clean close - network or server gone.';
  if (ev && ev.reason) return 'Closed (' + ev.code + '): ' + ev.reason;
  return 'Closed (' + (ev ? ev.code : '?') + ')';
}

function backoffMs() {
  var steps = [1000, 2000, 4000, 8000, 15000, 30000];
  return steps[Math.min(attempt, steps.length - 1)];
}

function connect() {
  clearTimeout(retryTimer);
  if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
  var myGen = ++gen;
  paint(STATE.CONNECTING, attempt === 0 ? 'Connecting to ' + host() : 'Reconnecting to ' + host());

  var sock;
  try {
    sock = new WebSocket(wsUrl());
  } catch (e) {
    attempt++;
    paint(STATE.DOWN, 'Cannot open socket: ' + (e && e.message ? e.message : e));
    scheduleRetry();
    return;
  }
  ws = sock;

  sock.onopen = function () {
    if (myGen !== gen) { try { sock.close(); } catch (e) {} return; }
    attempt = 0;
    lastInboundAt = Date.now();
    paint(STATE.UP, 'Connected' + (token() ? ' (token sent)' : ' (no token)'));
    refreshVitals();
  };

  sock.onmessage = function (ev) {
    if (myGen !== gen) return;               // superseded socket: ignore its traffic
    lastInboundAt = Date.now();
    var m;
    try { m = JSON.parse(ev.data); } catch (e) { return; }
    handle(m);
  };

  sock.onerror = function () {
    /* onerror carries no detail by spec; onclose reports the real reason. */
  };

  sock.onclose = function (ev) {
    // A socket we deliberately replaced must never be reported as a failure of
    // the current one - that was showing a phantom "Closed (1005)" on reconnect.
    if (myGen !== gen) return;
    ws = null;
    activity('');
    awaitingReply = false;
    // The strip must not keep showing the last brain/devices we happened to see.
    // Once the socket is gone those numbers are unverified, so stop asserting them.
    setVitalsUnknown('Vitals stale - not connected, so these cannot be checked.');
    attempt++;
    var why = closeReason(ev);
    if (ev && ev.code === 4001) {
      // Auth rejection: retrying at speed only spams the server. Slow right down.
      paint(STATE.DOWN, why);
      attempt = Math.max(attempt, 4);
    } else {
      paint(STATE.DOWN, why + ' Retry in ' + Math.round(backoffMs() / 1000) + 's.');
    }
    scheduleRetry();
  };
}

function scheduleRetry() {
  clearTimeout(retryTimer);
  var ms = backoffMs();
  retryTimer = setTimeout(connect, ms);
  // Count the wait down honestly rather than freezing on a stale number.
  var left = Math.round(ms / 1000);
  var tick = setInterval(function () {
    left--;
    if (left <= 0 || !retryTimer) { clearInterval(tick); return; }
    if (elDot.className.indexOf('state-down') >= 0 &&
        elConn.textContent.indexOf('Retry in ') >= 0) {
      elConn.textContent = elConn.textContent.replace(/Retry in \d+s\./, 'Retry in ' + left + 's.');
    }
  }, 1000);
}

function reconnectNow() {
  clearTimeout(retryTimer);
  attempt = 0;
  gen++;                                   // retires the old socket's callbacks
  if (ws) { try { ws.close(); } catch (e) {} ws = null; }
  connect();
}

/* ── inbound message handling ────────────────────────────────────────────── */
function handle(m) {
  switch (m.type) {
    case 'user_input':
      // Echo of *any* client's input. Ours is already on screen (optimistic
      // send is fine for our own text); label the ones from other devices.
      if (m.platform && m.platform !== PLATFORM) {
        bubble('me', m.text || '', 'from ' + m.platform);
      }
      break;

    case 'speak':
      awaitingReply = false;
      bubble('her', m.text || '');
      break;

    case 'status':
      var t = (m.text || '').trim();
      if (!t || /^idle$/i.test(t)) { activity(''); awaitingReply = false; }
      else { activity(t); }
      break;

    case 'audio':
      if (voiceOn() && m.b64) playAudio(m.b64, m.format || 'mp3');
      break;

    case 'state_update':
    case 'emotion_update':
    case 'mode':
    case 'task_list':
    case 'knowledge_graph_data':
      break;                                   // not surfaced in this client

    default:
      break;
  }
}

var audioEl = null;
function playAudio(b64, fmt) {
  try {
    if (!audioEl) audioEl = new Audio();
    audioEl.src = 'data:audio/' + (fmt === 'wav' ? 'wav' : 'mpeg') + ';base64,' + b64;
    var p = audioEl.play();
    if (p && p.catch) p.catch(function () { /* autoplay blocked until first tap */ });
  } catch (e) { /* never let audio break the chat */ }
}

/* ── outbound ────────────────────────────────────────────────────────────── */
function send(text) {
  text = (text || '').trim();
  if (!text) return;
  if (!ws || ws.readyState !== 1) {
    sysline('Not sent - socket is ' + connWord() + '. Your text is still in the box.', true);
    return;
  }
  try {
    ws.send(JSON.stringify({ type: 'chat', text: text, platform: PLATFORM }));
  } catch (e) {
    sysline('Send failed: ' + (e && e.message ? e.message : e), true);
    return;
  }
  bubble('me', text);
  awaitingReply = true;
  activity('Sent - waiting for her...');
  elInput.value = '';
  autosize();
  elLog.scrollTop = elLog.scrollHeight;
}
function connWord() {
  if (!ws) return 'disconnected';
  return ['connecting', 'open', 'closing', 'closed'][ws.readyState] || 'unknown';
}

/* ── vitals ──────────────────────────────────────────────────────────────── */
function setVitalsUnknown(reason) {
  elBrain.textContent = '--';
  elDevices.textContent = '--';
  elProviders.textContent = '--';
  elVitalsReason.hidden = false;
  elVitalsReason.textContent = reason;
}
function refreshVitals() {
  if (!token()) {
    setVitalsUnknown('Vitals need a token. Chat still works without one. Add it in settings.');
    return;
  }
  fetch(httpBase() + '/api/vitals', {
    headers: { 'X-Mizune-Key': token() },
    cache: 'no-store'
  }).then(function (r) {
    if (r.status === 401) throw new Error('401 - server rejected this token');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }).then(function (v) {
    elVitalsReason.hidden = true;
    var b = v.brain || {};
    elBrain.textContent = b.provider
      ? b.provider + (b.model ? ' / ' + b.model : '') + (b.tools ? ' (tools ' + b.tools + ')' : '')
      : 'unknown';
    var d = v.devices || [];
    elDevices.textContent = d.length ? d.join(', ') : 'none online';
    var p = v.providers || {};
    elProviders.textContent = (p.live != null ? p.live : '?') + '/' + (p.keyed != null ? p.keyed : '?') + ' live';
    var probs = v.problems || [];
    if (probs.length) {
      elVitalsReason.hidden = false;
      elVitalsReason.textContent = 'Problems: ' + probs.join('; ');
    }
  }).catch(function (e) {
    setVitalsUnknown('Vitals unavailable: ' + (e && e.message ? e.message : e));
  });
}

/* ── keyboard / viewport handling ────────────────────────────────────────── */
/* The on-screen keyboard shrinks visualViewport but not layout viewport, which
   is what normally buries the input. Translate the composer up by the delta. */
function syncKeyboard() {
  var vv = window.visualViewport;
  if (!vv) return;
  var kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
  document.documentElement.style.setProperty('--kb', kb + 'px');
  if (kb > 0) elLog.scrollTop = elLog.scrollHeight;
}
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', syncKeyboard);
  window.visualViewport.addEventListener('scroll', syncKeyboard);
}

function autosize() {
  elInput.style.height = 'auto';
  elInput.style.height = Math.min(elInput.scrollHeight, 130) + 'px';
}

/* ── background / screen-lock survival ───────────────────────────────────── */
document.addEventListener('visibilitychange', function () {
  if (document.hidden) { hiddenSince = Date.now(); return; }
  var away = hiddenSince ? Date.now() - hiddenSince : 0;
  hiddenSince = 0;

  if (!ws || ws.readyState !== 1) { reconnectNow(); return; }

  // Socket claims OPEN after a long background stretch. On mobile that claim is
  // often stale (half-open TCP). Verify against the server before trusting it.
  if (away > 20000) {
    paint(STATE.CONNECTING, 'Checking the connection after ' + Math.round(away / 1000) + 's away');
    fetch(httpBase() + '/health', { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        // Server is alive. If nothing has arrived while we were away and we are
        // not mid-reply, recycle the socket rather than trust a stale handle.
        if (!awaitingReply && Date.now() - lastInboundAt > away) reconnectNow();
        else { paint(STATE.UP, 'Connected' + (token() ? ' (token sent)' : ' (no token)')); refreshVitals(); }
      })
      .catch(function (e) {
        paint(STATE.DOWN, 'Server unreachable: ' + (e && e.message ? e.message : e));
        reconnectNow();
      });
  }
});
window.addEventListener('online', function () { reconnectNow(); });
window.addEventListener('offline', function () {
  paint(STATE.DOWN, 'Phone is offline - no network.');
});

/* ── settings sheet ──────────────────────────────────────────────────────── */
function openSheet() {
  $('f-host').value = localStorage.getItem(LS.host) || '';
  $('f-host').placeholder = host();
  $('f-token').value = token();
  $('f-voice').checked = voiceOn();
  $('build-line').textContent = BUILD + ' | target ' + host() + ' | token ' +
    (token() ? 'set (' + token().length + ' chars)' : 'not set');
  elResult.hidden = true;
  elSheet.hidden = false; elBackdrop.hidden = false;
}
function closeSheet() { elSheet.hidden = true; elBackdrop.hidden = true; }
function result(text, ok) {
  elResult.hidden = false;
  elResult.className = 'reason ' + (ok ? 'ok' : 'bad');
  elResult.textContent = text;
}

$('btn-settings').addEventListener('click', openSheet);
elBackdrop.addEventListener('click', closeSheet);
$('f-showtoken').addEventListener('change', function () {
  $('f-token').type = this.checked ? 'text' : 'password';
});
$('f-save').addEventListener('click', function () {
  var h = $('f-host').value.trim().replace(/^\w+:\/\//, '').replace(/\/+$/, '');
  if (h) localStorage.setItem(LS.host, h); else localStorage.removeItem(LS.host);
  var t = $('f-token').value.trim();
  if (t) localStorage.setItem(LS.token, t); else localStorage.removeItem(LS.token);
  localStorage.setItem(LS.voice, $('f-voice').checked ? '1' : '0');
  closeSheet();
  sysline('Settings saved. Reconnecting to ' + host() + (t ? ' with token.' : ' without a token.'));
  reconnectNow();
});
$('f-clear').addEventListener('click', function () {
  localStorage.removeItem(LS.token);
  $('f-token').value = '';
  result('Token cleared on this device. Chat keeps working while server auth is off.', true);
});
$('f-test').addEventListener('click', function () {
  var t = $('f-token').value.trim();
  if (!t) { result('No token entered.', false); return; }
  result('Testing against ' + httpBase() + '/api/vitals ...', true);
  fetch(httpBase() + '/api/vitals', { headers: { 'X-Mizune-Key': t }, cache: 'no-store' })
    .then(function (r) {
      if (r.status === 401) { result('Token REJECTED (401). Not saved yet - fix and save.', false); return null; }
      if (!r.ok) { result('Unexpected HTTP ' + r.status + '.', false); return null; }
      return r.json();
    })
    .then(function (v) {
      if (!v) return;
      result('Token accepted. Brain: ' + ((v.brain && v.brain.provider) || '?') +
             ', devices: ' + ((v.devices || []).join(', ') || 'none') + '.', true);
    })
    .catch(function (e) { result('Could not reach server: ' + (e && e.message ? e.message : e), false); });
});

/* ── input wiring ────────────────────────────────────────────────────────── */
elSend.addEventListener('click', function () { send(elInput.value); });
elInput.addEventListener('input', autosize);
elInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(elInput.value); }
});
var quicks = document.querySelectorAll('.quick');
for (var i = 0; i < quicks.length; i++) {
  quicks[i].addEventListener('click', function () { send(this.getAttribute('data-cmd')); });
}
elConn.addEventListener('click', function () {
  if (!ws || ws.readyState !== 1) reconnectNow();
});

/* ── boot ────────────────────────────────────────────────────────────────── */
if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
  navigator.serviceWorker.register('sw.js').catch(function () { /* offline shell is optional */ });
}
setVitalsUnknown('Vitals not loaded yet.');
sysline('Mizune PWA ' + BUILD + ' - target ' + host());
connect();
setInterval(refreshVitals, 30000);
autosize();
syncKeyboard();
