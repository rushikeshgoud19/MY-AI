package com.mizune.app.audio

import android.content.Context
import android.util.Log
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import org.vosk.android.StorageService

interface WakeWordListener {
    fun onWakeWordDetected()
    fun onCommandRecognized(command: String)
    fun onError(error: String)
    fun onReadyForSpeech()
}

/**
 * Offline "Baka Mizune" wake word via Vosk. Reads the raw microphone through
 * AudioRecord — so it does NOT play the system recognition beep, doesn't need the
 * network, and is far lighter than a continuous SpeechRecognizer restart loop.
 *
 * The model is bundled in assets/vosk-model-en and unpacked to filesDir on first use.
 */
class WakeWordDetector(private val context: Context, private val listener: WakeWordListener) {

    private var model: Model? = null
    private var speechService: SpeechService? = null
    private var paused = false
    private var lastFired = 0L

    // SpeechRecognizer transcribes the phrase a few ways — accept phonetic variants.
    private val WAKE_PHRASES = listOf("baka mizune", "baka mizu", "baka mizuni",
        "baka mizuné", "bakamizune", "mizune", "mizu ne")

    fun startListening() {
        if (model == null) {
            // Unpack the bundled model, then start. Until it's ready, we're silent
            // (no beep, no false triggers).
            StorageService.unpack(context, "vosk-model-en", "vosk-model",
                { m ->
                    model = m
                    startService()
                    Log.d("WakeWord", "Vosk model ready — Baka Mizune listening")
                },
                { e ->
                    Log.e("WakeWord", "Vosk model unpack failed", e)
                    listener.onError("Wake model failed to load: ${e.message}")
                })
        } else {
            startService()
        }
    }

    private fun startService() {
        if (speechService != null) return
        val m = model ?: return
        try {
            val rec = Recognizer(m, 16000.0f)
            speechService = SpeechService(rec, 16000.0f)
            speechService?.startListening(recognitionListener)
            paused = false
        } catch (e: Exception) {
            Log.e("WakeWord", "Vosk start failed", e)
            listener.onError(e.message ?: "wake start failed")
        }
    }

    fun stopListening() {
        speechService?.let { try { it.stop(); it.shutdown() } catch (_: Exception) {} }
        speechService = null
    }

    fun pause() {
        paused = true
        speechService?.setPause(true)
    }

    fun resume() {
        if (!paused) return
        paused = false
        if (speechService != null) speechService?.setPause(false) else startListening()
    }

    private fun matchedPhrase(text: String): String? =
        WAKE_PHRASES.firstOrNull { text.contains(it) }

    private fun handle(text: String) {
        if (paused || text.isBlank()) return
        val lower = text.lowercase().trim()
        val phrase = matchedPhrase(lower) ?: return
        // Debounce: partials + final can both fire; one trigger per ~2.5s.
        val now = System.currentTimeMillis()
        if (now - lastFired < 2500) return
        lastFired = now
        listener.onWakeWordDetected()
        val command = lower.substringAfter(phrase).trim().trimStart(',', '.').trim()
        if (command.isNotEmpty()) listener.onCommandRecognized(command)
    }

    private val recognitionListener = object : RecognitionListener {
        override fun onPartialResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("partial")) } catch (_: Exception) {}
        }
        override fun onResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("text")) } catch (_: Exception) {}
        }
        override fun onFinalResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("text")) } catch (_: Exception) {}
        }
        override fun onError(exception: Exception?) {
            Log.e("WakeWord", "Vosk error", exception)
        }
        override fun onTimeout() {}
    }
}
