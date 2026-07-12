package com.mizune.app

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
                mizuneMessage.value = text
                chatHistory.add(ChatMessage(isUser = false, text = text))

                lifecycleScope.launch {
                    appPreferences.setLastMessage(text)
                    MizuneWidget().updateAll(this@MainActivity)
                }

                currentEmotion.value = when (emotion.lowercase()) {
                    "happy" -> SlimeEmotion.HAPPY
                    "excited" -> SlimeEmotion.EXCITED
                    "angry" -> SlimeEmotion.ANGRY
                    "sad" -> SlimeEmotion.SAD
                    "blush" -> SlimeEmotion.PATTED
                    "surprised" -> SlimeEmotion.PLAYFUL
                    else -> SlimeEmotion.CALM
                }

                lifecycleScope.launch {
                    appPreferences.setWidgetEmotion(currentEmotion.value)
                    MizuneWidget().updateAll(this@MainActivity)
                }

                isThinking.value = false
                vibrateLight()

                val previousEmotion = currentEmotion.value
                currentEmotion.value = SlimeEmotion.SPEAKING
                ttsPlayer.playTts(text, currentApiBaseUrl) {
                    runOnUiThread {
                        currentEmotion.value = previousEmotion
                    }
                }
            }
        }

        override fun onStateUpdate(valence: Double, arousal: Double) {}

        override fun onStatusUpdate(status: String) {
            runOnUiThread {
                if (status.contains("Thinking", true)) {
                    isThinking.value = true
                    currentEmotion.value = SlimeEmotion.THINKING
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
                            onBack = { currentScreen.value = Screen.COMPANION }
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
                runOnUiThread { isRecording.value = true }
            }
            override fun onRecordingStopped() {
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
                runOnUiThread { isRecording.value = false }
                Log.e("MainActivity", "PTT Error: $message")
            }
        }, apiBaseUrl)
    }

    private fun buildApiBaseUrl(serverUrl: String): String {
        val normalized = serverUrl.trim().trimEnd('/')
        return when {
            normalized.startsWith("http://", ignoreCase = true) ||
                    normalized.startsWith("https://", ignoreCase = true) -> normalized
            else -> "https://$normalized"
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
        handleShortcutIntent(intent)
        handleShareIntent(intent)
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
                mizuneService?.sendVisionMessage(b64)
                isThinking.value = true
                mizuneMessage.value = "Analyzing what I see..."
            },
            onOpenSettings = { currentScreen.value = Screen.SETTINGS }
        )
    }

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
