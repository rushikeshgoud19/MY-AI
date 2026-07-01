package com.mizune.app.audio

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

interface PushToTalkListener {
    fun onRecordingStarted()
    fun onRecordingStopped()
    fun onUploadStarted()
    fun onSpeechResult(text: String)
    fun onError(message: String)
}

class PushToTalkManager(
    private val context: Context,
    private val listener: PushToTalkListener,
    private val serverBaseUrl: String
) {

    private var mediaRecorder: MediaRecorder? = null
    private var audioFile: File? = null
    private var isRecording = false

    private val managerScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val httpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    fun startRecording() {
        if (isRecording) return

        val file = createAudioFile()
        audioFile = file

        val recorder = newMediaRecorder()

        try {
            recorder.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioEncodingBitRate(128_000)
                setAudioSamplingRate(44_100)
                setOutputFile(file.absolutePath)
                prepare()
                start()
            }
            mediaRecorder = recorder
            isRecording = true
            listener.onRecordingStarted()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            listener.onError("Could not start recording: ${e.message}")
            safeReleaseRecorder()
            file.delete()
            audioFile = null
        }
    }

    fun stopRecordingAndUpload() {
        if (!isRecording) return
        
        // 1. Immediately update UI to show we stopped listening
        isRecording = false
        listener.onRecordingStopped()

        val file = audioFile
        val recorder = mediaRecorder
        audioFile = null
        mediaRecorder = null

        // 2. Stop and upload in the background to avoid blocking the main thread/UI
        managerScope.launch {
            try {
                recorder?.stop()
            } catch (e: Exception) {
                Log.w(TAG, "stop() threw — recording likely too short", e)
            } finally {
                try {
                    recorder?.release()
                } catch (e: Exception) {}
            }

            if (file == null || !file.exists() || file.length() < MIN_VALID_FILE_BYTES) {
                withContext(Dispatchers.Main) {
                    listener.onError("Recording was empty or too short — try holding the button longer.")
                }
                file?.delete()
                return@launch
            }

            uploadAudio(file)
        }
    }

    fun cancelRecording() {
        if (!isRecording) {
            audioFile?.delete()
            audioFile = null
            return
        }
        try {
            mediaRecorder?.stop()
        } catch (_: Exception) {} finally {
            safeReleaseRecorder()
            isRecording = false
            audioFile?.delete()
            audioFile = null
            listener.onRecordingStopped()
        }
    }

    fun release() {
        cancelRecording()
        managerScope.cancel()
    }

    private fun uploadAudio(file: File) {
        managerScope.launch(Dispatchers.Main) {
            listener.onUploadStarted()
        }

        managerScope.launch {
            try {
                val mediaType = "audio/mp4".toMediaTypeOrNull()
                val requestBody = file.asRequestBody(mediaType)

                val multipartBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("audio_file", file.name, requestBody)
                    .build()

                val request = Request.Builder()
                    .url("$serverBaseUrl/api/transcribe")
                    .post(multipartBody)
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    val bodyString = response.body?.string().orEmpty()

                    if (!response.isSuccessful) {
                        withContext(Dispatchers.Main) {
                            listener.onError("Server error ${response.code}: ${bodyString.take(200)}")
                        }
                        return@launch
                    }

                    val transcript = runCatching { JSONObject(bodyString).optString("text", "") }
                        .getOrDefault("")

                    withContext(Dispatchers.Main) {
                        if (transcript.isNotBlank()) {
                            listener.onSpeechResult(transcript)
                        } else {
                            listener.onError("Server returned an empty transcript.")
                        }
                    }
                }
            } catch (e: IOException) {
                withContext(Dispatchers.Main) {
                    listener.onError("Network error — is the server reachable? (${e.message})")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    listener.onError("Unexpected error: ${e.message}")
                }
            } finally {
                file.delete()
            }
        }
    }

    private fun newMediaRecorder(): MediaRecorder =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }

    private fun createAudioFile(): File =
        File(context.cacheDir, "ptt_${System.currentTimeMillis()}.m4a")

    private fun safeReleaseRecorder() {
        try {
            mediaRecorder?.release()
        } catch (_: Exception) {}
        mediaRecorder = null
    }

    companion object {
        private const val TAG = "PushToTalkManager"
        private const val MIN_VALID_FILE_BYTES = 1_000L
    }
}
