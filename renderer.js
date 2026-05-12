import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// Node built-ins in Electron
const { ipcRenderer } = window.require('electron');
const fs = window.require('fs');
const path = window.require('path');

const logFile = path.join(process.cwd(), 'renderer.log');
const lerp = (x, y, a) => x * (1 - a) + y * a;
const log = (msg) => {
    const timestamp = new Date().toISOString();
    try { fs.appendFileSync(logFile, `[${timestamp}] ${msg}\n`); } catch(e) {}
    console.log(msg);
};
window.onerror = (msg, url, line) => log(`ERROR: ${msg} at ${url}:${line}`);
log('Renderer started.');
const nowSeconds = () => Date.now() / 1000;

// ─── Config ──────────────────────────────────────────────────────────────────
const CONFIG_PATH = path.join(process.cwd(), 'config.json');
let cfg = {};
function loadCfg() {
    try { cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')); }
    catch(e) { cfg = {}; }
}
loadCfg();

// ─── Scene globals ────────────────────────────────────────────────────────────
let scene, camera, renderer, clock, currentVrm;
let cameraAdjusted = false;
let ws = null;
let reconnectTimer = null;
let isSpeaking = false;
let isSpeakingTimeout = null; // Safety: auto-reset isSpeaking if TTS hangs
let isWaving = false;
let isListening = false;
let waveStartTime = 0;

// Emotion system with smooth blending
let currentEmotion = 'neutral'; // Text-driven emotion
let currentMode = 'conversation';
let emotionTimer = 0;
let cameraEmotion = 'neutral';
let cameraEmotionAt = 0;
let activeEmotion = 'neutral';
const EMOTION_TEXT_WEIGHT = 0.6;
const EMOTION_CAMERA_WEIGHT = 0.4;
const EMOTION_CAMERA_TTL = 4.0;
let emotionBlends = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
let targetBlends  = { happy: 0.8, sad: 0, angry: 0, surprised: 0, relaxed: 0.2 };

// Blush system for Mizune
let blushIntensity = 0;
let targetBlush = 0.8;
let blushDecayTimer = 999999; // Never decay default blush
let shyTiltActive = false;
let shyTiltValue = 0;

// Blink system — independent of emotions
let blinkTimer = 0;
let blinkInterval = 3.5 + Math.random() * 2.5; // random 3.5–6s
let blinkValue = 0;
let isBlinking = false;
let blinkPhase = 0; // 0=closed, 1=open

// Lip sync with smooth interpolation
let audioAnalyzer = null;
let audioDataArray = null;
let micAnalyzer = null;
let micDataArray = null;
let micStream = null;
let micSource = null;
let micInitAttempted = false;
let micGateUntil = 0;
const MIC_GATE = 0.05;
const MIC_GATE_LISTENING = 0.02;
const MIC_GATE_HOLD = 0.25;
const MIC_BOOST = 1.2;
const LIP_SYNC_GATE = 0.03;
const TTS_GATE = 0.01;
let mouthVolume = 0;
let smoothMouthA = 0;
let smoothMouthOh = 0;

// Natural idle animation state
let idlePhaseOffset = Math.random() * Math.PI * 2;
let breathPhaseOffset = Math.random() * Math.PI * 2;
let hipSwayPhase = Math.random() * Math.PI * 2;

// Speaking head nod state
let speakNodTimer = 0;
let speakNodActive = false;
let speakNodValue = 0;

// Arm smooth targets — VRM bone axes:
// Upper arm Z = how far arm hangs from body (π/2 ≈ 1.57 = straight down)
// Upper arm X = forward/back swing
// Lower arm Y = forearm twist (supination/pronation)
// Lower arm Z = elbow bend
const armTargets = {
    leftUpperArm:  { x: 0.05, y: 0,     z:  1.55 },  // almost straight down, slight forward
    rightUpperArm: { x: 0.05, y: 0,     z: -1.55 },
    leftLowerArm:  { x: 0,    y: -0.2,  z:  0.08 },  // slight supination, barely bent
    rightLowerArm: { x: 0,    y:  0.2,  z: -0.08 },
    leftHand:      { x: 0.06, y: -0.08, z:  0.05 },
    rightHand:     { x: 0.06, y:  0.08, z: -0.05 },
    leftShoulder:  { x: 0,    y:  0.05, z:  0.2  },
    rightShoulder: { x: 0,    y: -0.05, z: -0.2  },
    // Thumbs excluded from lerp system — handled separately with safe values
};
const armCurrent = {};
for (const k of Object.keys(armTargets)) {
    armCurrent[k] = { ...armTargets[k] };
}

// ─── DOM References ───────────────────────────────────────────────────────────
const container = document.getElementById('container');
const statusEl = document.getElementById('status');
const responseBubble = document.getElementById('response-bubble');
const terminalContent = document.getElementById('terminal-content');
const chatInput = document.getElementById('chat-input');

// ─── Expose globals for inline onclick handlers ───────────────────────────────
window.toggleTerminal = toggleTerminal;
window.openSettings = openSettings;
window.sendTextMessage = sendTextMessage;

function setIgnoreMouse(ignore) {
    ipcRenderer.send('set-ignore-mouse', ignore);
}

function logTerminal(text, type = 'system') {
    if (!terminalContent) return;
    const line = document.createElement('div');
    line.className = `terminal-line terminal-${type}`;
    const prefix = type === 'user' ? 'You: ' : type === 'risse' ? `${cfg.character_name || 'Mizune'}: ` : type === 'emotion' ? '✦ ' : '> ';
    line.textContent = prefix + text;
    terminalContent.appendChild(line);
    terminalContent.scrollTop = terminalContent.scrollHeight;
}

// ─── Settings ─────────────────────────────────────────────────────────────────
function openSettings() {
    ipcRenderer.send('open-settings');
}

ipcRenderer.on('config-updated', (_event, newCfg) => {
    const oldFile = cfg.character_file;
    cfg = newCfg;
    if (newCfg.character_file !== oldFile) {
        log(`[CONFIG] Character changed to: ${newCfg.character_file}`);
        loadVRM(newCfg.character_file);
    }
});

// ─── Text Chat ────────────────────────────────────────────────────────────────
function sendTextMessage() {
    const text = chatInput ? chatInput.value.trim() : '';
    if (!text) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'chat', text }));
        logTerminal(text, 'user');
        chatInput.value = '';
    } else {
        logTerminal('Not connected to backend.', 'error');
    }
}

if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); sendTextMessage(); }
    });
}

// Click-through by default; Alt + click to interact
setIgnoreMouse(true);

function enableInteraction() {
    setIgnoreMouse(false);
    ipcRenderer.send('focus-window');
}

function disableInteractionIfIdle() {
    if (document.activeElement !== chatInput) {
        setIgnoreMouse(true);
    }
}

window.addEventListener('mousedown', (e) => {
    if (e.altKey) {
        enableInteraction();
    }
});

