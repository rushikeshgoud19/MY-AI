const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

// Allow audio to autoplay without user interaction
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

const CONFIG_PATH = path.join(__dirname, 'config.json');

const DEFAULT_CONFIG = {
  gemini_api_key: '', openai_api_key: '', anthropic_api_key: '', openrouter_api_key: '', murf_api_key: '',
  elevenlabs_api_key: '', elevenlabs_voice_id: 'MF3mGyEYCl7XYWbV9V6O', elevenlabs_voice_id_custom: '',
  ai_model: 'gemini', gemini_model: 'gemini-2.5-flash',
  openai_model: 'gpt-4o', anthropic_model: 'claude-3-opus-20240229', openrouter_model: 'anthropic/claude-3-opus',
  wake_words: ['mizune', 'misune', 'mizuna', 'mizu', 'missy', 'darling', 'baka'],
  custom_wake_word: '', voice_id: 'ja-JP-kimi', voice_style: 'Cheerful',
  voice_rate: -2, voice_pitch: 6, memory_size: 30,
  character_name: 'Mizune', character_file: 'character/5816025470716354497.vrm',
  personality: 'You are Mizune, an adorable and devoted anime AI assistant.',
  streamer_mode: false, twitch_channel: '', window_scale: 1.0, always_on_top: true,
};

function loadConfig() {
  try {
    return { ...DEFAULT_CONFIG, ...JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

function saveConfig(cfg) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
}

let win;
let settingsWin = null;
let cfg = loadConfig();

// ─── Base window size (Face focus) ──────────────────────────────────────────
const BASE_W = 150;
const BASE_H = 150;

function scaledSize() {
  const s = cfg.window_scale || 1.0;
  return { w: Math.round(BASE_W * s), h: Math.round(BASE_H * s) };
}

function createWindow() {
  const { width } = screen.getPrimaryDisplay().workAreaSize;
  const { w, h } = scaledSize();

  win = new BrowserWindow({
    width: w,
    height: h,
    x: Math.round((width - w) / 2),
    y: 0,
    transparent: true,
    frame: false,
    alwaysOnTop: cfg.always_on_top !== false,
    skipTaskbar: false,
    resizable: true,
    hasShadow: false,
      webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
    }
  });

  win.loadFile('index.html');
  win.webContents.once('did-finish-load', () => {
    ipcMain.emit('open-settings');
  });

  // ─── Drag-to-move Disabled per User Request ──────────────────────────────

  ipcMain.on('quit-app', () => app.quit());

  ipcMain.on('set-ignore-mouse', (_event, ignore) => {
    win.setIgnoreMouseEvents(ignore, { forward: true });
  });

  // ─── Settings window ──────────────────────────────────────────────────────
  ipcMain.on('open-settings', () => {
    if (settingsWin) { settingsWin.focus(); return; }

    settingsWin = new BrowserWindow({
      width: 620,
      height: 700,
      minWidth: 480,
      minHeight: 500,
      frame: false,
      transparent: false,
      alwaysOnTop: false,
      skipTaskbar: false,
      resizable: true,
      backgroundColor: '#0d0d1a',
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        webSecurity: false,
      }
    });

    settingsWin.loadFile('settings.html');
    settingsWin.on('closed', () => { settingsWin = null; });
  });

  ipcMain.on('close-settings', () => {
    if (settingsWin) settingsWin.close();
  });

  ipcMain.on('settings-saved', (_event, newCfg) => {
    cfg = { ...cfg, ...newCfg };
    saveConfig(cfg);

    // Apply always-on-top immediately with highest priority level
    win.setAlwaysOnTop(cfg.always_on_top !== false, 'screen-saver', 1);
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

    // Apply window scale
    const { w, h } = scaledSize();
    win.setSize(w, h);

    // Notify renderer to reload character if it changed
    win.webContents.send('config-updated', cfg);

    // Tell Python backend to reload config
    const http = require('http');
    const req = http.request({ host: 'localhost', port: 8000, path: '/reload-config', method: 'POST' });
    req.on('error', () => {});
    req.end();

    if (settingsWin) settingsWin.close();
  });

  ipcMain.on('reset-config', () => {
    saveConfig(DEFAULT_CONFIG);
    cfg = { ...DEFAULT_CONFIG };
    win.webContents.send('config-updated', cfg);
    if (settingsWin) settingsWin.close();
  });

  // ─── Scale controls from renderer ────────────────────────────────────────
  ipcMain.on('scale-up', () => {
    cfg.window_scale = Math.min(3.0, (cfg.window_scale || 1.0) + 0.1);
    const { w, h } = scaledSize();
    win.setSize(w, h);
  });

  ipcMain.on('scale-down', () => {
    cfg.window_scale = Math.max(0.3, (cfg.window_scale || 1.0) - 0.1);
    const { w, h } = scaledSize();
    win.setSize(w, h);
  });

  win.on('blur', () => {
    if (cfg.always_on_top !== false) {
        win.setAlwaysOnTop(true, 'screen-saver', 1);
    }
  });

  win.on('focus', () => {
    if (cfg.always_on_top !== false) {
        win.setAlwaysOnTop(true, 'screen-saver', 1);
    }
  });

  win.on('minimize', (e) => { e.preventDefault(); win.restore(); });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
