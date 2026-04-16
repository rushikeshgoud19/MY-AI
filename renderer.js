import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';

// Node built-ins in Electron
const { ipcRenderer } = window.require('electron');
const fs = window.require('fs');
const path = window.require('path');

const logFile = path.join(process.cwd(), 'renderer.log');
const log = (msg) => {
    const timestamp = new Date().toISOString();
    try { fs.appendFileSync(logFile, `[${timestamp}] ${msg}\n`); } catch(e) {}
    console.log(msg);
};
window.onerror = (msg, url, line) => log(`ERROR: ${msg} at ${url}:${line}`);
log('Renderer started.');

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
let ws = null;
let reconnectTimer = null;
let isSpeaking = false;
let isWaving = false;
let waveStartTime = 0;

// Emotion system with smooth blending
let currentEmotion = 'neutral';
let emotionTimer = 0;
let emotionBlends = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
let targetBlends  = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0.2 };

// Blush system for Mizune
let blushIntensity = 0;
let targetBlush = 0;
let blushDecayTimer = 0;
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

// ─── Terminal Toggle ──────────────────────────────────────────────────────────
function toggleTerminal() {
    const terminal = document.getElementById('terminal-overlay');
    if (!terminal) return;
    const isHidden = window.getComputedStyle(terminal).display === 'none';
    terminal.style.display = isHidden ? 'flex' : 'none';
}

// ─── Drag-to-Move ─────────────────────────────────────────────────────────────
let isDragging = false;
let dragLastX = 0;
let dragLastY = 0;

container.addEventListener('mousedown', (e) => {
    isDragging = true;
    dragLastX = e.screenX;
    dragLastY = e.screenY;
    container.classList.add('dragging');
    ipcRenderer.send('drag-start');
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const deltaX = e.screenX - dragLastX;
    const deltaY = e.screenY - dragLastY;
    dragLastX = e.screenX;
    dragLastY = e.screenY;
    ipcRenderer.send('drag-move', deltaX, deltaY);
});