window.addEventListener('mouseup', (e) => {
    if (!e.altKey) {
        disableInteractionIfIdle();
    }
});

window.addEventListener('blur', () => {
    setIgnoreMouse(true);
});

if (chatInput) {
    chatInput.addEventListener('focus', () => setIgnoreMouse(false));
    chatInput.addEventListener('blur', () => setIgnoreMouse(true));
}

// ─── Alt+M Global Shortcut Handler ─────────────────────────────────────────────
// When user presses Alt+M anywhere on the system, main process sends this event.
// We enable interaction and focus the chat input so they can type immediately.
ipcRenderer.on('focus-chat-input', () => {
    log('[UI] Alt+M pressed — focusing chat input');
    enableInteraction();
    if (chatInput) {
        chatInput.focus();
        chatInput.scrollIntoView({ behavior: 'smooth' });
    }
});

// ─── Terminal Toggle ──────────────────────────────────────────────────────────
function toggleTerminal() {
    const terminal = document.getElementById('terminal-overlay');
    if (!terminal) return;
    const isHidden = window.getComputedStyle(terminal).display === 'none';
    terminal.style.display = isHidden ? 'flex' : 'none';
}

// ─── Drag-to-Move Disabled per User Request ────────────────────────────────────
let isDragging = false;

// ─── Audio Unlock (Fix C) ───────────────────────────────────────────────────
let audioCtx = null;
async function initMicLipSync() {
    if (micInitAttempted) return;
    micInitAttempted = true;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        log('[MIC] getUserMedia not available in this environment.');
        return;
    }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
        });
        micStream = stream;
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') await audioCtx.resume();
        micSource = audioCtx.createMediaStreamSource(stream);
        micAnalyzer = audioCtx.createAnalyser();
        micAnalyzer.fftSize = 256;
        micDataArray = new Uint8Array(micAnalyzer.frequencyBinCount);
        micSource.connect(micAnalyzer);
        log('[MIC] Lip-sync mic capture enabled.');
    } catch (e) {
        log('[MIC] Mic capture failed: ' + (e.message || e));
    }
}
async function resumeAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
        log('[AUDIO] Context resumed on user gesture.');
    }
    initMicLipSync().catch(e => log('[MIC] Init error: ' + (e.message || e)));
}

// Global unlock on any interaction
document.body.addEventListener('mousedown', () => {
    resumeAudio().catch(e => log('Audio resume failed: ' + e));
}, { once: true });

if (chatInput) {
    chatInput.addEventListener('focus', () => resumeAudio());
}

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
    log('Initializing Three.js scene...');
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(35.0, window.innerWidth / window.innerHeight, 0.1, 20.0);
    camera.position.set(0.0, 1.45, 0.70);
    camera.lookAt(0, 1.45, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.zIndex = '1';
    container.appendChild(renderer.domElement);

    // FIX FOR ELECTRON RESIZE RACE CONDITION
    let resizeTicks = 0;
    const resizeInterval = setInterval(() => {
        if (resizeTicks++ > 15) clearInterval(resizeInterval);
        if (window.innerWidth > 10 && camera && renderer) {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }
    }, 200);

    const ambientLight = new THREE.AmbientLight(0xffffff, 2.0);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
    directionalLight.position.set(0, 1, 1).normalize();
    scene.add(directionalLight);

    clock = new THREE.Clock();
    loadVRM(cfg.character_file || 'character/5816025470716354497.vrm');
    animate();
    connectWebSocket();
}

// ─── VRM Loading ──────────────────────────────────────────────────────────────
function loadVRM(vrmPath) {
    if (currentVrm) {
        scene.remove(currentVrm.scene);
        currentVrm = null;
    }
    // Reset animation state for new model
    emotionBlends = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
    targetBlends  = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0.2 };
    smoothMouthA = 0;
    smoothMouthOh = 0;
    blinkValue = 0;
    cameraAdjusted = false;

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser)); // ← CRITICAL LINE: ensures VRM features are parsed
    log(`[VRM] Loading: ${vrmPath}`);

    // Path is relative to index.html
    loader.load(
        vrmPath,
        (gltf) => {
            VRMUtils.removeUnnecessaryJoints(gltf.scene);
            const vrm = gltf.userData.vrm;
            if (!vrm) {
                log('[VRM] gltf loaded but no VRM data found');
                return;
            }
            vrm.scene.scale.set(1.0, 1.0, 1.0);
            vrm.scene.rotation.y = Math.PI;
            vrm.scene.position.set(0, 0, 0);
            scene.add(vrm.scene);
            currentVrm = vrm;
            log('[VRM] Model loaded and added to scene.');
        },
        (xhr) => {
            const pct = (xhr.loaded / xhr.total * 100).toFixed(1);
            log(`[VRM] Loading progress: ${pct}%`);
        },
        (error) => {
            log('[VRM] Critical Error loading model: ' + error.message);
            console.error('[VRM] Error:', error);
        }
    );
}

// ─── Smooth lerp helper ───────────────────────────────────────────────────────
function updateBlush(deltaTime) {
    blushIntensity = lerp(blushIntensity, targetBlush, deltaTime * 2.5);
    if (blushDecayTimer > 0) {
        blushDecayTimer -= deltaTime;
        if (blushDecayTimer <= 0) targetBlush = 0;
    }
    if (currentVrm && currentVrm.expressionManager) {
        const em = currentVrm.expressionManager;
        // Apply blush blendshape if available on the VRM model
        try { em.setValue('blush', blushIntensity); } catch(e) {}
    }
    // Update shy tilt based on blush
    shyTiltValue = lerp(shyTiltValue, blushIntensity * 0.5, deltaTime * 2.0);
}
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// ─── Blink System (independent, natural timing) ───────────────────────────────
function updateBlink(deltaTime) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const em = currentVrm.expressionManager;

    blinkTimer += deltaTime;

    if (!isBlinking) {
        if (blinkTimer >= blinkInterval) {
            isBlinking = true;
            blinkPhase = 0;
            blinkTimer = 0;
            // Randomize next blink interval: 2.5–7s
            blinkInterval = 2.5 + Math.random() * 4.5;
        }
    } else {
        // Close eye (0→1 in 0.06s), hold (6 frames), open (1→0 in 0.08s)
        const closeSpeed = deltaTime / 0.06;
        const openSpeed  = deltaTime / 0.08;
        if (blinkPhase === 0) {
            blinkValue = Math.min(blinkValue + closeSpeed, 1.0);
            if (blinkValue >= 1.0) { blinkPhase = 1; blinkTimer = 0; }
        } else if (blinkPhase === 1) {
            if (blinkTimer > 0.05) blinkPhase = 2;
        } else {
            blinkValue = Math.max(blinkValue - openSpeed, 0.0);
            if (blinkValue <= 0.0) { isBlinking = false; blinkValue = 0; }
        }
    }

    // Suppress blink if currently making an expression that closes eyes
    // (prevents geometry clipping/blinding effect when eyes are already closed)
    const suppressBlink = ['happy', 'smile', 'sleepy', 'blush', 'shy', 'excited'].includes(activeEmotion);
    const finalBlink = suppressBlink ? 0 : blinkValue;

    em.setValue('blink', finalBlink);
}

