package com.mizune.app

import android.annotation.SuppressLint
import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Base64
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.glance.appwidget.updateAll
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import com.mizune.app.audio.PushToTalkListener
import com.mizune.app.audio.PushToTalkManager
import com.mizune.app.audio.TtsPlayer
import com.mizune.app.data.AppPreferences
import com.mizune.app.network.MizuneWebSocketListener
import com.mizune.app.network.TaskItem
import com.mizune.app.service.MizuneService
import com.mizune.app.ui.ConnectionState
import com.mizune.app.widget.MizuneWidget
import com.mizune.app.ui.SettingsScreen
import com.mizune.app.ui.SlimeEmotion
import com.mizune.app.ui.SlimeScreen
import kotlinx.coroutines.launch
import java.io.ByteArrayOutputStream

import androidx.compose.runtime.mutableStateListOf

data class ChatMessage(val isUser: Boolean, val text: String)


class MainActivity : ComponentActivity() {

    private companion object {
        /** Longest the mic stays deaf for one spoken reply before it is force-resumed.
         *  Matches MizuneService.MAX_SPEAK_MS — the two speak paths must not disagree. */
        const val MAX_SPEAK_MS = 60_000L
    }

    private val uiHandler = android.os.Handler(android.os.Looper.getMainLooper())

    private lateinit var appPreferences: AppPreferences
    private var mizuneService: MizuneService? = null
    private lateinit var ttsPlayer: TtsPlayer
    private var pttManager: PushToTalkManager? = null
    private var currentApiBaseUrl = ""

    // Compose State
    private var currentEmotion = mutableStateOf(SlimeEmotion.CALM)
    private var mizuneMessage = mutableStateOf("Hello Master! Ready when you are.")
    private var isThinking = mutableStateOf(false)
    private var connectionState = mutableStateOf(ConnectionState.DISCONNECTED)
    private var isRecording = mutableStateOf(false)
    private var recordingAmplitude = mutableStateOf(0)
    private val chatHistory = mutableStateListOf<ChatMessage>()
    private var lastMizuneChunkAt = 0L
    private val tasks = mutableStateListOf<TaskItem>()
    private var currentScreen = mutableStateOf(Screen.COMPANION)
    private var shortcutAction = mutableStateOf<String?>(null)

