package com.mizune.app.audio

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

interface WakeWordListener {
    fun onWakeWordDetected()
    fun onCommandRecognized(command: String)
    fun onError(error: String)
    fun onReadyForSpeech()
}

class WakeWordDetector(private val context: Context, private val listener: WakeWordListener) {
    private var speechRecognizer: SpeechRecognizer? = null
    private var isListening = false
    private var paused = false
    // "Baka Mizune" is the wake phrase. SpeechRecognizer transcripts vary, so accept
    // a few phonetic forms; the 2-word form is preferred to cut false triggers.
    private val WAKE_PHRASES = listOf("baka mizune", "baka mizu", "baka mizuné", "mizune", "mizu ne")

    fun startListening() {
        if (isListening) return
        
        try {
            if (SpeechRecognizer.isRecognitionAvailable(context)) {
                speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
                speechRecognizer?.setRecognitionListener(createRecognitionListener())

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                }
                
                speechRecognizer?.startListening(intent)
                isListening = true
            } else {
                listener.onError("Speech recognition not available on this device")
            }
        } catch (e: Exception) {
            Log.e("WakeWord", "Failed to start listening", e)
            listener.onError(e.message ?: "Unknown error")
        }
    }

    fun stopListening() {
        speechRecognizer?.let {
            try { it.stopListening(); it.destroy() } catch (_: Exception) {}
        }
        speechRecognizer = null
        isListening = false
    }

    /** Pause wake detection (e.g. while push-to-talk uses the mic) without tearing down. */
    fun pause() { paused = true; stopListening() }
    fun resume() { if (paused) { paused = false; startListening() } }

    private fun matchedPhrase(text: String): String? =
        WAKE_PHRASES.firstOrNull { text.contains(it) }

    private fun createRecognitionListener() = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            listener.onReadyForSpeech()
        }

        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            isListening = false
            if (!paused) startListening()
        }

        override fun onError(error: Int) {
            // No-speech (7) / timeout are normal; keep the loop alive unless paused.
            isListening = false
            if (!paused) {
                // Tiny backoff avoids a hot restart loop when the recognizer is busy.
                android.os.Handler(android.os.Looper.getMainLooper())
                    .postDelayed({ if (!paused) startListening() }, 400)
            }
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if (!matches.isNullOrEmpty()) {
                val text = matches[0].lowercase()
                Log.d("WakeWord", "Recognized: $text")
                val phrase = matchedPhrase(text)
                if (phrase != null) {
                    listener.onWakeWordDetected()
                    // Everything after the wake phrase is the command
                    // ("baka mizune play shakira" → "play shakira").
                    val command = text.substringAfter(phrase).trim().trimStart(',', '.').trim()
                    if (command.isNotEmpty()) listener.onCommandRecognized(command)
                }
                // NOTE: non-wake speech is IGNORED — she only acts when addressed.
            }
            isListening = false
            if (!paused) startListening()
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if (!matches.isNullOrEmpty() && matchedPhrase(matches[0].lowercase()) != null) {
                listener.onWakeWordDetected()
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