// ─── Emotion Blend System (smooth transitions) ────────────────────────────────
function normalizeEmotionName(raw) {
    const key = (raw || '').toString().toLowerCase();
    const map = {
        joy: 'happy',
        joyful: 'happy',
        cheerful: 'happy',
        surprise: 'surprised',
        curious: 'thinking',
    };
    return map[key] || key;
}

function emotionToBlend(emotion) {
    const blends = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
    let blush = 0;
    const e = normalizeEmotionName(emotion);

    if (e === 'happy')          { blends.happy = 1.0; }
    else if (e === 'blush')     { blends.happy = 0.6; blush = 1.0; }
    else if (e === 'smile')     { blends.happy = 0.7; blends.relaxed = 0.3; }
    else if (e === 'sad')       { blends.sad = 0.8; }
    else if (e === 'angry')     { blends.angry = 0.5; blends.sad = 0.2; }
    else if (e === 'surprised') { blends.surprised = 1.0; }
    else if (e === 'thinking')  { blends.happy = 0.15; blends.relaxed = 0.5; }
    else if (e === 'pout')      { blends.sad = 0.25; blends.angry = 0.2; }
    else if (e === 'excited')   { blends.happy = 1.0; blends.surprised = 0.3; }
    else if (e === 'shy')       { blends.happy = 0.4; blush = 1.0; }
    else if (e === 'sleepy')    { blends.relaxed = 0.8; blends.sad = 0.15; }
    else if (e === 'fear')      { blends.sad = 0.6; blends.surprised = 0.3; blends.relaxed = 0.1; }
    else if (e === 'disgust')   { blends.angry = 0.3; blends.sad = 0.2; }
    else                        { blends.relaxed = 0.2; }

    return { blends, blush, name: e };
}

function setTextEmotion(emotion, duration = 5.0) {
    const info = emotionToBlend(emotion);
    currentEmotion = info.name;
    emotionTimer = Math.max(0, duration);

    if (info.name === 'blush') { targetBlush = 1.0; blushDecayTimer = 6.0; }
    if (info.name === 'shy')   { targetBlush = 1.0; blushDecayTimer = 8.0; }
}

function applyBlendedEmotion(nowSec) {
    const textActive = currentEmotion !== 'neutral' && emotionTimer > 0;
    const cameraActive = cameraEmotion !== 'neutral' && (nowSec - cameraEmotionAt) <= EMOTION_CAMERA_TTL;

    let textWeight = textActive ? EMOTION_TEXT_WEIGHT : 0;
    let cameraWeight = cameraActive ? EMOTION_CAMERA_WEIGHT : 0;
    const total = textWeight + cameraWeight;

    if (total <= 0) {
        const neutral = emotionToBlend('neutral');
        for (const key of Object.keys(targetBlends)) {
            targetBlends[key] = neutral.blends[key];
        }
        activeEmotion = 'neutral';
        return;
    }

    textWeight /= total;
    cameraWeight /= total;

    const textBlend = emotionToBlend(currentEmotion);
    const camBlend = emotionToBlend(cameraEmotion);

    for (const key of Object.keys(targetBlends)) {
        targetBlends[key] = (textBlend.blends[key] * textWeight) + (camBlend.blends[key] * cameraWeight);
    }

    if (textActive && (textBlend.name === 'blush' || textBlend.name === 'shy')) {
        targetBlush = Math.max(targetBlush, 1.0);
    }

    activeEmotion = textActive ? textBlend.name : (cameraActive ? camBlend.name : 'neutral');
}

function setTargetEmotion(emotion) {
    const info = emotionToBlend(emotion);
    for (const key of Object.keys(targetBlends)) {
        targetBlends[key] = info.blends[key];
    }
    if (info.blush > 0) {
        targetBlush = info.blush;
        blushDecayTimer = info.name === 'shy' ? 8.0 : 6.0;
    }
}

function updateEmotionBlends(deltaTime) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const em = currentVrm.expressionManager;
    const blendSpeed = deltaTime * 3.0; // smooth over ~0.33s

    for (const key of Object.keys(emotionBlends)) {
        emotionBlends[key] = lerp(emotionBlends[key], targetBlends[key], Math.min(blendSpeed, 1.0));
        em.setValue(key, emotionBlends[key]);
    }
}

// ─── Lip Sync with multi-vowel frequency mapping ─────────────────────────────
let smoothMouthIh = 0;
let smoothMouthEe = 0;
let smoothMouthOu = 0;

function getBandsFromAnalyzer(analyzer, dataArray) {
    if (!analyzer || !dataArray) return null;
    analyzer.getByteFrequencyData(dataArray);
    const len = dataArray.length;

    let lowSum = 0, midSum = 0, highSum = 0;
    const lowEnd = Math.min(4, len);
    const midEnd = Math.min(10, len);
    const highEnd = Math.min(20, len);

    for (let i = 1; i < lowEnd; i++) lowSum += dataArray[i];
    for (let i = lowEnd; i < midEnd; i++) midSum += dataArray[i];
    for (let i = midEnd; i < highEnd; i++) highSum += dataArray[i];

    const low = lowSum / Math.max(1, lowEnd - 1) / 255;
    const mid = midSum / Math.max(1, midEnd - lowEnd) / 255;
    const high = highSum / Math.max(1, highEnd - midEnd) / 255;
    const volume = (low + mid + high) / 3;

    return { low, mid, high, volume };
}

