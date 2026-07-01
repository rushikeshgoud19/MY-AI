package com.mizune.app.network

import android.util.Log
import kotlinx.serialization.json.*
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit

interface MizuneWebSocketListener {
    fun onConnected()
    fun onDisconnected()
    fun onMessage(text: String, emotion: String)
    fun onStateUpdate(valence: Double, arousal: Double)
    fun onStatusUpdate(status: String)
}

class MizuneWebSocket(private val listener: MizuneWebSocketListener) {
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(15, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val WS_URL = "ws://40.123.215.32:8001/ws"
    
    fun connect() {
        if (webSocket != null) return
        val request = Request.Builder().url(WS_URL).build()
        webSocket = client.newWebSocket(request, createWebSocketListener())
    }

    fun disconnect() {
        webSocket?.close(1000, "App closed")
        webSocket = null
    }

    fun sendMessage(text: String) {
        val json = buildJsonObject {
            put("type", "chat")
            put("text", text)
            put("platform", "mobile")
        }
        webSocket?.send(json.toString())
    }

    fun sendVisionMessage(base64Image: String) {
        val json = buildJsonObject {
            put("type", "mobile_vision")
            put("image_b64", base64Image)
        }
        webSocket?.send(json.toString())
    }

    private fun createWebSocketListener(): WebSocketListener {
        return object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("MizuneWS", "Connected to Azure Cloud")
                listener.onConnected()
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
                    }
                } catch (e: Exception) {
                    Log.e("MizuneWS", "Error parsing message: $text", e)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d("MizuneWS", "Disconnected: $reason")
                this@MizuneWebSocket.webSocket = null
                listener.onDisconnected()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("MizuneWS", "Connection failure", t)
                this@MizuneWebSocket.webSocket = null
                listener.onDisconnected()
                // Auto-reconnect after 3 seconds without blocking
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ connect() }, 3000)
            }
        }
    }
}
