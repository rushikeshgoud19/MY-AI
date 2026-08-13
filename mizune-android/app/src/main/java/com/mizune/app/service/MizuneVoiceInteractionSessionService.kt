package com.mizune.app.service

import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

/** Factory for the session Android creates each time the assist gesture fires. */
class MizuneVoiceInteractionSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession =
        MizuneVoiceInteractionSession(this)
}