function updateLipSync(deltaTime, time) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const em = currentVrm.expressionManager;
    const lerpSpeed = deltaTime * 14.0; // smooth but responsive

    const ttsBands = getBandsFromAnalyzer(audioAnalyzer, audioDataArray);
    const micBandsRaw = getBandsFromAnalyzer(micAnalyzer, micDataArray);
    const nowSec = nowSeconds();
    let micBands = null;
    let micVolume = 0;

    if (micBandsRaw) {
        const boosted = {
            low: micBandsRaw.low * MIC_BOOST,
            mid: micBandsRaw.mid * MIC_BOOST,
            high: micBandsRaw.high * MIC_BOOST,
            volume: micBandsRaw.volume * MIC_BOOST,
        };
        const threshold = isListening ? MIC_GATE_LISTENING : MIC_GATE;
        if (boosted.volume > threshold) {
            micGateUntil = nowSec + MIC_GATE_HOLD;
        }
        if (boosted.volume > threshold || nowSec < micGateUntil) {
            micBands = boosted;
            micVolume = boosted.volume;
        }
    }

    const hasTtsAnalyzer = !!ttsBands;
    const ttsVolume = ttsBands ? ttsBands.volume : 0;
    const ttsActive = hasTtsAnalyzer && ttsVolume > TTS_GATE;
    let lowBand = 0, midBand = 0, highBand = 0, rawVolume = 0;
    let useFallback = false;

    if (!ttsActive && !micBands) {
        if (isSpeaking && !hasTtsAnalyzer) {
            useFallback = true;
        } else {
            mouthVolume   = 0;
            smoothMouthA  = lerp(smoothMouthA,  0, Math.min(lerpSpeed, 1.0));
            smoothMouthOh = lerp(smoothMouthOh, 0, Math.min(lerpSpeed, 1.0));
            smoothMouthIh = lerp(smoothMouthIh, 0, Math.min(lerpSpeed, 1.0));
            smoothMouthEe = lerp(smoothMouthEe, 0, Math.min(lerpSpeed, 1.0));
            smoothMouthOu = lerp(smoothMouthOu, 0, Math.min(lerpSpeed, 1.0));
            em.setValue('aa', smoothMouthA);
            em.setValue('oh', smoothMouthOh);
            em.setValue('ih', smoothMouthIh);
            em.setValue('ee', smoothMouthEe);
            em.setValue('ou', smoothMouthOu);

            if (!isSpeaking && smoothMouthA < 0.01 && smoothMouthOh < 0.01 && smoothMouthIh < 0.01) {
                audioAnalyzer = null;
            }
            return;
        }
    }

    if (useFallback) {
        rawVolume = 0.12
            + 0.12 * Math.sin(time * 18.0)
            + 0.06 * Math.sin(time * 31.0 + 1.2)
            + 0.03 * Math.sin(time * 47.0 + 2.4);
        lowBand  = 0.15 + 0.15 * Math.sin(time * 14.0);
        midBand  = 0.12 + 0.12 * Math.sin(time * 22.0 + 0.8);
        highBand = 0.08 + 0.10 * Math.sin(time * 35.0 + 1.5);
    } else {
        const ttsWeight = ttsActive ? ttsVolume : 0;
        const micWeight = micBands ? micVolume : 0;
        const total = ttsWeight + micWeight;
        const wTts = total > 0 ? ttsWeight / total : 0;
        const wMic = total > 0 ? micWeight / total : 0;

        lowBand  = (ttsBands ? ttsBands.low : 0) * wTts + (micBands ? micBands.low : 0) * wMic;
        midBand  = (ttsBands ? ttsBands.mid : 0) * wTts + (micBands ? micBands.mid : 0) * wMic;
        highBand = (ttsBands ? ttsBands.high : 0) * wTts + (micBands ? micBands.high : 0) * wMic;
        rawVolume = clamp(total, 0, 1);
    }

    if (!isSpeaking && !micBands && rawVolume < LIP_SYNC_GATE) {
        mouthVolume = 0;
        smoothMouthA  = lerp(smoothMouthA,  0, Math.min(lerpSpeed, 1.0));
        smoothMouthOh = lerp(smoothMouthOh, 0, Math.min(lerpSpeed, 1.0));
        smoothMouthIh = lerp(smoothMouthIh, 0, Math.min(lerpSpeed, 1.0));
        smoothMouthEe = lerp(smoothMouthEe, 0, Math.min(lerpSpeed, 1.0));
        smoothMouthOu = lerp(smoothMouthOu, 0, Math.min(lerpSpeed, 1.0));
        em.setValue('aa', smoothMouthA);
        em.setValue('oh', smoothMouthOh);
        em.setValue('ih', smoothMouthIh);
        em.setValue('ee', smoothMouthEe);
        em.setValue('ou', smoothMouthOu);
        return;
    }

    mouthVolume = clamp(rawVolume, 0, 1);

    const targetA  = clamp(lowBand * 1.1, 0, 0.45);
    const targetOh = clamp(lowBand * 0.5 - highBand * 0.2, 0, 0.35);
    const targetIh = clamp(midBand * 1.0 - lowBand * 0.3, 0, 0.30);
    const targetEe = clamp(highBand * 1.2 - lowBand * 0.3, 0, 0.35);
    const targetOu = clamp(midBand * 0.6 + lowBand * 0.2 - highBand * 0.3, 0, 0.25);

    const micro = 0.03 * Math.sin(time * 25.0 + 0.7);

    smoothMouthA  = lerp(smoothMouthA,  targetA + micro,  Math.min(lerpSpeed, 1.0));
    smoothMouthOh = lerp(smoothMouthOh, targetOh,         Math.min(lerpSpeed * 0.8, 1.0));
    smoothMouthIh = lerp(smoothMouthIh, targetIh,         Math.min(lerpSpeed * 0.9, 1.0));
    smoothMouthEe = lerp(smoothMouthEe, targetEe,         Math.min(lerpSpeed * 0.7, 1.0));
    smoothMouthOu = lerp(smoothMouthOu, targetOu,         Math.min(lerpSpeed * 0.7, 1.0));

    em.setValue('aa', smoothMouthA);
    em.setValue('oh', smoothMouthOh);
    em.setValue('ih', smoothMouthIh);
    em.setValue('ee', smoothMouthEe);
    em.setValue('ou', smoothMouthOu);
}

// ─── Animation Loop ───────────────────────────────────────────────────────────
let fpsInterval = 1000 / 30; // 30 FPS cap
let lastFrameTime = performance.now();

