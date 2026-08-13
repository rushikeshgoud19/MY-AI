package com.mizune.app.service

import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.util.Log

/**
 * Quick Settings tile — talk to Mizune in one pull-down, without unlocking to find the
 * app. Same one-shot capture as the assist gesture, so there is one voice entry point
 * behind three triggers (wake word, power long-press, this tile).
 */
class MizuneTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            state = Tile.STATE_INACTIVE
            label = "Mizune"
            contentDescription = "Talk to Mizune"
            updateTile()
        }
    }

    override fun onClick() {
        super.onClick()
        val intent = Intent(this, MizuneService::class.java).apply {
            action = MizuneService.ACTION_ASSIST_LISTEN
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            qsTile?.apply {
                state = Tile.STATE_ACTIVE
                updateTile()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Tile start failed", e)
        }
    }

    companion object {
        private const val TAG = "MizuneTile"
    }
}
