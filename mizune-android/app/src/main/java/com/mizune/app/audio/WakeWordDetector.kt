package com.mizune.app.audio

import android.content.Context
import android.util.Log
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.File

interface WakeWordListener {
    fun onWakeWordDetected()
    fun onCommandRecognized(command: String)
    fun onError(error: String)
    fun onReadyForSpeech()
    /** Any transcript the mic picks up — used for a live on-screen debug readout. */
    fun onHeard(text: String) {}
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

    // Vosk's English model doesn't know "baka mizune", so it transcribes it as
    // similar-sounding English words (e.g. "but came"). We fuzzy-match: a "baka"-ish
    // word immediately followed by a "mizune"-ish word = the wake phrase. Requiring
    // BOTH keeps common speech from false-triggering.
    private val BAKA = setOf("baka", "back", "buck", "but", "bak", "bacca", "bakka",
        "booka", "barker", "bianca", "vodka", "pucker")
    private val MIZU = setOf("mizune", "mizu", "mizuni", "mizuné", "museum", "came",
        "cami", "camy", "kami", "missouri", "amazon", "muzu", "mausam", "mizzou", "misty")

    fun startListening() {
        if (model != null) { startService(); return }
        // Load on a background thread; surface the REAL error if anything goes wrong.
        Thread {
            try {
                val dir = copyAssetModel()
                model = Model(dir.absolutePath)
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    startService()
                    listener.onReadyForSpeech()
                }
                Log.d("WakeWord", "Vosk model loaded from ${dir.absolutePath}")
            } catch (e: Throwable) {
                Log.e("WakeWord", "Vosk model load failed", e)
                val msg = "${e.javaClass.simpleName}: ${e.message}"
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    listener.onError(msg)
                }
            }
        }.start()
    }

    /** Copy the bundled model from assets/vosk-model-en → filesDir (once). Returns the dir. */
    private fun copyAssetModel(): File {
        val dest = File(context.filesDir, "vosk-model-en")
        val marker = File(dest, "conf/model.conf")
        if (marker.exists()) return dest   // already copied
        copyAssetDir("vosk-model-en", dest)
        if (!marker.exists()) throw IllegalStateException("model incomplete after copy (missing conf/model.conf)")
        return dest
    }

    private fun copyAssetDir(assetPath: String, dest: File) {
        val children = context.assets.list(assetPath) ?: emptyArray()
        if (children.isEmpty()) {
            // It's a file — copy it.
            dest.parentFile?.mkdirs()
            context.assets.open(assetPath).use { input ->
                dest.outputStream().use { input.copyTo(it) }
            }
        } else {
            dest.mkdirs()
            for (child in children) copyAssetDir("$assetPath/$child", File(dest, child))
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

    /** Returns the command text after the wake phrase, or null if no wake detected. */
    private fun detectWake(text: String): String? {
        val tokens = text.split(Regex("\\s+")).filter { it.isNotBlank() }
        // Look for a BAKA word followed by a MIZU word within the first few tokens.
        val limit = minOf(tokens.size - 1, 4)
        for (i in 0..limit) {
            if (tokens[i] in BAKA && i + 1 < tokens.size && tokens[i + 1] in MIZU) {
                return tokens.drop(i + 2).joinToString(" ").trim()   // command after the phrase
            }
        }
        return null
    }

    private fun handle(text: String) {
        if (paused || text.isBlank()) return
        val lower = text.lowercase().trim()
        listener.onHeard(lower)   // live debug: shows the mic IS working + what it hears
        val command = detectWake(lower) ?: return
        // Debounce: partials + final can both fire; one trigger per ~2.5s.
        val now = System.currentTimeMillis()
        if (now - lastFired < 2500) return
        lastFired = now
        listener.onWakeWordDetected()
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