function animate() {
    requestAnimationFrame(animate);
    
    const now = performance.now();
    const elapsed = now - lastFrameTime;
    if (elapsed < fpsInterval) return;
    lastFrameTime = now - (elapsed % fpsInterval);

    const deltaTime = clock.getDelta();

    if (currentVrm) {
        const time = clock.elapsedTime;
        const humanoid = currentVrm.humanoid;

        currentVrm.update(deltaTime);

        // ── Emotion decay ──
        if (currentEmotion !== 'neutral') {
            emotionTimer -= deltaTime;
            if (emotionTimer <= 0) {
                currentEmotion = 'neutral';
            }
        }

        // ── Independent blink ──
        updateBlink(deltaTime);

        // ── Emotion blends ──
        applyBlendedEmotion(nowSeconds());
        updateEmotionBlends(deltaTime);
        updateBlush(deltaTime);

        // ── Special emotion animations ──
        // Thinking: curious head tilt
        if (activeEmotion === 'thinking') {
            const thinkTilt = 0.12 * Math.sin(time * 0.5);
            if (humanoid.getRawBoneNode('head')) {
                humanoid.getRawBoneNode('head').rotation.z += thinkTilt;
            }
        }
        // Sleepy: gentle head droop
        if (activeEmotion === 'sleepy') {
            const droopAmount = 0.06 + 0.03 * Math.sin(time * 0.3);
            if (humanoid.getRawBoneNode('head')) {
                humanoid.getRawBoneNode('head').rotation.x += droopAmount;
            }
        }
        // Excited: subtle bounce via spine
        if (activeEmotion === 'excited') {
            const bounceVal = Math.abs(Math.sin(time * 6.0)) * 0.008;
            if (humanoid.getRawBoneNode('spine')) {
                humanoid.getRawBoneNode('spine').position.y += bounceVal;
            }
        }

        // ── Lip sync ──
        updateLipSync(deltaTime, time);

        // ── Vision Mode Framing ──
        // Ensure she doesn't tilt or move out of the tiny 150x150 frame during thinking/vision
        if (currentMode === 'vision' || currentMode === 'coding') {
            const head = humanoid.getRawBoneNode('head');
            if (head) {
                // Clamp extreme tilts that might push her out of frame
                head.rotation.x = clamp(head.rotation.x, -0.2, 0.2);
                head.rotation.z = clamp(head.rotation.z, -0.2, 0.2);
            }
        }

        // ── Breathing (chest + shoulders rise) ──
        const breathe = 0.018 * Math.sin(time * 1.4 + breathPhaseOffset)
                       + 0.006 * Math.sin(time * 2.8 + breathPhaseOffset); // slight double-breath
        const chest = humanoid.getRawBoneNode('chest');
        if (chest) {
            chest.rotation.x = breathe;
            chest.rotation.z = 0.006 * Math.sin(time * 0.7 + breathPhaseOffset);
        }
        const spine = humanoid.getRawBoneNode('spine');
        if (spine) {
            spine.rotation.x = breathe * 0.4;
        }

        // ── Idle body sway (hips) ──
        const hipSwayX = 0.008 * Math.sin(time * 0.55 + hipSwayPhase);
        const hipSwayZ = 0.005 * Math.cos(time * 0.38 + hipSwayPhase + 0.8);
        const hips = humanoid.getRawBoneNode('hips');
        if (hips) {
            hips.rotation.z = hipSwayZ;
            hips.rotation.x = hipSwayX * 0.3;
        }

        // ── Head movement ──
        const head = humanoid.getRawBoneNode('head');
        if (head) {
            let headY, headZ, headX;
            if (isSpeaking) {
                // More expressive head movement while speaking
                headY = 0.12 * Math.sin(time * 1.3 + idlePhaseOffset)
                       + 0.04 * Math.sin(time * 2.7 + idlePhaseOffset + 0.5);
                headZ = 0.07 * Math.cos(time * 1.6 + idlePhaseOffset)
                       + 0.02 * Math.cos(time * 3.1 + idlePhaseOffset + 1.0);
                // Speaking nod: gentle downward nod
                speakNodTimer += deltaTime;
                if (!speakNodActive && speakNodTimer > 1.2 + Math.random() * 1.5) {
                    speakNodActive = true;
                    speakNodTimer = 0;
                }
                if (speakNodActive) {
                    speakNodValue = Math.min(speakNodValue + deltaTime * 4, 1.0);
                    if (speakNodValue >= 1.0) { speakNodActive = false; }
                } else {
                    speakNodValue = Math.max(speakNodValue - deltaTime * 3, 0.0);
                }
                headX = 0.04 * Math.sin(speakNodValue * Math.PI); // nod arc
            } else {
                headY = 0.05 * Math.sin(time * 0.9 + idlePhaseOffset)
                       + 0.02 * Math.sin(time * 2.1 + idlePhaseOffset + 1.3);
                headZ = 0.03 * Math.cos(time * 1.1 + idlePhaseOffset)
                       + 0.01 * Math.cos(time * 2.3 + idlePhaseOffset + 0.7);
                headX = 0;
                speakNodTimer = 0;
                speakNodValue = Math.max(speakNodValue - deltaTime * 3, 0.0);
            }
            head.rotation.y = headY;
            head.rotation.z = headZ + shyTiltValue * 0.12; // shy tilt when blushing
            head.rotation.x = headX + shyTiltValue * 0.06; // slight downward look when shy
        }

        // ── Absolute Magnetic Camera Lock (Eye-Level) ──
        const headNode = humanoid.getRawBoneNode('head');
        if (headNode) {
            const headPos = new THREE.Vector3();
            headNode.getWorldPosition(headPos);
            // Ignore (0,0,0) before skeleton loads completely
            if (headPos.y > 0.5) {
                // Eye-Level gaze at exact head height, pulled back to Z=0.65 to fit shoulders
                camera.position.set(headPos.x, headPos.y + 0.05, headPos.z + 0.70);
                camera.lookAt(headPos.x, headPos.y - 0.05, headPos.z);
            }
        }

        // ── Neck subtle tilt ──
        const neck = humanoid.getRawBoneNode('neck');
        if (neck) {
            neck.rotation.z = 0.015 * Math.sin(time * 0.6 + idlePhaseOffset + 1.5);
        }

        // ── Eye tracking (slow, natural drift) ──
        if (currentVrm.lookAt) {
            const eyeX = 0.6 * Math.sin(time * 0.35 + idlePhaseOffset)
                        + 0.2 * Math.sin(time * 0.9 + idlePhaseOffset + 2.1);
            const eyeY = 0.25 * Math.cos(time * 0.22 + idlePhaseOffset)
                        + 0.08 * Math.cos(time * 0.6 + idlePhaseOffset + 1.0);
            currentVrm.lookAt.lookAt(new THREE.Vector3(eyeX, eyeY, 15.0));
        }

        // ── Arm animation — smooth lerp targets, no hard snapping ──
        const breathLift = 0.012 * Math.sin(time * 1.4 + breathPhaseOffset);
        const hipZ = hipSwayZ; // reuse from hips above

        if (isWaving) {
            const waveElapsed = time - waveStartTime;
            const waveDuration = 5.0;  // Longer, more visible wave
            if (waveElapsed > waveDuration) {
                isWaving = false;
            } else {
                const rawRaise = Math.min(waveElapsed / 0.3, 1.0);  // Faster arm raise
                const rawLower = Math.max((waveElapsed - (waveDuration - 0.6)) / 0.6, 0.0);
                const easeIn  = rawRaise * rawRaise * (3 - 2 * rawRaise);
                const easeOut = 1.0 - (rawLower * rawLower * (3 - 2 * rawLower));
                const armUp   = easeIn * easeOut;
                // Bigger, more energetic wave motion
                const wave1   = Math.sin(waveElapsed * 8.0) * 0.55;
                const wave2   = Math.sin(waveElapsed * 5.0 + 0.9) * 0.25;
                const waveAngle = (wave1 + wave2) * armUp;
                // Right arm raises high, bends elbow hard, sways for visible wave
                armTargets.rightUpperArm = { x: 0.3 * (1 - armUp) - waveAngle * 0.9, y: 0.35 * armUp, z: -1.55 + 1.45 * armUp };
                armTargets.rightLowerArm = { x: 0, y: 0.25 * (1 - armUp), z: -0.08 - 1.6 * armUp };
                armTargets.rightHand     = { x: 0.12 * armUp, y: 0.15 * armUp, z: -0.05 + waveAngle * 0.6 };
                // Left arm hangs naturally
                armTargets.leftUpperArm  = { x: 0.05, y: -0.04 * armUp, z: 1.55 + breathLift };
                armTargets.leftLowerArm  = { x: 0, y: -0.2, z: 0.08 };
                armTargets.leftHand      = { x: 0.06, y: -0.08, z: 0.05 };
            }
        } else {
            // Idle: arms hang at sides, driven by breath + hip sway
            const idleSway = 0.01 * Math.sin(time * 0.75 + idlePhaseOffset);
            armTargets.leftUpperArm  = { x: 0.05, y: -hipZ * 0.3, z:  1.55 + breathLift + idleSway };
            armTargets.rightUpperArm = { x: 0.05, y:  hipZ * 0.3, z: -1.55 - breathLift - idleSway };
            armTargets.leftLowerArm  = { x: 0, y: -0.2 + 0.015 * Math.sin(time * 0.5 + idlePhaseOffset), z:  0.08 };
            armTargets.rightLowerArm = { x: 0, y:  0.2 - 0.015 * Math.sin(time * 0.5 + idlePhaseOffset), z: -0.08 };
            armTargets.leftHand      = { x: 0.06, y: -0.08 + 0.01 * Math.sin(time * 0.8), z:  0.05 };
            armTargets.rightHand     = { x: 0.06, y:  0.08 - 0.01 * Math.sin(time * 0.8), z: -0.05 };
        }

        // Lerp all arm bones toward targets
        const armSpeed = Math.min(deltaTime * (isWaving ? 12.0 : 6.0), 1.0);  // Faster during wave
        for (const [boneName, target] of Object.entries(armTargets)) {
            const bone = humanoid.getRawBoneNode(boneName);
            if (!bone) continue;
            const cur = armCurrent[boneName];
            cur.x = lerp(cur.x, target.x, armSpeed);
            cur.y = lerp(cur.y, target.y, armSpeed);
            cur.z = lerp(cur.z, target.z, armSpeed);
            bone.rotation.set(cur.x, cur.y, cur.z);
        }

        // ── Fingers: proximal curl + per-finger micro-animation ──
        const fingerDefs = [
            { name: 'leftIndexProximal',   baseZ:  0.30, side:  1 },
            { name: 'leftMiddleProximal',  baseZ:  0.32, side:  1 },
            { name: 'leftRingProximal',    baseZ:  0.28, side:  1 },
            { name: 'leftLittleProximal',  baseZ:  0.25, side:  1 },
            { name: 'rightIndexProximal',  baseZ:  0.30, side: -1 },
            { name: 'rightMiddleProximal', baseZ:  0.32, side: -1 },
            { name: 'rightRingProximal',   baseZ:  0.28, side: -1 },
            { name: 'rightLittleProximal', baseZ:  0.25, side: -1 },
        ];
        fingerDefs.forEach(({ name, baseZ, side }, i) => {
            const bone = humanoid.getRawBoneNode(name);
            if (bone) {
                const micro = 0.03 * Math.sin(time * 0.45 + i * 0.85 + idlePhaseOffset);
                bone.rotation.z = side * (baseZ + micro);
                bone.rotation.x = 0.08 + 0.015 * Math.sin(time * 0.3 + i * 0.5);
            }
        });

        // ── Thumbs — VRM thumb local axis is very different, keep small safe values ──
        const lThumb = humanoid.getRawBoneNode('leftThumbProximal');
        if (lThumb) { lThumb.rotation.set(0.2, 0.3, 0.15); }
        const rThumb = humanoid.getRawBoneNode('rightThumbProximal');
        if (rThumb) { rThumb.rotation.set(0.2, -0.3, -0.15); }

    }

    renderer.render(scene, camera);
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

    ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => {
        log('[WS] Connected.');
        const charName = cfg.character_name || 'Mizune';
        statusEl.textContent = `Connected! Say "${charName}" or press F2.`;
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }

        setTimeout(() => {
            // Greeting is now handled dynamically by the CameraAgent when it sees the user
            if (statusEl) statusEl.textContent = `Say "${charName}" or press F2.`;
        }, 1000);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'speak') {
            hideTypingIndicator();
            const cleanText = (msg.text || '')
                .replace(/\[EMOTION:.*?\]/gi, '')
                .replace(/\[ACTION:.*?\]/gi, '')
                .trim();
            // Defer text + lips until audio actually starts
            playTTS(cleanText, () => {
                showResponse(cleanText);
                logTerminal(cleanText, 'risse');
            });
            // Reset status light back to idle when response arrives
            const indicator = document.getElementById('status-indicator');
            if (indicator) {
                indicator.style.backgroundColor = 'rgba(255,255,255,0.2)';
                indicator.style.boxShadow = 'none';
            }
            const charName = cfg.character_name || 'Mizune';
            if (statusEl) statusEl.textContent = `Say "${charName}" or press F2.`;
        }

        if (msg.type === 'user_input') {
            logTerminal(msg.text, 'user');
        }

        if (msg.type === 'emotion') {
            const normalized = normalizeEmotionName(msg.emotion);
            setTextEmotion(normalized, 5.0);
            logTerminal(`Emotion detected: ${normalized}`, 'emotion');
        }

        if (msg.type === 'config_reloaded') {
            loadCfg();
            if (msg.character_file && msg.character_file !== (cfg.character_file || '')) {
                loadVRM(msg.character_file);
            }
        }

        if (msg.type === 'mode') {
            currentMode = msg.mode;
            const modeColors = {
                conversation: '#a777e3',
                writing: '#4ecdc4',
                focus: '#ff6b6b',
                entertainment: '#ffd93d',
                research: '#6bcb77',
                system: '#4d96ff',
                coding: '#00d4ff',
                vision: '#ff6ec7',
                calibration: '#a777e3',
            };
            const color = modeColors[msg.mode] || '#a777e3';
            const indicator = document.getElementById('status-indicator');
            if (indicator && msg.mode !== 'conversation') {
                indicator.style.backgroundColor = color;
                indicator.style.boxShadow = `0 0 10px ${color}`;
            }
            logTerminal(`Mode: ${msg.mode.toUpperCase()}`, 'system');

            // Handle Vision Indicator
            const vIndicator = document.getElementById('vision-indicator');
            if (vIndicator) {
                if (msg.mode === 'vision' || msg.mode === 'coding') {
                    vIndicator.classList.remove('hidden');
                } else {
                    vIndicator.classList.add('hidden');
                }
            }
        }

        if (msg.type === 'vision_update') {
            const vText = document.getElementById('vision-text');
            if (vText) vText.innerText = `SCANNING: ${msg.count || 0}`;
        }

        if (msg.type === 'emotion_track') {
            const emojiMap = {
                happy: '😊', sad: '😢', angry: '😠', fear: '😨',
                surprise: '😲', surprised: '😲', disgust: '🤢', neutral: '😐'
            };
            const colorMap = {
                happy: 'rgba(46, 204, 113, 0.4)', sad: 'rgba(52, 152, 219, 0.4)',
                angry: 'rgba(231, 76, 60, 0.4)', fear: 'rgba(155, 89, 182, 0.4)',
                surprise: 'rgba(241, 196, 15, 0.4)', surprised: 'rgba(241, 196, 15, 0.4)',
                disgust: 'rgba(39, 174, 96, 0.4)',
                neutral: 'rgba(167, 119, 227, 0.35)'
            };
            const hudEmoji = document.getElementById('emotion-hud-emoji');
            const hudLabel = document.getElementById('emotion-hud-label');
            const hud = document.getElementById('emotion-hud');
            const normalized = normalizeEmotionName(msg.emotion);
            cameraEmotion = normalized || 'neutral';
            cameraEmotionAt = nowSeconds();
            if (hudEmoji) hudEmoji.textContent = emojiMap[msg.emotion] || emojiMap[normalized] || '😐';
            if (hudLabel) hudLabel.textContent = normalized || 'neutral';
            if (hud) hud.style.borderColor = colorMap[msg.emotion] || colorMap[normalized] || colorMap.neutral;
        }

        if (msg.type === 'status') {
            const indicator = document.getElementById('status-indicator');
            if (indicator) {
                if (msg.text === 'Triggered') {
                    // Wake word detected — magenta glow
                    indicator.style.backgroundColor = '#ff00c8';
                    indicator.style.boxShadow = '0 0 14px #ff00c8';
                } else if (msg.text === 'Listening...') {
                    // Wake listener active — sapphire glow
                    indicator.style.backgroundColor = '#0f52ba';
                    indicator.style.boxShadow = '0 0 12px #0f52ba';
                } else if (msg.text === 'Processing...' || msg.text === 'Thinking...') {
                    indicator.style.backgroundColor = '#ffcc00';
                    indicator.style.boxShadow = '0 0 8px #ffcc00';
                    showTypingIndicator();
                } else if (msg.text === 'CALIBRATING (Talk to me...)') {
                    indicator.style.backgroundColor = '#a777e3';
                    indicator.style.boxShadow = '0 0 20px #a777e3';
                    showTypingIndicator();
                } else if (msg.text.toLowerCase().includes('installing') || msg.text.toLowerCase().includes('searching') || msg.text.toLowerCase().includes('processing')) {
                    // Active Work Status
                    indicator.style.backgroundColor = '#00ccff';
                    indicator.style.boxShadow = '0 0 8px #00ccff';
                    showTypingIndicator();
                    if (statusEl) statusEl.textContent = msg.text;
                } else {
                    indicator.style.backgroundColor = 'rgba(255,255,255,0.2)';
                    indicator.style.boxShadow = 'none';
                    hideTypingIndicator();
                }
            }
        }

        if (msg.type === 'listening_start') {
            isListening = true;
            setTextEmotion('surprised', 10.0); // Stay in this state until listening stops
            if (statusEl) {
                statusEl.classList.add('listening');
                statusEl.textContent = "Listening... (I can hear you!)";
            }
        }

        if (msg.type === 'listening_stop') {
            isListening = false;
            if (currentEmotion === 'surprised') {
                setTextEmotion('neutral', 0);
            }
            if (statusEl) {
                statusEl.classList.remove('listening');
                statusEl.textContent = `Say "${cfg.character_name || 'Mizune'}" or press F2.`;
            }
        }
    };

    ws.onclose = () => {
        log('[WS] Disconnected. Reconnecting in 3s...');
        if (statusEl) statusEl.textContent = 'Reconnecting...';
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => { reconnectTimer = null; connectWebSocket(); }, 3000);
        }
    };

    ws.onerror = (err) => log('[WS] Error: ' + (err.message || 'connection failed'));
}

