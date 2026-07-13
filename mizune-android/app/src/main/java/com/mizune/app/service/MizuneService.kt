package com.mizune.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.net.Uri
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.mizune.app.MainActivity
import com.mizune.app.R
import com.mizune.app.data.AppPreferences
import com.mizune.app.network.MizuneWebSocket
import com.mizune.app.network.MizuneWebSocketListener
import com.mizune.app.network.TaskItem
import com.mizune.app.ui.ConnectionState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MizuneService : Service() {

    private val binder = LocalBinder()
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var appPreferences: AppPreferences
    private lateinit var webSocket: MizuneWebSocket

    private val uiListeners = mutableListOf<MizuneWebSocketListener>()
    private val listenersLock = Object()
    private var isAppInForeground = false
    private var lastConnectionState = ConnectionState.DISCONNECTED

    companion object {
        private const val TAG = "MizuneService"
        private const val CHANNEL_ID = "mizune_persistent"
        private const val ALERT_CHANNEL_ID = "mizune_alerts"
        private const val NOTIFICATION_ID = 1
    }

    inner class LocalBinder : Binder() {
        fun getService(): MizuneService = this@MizuneService
    }

    override fun onCreate() {
        super.onCreate()
        appPreferences = AppPreferences(this)
        createNotificationChannels()
        serviceScope.launch {
            appPreferences.serverUrl.collect { newUrl ->
                if (::webSocket.isInitialized) {
                    webSocket.disconnect()
                }
                initializeWebSocket(newUrl)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, createPersistentNotification())
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onDestroy() {
        super.onDestroy()
        if (::webSocket.isInitialized) {
            webSocket.disconnect()
        }
        serviceScope.launch { /* allow cleanup */ }
    }

    private fun initializeWebSocket(serverUrl: String) {
        webSocket = MizuneWebSocket(object : MizuneWebSocketListener {
            override fun onConnected() {}
            override fun onDisconnected() {}

            override fun onConnectionStateChanged(state: ConnectionState) {
                lastConnectionState = state
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onConnectionStateChanged(state) }
                }
                updatePersistentNotification()
            }

            override fun onMessage(text: String, emotion: String) {
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onMessage(text, emotion) }
                }
                if (!isAppInForeground) {
                    showAlertNotification("Mizune", text)
                }
            }

            override fun onStateUpdate(valence: Double, arousal: Double) {
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onStateUpdate(valence, arousal) }
                }
            }

            override fun onStatusUpdate(status: String) {
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onStatusUpdate(status) }
                }
            }

            override fun onTaskList(tasks: List<TaskItem>) {
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onTaskList(tasks) }
                }
            }

            override fun onAudio(base64Mp3: String) {
                synchronized(listenersLock) {
                    uiListeners.forEach { it.onAudio(base64Mp3) }
                }
            }

            override fun onDeviceCommand(requestId: String, action: String, args: Map<String, String>) {
                val result = try {
                    when (action) {
                        "notify" -> {
                            val title = args["title"] ?: "Mizune"
                            val message = args["message"] ?: args["text"] ?: ""
                            showAlertNotification(title, message)
                            "Notification shown on phone."
                        }
                        "open_url" -> {
                            val url = args["url"] ?: ""
                            if (url.startsWith("http://") || url.startsWith("https://")) {
                                launchActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)), "open $url")
                            } else "Refused: only http(s) URLs are allowed."
                        }
                        "open_app" -> {
                            val name = args["app_name"] ?: args["app"] ?: args["name"] ?: ""
                            val launch = resolveLaunchIntent(name)
                            if (launch == null) "Couldn't find an app matching '$name' on the phone."
                            else launchActivity(launch, "open $name")
                        }
                        "speak" -> {
                            val text = args["text"] ?: args["message"] ?: ""
                            synchronized(listenersLock) {
                                uiListeners.forEach { it.onMessage(text, "neutral") }
                            }
                            if (!isAppInForeground) showAlertNotification("Mizune", text)
                            "Spoken/notified on phone."
                        }
                        else -> "Unknown action '$action'. Phone supports: notify, open_url, open_app, speak."
                    }
                } catch (e: Exception) {
                    Log.e("MizuneService", "Device command failed", e)
                    "Error executing $action on phone: ${e.message}"
                }
                webSocket.sendDeviceResult(requestId, result)
            }
        }, serverUrl)

        webSocket.connect()
    }

    fun setAppInForeground(inForeground: Boolean) {
        isAppInForeground = inForeground
    }

    fun addListener(listener: MizuneWebSocketListener) {
        synchronized(listenersLock) {
            uiListeners.add(listener)
        }
        // Immediately sync current state
        listener.onConnectionStateChanged(lastConnectionState)
    }

    fun removeListener(listener: MizuneWebSocketListener) {
        synchronized(listenersLock) {
            uiListeners.remove(listener)
        }
    }

    /**
     * Launch an activity from the background. Android 10+ blocks this silently unless
     * the app holds the "Display over other apps" (overlay) privilege — so we report
     * HONESTLY whether the launch could actually happen, and fall back to a tappable
     * notification when the privilege is missing (instead of pretending it worked).
     */
    private fun launchActivity(intent: Intent, describe: String): String {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val canLaunch = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
                android.provider.Settings.canDrawOverlays(this)
        return try {
            if (canLaunch) {
                startActivity(intent)
                "Done — asked the phone to $describe."
            } else {
                // No overlay privilege: post a full-screen-intent notification the user
                // can tap to complete the action, and say so plainly.
                showLaunchNotification(intent, describe)
                "I set up '$describe' but Android needs the 'Display over other apps' " +
                    "permission for me to open it myself — tap the notification, or grant " +
                    "that permission once in the Mizune app settings."
            }
        } catch (e: Exception) {
            showLaunchNotification(intent, describe)
            "Android blocked the direct launch ($describe); I sent a tappable notification instead."
        }
    }

    /** Resolve a spoken app name (e.g. "brave", "spotify") to a launch intent. */
    private fun resolveLaunchIntent(name: String): Intent? {
        if (name.isBlank()) return null
        val pm = packageManager
        val query = name.trim().lowercase()
        // Common aliases → package hints
        val aliases = mapOf(
            "brave" to "com.brave", "chrome" to "com.android.chrome",
            "youtube" to "com.google.android.youtube", "yt music" to "com.google.android.apps.youtube.music",
            "youtube music" to "com.google.android.apps.youtube.music",
            "spotify" to "com.spotify", "whatsapp" to "com.whatsapp",
            "instagram" to "com.instagram", "maps" to "com.google.android.apps.maps",
            "gmail" to "com.google.android.gm"
        )
        val hint = aliases.entries.firstOrNull { query.contains(it.key) }?.value
        val installed = pm.getInstalledApplications(0)
        val match = installed.firstOrNull { app ->
            (hint != null && app.packageName.startsWith(hint)) ||
                pm.getApplicationLabel(app).toString().lowercase() == query ||
                pm.getApplicationLabel(app).toString().lowercase().contains(query)
        }
        return match?.let { pm.getLaunchIntentForPackage(it.packageName) }
    }

    private fun showLaunchNotification(intent: Intent, describe: String) {
        val pending = PendingIntent.getActivity(
            this, describe.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notif = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Mizune")
            .setContentText("Tap to $describe")
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setFullScreenIntent(pending, true)
            .setContentIntent(pending)
            .build()
        getSystemService(NotificationManager::class.java)
            .notify(describe.hashCode(), notif)
    }

    fun sendMessage(text: String) {
        if (::webSocket.isInitialized) {
            webSocket.sendMessage(text)
        }
    }

    fun sendVisionMessage(base64Image: String) {
        if (::webSocket.isInitialized) {
            webSocket.sendVisionMessage(base64Image)
        }
    }

    fun reconnectWithServer(serverUrl: String) {
        if (::webSocket.isInitialized) {
            webSocket.disconnect()
        }
        initializeWebSocket(serverUrl)
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val persistentChannel = NotificationChannel(
                CHANNEL_ID,
                "Mizune Connection",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Mizune connected in the background"
                setShowBadge(false)
            }

            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "Mizune Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifications for messages and reminders"
                setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION), null)
            }

            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannels(listOf(persistentChannel, alertChannel))
        }
    }

    private fun createPersistentNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Mizune is awake")
            .setContentText("Status: ${lastConnectionState.label}")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun updatePersistentNotification() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, createPersistentNotification())
    }

    private fun showAlertNotification(title: String, message: String) {
        val pendingIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(message.take(100))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(System.currentTimeMillis().toInt(), notification)
    }
}
