package com.mizune.app.service

import android.service.voice.VoiceInteractionService
import android.util.Log

/**
 * Makes Mizune selectable as the phone's **Digital assistant app**, replacing Google
 * Assistant on the long-press-power / long-press-home gesture.
 *
 * Android requires a matched set for this to appear in Settings at all — a
 * VoiceInteractionService (this), a [MizuneVoiceInteractionSessionService], and a
 * [MizuneRecognitionService] — wired together by res/xml/voice_interaction_service.xml.
 * Omit any one of them and the app is silently absent from the assistant picker with no
 * error to debug, which is why the stub recognition service exists.
 *
 * Selecting Mizune here is what makes her the assistant; the app cannot set it itself.
 */
class MizuneVoiceInteractionService : VoiceInteractionService() {

    override fun onReady() {
        super.onReady()
        Log.d(TAG, "Mizune is now the device assistant")
    }

    companion object {
        private const val TAG = "MizuneVoiceIS"
    }
}
