const { 
  makeWASocket, 
  useMultiFileAuthState, 
  fetchLatestBaileysVersion,
  downloadMediaMessage 
} = require('@whiskeysockets/baileys');
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Ensure session directory exists
const SESSION_DIR = path.join(process.cwd(), '.wwebjs_auth_baileys');
if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
}

const SESSION_PATH = SESSION_DIR;
const IPC_PORT = 9876;

class MizuneWhatsAppBridge {
  constructor() {
    this.sock = null;
    this.wss = null;
    this.messageQueue = [];
    this.pythonConnected = false;
  }

  async start() {
    // Start IPC server for Python core only once
    if (!this.wss) {
      this.wss = new WebSocket.Server({ port: IPC_PORT });
      this.wss.on('connection', (ws) => {
        console.log('[Bridge] Python core connected');
        this.pythonConnected = true;
        this.pythonWS = ws;
        
        // Flush queued messages
        while (this.messageQueue.length > 0) {
          ws.send(JSON.stringify(this.messageQueue.shift()));
        }
        
        ws.on('message', (data) => this.handlePythonCommand(JSON.parse(data)));
        ws.on('close', () => {
            console.log('[Bridge] Python core disconnected');
            this.pythonConnected = false;
            this.pythonWS = null;
        });
      });
    }

    // Auth state
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_PATH);
    const { version } = await fetchLatestBaileysVersion();

    this.sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: true,
      syncFullHistory: false,           // Don't download old messages
      markOnlineOnConnect: true,
      fireInitQueries: true,
      shouldIgnoreJid: (jid) => {
        // Ignore status broadcasts, newsletters
        return jid?.endsWith('@broadcast') || jid?.endsWith('@newsletter');
      }
    });

    this.sock.ev.on('creds.update', saveCreds);
    
    this.sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
      if (qr) {
        console.log('\n==================================================');
        console.log('SCAN THIS QR CODE WITH WHATSAPP!');
        console.log('==================================================\n');
        require('qrcode-terminal').generate(qr, { small: true });
      }

      if (connection === 'close') {
        const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== 401;
        if (shouldReconnect) {
          console.log('[Bridge] Reconnecting...');
          setTimeout(() => this.start(), 3000);
        } else {
            console.log('[Bridge] Logged out! Please delete the session folder and restart.');
        }
      } else if (connection === 'open') {
        console.log('[Bridge] Connected to WhatsApp');
      }
    });

    // INCOMING MESSAGE HANDLER
    this.sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify') return; // Only new messages
      
      for (const msg of messages) {
        if (msg.key.fromMe) {
            // Forward own messages for self-chat and memory tracking
            const enriched = await this.enrichMessage(msg);
            this.forwardToPython(enriched);
            continue;
        }
        
        const enriched = await this.enrichMessage(msg);
        this.forwardToPython(enriched);
      }
    });

    // MESSAGE STATUS UPDATES (read receipts, etc.)
    this.sock.ev.on('messages.update', async (updates) => {
      for (const update of updates) {
        this.forwardToPython({
          type: 'status_update',
          message_id: update.key.id,
          status: update.update?.status,
          timestamp: Date.now()
        });
      }
    });
  }

  async enrichMessage(msg) {
    const jid = msg.key.remoteJid;
    const isGroup = jid.endsWith('@g.us');
    const sender = isGroup ? msg.key.participant : jid;
    
    let media = null;
    let text = msg.message?.conversation || 
               msg.message?.extendedTextMessage?.text || 
               msg.message?.imageMessage?.caption ||
               msg.message?.videoMessage?.caption || '';

    // Handle voice messages
    if (msg.message?.audioMessage?.ptt) {
      try {
          const buffer = await downloadMediaMessage(msg, 'buffer', {}, { 
            reuploadRequest: this.sock.updateMediaMessage 
          });
          media = {
            type: 'voice',
            mimetype: msg.message.audioMessage.mimetype,
            duration: msg.message.audioMessage.seconds,
            buffer: buffer.toString('base64') // Send as base64 over IPC
          };
          text = '[VOICE_MESSAGE]';
      } catch (err) {
          console.error("Failed to download media", err);
      }
    }

    // Handle images
    if (msg.message?.imageMessage) {
      try {
          const buffer = await downloadMediaMessage(msg, 'buffer', {}, {
            reuploadRequest: this.sock.updateMediaMessage
          });
          media = {
            type: 'image',
            mimetype: msg.message.imageMessage.mimetype,
            buffer: buffer.toString('base64')
          };
      } catch(err) {
          console.error("Failed to download media", err);
      }
    }

    // Extract mentions
    const mentionedJids = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid || [];
    const isMentioned = this.sock.user && mentionedJids.some(j => j.includes(this.sock.user.id.split(':')[0]));

    // Extract quoted message
    const quoted = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;
    
    return {
      type: 'incoming_message',
      platform: 'whatsapp',
      message_id: msg.key.id,
      timestamp: msg.messageTimestamp,
      chat_jid: jid,
      chat_type: isGroup ? 'group' : 'dm',
      sender_jid: sender,
      sender_phone: sender ? sender.split('@')[0] : '',
      sender_name: msg.pushName || 'Unknown',
      text: text,
      is_mentioned: isMentioned,
      is_self: msg.key.fromMe,
      mentioned_jids: mentionedJids,
      quoted_message: quoted ? {
        text: quoted.conversation || quoted.extendedTextMessage?.text,
        sender: msg.message?.extendedTextMessage?.contextInfo?.participant
      } : null,
      media: media,
      raw: msg // Full payload for advanced parsing
    };
  }

  forwardToPython(payload) {
    const data = JSON.stringify(payload);
    if (this.pythonConnected && this.pythonWS) {
      this.pythonWS.send(data);
    } else {
      this.messageQueue.push(data);
      if (this.messageQueue.length > 1000) this.messageQueue.shift(); // Prevent memory bloat
    }
  }

  async handlePythonCommand(cmd) {
    console.log(`[Bridge] Received IPC command: ${JSON.stringify(cmd)}`);
    try {
        if (cmd.type === 'send_message') {
          await this.sock.sendMessage(cmd.to_jid, {
            text: cmd.text,
            ...(cmd.quoted_message_id && { 
              quoted: { key: { id: cmd.quoted_message_id, remoteJid: cmd.to_jid } } 
            })
          });
        } else if (cmd.type === 'send_voice') {
          // Convert MP3/WAV to OGG/OPUS if needed, then send
          await this.sock.sendMessage(cmd.to_jid, {
            audio: Buffer.from(cmd.audio_base64, 'base64'),
            ptt: true, // Push-to-talk style
            mimetype: 'audio/ogg; codecs=opus'
          });
        } else if (cmd.type === 'typing') {
          await this.sock.sendPresenceUpdate('composing', cmd.to_jid);
        } else if (cmd.type === 'read_receipt') {
          await this.sock.readMessages([{ remoteJid: cmd.chat_jid, id: cmd.message_id }]);
        }
    } catch (e) {
        console.error(`[Bridge] Error executing python command: ${e}`);
    }
  }
}

const bridge = new MizuneWhatsAppBridge();
bridge.start().catch(console.error);
