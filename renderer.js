import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

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
log('Renderer process started (Portrait Mode).');

let scene, camera, renderer, clock, currentVrm;
let ws = null;
let reconnectTimer = null;
let isSpeaking = false;
let isWaving = false;
let isSmiling = false;
let waveStartTime = 0;
const vrmPath = './character/5816025470716354497.vrm';

// Lip-Sync Globals
let audioAnalyzer = null;
let audioDataArray = null;
let mouthVolume = 0;

// ─── DOM References ──────────────────────────────────────────────────────────
const container = document.getElementById('container');
const statusEl = document.getElementById('status');
const responseBubble = document.getElementById('response-bubble');
const talkBtn = document.getElementById('talk-btn');
const terminalContent = document.getElementById('terminal-content');

function logTerminal(text, type = 'system') {
    if (!terminalContent) return;
    const line = document.createElement('div');
    line.className = `terminal-line terminal-${type}`;
    const prefix = type === 'user' ? 'You: ' : type === 'risse' ? 'Risse: ' : '> ';
    line.textContent = prefix + text;
    terminalContent.appendChild(line);
    terminalContent.scrollTop = terminalContent.scrollHeight;
}

// ─── Drag-to-Move ────────────────────────────────────────────────────────────
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

// ─── Init ────────────────────────────────────────────────────────────────────
function init() {
    log('Initializing Three.js scene...');
    scene = new THREE.Scene();
    
    // Portrait lens for 120x150 head-to-chest framing
    camera = new THREE.PerspectiveCamera(
        35.0, 
        window.innerWidth / window.innerHeight,
        0.1,
        20.0
    );
    // Camera centered on face/chest, pulled back enough to fit head
    camera.position.set(0.0, -0.05, 1.55); 
    camera.lookAt(0, -0.05, 0);

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

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    log('Loading VRM...');
    loader.load(
        vrmPath,
        (gltf) => {
            const vrm = gltf.userData.vrm;
            vrm.scene.scale.set(1.0, 1.0, 1.0);
            vrm.scene.rotation.y = Math.PI; 
            
            // Translate model so face (eyes) is at (0, 0)
            vrm.scene.position.set(0, -1.48, 0);
            
            scene.add(vrm.scene);
            currentVrm = vrm;
            log('[VRM] Model loaded face-center.');
            
            applyAPose(vrm);
        },
        null,
        (error) => log('[VRM] Error: ' + error.message)
    );

    clock = new THREE.Clock();
    animate();
    connectWebSocket();
}

// ─── Animation Helpers ──────────────────────────────────────────────────────
function findBoneByName(node, namePart) {
    let result = null;
    node.traverse((child) => {
        if (child.isBone && child.name.toLowerCase().includes(namePart.toLowerCase())) {
            result = child;
        }
    });
    return result;
}

function applyAPose(vrm) {
    if (!vrm) return;
    log('[VRM] A-Pose engine ready.');
}

