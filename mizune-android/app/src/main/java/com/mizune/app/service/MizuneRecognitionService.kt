package com.mizune.app.service

import android.content.Intent
import android.speech.RecognitionService
import android.speech.SpeechRecognizer

/**
 * Required by the assistant contract, not by Mizune.
 *
 * `voice_interaction_service.xml` must name a `recognitionService` owned by this same
 * app, or the whole assistant registration is rejected and Mizune never appears in the
 * assistant picker. Mizune does not route speech through this API — she captures audio
 * herself (Porcupine wake word, Vosk command capture, server-side STT) — so this
 * declines cleanly rather than pretending to recognise anything.
 *
 * Returning ERROR_CLIENT is the honest answer: a caller that asked *this* component to
 * recognise speech is using a path Mizune does not implement, and silently returning
 * empty results would look like "heard nothing" instead of "not supported here".
 */
class MizuneRecognitionService : RecognitionService() {

    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        listener?.error(SpeechRecognizer.ERROR_CLIENT)
    }

    override fun onCancel(listener: Callback?) {}

    override fun onStopListening(listener: Callback?) {}
}
