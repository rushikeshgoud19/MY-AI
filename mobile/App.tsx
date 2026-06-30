import React, { useState } from 'react';
import { StyleSheet, SafeAreaView, KeyboardAvoidingView, Platform, StatusBar, View, TouchableOpacity, Text } from 'react-native';
import ChatInterface from './src/components/ChatInterface';
import TaskManager from './src/components/TaskManager';

export default function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'tasks'>('chat');

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardAvoid}
      >
        <View style={styles.content}>
          {activeTab === 'chat' ? <ChatInterface /> : <TaskManager />}
        </View>

        {/* Custom Bottom Navigation Bar */}
        <View style={styles.tabBar}>
          <TouchableOpacity 
            style={[styles.tabButton, activeTab === 'chat' && styles.tabButtonActive]}
            onPress={() => setActiveTab('chat')}
          >
            <Text style={[styles.tabText, activeTab === 'chat' && styles.tabTextActive]}>Chat</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.tabButton, activeTab === 'tasks' && styles.tabButtonActive]}
            onPress={() => setActiveTab('tasks')}
          >
            <Text style={[styles.tabText, activeTab === 'tasks' && styles.tabTextActive]}>Tasks</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  keyboardAvoid: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#1e293b',
    borderTopWidth: 1,
    borderTopColor: '#334155',
    paddingBottom: Platform.OS === 'ios' ? 20 : 0,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 16,
    alignItems: 'center',
    borderTopWidth: 2,
    borderTopColor: 'transparent',
  },
  tabButtonActive: {
    borderTopColor: '#3b82f6',
  },
  tabText: {
    color: '#64748b',
    fontSize: 16,
    fontWeight: 'bold',
  },
  tabTextActive: {
    color: '#3b82f6',
  },
});
