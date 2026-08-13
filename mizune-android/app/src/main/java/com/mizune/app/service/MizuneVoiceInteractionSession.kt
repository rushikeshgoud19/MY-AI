package com.mizune.app.service

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.util.Log

/**
 * What actually happens when Master long-presses power: Mizune starts listening.
 *
 * Deliberately **headless** — no assistant sheet, no UI of its own. Google Assistant
 * slides a panel up; Mizune just buzzes and listens, then answers through the service's
 * own TTS, so it works with the screen locked and the app closed. Showing a window here
 * would fight the existing foreground-service voice path for the mic and the speaker.
 */
class MizuneVoiceInteractionSession(context: Context) : VoiceInteractionSession(context) {

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        val intent = Intent(context, MizuneService::class.java).apply {
            action = MizuneService.ACTION_ASSIST_LISTEN
        }
        try {
            // The service is already foreground in the normal case; this is a
            // deliver-command start, not a cold start. Guarded because a locked phone
            // with the service killed can still refuse a background start.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Assist start failed", e)
        }
        // Close the (invisible) session immediately — the capture lives in the service,
        // so holding the session open would just pin a dead window over the launcher.
        hide()
    }

    companion object {
        private const val TAG = "MizuneAssistSession"
    }
}