// ─── Typing Indicator ─────────────────────────────────────────────────────────
let typingEl = null;

function showTypingIndicator() {
    if (typingEl) return; // already showing
    typingEl = document.createElement('div');
    typingEl.id = 'typing-indicator';
    typingEl.innerHTML = `${cfg.character_name || 'Mizune'} is thinking<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>`;
    // Style it like the response bubble
    Object.assign(typingEl.style, {
        maxWidth: '90%',
        background: 'rgba(20, 20, 35, 0.88)',
        color: 'rgba(167, 119, 227, 0.8)',
        padding: '8px 14px',
        borderRadius: '14px',
        fontSize: '11px',
        textAlign: 'center',
        border: '1px solid rgba(110, 142, 251, 0.3)',
        backdropFilter: 'blur(10px)',
        fontStyle: 'italic',
        pointerEvents: 'none',
    });
    const overlay = document.getElementById('ui-overlay');
    if (overlay) overlay.insertBefore(typingEl, responseBubble);
}

function hideTypingIndicator() {
    if (typingEl) {
        typingEl.remove();
        typingEl = null;
    }
}

function showResponse(text) {
    const cleanText = text
        .replace(/\[EMOTION:.*?\]/gi, '')
        .replace(/\[ACTION:.*?\]/gi, '')
        .trim();
    responseBubble.classList.remove('hidden');
    responseBubble.textContent = '';
    // Typewriter effect
    clearTimeout(responseBubble._hideTimer);
    clearInterval(responseBubble._typeTimer);
    let i = 0;
    const speed = Math.max(18, Math.min(40, Math.round(20000 / Math.max(cleanText.length, 1)))); // adaptive speed
    responseBubble._typeTimer = setInterval(() => {
        if (i < cleanText.length) {
            responseBubble.textContent += cleanText[i++];
        } else {
            clearInterval(responseBubble._typeTimer);
            // Auto-hide: ~1s per 15 chars, clamped 5s–20s
            const duration = Math.max(5000, Math.min(20000, cleanText.length * 65));
            responseBubble._hideTimer = setTimeout(() => responseBubble.classList.add('hidden'), duration);
        }
    }, speed);
}

