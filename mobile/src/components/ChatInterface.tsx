import React, { useEffect, useState, useRef } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { wsClient, WSMessage } from '../services/WebSocketClient';

export default function ChatInterface() {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<{id: string, text: string, sender: 'user' | 'mizune'}[]>([]);
  const [inputText, setInputText] = useState('');
  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    wsClient.connect();

    const unsubStatus = wsClient.subscribeStatus((status) => {
      setIsConnected(status);
      if (status) {
        setMessages(prev => [...prev, { id: Date.now().toString(), text: 'Connected to Mizune Core.', sender: 'mizune' }]);
      }
    });

    const unsubMsg = wsClient.subscribe((msg: WSMessage) => {
      if (msg.type === 'speak' && msg.text) {
        setMessages(prev => [...prev, { id: Date.now().toString() + Math.random(), text: msg.text, sender: 'mizune' }]);
      }
    });

    return () => {
      unsubStatus();
      unsubMsg();
    };
  }, []);

  const sendMessage = () => {
    if (!inputText.trim() || !isConnected) return;
    
    setMessages(prev => [...prev, { id: Date.now().toString(), text: inputText, sender: 'user' }]);
    wsClient.send({ type: 'transcription', text: inputText });
    setInputText('');
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Mizune Comm-Link</Text>
        <View style={[styles.statusDot, { backgroundColor: isConnected ? '#4ade80' : '#ef4444' }]} />
      </View>

      <ScrollView 
        ref={scrollViewRef}
        style={styles.chatContainer}
        contentContainerStyle={styles.chatContent}
        onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map((msg) => (
          <View key={msg.id} style={[styles.messageBubble, msg.sender === 'user' ? styles.messageUser : styles.messageMizune]}>
            <Text style={[styles.messageText, msg.sender === 'user' ? styles.messageTextUser : styles.messageTextMizune]}>
              {msg.text}
            </Text>
          </View>
        ))}
        {!isConnected && (
          <View style={styles.connecting}>
            <ActivityIndicator size="small" color="#64748b" />
            <Text style={styles.connectingText}>Re-establishing link...</Text>
          </View>
        )}
      </ScrollView>

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Message Mizune..."
          placeholderTextColor="#94a3b8"
          onSubmitEditing={sendMessage}
        />
        <TouchableOpacity style={styles.sendButton} onPress={sendMessage}>
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  headerTitle: { color: '#f8fafc', fontSize: 18, fontWeight: 'bold', marginRight: 8 },
  statusDot: { width: 10, height: 10, borderRadius: 5 },
  chatContainer: { flex: 1 },
  chatContent: { padding: 16, paddingBottom: 32 },
  messageBubble: { maxWidth: '85%', padding: 14, borderRadius: 16, marginBottom: 12 },
  messageUser: { alignSelf: 'flex-end', backgroundColor: '#3b82f6', borderBottomRightRadius: 4 },
  messageMizune: { alignSelf: 'flex-start', backgroundColor: '#1e293b', borderBottomLeftRadius: 4 },
  messageText: { fontSize: 16, lineHeight: 22 },
  messageTextUser: { color: '#ffffff' },
  messageTextMizune: { color: '#f1f5f9' },
  inputContainer: { flexDirection: 'row', padding: 16, backgroundColor: '#1e293b', alignItems: 'center' },
  input: { flex: 1, backgroundColor: '#0f172a', color: '#f8fafc', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 24, fontSize: 16, marginRight: 12 },
  sendButton: { backgroundColor: '#3b82f6', paddingHorizontal: 20, paddingVertical: 12, borderRadius: 24 },
  sendButtonText: { color: '#ffffff', fontWeight: 'bold', fontSize: 16 },
  connecting: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 20 },
  connectingText: { color: '#64748b', marginLeft: 10 }
});
