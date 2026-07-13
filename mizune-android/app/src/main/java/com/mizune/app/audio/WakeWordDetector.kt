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

    /**
     * One-shot command capture (used AFTER Porcupine detects the wake word and releases
     * the mic). Starts Vosk, returns the first non-blank final transcript (or null on
     * timeout), then stops — freeing the mic for Porcupine again.
     */
    fun captureCommandOnce(timeoutMs: Long = 7000L, onDone: (String?) -> Unit) {
        val ensureModel: () -> Unit = {
            if (model == null) {
                val dir = copyAssetModel(); model = Model(dir.absolutePath)
            }
        }
        Thread {
            try {
                ensureModel()
                val rec = Recognizer(model, 16000.0f)
                val svc = SpeechService(rec, 16000.0f)
                val done = java.util.concurrent.atomic.AtomicBoolean(false)
                val finish: (String?) -> Unit = { result ->
                    if (done.compareAndSet(false, true)) {
                        try { svc.stop(); svc.shutdown() } catch (_: Exception) {}
                        android.os.Handler(android.os.Looper.getMainLooper()).post { onDone(result) }
                    }
                }
                svc.startListening(object : RecognitionListener {
                    override fun onPartialResult(h: String?) {}
                    override fun onResult(h: String?) {
                        val t = try { JSONObject(h ?: "{}").optString("text").trim() } catch (_: Exception) { "" }
                        if (t.isNotBlank()) finish(t)
                    }
                    override fun onFinalResult(h: String?) {
                        val t = try { JSONObject(h ?: "{}").optString("text").trim() } catch (_: Exception) { "" }
                        finish(if (t.isNotBlank()) t else null)
                    }
                    override fun onError(e: Exception?) { finish(null) }
                    override fun onTimeout() { finish(null) }
                })
                android.os.Handler(android.os.Looper.getMainLooper())
                    .postDelayed({ finish(null) }, timeoutMs)
            } catch (e: Throwable) {
                android.os.Handler(android.os.Looper.getMainLooper()).post { onDone(null) }
            }
        }.start()
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

    // Two-phase state: after the wake phrase, we stay AWAKE for a few seconds and take
    // the next spoken sentence as the command — so "Baka Mizune" <pause> "play Shakira"
    // works, not just a single perfect breath.
    private var awakeUntil = 0L
    private val COMMAND_WINDOW_MS = 7000L

    /** Returns command-after-phrase (may be ""), or null if the wake phrase isn't present. */
    private fun detectWake(text: String): String? {
        val tokens = text.split(Regex("\\s+")).filter { it.isNotBlank() }
        val limit = minOf(tokens.size - 1, 4)
        for (i in 0..limit) {
            if (tokens[i] in BAKA && i + 1 < tokens.size && tokens[i + 1] in MIZU) {
                return tokens.drop(i + 2).joinToString(" ").trim()
            }
        }
        return null
    }

    private fun handle(text: String, isFinal: Boolean) {
        if (paused || text.isBlank()) return
        val lower = text.lowercase().trim()
        listener.onHeard(lower)
        val now = System.currentTimeMillis()

        // PHASE 2: we're awake and waiting for the command sentence.
        if (now < awakeUntil) {
            if (!isFinal) return                       // wait for a complete sentence
            val afterWake = detectWake(lower)          // in case they repeated the phrase
            val command = (afterWake ?: lower).trim()
            if (command.isNotBlank()) {
                awakeUntil = 0
                listener.onCommandRecognized(command)
            }
            return
        }

        // PHASE 1: listen for the wake phrase.
        val cmd = detectWake(lower) ?: return
        if (now - lastFired < 2000) return
        lastFired = now
        listener.onWakeWordDetected()
        if (cmd.isNotEmpty()) {
            listener.onCommandRecognized(cmd)          // same-breath command
        } else {
            awakeUntil = now + COMMAND_WINDOW_MS        // wait for the next sentence
        }
    }

    private val recognitionListener = object : RecognitionListener {
        override fun onPartialResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("partial"), false) } catch (_: Exception) {}
        }
        override fun onResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("text"), true) } catch (_: Exception) {}
        }
        override fun onFinalResult(hypothesis: String?) {
            hypothesis ?: return
            try { handle(JSONObject(hypothesis).optString("text"), true) } catch (_: Exception) {}
        }
        override fun onError(exception: Exception?) {
            Log.e("WakeWord", "Vosk error", exception)
        }
        override fun onTimeout() {}
    }
}