// ─── TTS Voice Cache — EXACT Short Phrases Only (Free, Instant) ──────────────
// ONLY exact, very short phrases use free browser TTS.
// Everything else goes through paid APIs for quality voice.
const CACHED_PHRASES = new Set([
    'hai', 'hai~', 'hai!',
    'yes master', 'yes master!', 'yes goshujin-sama',
    'got it', 'got it!',
    'on it', 'on it!',
    'right away', 'right away!',
    'of course', 'of course!',
    'arigatou', 'arigatou!', 'arigatou gozaimasu',
    'gomen', 'gomen ne',
    'sugoi', 'sugoi!',
    'wakarimashita',
]);

function isCachedPhrase(text) {
    // ONLY exact matches on very short phrases (under 25 chars)
    const normalized = text.toLowerCase().trim().replace(/[~✦💫🎵❤️]/g, '').trim();
    if (normalized.length > 25) return false;  // Anything long → use real TTS
    return CACHED_PHRASES.has(normalized);
}

// ─── TTS — Cache → ElevenLabs → Murf → Browser ──────────────────────────────
let murfApiFailed = false;
let elevenApiFailed = false;

async function playTTS(text, onAudioStart = null) {
    if (isSpeaking) return;
    const fireStart = () => { if (onAudioStart) onAudioStart(); };

    // Safety: auto-reset isSpeaking after 30s in case onended never fires
    if (isSpeakingTimeout) clearTimeout(isSpeakingTimeout);
    isSpeakingTimeout = setTimeout(() => {
        if (isSpeaking) {
            log('[TTS] Safety timeout: resetting isSpeaking after 30s');
            isSpeaking = false;
        }
    }, 30000);

    // ── 0. Check voice cache — free & instant ──────────────────────────────────
    if (isCachedPhrase(text)) {
        log('[TTS] Using cached browser voice for: ' + text.substring(0, 40));
        fallbackTTS(text, fireStart);
        return;
    }

    // Helper: decode audio buffer and play with lip sync
    async function playAudioBuffer(arrayBuffer) {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') await audioCtx.resume();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        audioAnalyzer = audioCtx.createAnalyser();
        audioAnalyzer.fftSize = 256;
        audioDataArray = new Uint8Array(audioAnalyzer.frequencyBinCount);
        source.connect(audioAnalyzer);
        audioAnalyzer.connect(audioCtx.destination);
        source.onended = () => { isSpeaking = false; };
        fireStart();
        isSpeaking = true;
        source.start(0);
    }

    // ── 1. ElevenLabs (paid, high quality) ────────────────────────────────────
    try {
        const elevenKey   = cfg.elevenlabs_api_key || '';
        const elevenVoice = cfg.elevenlabs_voice_id || 'EXAVITQu4vr4xnSDxMaL';

        if (elevenKey && !elevenApiFailed) {
            try {
                const response = await fetch(
                    `https://api.elevenlabs.io/v1/text-to-speech/${elevenVoice}/stream`,
                    {
                        method: 'POST',
                        headers: { 'xi-api-key': elevenKey, 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            text,
                            model_id: 'eleven_turbo_v2_5',
                            voice_settings: { stability: 0.30, similarity_boost: 0.85, style: 0.65, use_speaker_boost: true },
                        }),
                        signal: AbortSignal.timeout(6000)
                    }
                );

                if (response.status === 401 || response.status === 403) {
                    elevenApiFailed = true;
                    throw new Error('ElevenLabs auth failed');
                }
                if (response.status === 429) {
                    elevenApiFailed = true;
                    throw new Error('ElevenLabs quota');
                }
                if (!response.ok) throw new Error(`ElevenLabs ${response.status}`);

                const arrayBuffer = await response.arrayBuffer();
                await playAudioBuffer(arrayBuffer);
                return;
            } catch (e) {
                log('[TTS] ElevenLabs failed: ' + e.message);
            }
        }

        // ── 3. Murf AI (paid) ─────────────────────────────────────────────────────
        const murfKey    = cfg.murf_api_key || '';
        const voiceId    = cfg.voice_id || 'ja-JP-kimi';
        const voiceStyle = cfg.voice_style || 'Cheerful';
        const voiceRate  = cfg.voice_rate !== undefined ? cfg.voice_rate : -2;
        const voicePitch = cfg.voice_pitch !== undefined ? cfg.voice_pitch : 6;

        if (murfKey && !murfApiFailed) {
            try {
                const response = await fetch('https://api.murf.ai/v1/speech/generate', {
                    method: 'POST',
                    headers: { 'api-key': murfKey, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        voiceId, style: voiceStyle, text,
                        format: 'WAV', encodeAsBase64: true,
                        rate: voiceRate, pitch: voicePitch
                    }),
                    signal: AbortSignal.timeout(12000)
                });

                if (response.status === 401 || response.status === 403 || response.status === 429) {
                    murfApiFailed = true;
                    const errText = await response.text();
                    throw new Error(`Murf Auth/Quota (${response.status}): ${errText}`);
                }
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`Murf API ${response.status}: ${errText}`);
                }

                const data = await response.json();
                const base64Audio = data.encodedAudio;
                const audioFileUrl = data.audioFile;

                let arrayBuffer;
                if (base64Audio) {
                    const binaryString = atob(base64Audio);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    arrayBuffer = bytes.buffer;
                } else if (audioFileUrl) {
                    const audioResp = await fetch(audioFileUrl);
                    arrayBuffer = await audioResp.arrayBuffer();
                } else {
                    throw new Error('No audio data in Murf response');
                }

                await playAudioBuffer(arrayBuffer);
                return;
            } catch (e) {
                log('[TTS] Murf failed: ' + e.message);
            }
        }
    } catch (globalErr) {
        log('[TTS] Unexpected error in Murf/ElevenLabs: ' + globalErr.stack);
    }

    // ── 3. Edge-TTS via server (FREE — Microsoft Neural) ──────────────────────
    try {
        log('[TTS] Trying Edge-TTS fallback...');
        const edgeResp = await fetch('http://localhost:8000/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
            signal: AbortSignal.timeout(12000)
        });
        if (edgeResp.ok) {
            const arrayBuffer = await edgeResp.arrayBuffer();
            if (arrayBuffer.byteLength > 100) {
                await playAudioBuffer(arrayBuffer);
                log('[TTS] Edge-TTS playing!');
                return;
            }
        }
    } catch (edgeErr) {
        log('[TTS] Edge-TTS failed: ' + edgeErr.message);
    }

    // ── 4. Browser speech synthesis (absolute last resort) ────────────────────
    log('[TTS] All APIs failed — falling back to browser TTS');
    fallbackTTS(text, fireStart);
}

function fallbackTTS(text, onAudioStart = null) {
    if (!text || text.trim() === '') return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    utterance.volume = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang === 'en-US' && v.name.includes('Female'))
        || voices.find(v => v.lang === 'en-US')
        || voices[0];
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => {
        isSpeaking = true;
        if (onAudioStart) onAudioStart();
        console.log('Speaking:', text.substring(0, 40));
    };
    utterance.onend = () => { isSpeaking = false; };
    utterance.onerror = () => { isSpeaking = false; };
    window.speechSynthesis.speak(utterance);
}

if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
        log('[TTS] Browser voices loaded: ' + window.speechSynthesis.getVoices().length);
    };
}

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.altKey && e.shiftKey) {
        if (e.code === 'KeyP') { ipcRenderer.send('scale-up'); }
        else if (e.code === 'KeyO') { ipcRenderer.send('scale-down'); }
        else if (e.code === 'KeyQ') { ipcRenderer.send('quit-app'); }
        else if (e.code === 'KeyT') { toggleTerminal(); }
        else if (e.code === 'KeyK') { window.location.reload(); }
        else if (e.code === 'KeyS') { openSettings(); }
    }
});

// ─── Window resize ────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
    if (camera && renderer) {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }
});

init();