document.addEventListener('mouseup', () => {
    if (isDragging) {
        isDragging = false;
        container.classList.remove('dragging');
        ipcRenderer.send('drag-end');
    }
});

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
    log('Initializing Three.js scene...');
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(45.0, window.innerWidth / window.innerHeight, 0.1, 20.0);
    camera.position.set(0.0, 1.3, 1.3);
    camera.lookAt(0, 1.1, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.zIndex = '1';
    container.appendChild(renderer.domElement);

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

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    log(`[VRM] Loading: ${vrmPath}`);

    loader.load(
        vrmPath,
        (gltf) => {
            const vrm = gltf.userData.vrm;
            vrm.scene.scale.set(1.0, 1.0, 1.0);
            vrm.scene.rotation.y = Math.PI;
            // Ensure model is centered and slightly raised to avoid floor clipping
            vrm.scene.position.set(0, 0, 0);
            scene.add(vrm.scene);
            currentVrm = vrm;
            log('[VRM] Model loaded and added to scene.');
        },
        (xhr) => {
            log(`[VRM] Loading progress: ${(xhr.loaded / xhr.total * 100).toFixed(2)}%`);
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
        // Try blush blendshape first, otherwise fallback to subtle red tint (simulation)
        if (em.prototype && em.prototype.setValue) {
            em.setValue('blush', blushIntensity);
        }
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

    em.setValue('blink', blinkValue);
}

// ─── Emotion Blend System (smooth transitions) ────────────────────────────────
function setTargetEmotion(emotion) {
    targetBlends = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
    targetBlush = 0;

    if (emotion === 'happy')     { targetBlends.happy = 1.0; }
    else if (emotion === 'blush') { targetBlends.happy = 0.6; targetBlush = 1.0; blushDecayTimer = 6.0; }
    else if (emotion === 'smile') { targetBlends.happy = 0.7; targetBlends.relaxed = 0.3; }
    else if (emotion === 'sad')   { targetBlends.sad = 0.8; }
    else if (emotion === 'angry') { targetBlends.angry = 0.5; targetBlends.sad = 0.2; }
    else if (emotion === 'surprised') { targetBlends.surprised = 1.0; }
    else                          { targetBlends.relaxed = 0.2; }
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

// ─── Lip Sync with smooth interpolation ──────────────────────────────────────
function updateLipSync(deltaTime, time) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const em = currentVrm.expressionManager;
    const lerpSpeed = deltaTime * 18.0; // snappy but not jarring

    if (isSpeaking) {
        let rawVolume = 0;
        if (audioAnalyzer) {
            audioAnalyzer.getByteFrequencyData(audioDataArray);
            let sum = 0;
            // Focus on speech-frequency bins (roughly 300Hz–3kHz)
            const start = 1;
            const end = Math.min(8, audioDataArray.length);
            for (let i = start; i < end; i++) sum += audioDataArray[i];
            rawVolume = sum / (end - start) / 255;
        } else {
            // Fallback: simulate varied mouth movement
            rawVolume = 0.25
                + 0.25 * Math.sin(time * 18.0)
                + 0.10 * Math.sin(time * 31.0 + 1.2)
                + 0.05 * Math.sin(time * 47.0 + 2.4);
        }

        mouthVolume = clamp(rawVolume, 0, 1);
        const targetA  = clamp(mouthVolume * 2.8, 0, 1.0);
        const targetOh = clamp(mouthVolume * 0.4, 0, 0.5);

        smoothMouthA  = lerp(smoothMouthA,  targetA,  Math.min(lerpSpeed, 1.0));
        smoothMouthOh = lerp(smoothMouthOh, targetOh, Math.min(lerpSpeed * 0.6, 1.0));

        em.setValue('aa', smoothMouthA);
        em.setValue('oh', smoothMouthOh);
    } else {
        mouthVolume   = 0;
        smoothMouthA  = lerp(smoothMouthA,  0, Math.min(lerpSpeed, 1.0));
        smoothMouthOh = lerp(smoothMouthOh, 0, Math.min(lerpSpeed, 1.0));
        em.setValue('aa', smoothMouthA);
        em.setValue('oh', smoothMouthOh);
        em.setValue('ih', 0);
        em.setValue('ou', 0);
        em.setValue('ee', 0);

        // Release analyzer only after mouth is fully closed
        if (smoothMouthA < 0.01 && smoothMouthOh < 0.01) {
            audioAnalyzer = null;
        }
    }
}

// ─── Animation Loop ───────────────────────────────────────────────────────────
function animate() {
    requestAnimationFrame(animate);
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
                setTargetEmotion('neutral');
            }
        }

        // ── Independent blink ──
        updateBlink(deltaTime);

        // ── Emotion blends ──
        updateEmotionBlends(deltaTime);
        updateBlush(deltaTime);

        // ── Lip sync ──
        updateLipSync(deltaTime, time);

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

        camera.lookAt(0, 0.35, 0);
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
            const greeting = `Hai~ Master! ${charName} is ready to serve you~!`;
            showResponse(greeting);
            playTTS(greeting);
            logTerminal(greeting, 'risse');
            // Happy face on startup
            currentEmotion = 'happy';
            emotionTimer = 4.0;
            setTargetEmotion('happy');
        }, 2500);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'speak') {
            hideTypingIndicator();
            showResponse(msg.text);
            playTTS(msg.text);
            logTerminal(msg.text, 'risse');
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
            currentEmotion = msg.emotion;
            emotionTimer = 5.0;
            setTargetEmotion(msg.emotion);
            logTerminal(`Emotion detected: ${msg.emotion}`, 'emotion');
        }

        if (msg.type === 'config_reloaded') {
            loadCfg();
            if (msg.character_file && msg.character_file !== (cfg.character_file || '')) {
                loadVRM(msg.character_file);
            }
        }

        if (msg.type === 'status') {
            const indicator = document.getElementById('status-indicator');
            if (indicator) {
                if (msg.text === 'Listening...' || msg.text === 'Triggered') {
                    indicator.style.backgroundColor = '#00ff00';
                    indicator.style.boxShadow = '0 0 12px #00ff00';
                } else if (msg.text === 'Processing...' || msg.text === 'Thinking...') {
                    indicator.style.backgroundColor = '#ffcc00';
                    indicator.style.boxShadow = '0 0 8px #ffcc00';
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
    responseBubble.classList.remove('hidden');
    responseBubble.textContent = '';
    // Typewriter effect
    clearTimeout(responseBubble._hideTimer);
    clearInterval(responseBubble._typeTimer);
    let i = 0;
    const speed = Math.max(18, Math.min(40, Math.round(20000 / text.length))); // adaptive speed
    responseBubble._typeTimer = setInterval(() => {
        if (i < text.length) {
            responseBubble.textContent += text[i++];
        } else {
            clearInterval(responseBubble._typeTimer);
            // Auto-hide: ~1s per 15 chars, clamped 5s–20s
            const duration = Math.max(5000, Math.min(20000, text.length * 65));
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

async function playTTS(text) {
    if (isSpeaking) return;

    // ── 0. Check voice cache — free & instant ──────────────────────────────────
    if (isCachedPhrase(text)) {
        log('[TTS] Using cached browser voice for: ' + text.substring(0, 40));
        fallbackTTS(text);
        return;
    }

    try {
        const elevenKey   = cfg.elevenlabs_api_key || '';
        const elevenVoice = cfg.elevenlabs_voice_id || 'EXAVITQu4vr4xnSDxMaL';
        const murfKey     = cfg.murf_api_key || '';
        const voiceId     = cfg.voice_id || 'ja-JP-kimi';
        const voiceStyle  = cfg.voice_style || 'Cheerful';
        const voiceRate   = cfg.voice_rate !== undefined ? cfg.voice_rate : -2;
        const voicePitch  = cfg.voice_pitch !== undefined ? cfg.voice_pitch : 6;

        log(`[TTS] Requesting voice. MurfKey length: ${murfKey.length}, ElevenLabsKey length: ${elevenKey.length}`);

        // ── 1. ElevenLabs ──────────────────────────────────────────────────────────
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

                // Decode fully before playing — lip sync starts exactly when audio starts
                const arrayBuffer = await response.arrayBuffer();
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
                const source = audioCtx.createBufferSource();
                source.buffer = audioBuffer;
                audioAnalyzer = audioCtx.createAnalyser();
                audioAnalyzer.fftSize = 64;
                audioDataArray = new Uint8Array(audioAnalyzer.frequencyBinCount);
                source.connect(audioAnalyzer);
                audioAnalyzer.connect(audioCtx.destination);
                source.onended = () => { isSpeaking = false; audioCtx.close(); };
                isSpeaking = true; // set JUST before playback starts
                source.start(0);
                return;
            } catch (e) {
                log('[TTS] ElevenLabs failed: ' + e.message);
            }
        }

        // ── 2. Murf AI ─────────────────────────────────────────────────────────────
        if (murfKey && !murfApiFailed) {
            try {
                const response = await fetch('https://api.murf.ai/v1/speech/generate', {
                    method: 'POST',
                    headers: { 'api-key': murfKey, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voiceId, style: voiceStyle, text, format: 'MP3', rate: voiceRate, pitch: voicePitch }),
                    signal: AbortSignal.timeout(6000)
                });

                if (response.status === 401 || response.status === 403 || response.status === 429) {
                    murfApiFailed = true;
                    const errText = await response.text();
                    throw new Error(`Murf Exhausted or Auth Failed (${response.status}): ${errText}`);
                }
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`Murf API ${response.status}: ${errText}`);
                }

                const data = await response.json();
                const audioUrl = data.encodedAudio || data.audioFile;
                if (!audioUrl) throw new Error('No audio URL in Murf response');

                const audio = new Audio(audioUrl);
                audio.onended = () => { isSpeaking = false; };
                audio.onerror = (err) => { 
                    log('[TTS] Murf audio playback error: ' + (err.message || 'unknown error'));
                    isSpeaking = false; fallbackTTS(text); 
                };
                isSpeaking = true; // set JUST before playback
                audioAnalyzer = null; // force simulated lip-sync due to CORS
                
                try {
                    await audio.play();
                } catch (playErr) {
                    log('[TTS] Murf audio.play() failed (autoplay policy?): ' + playErr.message);
                    isSpeaking = false;
                    fallbackTTS(text);
                }
                return;
            } catch (e) {
                log('[TTS] Murf failed completely: ' + e.message);
            }
        }
    } catch (globalErr) {
        log('[TTS] Unexpected error in playTTS: ' + globalErr.stack);
    }

    // ── 3. Browser speech synthesis ────────────────────────────────────────────
    log('[TTS] Falling back to browser TTS');
    fallbackTTS(text);
}

function fallbackTTS(text) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang.startsWith('ja'))
        || voices.find(v => v.lang.startsWith('en') && v.name.toLowerCase().includes('zira'))
        || voices.find(v => v.lang.startsWith('en') && v.name.toLowerCase().includes('samantha'))
        || voices.find(v => v.lang.startsWith('en'));
    if (preferred) { utterance.voice = preferred; }
    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    utterance.onstart = () => { isSpeaking = true; };  // lip sync starts with speech
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
