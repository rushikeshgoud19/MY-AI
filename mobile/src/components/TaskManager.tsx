import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View, FlatList, ActivityIndicator } from 'react-native';
import { wsClient, WSMessage } from '../services/WebSocketClient';

export default function TaskManager() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Request tasks on mount
    wsClient.send({ type: 'get_tasks' });

    const unsub = wsClient.subscribe((msg: WSMessage) => {
      if (msg.type === 'task_list') {
        setTasks(msg.tasks || []);
        setLoading(false);
      }
    });

    return () => { unsub(); };
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Mizune Subconscious Queue</Text>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={styles.loadingText}>Syncing memory...</Text>
        </View>
      ) : (
        <FlatList
          data={tasks}
          keyExtractor={(item, index) => index.toString()}
          renderItem={({ item }) => (
            <View style={styles.taskCard}>
              <Text style={styles.taskTitle}>{item.title}</Text>
              <Text style={styles.taskDesc}>{item.description}</Text>
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.loadingText}>No active tasks in the queue.</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  headerTitle: { color: '#f8fafc', fontSize: 18, fontWeight: 'bold' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: '#94a3b8', marginTop: 12 },
  taskCard: { backgroundColor: '#1e293b', margin: 12, padding: 16, borderRadius: 12 },
  taskTitle: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold' },
  taskDesc: { color: '#cbd5e1', marginTop: 4 },
});
