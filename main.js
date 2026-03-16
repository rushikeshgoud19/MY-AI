const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');

let win;

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: 120,
    height: 150,
    x: width - 140, // 20px padding from right edge
    y: height - 170, // 20px padding from taskbar
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true, // Let the user control her size
    hasShadow: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  win.loadFile('index.html');

  // ─── Drag-to-move: Renderer sends delta, we move the window ────────────
  ipcMain.on('drag-start', () => {
    // Store the initial window position when drag starts
    const [x, y] = win.getPosition();
    win._dragStartX = x;
    win._dragStartY = y;
  });

  ipcMain.on('drag-move', (event, deltaX, deltaY) => {
    if (win._dragStartX !== undefined) {
      const [currentX, currentY] = win.getPosition();
      win.setPosition(currentX + deltaX, currentY + deltaY);
    }
  });

  ipcMain.on('drag-end', () => {
    delete win._dragStartX;
    delete win._dragStartY;
  });

  ipcMain.on('quit-app', () => {
    app.quit();
  });

  // Listen for renderer to toggle mouse events on interactive elements
  ipcMain.on('set-ignore-mouse', (event, ignore) => {
    win.setIgnoreMouseEvents(ignore, { forward: true });
  });

  // Keep window visible even during screenshots or focus loss
  win.on('blur', () => {
    // Re-assert always on top when losing focus (e.g. during screenshots)
    win.setAlwaysOnTop(true, 'screen-saver');
  });

  win.on('minimize', (e) => {
    e.preventDefault();
    win.restore();
  });

  // Optional: DevTools for debugging
  // win.webContents.openDevTools({ mode: 'detach' });
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
