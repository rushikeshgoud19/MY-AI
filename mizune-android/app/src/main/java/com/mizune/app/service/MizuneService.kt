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
    private var wakeWord: com.mizune.app.audio.WakeWordDetector? = null

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
        startWakeWord()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    /** Always-on "Baka Mizune" listener → routes the spoken command to her brain. */
    private fun startWakeWord() {
        if (wakeWord != null) return
        wakeWord = com.mizune.app.audio.WakeWordDetector(this, object : com.mizune.app.audio.WakeWordListener {
            override fun onWakeWordDetected() {
                vibrateOnce()   // subtle "I'm listening" cue
            }
            override fun onCommandRecognized(command: String) {
                if (command.isNotBlank() && ::webSocket.isInitialized) {
                    webSocket.sendMessage(command)   // → {type:chat} → brain → real-voice reply
                }
            }
            override fun onError(error: String) { Log.w(TAG, "WakeWord: $error") }
            override fun onReadyForSpeech() {}
        }).also { it.startListening() }
        Log.d(TAG, "Baka-Mizune wake word listening")
    }

    /** Pause/resume wake detection so it doesn't fight push-to-talk for the mic. */
    fun pauseWakeWord() { wakeWord?.pause() }
    fun resumeWakeWord() { wakeWord?.resume() }

    private fun vibrateOnce() {
        try {
            val v = getSystemService(android.os.Vibrator::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                v?.vibrate(android.os.VibrationEffect.createOneShot(35, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
            else @Suppress("DEPRECATION") v?.vibrate(35)
        } catch (_: Exception) {}
    }

    override fun onDestroy() {
        super.onDestroy()
        wakeWord?.stopListening()
        wakeWord = null
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
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                // Optional: force a specific browser (e.g. Brave) instead of
                                // letting the URL deep-link into an app (YT Music app).
                                val browser = args["browser"] ?: args["package"]
                                val pkg = if (!browser.isNullOrBlank()) resolveBrowserPackage(browser) else null
                                if (pkg != null) intent.setPackage(pkg)
                                launchIntent(intent, "open $url" + if (pkg != null) " in $browser" else "")
                            } else "Refused: only http(s) URLs are allowed."
                        }
                        "open_app" -> {
                            val name = args["app_name"] ?: args["app"] ?: args["name"] ?: ""
                            val launch = resolveLaunchIntent(name)
                            if (launch == null) "Couldn't find an app matching '$name' on the phone."
                            else launchIntent(launch, "open $name")
                        }
                        "tap" -> {
                            val text = args["text"] ?: args["target"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("tap '$text'")
                            else if (MizuneAccessibilityService.instance?.tapByText(text) == true)
                                "Tapped '$text' on the phone."
                            else "Couldn't find '$text' on the current screen."
                        }
                        "type" -> {
                            val text = args["text"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("type text")
                            else if (MizuneAccessibilityService.instance?.typeText(text) == true)
                                "Typed the text on the phone."
                            else "No text field is focused on the phone right now."
                        }
                        "press" -> {
                            val key = args["key"] ?: args["button"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("press $key")
                            else if (MizuneAccessibilityService.instance?.press(key) == true)
                                "Pressed $key on the phone."
                            else "Couldn't press '$key' (try: back, home, recents, notifications)."
                        }
                        "scroll" -> {
                            val dir = args["direction"] ?: "down"
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("scroll")
                            else if (MizuneAccessibilityService.instance?.scroll(dir) == true)
                                "Scrolled $dir on the phone."
                            else "Nothing scrollable on the current screen."
                        }
                        "read_screen" -> {
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("read the screen")
                            else "SCREEN:\n" + (MizuneAccessibilityService.instance?.dumpScreen() ?: "(unreadable)")
                        }
                        "speak" -> {
                            val text = args["text"] ?: args["message"] ?: ""
                            synchronized(listenersLock) {
                                uiListeners.forEach { it.onMessage(text, "neutral") }
                            }
                            if (!isAppInForeground) showAlertNotification("Mizune", text)
                            "Spoken/notified on phone."
                        }
                        else -> "Unknown action '$action'. Phone supports: notify, open_url, open_app, tap, type, press, scroll, read_screen, speak."
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

    private fun needsAccessibility(what: String): String =
        "I need the Accessibility permission to $what. Open the Mizune app once and tap " +
        "\"Enable Mizune's hands\" (Settings → Accessibility → Mizune → On). Then I can do it every time."

    /**
     * Launch an app/URL. Preferred path is the AccessibilityService — it's exempt from
     * the OEM background-launch blocking (OnePlus/OxygenOS etc.) that silently swallows
     * a plain foreground-service startActivity. Falls back to overlay-based launch, then
     * to a tappable notification — and reports HONESTLY which happened.
     */
    private fun launchIntent(intent: Intent, describe: String): String {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // 1. Accessibility (reliable everywhere)
        if (MizuneAccessibilityService.isEnabled() &&
            MizuneAccessibilityService.instance?.launch(intent) == true) {
            return "Done — opened it on the phone ($describe)."
        }
        // 2. Overlay-privileged direct launch (works on stock Android with permission)
        val canOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
                android.provider.Settings.canDrawOverlays(this)
        if (canOverlay) {
            try {
                startActivity(intent)
                // On OEM ROMs this can be silently dropped, so be honest, not boastful.
                return "Tried to $describe on the phone. If nothing appeared, enable " +
                    "Mizune's Accessibility permission and I'll do it reliably."
            } catch (_: Exception) { /* fall through */ }
        }
        // 3. Tappable notification fallback
        showLaunchNotification(intent, describe)
        return "I couldn't launch it directly (OEM background limits). I sent a tappable " +
            "notification — or enable Mizune's Accessibility permission for one-tap-free launches."
    }

    /** Resolve a browser name to its installed package (so a URL opens THERE, not in
     *  an app that claims the link). Falls back to null if the browser isn't installed. */
    private fun resolveBrowserPackage(name: String): String? {
        val pm = packageManager
        val q = name.trim().lowercase()
        val candidates = when {
            q.contains("brave") -> listOf("com.brave.browser", "com.brave.browser_beta")
            q.contains("chrome") -> listOf("com.android.chrome")
            q.contains("firefox") -> listOf("org.mozilla.firefox")
            q.contains("edge") -> listOf("com.microsoft.emmx")
            else -> listOf(q)
        }
        for (c in candidates) {
            try { pm.getPackageInfo(c, 0); return c } catch (_: Exception) {}
        }
        return null
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