function animate() {
    requestAnimationFrame(animate);
    const deltaTime = clock.getDelta();
    if (currentVrm) {
        const time = clock.elapsedTime;
        const humanoid = currentVrm.humanoid;
        // ── 0. Update internal state FIRST (Humanoid/Expressions/Physics) ───
        currentVrm.update(deltaTime);

        // ── 1. Absolute Multi-Axis Pose Overrides (Post-Update Brute Force) ──
        const nodesToForce = [
            { name: 'leftUpperArm', rot: [0, 0, 1.45] },
            { name: 'rightUpperArm', rot: [0, 0, -1.45] },
            { name: 'leftShoulder', rot: [0, 0.1, 0.4] },
            { name: 'rightShoulder', rot: [0, -0.1, -0.4] },
            { name: 'leftLowerArm', rot: [0, 0, 0.2] },
            { name: 'rightLowerArm', rot: [0, 0, -0.2] }
        ];

        if (isWaving) {
            const waveElapsed = time - waveStartTime;
            const waveDuration = 3.0;
            if (waveElapsed > waveDuration) {
                isWaving = false;
            } else {
                // Smooth cubic ease-in/ease-out
                const rawRaise = Math.min(waveElapsed / 0.5, 1.0);
                const rawLower = Math.max((waveElapsed - (waveDuration - 0.5)) / 0.5, 0.0);
                const easeIn = rawRaise * rawRaise * (3 - 2 * rawRaise); // smoothstep
                const easeOut = 1.0 - (rawLower * rawLower * (3 - 2 * rawLower));
                const armUp = easeIn * easeOut;

                // Gentle, slow wave motion
                const wave1 = Math.sin(waveElapsed * 6) * 0.4;
                const wave2 = Math.sin(waveElapsed * 4 + 0.7) * 0.2;
                const waveAngle = (wave1 + wave2) * armUp;

                // Right upper arm: smoothly raise
                nodesToForce[1].rot = [
                    0.3 * (1 - armUp),
                    0.3 * armUp,
                    -1.2 - (1.2 * armUp)
                ];
                // Right lower arm: gentle waving
                nodesToForce[5].rot = [
                    0,
                    0.5 * (1 - armUp) + waveAngle,
                    -0.6 * (1 - armUp) - 0.4 * armUp
                ];
            }
        }

        nodesToForce.forEach(cfg => {
            const bone = humanoid.getRawBoneNode(cfg.name) || findBoneByName(currentVrm.scene, cfg.name);
            if (bone) {
                bone.rotation.set(cfg.rot[0], cfg.rot[1], cfg.rot[2]);
            }
        });

        // ── 2. Fluid Head & Body Sway ──────
        const breathe = 0.02 * Math.sin(time * 1.5);
        if (humanoid.getRawBoneNode('chest')) humanoid.getRawBoneNode('chest').rotation.x = breathe;

        const headSwayY = isSpeaking ? 0.15 : 0.06;
        const headSwayZ = isSpeaking ? 0.08 : 0.04;
        const head = humanoid.getRawBoneNode('head');
        if (head) {
            head.rotation.y = headSwayY * Math.sin(time * 1.1);
            head.rotation.z = headSwayZ * Math.cos(time * 1.4);
        }

        // ── 3. Eye Tracking ─────────────────────────────────
        if (currentVrm.lookAt) {
            currentVrm.lookAt.lookAt(new THREE.Vector3(
                0.8 * Math.sin(time * 0.4), 
                0.3 * Math.cos(time * 0.25), 
                15.0
            ));
        }

        // ── 4. Expressions ───────────────────────────────────
        if (currentVrm.expressionManager) {
            const blinkCycle = time % 5.0;
            currentVrm.expressionManager.setValue('blink', (blinkCycle > 4.75) ? 1.0 : 0.0);
            
            if (isSmiling) {
                currentVrm.expressionManager.setValue('happy', 1.0);
            } else {
                currentVrm.expressionManager.setValue('happy', 0.0);
            }

            if (isSpeaking) {
                // Audio Lip Sync
                if (audioAnalyzer) {
                    audioAnalyzer.getByteFrequencyData(audioDataArray);
                    let sum = 0;
                    for (let i = 0; i < audioDataArray.length; i++) sum += audioDataArray[i];
                    mouthVolume = sum / audioDataArray.length / 255;
                } else {
                    // Simple sine fallback if no analyzer (e.g. Web Speech API)
                    mouthVolume = 0.2 + 0.3 * Math.sin(time * 22.0);
                }
                const mouthA = mouthVolume * 2.5; // Boost for visibility
                currentVrm.expressionManager.setValue('aa', Math.min(mouthA, 1.0));
                currentVrm.expressionManager.setValue('oh', 0.1 * mouthVolume);
            } else {
                mouthVolume = 0;
                audioAnalyzer = null;
                // Completely close mouth to stop idle motion
                currentVrm.expressionManager.setValue('aa', 0.0);
                currentVrm.expressionManager.setValue('oh', 0.0);
                currentVrm.expressionManager.setValue('ih', 0.0);
                currentVrm.expressionManager.setValue('ou', 0.0);
                currentVrm.expressionManager.setValue('ee', 0.0);
                currentVrm.expressionManager.setValue('relaxed', 0.0); // This was holding the mouth open!
            }
        }
        camera.lookAt(0, -0.05, 0); 
    }
    renderer.render(scene, camera);
}

// ─── WebSocket ──────────────────────────────────────────────────────────────
function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
        return; // Already connected or connecting
    }
    
    ws = new WebSocket('ws://localhost:8000/ws');
    ws.onopen = () => {
        log('[WS] Connected.');
        statusEl.textContent = 'Connected! Say "Risse" or press F2.';
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        
        // Startup Greeting
        setTimeout(() => {
            const greeting = "Hello Shinshio!";
            showResponse(greeting);
            playTTS(greeting);
            logTerminal(greeting, 'risse');
            
            // Smile animation block
            isSmiling = true;
            isWaving = true;
            waveStartTime = clock.elapsedTime;
            setTimeout(() => {
                isSmiling = false;
            }, 3000); // Smile for 3 seconds
            
        }, 3000); // Small delay before speaking so things load visibly
    };
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'speak') { 
            showResponse(msg.text); 
            playTTS(msg.text); 
            logTerminal(msg.text, 'risse');
        }
        if (msg.type === 'status') { 
            const indicator = document.getElementById('status-indicator');
            if (indicator) {
                if (msg.text === 'Listening...') {
                    indicator.style.backgroundColor = '#00ffcc';
                    indicator.style.boxShadow = '0 0 10px #00ffcc';
                } else if (msg.text === 'Processing...' || msg.text === 'Thinking...') {
                    indicator.style.backgroundColor = '#ffcc00';
                    indicator.style.boxShadow = '0 0 10px #ffcc00';
                } else {
                    // Turn OFF indicator for idle/other states
                    indicator.style.backgroundColor = 'rgba(255,255,255,0.2)';
                    indicator.style.boxShadow = 'none';
                }
            }
        }
    };
    ws.onclose = () => {
        log('[WS] Disconnected. Reconnecting in 3s...');
        statusEl.textContent = 'Reconnecting...';
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectWebSocket();
            }, 3000);
        }
    };
    ws.onerror = (err) => {
        log('[WS] Error: ' + (err.message || 'connection failed'));
    };
}

