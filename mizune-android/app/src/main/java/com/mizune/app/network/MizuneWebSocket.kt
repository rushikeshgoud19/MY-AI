package com.mizune.app.network

import android.os.Handler
import android.os.Looper
import android.util.Log
import com.mizune.app.ui.ConnectionState
import kotlinx.serialization.json.*
import kotlinx.serialization.builtins.ListSerializer
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

interface MizuneWebSocketListener {
    fun onConnected()
    fun onDisconnected()
    fun onConnectionStateChanged(state: ConnectionState)
    fun onMessage(text: String, emotion: String)
    fun onStateUpdate(valence: Double, arousal: Double)
    fun onStatusUpdate(status: String)
    fun onTaskList(tasks: List<TaskItem>) {}
}

class MizuneWebSocket(
    private val listener: MizuneWebSocketListener,
    private val serverUrl: String
) {
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(15, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val handler = Handler(Looper.getMainLooper())
    private val reconnectRunnable = Runnable { connect() }
    private var reconnectAttempts = 0
    private val messageQueue = mutableListOf<String>()
    private val queueLock = Object()
    private val isConnected = AtomicBoolean(false)

    companion object {
        private const val TAG = "MizuneWS"
        private const val MAX_RECONNECT_DELAY_MS = 30_000L
    }

    private fun buildWsUrl(): String {
        var normalized = serverUrl.trim().trimEnd('/')
        if (normalized.startsWith("https://", ignoreCase = true)) {
            normalized = normalized.replaceFirst("https://", "wss://", ignoreCase = true)
        } else if (normalized.startsWith("http://", ignoreCase = true)) {
            normalized = normalized.replaceFirst("http://", "ws://", ignoreCase = true)
        } else if (!normalized.startsWith("ws://", ignoreCase = true) && !normalized.startsWith("wss://", ignoreCase = true)) {
            normalized = "wss://$normalized"
        }
        return "$normalized/ws"
    }

    fun connect() {
        if (webSocket != null) return

        updateState(ConnectionState.CONNECTING)
        val wsUrl = buildWsUrl()
        Log.d(TAG, "Connecting to $wsUrl (attempt ${reconnectAttempts + 1})")
        val request = Request.Builder().url(wsUrl).build()
        webSocket = client.newWebSocket(request, createWebSocketListener())
    }

    fun disconnect() {
        handler.removeCallbacks(reconnectRunnable)
        isConnected.set(false)
        webSocket?.close(1000, "App closed")
        webSocket = null
    }

    fun sendMessage(text: String) {
        val json = buildJsonObject {
            put("type", "chat")
            put("text", text)
            put("platform", "mobile")
        }
        sendOrQueue(json.toString())
    }

    fun sendVisionMessage(base64Image: String) {
        val json = buildJsonObject {
            put("type", "mobile_vision")
            put("image_b64", base64Image)
        }
        sendOrQueue(json.toString())
    }

    private fun sendOrQueue(payload: String) {
        synchronized(queueLock) {
            val ws = webSocket
            if (isConnected.get() && ws != null) {
                ws.send(payload)
            } else {
                messageQueue.add(payload)
                Log.d(TAG, "Queued message (offline). Queue size: ${messageQueue.size}")
            }
        }
    }

    private fun flushQueue() {
        synchronized(queueLock) {
            val ws = webSocket
            if (ws == null || !isConnected.get()) return

            if (messageQueue.isNotEmpty()) {
                Log.d(TAG, "Flushing ${messageQueue.size} queued messages")
                for (msg in messageQueue) {
                    ws.send(msg)
                }
                messageQueue.clear()
            }
        }
    }

    private fun scheduleReconnect() {
        reconnectAttempts++
        val delayMs = (1000L * (1 shl (reconnectAttempts - 1))).coerceAtMost(MAX_RECONNECT_DELAY_MS)
        updateState(ConnectionState.RECONNECTING)
        Log.d(TAG, "Reconnecting in ${delayMs}ms (attempt $reconnectAttempts)")
        handler.postDelayed(reconnectRunnable, delayMs)
    }

    private fun updateState(state: ConnectionState) {
        listener.onConnectionStateChanged(state)
        when (state) {
            ConnectionState.CONNECTED -> listener.onConnected()
            ConnectionState.DISCONNECTED -> listener.onDisconnected()
            else -> {}
        }
    }

    private fun createWebSocketListener(): WebSocketListener {
        return object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "Connected to $serverUrl")
                isConnected.set(true)
                reconnectAttempts = 0
                updateState(ConnectionState.CONNECTED)
                flushQueue()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = Json.parseToJsonElement(text).jsonObject
                    when (json["type"]?.jsonPrimitive?.content) {
                        "speak" -> {
                            val msg = json["text"]?.jsonPrimitive?.content ?: ""
                            val emo = json["emotion"]?.jsonPrimitive?.content ?: "neutral"
                            listener.onMessage(msg, emo)
                        }
                        "state_update" -> {
                            val payload = json["payload"]?.jsonObject
                            val v = payload?.get("valence")?.jsonPrimitive?.doubleOrNull ?: 0.0
                            val a = payload?.get("arousal")?.jsonPrimitive?.doubleOrNull ?: 0.5
                            listener.onStateUpdate(v, a)
                        }
                        "status" -> {
                            val status = json["text"]?.jsonPrimitive?.content ?: "Idle"
                            listener.onStatusUpdate(status)
                        }
                        "task_list" -> {
                            try {
                                val tasksJson = json["tasks"]?.jsonArray
                                val tasks = tasksJson?.let {
                                    Json.decodeFromJsonElement(ListSerializer(TaskItem.serializer()), it)
                                } ?: emptyList()
                                listener.onTaskList(tasks)
                            } catch (e: Exception) {
                                Log.e(TAG, "Error parsing task list", e)
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing message: $text", e)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "Disconnected: $reason")
                isConnected.set(false)
                this@MizuneWebSocket.webSocket = null
                updateState(ConnectionState.DISCONNECTED)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "Connection failure", t)
                isConnected.set(false)
                this@MizuneWebSocket.webSocket = null
                updateState(ConnectionState.DISCONNECTED)
                scheduleReconnect()
            }
        }
    }
}
