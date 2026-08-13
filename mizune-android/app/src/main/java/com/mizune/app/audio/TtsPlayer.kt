package com.mizune.app.audio

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import org.json.JSONObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

class TtsPlayer(private val context: Context) {
    private val player = ExoPlayer.Builder(context).build().apply {
        val audioAttributes = androidx.media3.common.AudioAttributes.Builder()
            .setUsage(androidx.media3.common.C.USAGE_MEDIA)
            .setContentType(androidx.media3.common.C.AUDIO_CONTENT_TYPE_SPEECH)
            .build()
        setAudioAttributes(audioAttributes, true)
    }

    private var onPlaybackEndedCallback: (() -> Unit)? = null

    init {
        player.addListener(object : androidx.media3.common.Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == androidx.media3.common.Player.STATE_ENDED) {
                    // Clean up all cached chunks occasionally
                    context.cacheDir.listFiles()?.forEach { if (it.name.startsWith("tts_chunk")) it.delete() }
                    
                    // Fire the callback
                    onPlaybackEndedCallback?.invoke()
                    player.clearMediaItems()
                }
            }
        })
    }

    /** Play server-streamed TTS audio directly (base64 MP3 from the /ws 'audio' event). */
    fun playBase64(base64Mp3: String, onPlaybackEnded: () -> Unit = {}) {
        onPlaybackEndedCallback = onPlaybackEnded
        Thread {
            try {
                val bytes = android.util.Base64.decode(base64Mp3, android.util.Base64.DEFAULT)
                val tempFile = java.io.File(context.cacheDir, "tts_chunk_${java.util.UUID.randomUUID()}.mp3")
                tempFile.writeBytes(bytes)
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    player.clearMediaItems()          // latest reply preempts anything queued
                    player.addMediaItem(MediaItem.fromUri(Uri.fromFile(tempFile)))
                    player.prepare()
                    player.play()
                }
            } catch (e: Exception) {
                Log.e("TtsPlayer", "Error playing streamed audio", e)
                android.os.Handler(android.os.Looper.getMainLooper()).post { onPlaybackEndedCallback?.invoke() }
            }
        }.start()
    }

    fun playTts(text: String, serverUrl: String, onPlaybackEnded: () -> Unit) {
        // Guard: ws:// URLs are invalid for OkHttp HTTP calls (silent failure = no voice).
        var baseUrl = serverUrl.trimEnd('/')
        if (baseUrl.startsWith("ws://", ignoreCase = true)) baseUrl = baseUrl.replaceFirst("ws://", "http://", ignoreCase = true)
        if (baseUrl.startsWith("wss://", ignoreCase = true)) baseUrl = baseUrl.replaceFirst("wss://", "https://", ignoreCase = true)
        val ttsUrl = "$baseUrl/tts"
        onPlaybackEndedCallback = onPlaybackEnded
        
        Thread {
            try {
                val client = okhttp3.OkHttpClient()
                val json = JSONObject().put("text", text).toString()
                val mediaType = "application/json".toMediaType()
                val body = json.toRequestBody(mediaType)
                val request = okhttp3.Request.Builder()
                    .url(ttsUrl)
                    .post(body)
                    .build()
                    
                val response = client.newCall(request).execute()
                if (response.isSuccessful) {
                    val bytes = response.body?.bytes()
                    if (bytes != null) {
                        val fileId = java.util.UUID.randomUUID().toString()
                        val tempFile = java.io.File(context.cacheDir, "tts_chunk_$fileId.mp3")
                        tempFile.writeBytes(bytes)
                        
                        // Queue and play on main thread
                        android.os.Handler(android.os.Looper.getMainLooper()).post {
                            player.addMediaItem(MediaItem.fromUri(Uri.fromFile(tempFile)))
                            if (player.playbackState == androidx.media3.common.Player.STATE_IDLE || 
                                player.playbackState == androidx.media3.common.Player.STATE_ENDED) {
                                player.prepare()
                                player.play()
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("TtsPlayer", "Error fetching TTS chunk", e)
                android.os.Handler(android.os.Looper.getMainLooper()).post { onPlaybackEndedCallback?.invoke() }
            }
        }.start()
    }

    fun release() {
        player.release()
    }
}