    private enum class Screen { COMPANION, SETTINGS }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        // Result handled implicitly; features check permissions at use time.
    }

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as MizuneService.LocalBinder
            mizuneService = binder.getService().apply {
                addListener(webSocketListener)
            }
            updateForegroundState()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            mizuneService?.removeListener(webSocketListener)
            mizuneService = null
        }
    }

    private val webSocketListener = object : MizuneWebSocketListener {
        override fun onConnected() {}
        override fun onDisconnected() {}

        override fun onConnectionStateChanged(state: ConnectionState) {
            runOnUiThread { connectionState.value = state }
            lifecycleScope.launch {
                appPreferences.setConnectionState(state)
                MizuneWidget().updateAll(this@MainActivity)
            }
        }

        override fun onMessage(text: String, emotion: String) {
            runOnUiThread {
                // Audio, haptics and notifications were gated on ownership; this path
                // never was. So a proactive tick or her reply to somebody else's
                // WhatsApp still seized the speech bubble, changed the slime's emotion
                // and rewrote the home-screen widget — she visibly talked at him every
                // 15 minutes while being technically silent. Half a gate reads as no
                // gate at all.
                //
                // Unsolicited turns are still worth SEEING, so they land in the chat
                // history and nowhere else. The bubble, the emotion and the widget are
                // reserved for turns this phone actually started.
                val ours = awaitingReply()
                if (!ours) {
                    chatHistory.add(ChatMessage(isUser = false, text = text))
                    return@runOnUiThread
                }
                // The server streams one reply as several sentence chunks — merge
                // them into ONE bubble instead of a fragmented wall of messages.
                val now = System.currentTimeMillis()
                val coalescing = chatHistory.isNotEmpty() && !chatHistory.last().isUser &&
                        (now - lastMizuneChunkAt) < 4000
                lastMizuneChunkAt = now

                val fullText: String
                if (coalescing) {
                    fullText = chatHistory.last().text + " " + text
                    chatHistory[chatHistory.size - 1] = ChatMessage(isUser = false, text = fullText)
                } else {
                    fullText = text
                    chatHistory.add(ChatMessage(isUser = false, text = text))
                    // Buzz once per reply. Ownership was already checked above.
                    vibrateLight()
                }
                mizuneMessage.value = fullText

                currentEmotion.value = when (emotion.lowercase()) {
                    "happy" -> SlimeEmotion.HAPPY
                    "excited" -> SlimeEmotion.EXCITED
                    "angry" -> SlimeEmotion.ANGRY
                    "sad" -> SlimeEmotion.SAD
                    "blush" -> SlimeEmotion.PATTED
                    "surprised" -> SlimeEmotion.PLAYFUL
                    else -> SlimeEmotion.CALM
                }
                isThinking.value = false

                if (!coalescing) {
                    lifecycleScope.launch {
                        appPreferences.setLastMessage(text)
                        appPreferences.setWidgetEmotion(currentEmotion.value)
                        MizuneWidget().updateAll(this@MainActivity)
                    }
                }
                // Voice: played ONCE per reply via the streamed 'audio' event (onAudio) —
                // per-sentence /tts calls raced each other and garbled playback.
            }
        }

        override fun onAudio(base64Mp3: String) {
            runOnUiThread {
                // Same rule as the service: her voice only plays for a turn Master
                // started. Unsolicited speech stays visible but silent, so a proactive
                // tick or a reply meant for someone else can't talk out of his pocket.
                if (!awaitingReply()) return@runOnUiThread
                val previousEmotion = currentEmotion.value
                currentEmotion.value = SlimeEmotion.SPEAKING
                // Go deaf while she talks — no AEC, so a live mic hears her own voice and
                // can wake on it, which starts another turn, which speaks again.
                mizuneService?.pauseWakeWord()
                // Watchdog, mirroring MizuneService.speakWithMicPaused. The service has
                // always had one; this path did not, so a playback that never reached
                // STATE_ENDED — a decode failure, or a second reply clearing the queue
                // out from under the first — left the wake word paused until the service
                // restarted. Deaf-forever is a worse bug than a duplicated resume, and
                // resume is idempotent.
                var resumed = false
                val resumeOnce = {
                    if (!resumed) {
                        resumed = true
                        currentEmotion.value = previousEmotion
                        mizuneService?.resumeWakeWord()
                    }
                }
                uiHandler.postDelayed({ resumeOnce() }, MAX_SPEAK_MS)
                ttsPlayer.playBase64(base64Mp3) { runOnUiThread { resumeOnce() } }
            }
        }

        override fun onStateUpdate(valence: Double, arousal: Double) {}

        override fun onStatusUpdate(status: String) {
            runOnUiThread {
                when {
                    // Only react to "Thinking" if WE asked something. The server
                    // broadcasts every frame to every client, so a scheduled task, a
                    // WhatsApp message or the dashboard used to drop this phone into a
                    // thinking state with Master having said nothing — the "she starts
                    // thinking on her own" bug. This is a client-side guard, not the
                    // fix: see .scratch/hands-free-voice/tickets/12-who-is-a-turn-for.md
                    status.contains("Thinking", true) -> {
                        if (awaitingReply()) {
                            isThinking.value = true
                            currentEmotion.value = SlimeEmotion.THINKING
                        }
                    }
                    // Only a 'speak' used to clear the spinner. When the server ended a
                    // turn WITHOUT speaking — vision failures broadcast "Vision Error",
                    // and every turn ends with "Idle" — the UI stayed stuck on
                    // "Analyzing what I see..." forever with no way back.
                    status.equals("Idle", true) || status.contains("Error", true) -> {
                        isThinking.value = false
                        if (status.contains("Error", true)) {
                            mizuneMessage.value = "Something went wrong on my side, Master."
                            currentEmotion.value = SlimeEmotion.SAD
                        }
                    }
                }
            }
        }

        override fun onTaskList(newTasks: List<TaskItem>) {
            runOnUiThread {
                tasks.clear()
                tasks.addAll(newTasks)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        appPreferences = AppPreferences(this)
        ttsPlayer = TtsPlayer(this)

        requestPermissions()

        lifecycleScope.launch {
            appPreferences.serverUrl.collect { serverUrl ->
                val apiBaseUrl = buildApiBaseUrl(serverUrl)
                currentApiBaseUrl = apiBaseUrl
                createOrRecreatePttManager(apiBaseUrl)
                if (mizuneService == null) {
                    startAndBindService(serverUrl)
                }
            }
        }

        handleShortcutIntent(intent)
        handleShareIntent(intent)
        handleAssistIntent(intent)

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    when (currentScreen.value) {
                        Screen.COMPANION -> CompanionScreen()
                        Screen.SETTINGS -> SettingsScreen(
                            connectionState = connectionState.value,
                            appPreferences = appPreferences,
                            onBack = { currentScreen.value = Screen.COMPANION },
                            onCalibrateVoice = { cb ->
                                mizuneService?.calibrateVoiceSample(cb)
                                    ?: cb("Service not connected")
                            },
                            onVoiceStatus = { cb ->
                                mizuneService?.voiceStatus(cb) ?: cb("Service not connected")
                            },
                            onResetVoice = { cb ->
                                mizuneService?.resetVoiceProfile(cb)
                                    ?: cb("Service not connected")
                            },
                            onTestWakeWord = { cb ->
                                mizuneService?.testWakeWord(cb)
                                    ?: cb(false, "Service not connected")
                            },
                            onWakeDiagnostics = {
                                mizuneService?.wakeDiagnostics() ?: emptyList()
                            }
                        )
                    }
                }
            }
        }
    }

    private fun createOrRecreatePttManager(apiBaseUrl: String) {
        if (pttManager?.isRecording() == true) {
            Log.w("MainActivity", "PTT URL change ignored while recording")
            return
        }
        pttManager?.release()
        pttManager = PushToTalkManager(this, object : PushToTalkListener {
            override fun onRecordingStarted() {
                mizuneService?.pauseWakeWord()   // free the mic for push-to-talk
                runOnUiThread { isRecording.value = true }
            }
            override fun onRecordingStopped() {
                mizuneService?.resumeWakeWord()
                runOnUiThread { isRecording.value = false }
            }
            override fun onAmplitude(amplitude: Int) {
                runOnUiThread { recordingAmplitude.value = amplitude }
            }
            override fun onUploadStarted() {
                runOnUiThread {
                    isThinking.value = true
                    mizuneMessage.value = "Processing..."
                }
            }
            override fun onSpeechResult(text: String) {
                runOnUiThread {
                    isRecording.value = false
                    if (text.isNotBlank()) {
                        sendMessage(text)
                    }
                }
            }
            override fun onError(message: String) {
                runOnUiThread {
                    isRecording.value = false
                    // onUploadStarted turns the spinner on; only a 'speak' or an Idle
                    // status turned it off. A failed transcribe produces neither, so the
                    // app sat on "Processing..." forever and looked like she was
                    // thinking on her own — with the network down, permanently.
                    isThinking.value = false
                    mizuneMessage.value = message
                }
                Log.e("MainActivity", "PTT Error: $message")
            }
        }, apiBaseUrl)
    }

    private fun buildApiBaseUrl(serverUrl: String): String {
        // Users enter ws:// URLs for the socket — HTTP calls (TTS/STT) must use
        // http(s). The old version produced "https://ws://..." → every API call died.
        var normalized = serverUrl.trim().trimEnd('/')
        if (normalized.endsWith("/ws", ignoreCase = true)) normalized = normalized.dropLast(3)
        return when {
            normalized.startsWith("ws://", ignoreCase = true) ->
                normalized.replaceFirst("ws://", "http://", ignoreCase = true)
            normalized.startsWith("wss://", ignoreCase = true) ->
                normalized.replaceFirst("wss://", "https://", ignoreCase = true)
            normalized.startsWith("http://", ignoreCase = true) ||
                    normalized.startsWith("https://", ignoreCase = true) -> normalized
            else -> "http://$normalized"   // VM serves plain HTTP on :8001
        }
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
            Manifest.permission.POST_NOTIFICATIONS,
            Manifest.permission.FOREGROUND_SERVICE
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            permissions.add(Manifest.permission.FOREGROUND_SERVICE_DATA_SYNC)
        }

        val needed = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (needed.isNotEmpty()) {
            requestPermissionLauncher.launch(needed.toTypedArray())
        }

        // Accessibility — Mizune's "hands". This is the RELIABLE way to launch apps,
        // tap, type and scroll on any phone (exempt from OEM background-launch blocks).
        // Guide the user to enable it once if it isn't already.
        if (!isAccessibilityEnabled()) {
            try {
                startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS))
                android.widget.Toast.makeText(
                    this,
                    "Enable \"Mizune\" here so she can open apps & do tasks on your phone.",
                    android.widget.Toast.LENGTH_LONG
                ).show()
            } catch (_: Exception) { }
        }
    }

    private fun isAccessibilityEnabled(): Boolean {
        val enabled = android.provider.Settings.Secure.getString(
            contentResolver, android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabled.contains("$packageName/.service.MizuneAccessibilityService") ||
            enabled.contains("$packageName/com.mizune.app.service.MizuneAccessibilityService")
    }

    private fun startAndBindService(serverUrl: String) {
        Intent(this, MizuneService::class.java).also { intent ->
            intent.putExtra("server_url", serverUrl)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        }
        bindService(Intent(this, MizuneService::class.java), serviceConnection, Context.BIND_AUTO_CREATE)
    }

    private fun updateForegroundState() {
        mizuneService?.setAppInForeground(
            lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)
        )
    }

    override fun onResume() {
        super.onResume()
        mizuneService?.setAppInForeground(true)
    }

    override fun onPause() {
        super.onPause()
        mizuneService?.setAppInForeground(false)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleShortcutIntent(intent)
        handleShareIntent(intent)
        handleAssistIntent(intent)
    }

    /**
     * OEM fallback for the assist gesture: some ROMs deliver ACTION_ASSIST to an
     * activity rather than the VoiceInteractionService. Route it to the same one-shot
     * capture so the gesture behaves identically either way.
     */
    /**
     * Android re-delivers the launch Intent to onCreate on every process restart and
     * configuration change, so an Intent acted on once will be acted on again — and
     * again — for the life of that task. Resuming from Recents after a share re-sent the
     * shared text; after an assist gesture it re-opened the microphone with nobody
     * asking. Consuming the Intent is what makes these one-shot.
     */
    private fun consumeIntent(intent: Intent?) {
        intent?.action = null
        intent?.removeExtra(Intent.EXTRA_TEXT)
        intent?.removeExtra(Intent.EXTRA_STREAM)
    }

    private fun handleAssistIntent(intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_ASSIST && action != "android.intent.action.VOICE_COMMAND") return
        consumeIntent(intent)
        Intent(this, MizuneService::class.java).also {
            it.action = MizuneService.ACTION_ASSIST_LISTEN
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(it)
            else startService(it)
        }
        mizuneMessage.value = "Listening, Master…"
    }

    private fun handleShortcutIntent(intent: Intent?) {
        val action = intent?.getStringExtra("shortcut")
        if (!action.isNullOrBlank()) {
            shortcutAction.value = action
        }
    }

    private fun handleShareIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type?.startsWith("text/") == true) {
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
            consumeIntent(intent)   // one share = one send; see consumeIntent
            if (!sharedText.isNullOrBlank()) {
                Thread {
                    Thread.sleep(1500)
                    runOnUiThread {
                        sendMessage("[Shared from another app]\n$sharedText")
                        mizuneMessage.value = "I received what you shared. Let me take a look..."
                        isThinking.value = true
                    }
                }.start()
            }
        } else if (intent?.action == Intent.ACTION_SEND && intent.type?.startsWith("image/") == true) {
            val imageUri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            consumeIntent(intent)   // one share = one send; see consumeIntent
            if (imageUri != null) {
                Thread {
                    try {
                        contentResolver.openInputStream(imageUri)?.use { inputStream ->
                            val bitmap = BitmapFactory.decodeStream(inputStream)
                            if (bitmap != null) {
                                val outputStream = ByteArrayOutputStream()
                                bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 80, outputStream)
                                val base64 = Base64.encodeToString(outputStream.toByteArray(), Base64.NO_WRAP)

                                Thread.sleep(1500)
                                mizuneService?.sendVisionMessage(base64)
                                runOnUiThread {
                                    markOutbound()   // shared image is our turn
                                    isThinking.value = true
                                    mizuneMessage.value = "Looking at your screenshot..."
                                }
                            } else {
                                Log.e("MainActivity", "Failed to decode image from intent")
                            }
                        }
                    } catch (e: Exception) {
                        Log.e("MainActivity", "Failed to process shared image", e)
                    }
                }.start()
            }
        }
    }

    @Composable
    private fun CompanionScreen() {
        SlimeScreen(
            emotion = currentEmotion.value,
            mizuneMessage = mizuneMessage.value,
            chatHistory = chatHistory,
            isThinking = isThinking.value,
            connectionState = connectionState.value,
            isRecording = isRecording.value,
            recordingAmplitude = recordingAmplitude.value,
            tasks = tasks,
            shortcutAction = shortcutAction.value,
            onShortcutHandled = { shortcutAction.value = null },
            onSendMessage = { text -> sendMessage(text) },
            onStartRecording = { pttManager?.startRecording() },
            onStopRecording = { pttManager?.stopRecordingAndUpload() },
            onCancelRecording = { pttManager?.cancelRecording() },
            onCaptureVision = { b64 ->
                markOutbound()      // the camera turn is ours; let its spinner through
                mizuneService?.sendVisionMessage(b64)
                isThinking.value = true
                mizuneMessage.value = "Analyzing what I see..."
            },
            onOpenSettings = { currentScreen.value = Screen.SETTINGS }
        )
    }

    // VIBRATE is declared in the manifest (install-time permission) and the call is
    // guarded; Lint can't see the manifest merge so it false-flags MissingPermission.
    @SuppressLint("MissingPermission")
    private fun vibrateLight() {
        try {
            val vibrator = getSystemService(Vibrator::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(40)
            }
        } catch (e: Exception) {
            Log.w("MainActivity", "Vibration failed", e)
        }
    }

    /**
     * True when this phone is genuinely waiting on a reply to something it sent.
     *
     * The server broadcasts to every client, so without this the phone cannot tell its
     * own turn from a cron job's. The window is generous — a slow model turn can take
     * tens of seconds — but bounded, so a turn that dies server-side can't leave the
     * phone permanently convinced it's still waiting.
     */
    private fun awaitingReply(): Boolean = mizuneService?.turnIsOurs() ?: false

    private fun markOutbound() { mizuneService?.markOutbound() }

    private fun sendMessage(text: String) {
        if (text.isNotBlank()) {
            chatHistory.add(ChatMessage(isUser = true, text = text))
            mizuneService?.sendMessage(text)
            currentEmotion.value = SlimeEmotion.THINKING
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (mizuneService != null) {
            unbindService(serviceConnection)
        }
        pttManager?.release()
        ttsPlayer.release()
    }
}
