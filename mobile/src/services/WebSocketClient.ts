export type WSMessage = {
  type: string;
  [key: string]: any;
};

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private listeners: Set<(msg: WSMessage) => void> = new Set();
  private statusListeners: Set<(connected: boolean) => void> = new Set();
  private isConnected = false;

  constructor(url: string = 'ws://40.123.215.32:8001/ws') {
    this.url = url;
  }

  connect() {
    if (this.ws) return;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.notifyStatusListeners(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.notifyListeners(data);
        } catch (e) {
          console.error('[WS] Parse error', e);
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        this.isConnected = false;
        this.notifyStatusListeners(false);
        setTimeout(() => this.connect(), 5000);
      };

      this.ws.onerror = (e) => {
        console.error('[WS] Connection Error', e);
      };
    } catch (e) {
      console.error('[WS] Setup Error', e);
      setTimeout(() => this.connect(), 5000);
    }
  }

  send(data: WSMessage) {
    if (this.ws && this.isConnected) {
      this.ws.send(JSON.stringify(data));
    }
  }

  subscribe(callback: (msg: WSMessage) => void) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  subscribeStatus(callback: (connected: boolean) => void) {
    this.statusListeners.add(callback);
    callback(this.isConnected);
    return () => this.statusListeners.delete(callback);
  }

  private notifyListeners(msg: WSMessage) {
    this.listeners.forEach(cb => cb(msg));
  }

  private notifyStatusListeners(status: boolean) {
    this.statusListeners.forEach(cb => cb(status));
  }
}

export const wsClient = new WebSocketClient();
