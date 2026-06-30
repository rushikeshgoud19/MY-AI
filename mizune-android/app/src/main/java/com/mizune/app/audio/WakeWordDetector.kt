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
    private val WAKE_WORD = "mizune"

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
        if (!isListening) return
        speechRecognizer?.stopListening()
        speechRecognizer?.destroy()
        speechRecognizer = null
        isListening = false
    }

    private fun createRecognitionListener() = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            listener.onReadyForSpeech()
        }

        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            // Restart listening if we didn't catch anything, to keep it continuous
            isListening = false
            startListening()
        }

        override fun onError(error: Int) {
            // Common errors like no speech input (7) or network timeouts
            isListening = false
            startListening() // Keep loop alive
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if (!matches.isNullOrEmpty()) {
                val text = matches[0].lowercase()
                Log.d("WakeWord", "Recognized: $text")
                
                if (text.contains(WAKE_WORD)) {
                    listener.onWakeWordDetected()
                    // If they said more than just the wake word (e.g., "Mizune what is the time"), process the rest
                    val command = text.substringAfter(WAKE_WORD).trim()
                    if (command.isNotEmpty()) {
                        listener.onCommandRecognized(command)
                    }
                } else {
                    // Just conversational text if already awake, but for now we only act on wake word
                    listener.onCommandRecognized(text)
                }
            }
            
            isListening = false
            startListening()
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if (!matches.isNullOrEmpty()) {
                val text = matches[0].lowercase()
                if (text.contains(WAKE_WORD)) {
                    listener.onWakeWordDetected()
                }
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
