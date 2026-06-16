import React from 'react';

interface WhatsAppMessage {
  id: string;
  sender: string;
  text: string;
  urgency: string;
  timestamp: number;
}

interface Props {
  messages: WhatsAppMessage[];
}

export const WhatsAppPanel: React.FC<Props> = ({ messages }) => {
  return (
    <div className="panel-container whatsapp-panel">
      <h2>WhatsApp Feed</h2>
      {messages.length === 0 ? (
        <p className="empty-state">No new WhatsApp messages.</p>
      ) : (
        <div className="whatsapp-feed">
          {messages.map(msg => (
            <div key={msg.id} className={`wa-card urgency-${msg.urgency.toLowerCase()}`}>
              <div className="wa-card-header">
                <span className="wa-sender">{msg.sender}</span>
                <span className="wa-time">{new Date(msg.timestamp).toLocaleTimeString()}</span>
              </div>
              <p className="wa-text">{msg.text}</p>
              <div className="wa-badge">{msg.urgency}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