function showResponse(text) {
    responseBubble.textContent = text;
    responseBubble.classList.remove('hidden');
    setTimeout(() => responseBubble.classList.add('hidden'), 8000);
}

// ─── TTS with Smart Fallback ────────────────────────────────────────────────
let murfApiFailed = false; // Cache so we don't keep hitting a dead API

async function playTTS(text) {
    if (isSpeaking) return;
    isSpeaking = true;

    // Try Murf AI first (unless previously failed permanently)
    if (!murfApiFailed) {
        try {
            const response = await fetch('https://api.murf.ai/v1/speech/generate', {
                method: 'POST',
                headers: {
                    'api-key': 'ap2_7128ab65-3e5d-4b29-a89b-628c0db26fce',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    voiceId: 'ja-JP-kimi',
                    style: 'Conversational',
                    text: text,
                    format: 'MP3',
                    rate: -2,
                    pitch: 4
                })
            });

            if (response.status === 401 || response.status === 403 || response.status === 429) {
                log(`[TTS] Murf API returned ${response.status} — key exhausted or invalid. Switching to fallback permanently.`);
                murfApiFailed = true;
                throw new Error('API key exhausted');
            }

            if (!response.ok) {
                log(`[TTS] Murf API returned ${response.status}`);
                throw new Error('Murf API error');
            }

            const data = await response.json();
            const audioUrl = data.encodedAudio || data.audioFile;
            if (!audioUrl) throw new Error('No audio URL in response');

            const audio = new Audio(audioUrl);
            
            // Lip-Sync Hookup
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaElementSource(audio);
            audioAnalyzer = audioCtx.createAnalyser();
            audioAnalyzer.fftSize = 32;
            audioDataArray = new Uint8Array(audioAnalyzer.frequencyBinCount);
            source.connect(audioAnalyzer);
            audioAnalyzer.connect(audioCtx.destination);

            audio.onended = () => { isSpeaking = false; audioCtx.close(); };
            audio.onerror = () => { isSpeaking = false; audioCtx.close(); fallbackTTS(text); };
            await audio.play();
            return;
        } catch (e) {
            log('[TTS] Murf failed: ' + e.message + ' — using browser speech.');
        }
    }

    // Fallback: Web Speech API (free, built-in)
    fallbackTTS(text);
}

function fallbackTTS(text) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Try to pick a nice female English voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v =>
        v.lang.startsWith('en') && v.name.toLowerCase().includes('zira')
    ) || voices.find(v =>
        v.lang.startsWith('en') && (v.name.toLowerCase().includes('female') || v.name.toLowerCase().includes('samantha'))
    ) || voices.find(v =>
        v.lang.startsWith('en')
    );

    if (preferred) {
        utterance.voice = preferred;
        log(`[TTS] Using fallback voice: ${preferred.name}`);
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    utterance.onend = () => { isSpeaking = false; };
    utterance.onerror = () => { isSpeaking = false; };
    window.speechSynthesis.speak(utterance);
}

// Pre-load voices (Chrome-based browsers load them async)
if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
        log('[TTS] Browser voices loaded: ' + window.speechSynthesis.getVoices().length);
    };
}

// ─── Keyboard Shortcuts ─────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.altKey && e.shiftKey) {
        if (!currentVrm) return;
        const scaleStep = 0.1;
        // User asked for Alt+Shift+P to increase size, we use e.code to avoid shift-casing issues
        if (e.code === 'KeyP') {
            const newScale = currentVrm.scene.scale.x + scaleStep;
            currentVrm.scene.scale.set(newScale, newScale, newScale);
            log(`[Scale] Increased to ${newScale.toFixed(2)}`);
        } else if (e.code === 'KeyO') {
            const newScale = Math.max(0.1, currentVrm.scene.scale.x - scaleStep);
            currentVrm.scene.scale.set(newScale, newScale, newScale);
            log(`[Scale] Decreased to ${newScale.toFixed(2)}`);
        } else if (e.code === 'KeyQ') {
            log(`[Exit] User requested quit.`);
            ipcRenderer.send('quit-app');
        } else if (e.code === 'KeyT') {
            const terminal = document.getElementById('terminal-overlay');
            if (terminal) {
                const isHidden = window.getComputedStyle(terminal).display === 'none';
                terminal.style.display = isHidden ? 'flex' : 'none';
                log(`[Terminal] Toggled to ${isHidden ? 'visible' : 'hidden'}`);
            }
        } else if (e.code === 'KeyK') {
            log(`[Refresh] User requested manual reload.`);
            window.location.reload();
        }
    }
});

// ─── Handle window resize ───────────────────────────────────────────────────
window.addEventListener('resize', () => {
    if (camera && renderer) {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }
});

init();
