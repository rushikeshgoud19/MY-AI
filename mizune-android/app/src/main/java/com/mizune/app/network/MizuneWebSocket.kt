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
    /** Device-node command from the brain (notify / open_url / speak). */
    fun onDeviceCommand(requestId: String, action: String, args: Map<String, String>) {}
    /** Server-generated TTS audio for the last reply (base64, one per full reply). */
    fun onAudio(base64Mp3: String) {}
}

class MizuneWebSocket(
    private val listener: MizuneWebSocketListener,
    private val serverUrl: String,
    /** Dashboard API key. Sent as ?key= so the server can flip ws_auth_required on
     *  without cutting the phone off. Blank = omitted (server default is auth-off). */
    private val apiKey: String = "",
    /** Live capability list, evaluated at every (re)registration — never a constant.
     *  See [com.mizune.app.service.DeviceCapabilities] for why this is a lambda. */
    private val capabilityProvider: () -> List<String> = { emptyList() }
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
    /** Set while WE are tearing the socket down, so onClosed doesn't reconnect it. */
    private val intentionalClose = AtomicBoolean(false)

    /** This connection's id, from the server's `hello` frame. Null on an older backend. */
    @Volatile private var myClientId: String? = null

    /** `origin` of the frame being dispatched right now. Null on an older backend. */
    @Volatile private var lastFrameOrigin: String? = null

    /**
     * Whether the frame currently being handled belongs to a turn THIS phone started.
     *
     * TRUE / FALSE only when the server said so. Null means "no opinion" — an older
     * backend that doesn't stamp frames — and the caller must fall back to its timing
     * guess rather than assume either way. Assuming false there would mute her
     * completely the moment the app is rebuilt without the server being redeployed,
     * which is a far worse failure than the one this replaces.
     */
    fun frameIsOurs(): Boolean? {
        val mine = myClientId ?: return null
        val origin = lastFrameOrigin ?: return null
        return origin == mine
    }

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
            // Backend has NO TLS (plain http on the VM) — defaulting a bare host to
            // wss:// made every connection die at the TLS handshake, silently.
            normalized = "ws://$normalized"
        }
        // Idempotent: accept URLs entered with or without a trailing /ws —
        // appending blindly produced /ws/ws → handshake 403 → reconnect flapping.
        val base = if (normalized.endsWith("/ws", ignoreCase = true)) normalized else "$normalized/ws"
        // Auth token as a query param (the server reads ?key=). Encoded, because an
        // unescaped key with +/= in it silently authenticates as a DIFFERENT string.
        val key = apiKey.trim()
        if (key.isEmpty()) return base
        val encoded = java.net.URLEncoder.encode(key, "UTF-8")
        return if (base.contains('?')) "$base&key=$encoded" else "$base?key=$encoded"
    }

    fun connect() {
        if (webSocket != null) return

        intentionalClose.set(false)
        // A new connection gets a new id. Carrying the old one over would mark every
        // frame "not ours" until the next hello — silent, but wrong for a real reply.
        myClientId = null
        lastFrameOrigin = null
        updateState(ConnectionState.CONNECTING)
        val wsUrl = buildWsUrl()
        // Log the key-free form: the URL now carries the API key and logcat is readable
        // by anyone with adb.
        Log.d(TAG, "Connecting to ${wsUrl.substringBefore("?key=")} (attempt ${reconnectAttempts + 1})")
        val request = Request.Builder().url(wsUrl).build()
        webSocket = client.newWebSocket(request, createWebSocketListener())
    }

    fun disconnect() {
        intentionalClose.set(true)
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

    /**
     * Register this phone as a device node, advertising exactly what it can do RIGHT NOW.
     * Re-sent whenever a runtime grant changes (e.g. Master toggles Accessibility), so a
     * revoked permission disappears from the registry instead of lingering as a false claim.
     */
    fun sendRegistration(target: WebSocket? = null) {
        val caps = capabilityProvider()
        val reg = buildJsonObject {
            put("type", "register_device")
            put("device_name", "phone")
            put("platform", "android")
            put("capabilities", buildJsonArray { caps.forEach { add(it) } })
        }
        // [target] is the socket handed to onOpen. It must be used there: onOpen runs on
        // OkHttp's thread and can beat the `webSocket = ...` assignment in connect(), so
        // reading the field would drop the very first registration and leave the phone
        // advertising nothing at all.
        // Registration is state, not a queued event: if we're offline there is nothing to
        // re-declare to, and onOpen re-registers with a freshly evaluated list anyway.
        val sent = synchronized(queueLock) {
            val ws = target ?: webSocket
            if (ws != null && (target != null || isConnected.get())) {
                ws.send(reg.toString()); true
            } else false
        }
        Log.d(TAG, if (sent) "Registered capabilities: $caps" else "Skipped registration (offline)")
    }

    fun sendDeviceResult(requestId: String, result: String) {
        val payload = buildJsonObject {
            put("type", "device_result")
            put("request_id", requestId)
            put("result", result)
        }
        sendOrQueue(payload.toString())
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
                sendRegistration(webSocket)   // the onOpen socket, not the field — see above
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = Json.parseToJsonElement(text).jsonObject
                    val frameType = json["type"]?.jsonPrimitive?.content
                    // The server now stamps every frame with the client whose turn
                    // produced it (server/websocket.py). Absent on an un-deployed
                    // backend, which is why nothing here may REQUIRE it.
                    lastFrameOrigin = json["origin"]?.jsonPrimitive?.content
                    // Every inbound frame, typed. Without this there was no way to tell
                    // "the server pushed a turn at this phone" from "the phone woke
                    // itself" — which is the question three attempted fixes were
                    // decided without. Type and size only: an audio frame is megabytes
                    // of base64 and logcat is readable by anyone with adb.
                    Log.d(TAG, "RX type=$frameType len=${text.length}")
                    when (frameType) {
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
                        "device_command" -> {
                            val requestId = json["request_id"]?.jsonPrimitive?.content ?: ""
                            val action = json["action"]?.jsonPrimitive?.content ?: ""
                            val args = json["args"]?.jsonObject?.mapValues { entry ->
                                entry.value.jsonPrimitive.content
                            } ?: emptyMap()
                            if (requestId.isNotEmpty() && action.isNotEmpty()) {
                                listener.onDeviceCommand(requestId, action, args)
                            }
                        }
                        "device_registered" -> Log.d(TAG, "Registered as device node")
                        "hello" -> {
                            myClientId = json["client_id"]?.jsonPrimitive?.content
                            Log.d(TAG, "Turn ownership available: client_id=$myClientId")
                        }
                        "audio" -> {
                            val b64 = json["b64"]?.jsonPrimitive?.content ?: ""
                            if (b64.isNotEmpty()) listener.onAudio(b64)
                        }
                        // The VM runs a backend that matches neither server.py nor
                        // legacy/backend_main.py, so frames this client has never seen
                        // are expected. Dropping them silently is how a whole feature
                        // can be live on the server and invisible on the phone.
                        else -> Log.d(TAG, "RX unhandled frame type=$frameType")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing message: $text", e)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "Disconnected: code=$code reason=$reason")
                isConnected.set(false)
                this@MizuneWebSocket.webSocket = null
                updateState(ConnectionState.DISCONNECTED)
                // A CLEAN close is not a reason to stay dead. Only onFailure used to
                // reconnect, so every orderly shutdown from the other end — the VM
                // restarting, a proxy idle-timeout, the server dropping the client —
                // left the phone silently disconnected until the app was reopened. It
                // looked exactly like "she stopped answering". Reconnect unless WE
                // closed it.
                if (!intentionalClose.get()) scheduleReconnect()
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
