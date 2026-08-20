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

    @Volatile private var onPlaybackEndedCallback: (() -> Unit)? = null

    /** The clip currently loaded. Only this one gets deleted when playback ends. */
    @Volatile private var currentFile: java.io.File? = null

    /**
     * Take the pending callback and clear it, so it can only ever run once.
     *
     * Callers pause the microphone before playing and un-pause in this callback. The
     * field used to be plain-overwritten by the next `playBase64`, so a second reply
     * arriving while the first was still playing dropped the first callback on the
     * floor — and with it the un-pause. The mic stayed deaf with nothing left to wake it.
     */
    private fun fireEnded() {
        val cb = onPlaybackEndedCallback
        onPlaybackEndedCallback = null
        cb?.invoke()
    }

    /** Delete the clip we just finished with — and only that one. */
    private fun cleanupCurrent() {
        val f = currentFile
        currentFile = null
        try { f?.delete() } catch (_: Exception) {}
    }

    init {
        player.addListener(object : androidx.media3.common.Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == androidx.media3.common.Player.STATE_ENDED) {
                    // Delete THIS clip, not every tts_chunk in the cache. There are two
                    // TtsPlayers alive — MainActivity's and MizuneService's — sharing one
                    // cacheDir, so the blanket wipe deleted the other one's file out from
                    // under it mid-playback and turned her voice into a playback error.
                    cleanupCurrent()
                    fireEnded()
                    player.clearMediaItems()
                }
            }

            // Callers now pause the MICROPHONE while she speaks (so she can't wake on
            // her own voice) and un-pause in the callback. A playback error that never
            // fired it would leave the wake word dead until the service restarted, so
            // failure must complete the callback too.
            override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                Log.e("TtsPlayer", "Playback error", error)
                cleanupCurrent()
                fireEnded()
                player.clearMediaItems()
            }
        })
    }

    /** Play server-streamed TTS audio directly (base64 MP3 from the /ws 'audio' event). */
    fun playBase64(base64Mp3: String, onPlaybackEnded: () -> Unit = {}) {
        // Retire the previous clip's callback before adopting a new one. Preempting is
        // deliberate — the latest reply should win — but the preempted turn still has a
        // paused microphone waiting on its callback, and clearMediaItems() moves the
        // player to IDLE, not ENDED, so no listener would ever fire it.
        fireEnded()
        onPlaybackEndedCallback = onPlaybackEnded
        Thread {
            try {
                val bytes = android.util.Base64.decode(base64Mp3, android.util.Base64.DEFAULT)
                val tempFile = java.io.File(context.cacheDir, "tts_chunk_${java.util.UUID.randomUUID()}.mp3")
                tempFile.writeBytes(bytes)
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    player.clearMediaItems()          // latest reply preempts anything queued
                    cleanupCurrent()                  // ...and its file goes with it
                    currentFile = tempFile
                    player.addMediaItem(MediaItem.fromUri(Uri.fromFile(tempFile)))
                    player.prepare()
                    player.play()
                }
            } catch (e: Exception) {
                Log.e("TtsPlayer", "Error playing streamed audio", e)
                android.os.Handler(android.os.Looper.getMainLooper()).post { fireEnded() }
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
                android.os.Handler(android.os.Looper.getMainLooper()).post { fireEnded() }
            }
        }.start()
    }

    fun release() {
        // A caller waiting on the un-pause must not be stranded by a teardown either.
        fireEnded()
        cleanupCurrent()
        player.release()
    }
}
