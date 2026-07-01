
package com.mizune.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import java.io.ByteArrayOutputStream
import com.mizune.app.audio.TtsPlayer
import com.mizune.app.audio.PushToTalkManager
import com.mizune.app.audio.PushToTalkListener
import com.mizune.app.network.MizuneWebSocket
import com.mizune.app.network.MizuneWebSocketListener
import com.mizune.app.ui.SlimeEmotion
import com.mizune.app.ui.SlimeScreen

import androidx.compose.runtime.mutableStateListOf

data class ChatMessage(val isUser: Boolean, val text: String)

class MainActivity : ComponentActivity() {

    private lateinit var webSocket: MizuneWebSocket
    private lateinit var ttsPlayer: TtsPlayer
    private lateinit var pttManager: PushToTalkManager

    // Compose State
    private var currentEmotion = mutableStateOf(SlimeEmotion.CALM)
    private var mizuneMessage = mutableStateOf("Hello Master! Ready when you are.")
    private var isThinking = mutableStateOf(false)
    private var connectionStatus = mutableStateOf("Disconnected")
    private var isRecording = mutableStateOf(false)
    private val chatHistory = mutableStateListOf<ChatMessage>()

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // Handle permissions
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        ttsPlayer = TtsPlayer(this)
        
        pttManager = PushToTalkManager(this, object : PushToTalkListener {
            override fun onRecordingStarted() {
                runOnUiThread { isRecording.value = true }
            }
            override fun onRecordingStopped() {
                runOnUiThread { isRecording.value = false }
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
        }, "http://40.123.215.32:8000")

        webSocket = MizuneWebSocket(object : MizuneWebSocketListener {
            override fun onConnected() {
                runOnUiThread { connectionStatus.value = "Connected to Server" }
            }

            override fun onDisconnected() {
                runOnUiThread { connectionStatus.value = "Disconnected" }
            }

            override fun onMessage(text: String, emotion: String) {
                runOnUiThread {
                    mizuneMessage.value = text
                    chatHistory.add(ChatMessage(isUser = false, text = text))
                    
                    // Map emotion string to SlimeEmotion
                    currentEmotion.value = when(emotion.lowercase()) {
                        "happy" -> SlimeEmotion.HAPPY
                        "excited" -> SlimeEmotion.EXCITED
                        "angry" -> SlimeEmotion.ANGRY
                        "sad" -> SlimeEmotion.SAD
                        "blush" -> SlimeEmotion.PATTED
                        "surprised" -> SlimeEmotion.PLAYFUL
                        else -> SlimeEmotion.CALM
                    }
                    
                    isThinking.value = false
                    
                    // Play TTS and trigger speaking animation
                    val previousEmotion = currentEmotion.value
                    currentEmotion.value = SlimeEmotion.SPEAKING
                    ttsPlayer.playTts(text) {
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
        })

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissionLauncher.launch(arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA))
        }

        webSocket.connect()
        
        // Handle incoming image share
        if (intent?.action == Intent.ACTION_SEND && intent.type?.startsWith("image/") == true) {
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
                                
                                // Wait for websocket to connect (hacky but works for now)
                                Thread.sleep(1500)
                                webSocket.sendVisionMessage(base64)
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

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    SlimeScreen(
                        emotion = currentEmotion.value,
                        mizuneMessage = mizuneMessage.value,
                        chatHistory = chatHistory,
                        isThinking = isThinking.value,
                        connectionStatus = connectionStatus.value,
                        isRecording = isRecording.value,
                        onSendMessage = { text -> sendMessage(text) },
                        onStartRecording = { pttManager.startRecording() },
                        onStopRecording = { pttManager.stopRecordingAndUpload() },
                        onCancelRecording = { pttManager.cancelRecording() },
                        onCaptureVision = { b64 ->
                            webSocket.sendVisionMessage(b64)
                            isThinking.value = true
                            mizuneMessage.value = "Analyzing what I see..."
                        }
                    )
                }
            }
        }
    }

    private fun sendMessage(text: String) {
        if (text.isNotBlank()) {
            chatHistory.add(ChatMessage(isUser = true, text = text))
            webSocket.sendMessage(text)
            currentEmotion.value = SlimeEmotion.THINKING
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocket.disconnect()
        pttManager.release()
        ttsPlayer.release()
    }
}
