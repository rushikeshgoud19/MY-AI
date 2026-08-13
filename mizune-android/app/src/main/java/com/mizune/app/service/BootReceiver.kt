package com.mizune.app.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * Brings Mizune back after a reboot.
 *
 * START_STICKY only survives the *process* being killed, not the device restarting —
 * so before this, every reboot left the phone silently absent from the device registry
 * until Master happened to open the app. That is the single biggest hole in "holds the
 * socket for 24h unbroken".
 *
 * Starts dataSync-only via [MizuneService.EXTRA_FROM_BOOT]: Android 14 blocks starting a
 * microphone foreground service from BOOT_COMPLETED, so claiming the mic here would
 * throw instead of reconnecting.
 */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED &&
            action != Intent.ACTION_MY_PACKAGE_REPLACED &&
            action != "android.intent.action.QUICKBOOT_POWERON"   // HTC/Xiaomi fast boot
        ) return

        val svc = Intent(context, MizuneService::class.java)
            .putExtra(MizuneService.EXTRA_FROM_BOOT, true)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(svc)
            } else {
                context.startService(svc)
            }
            Log.d(TAG, "Restarted Mizune after $action")
        } catch (e: Exception) {
            // Never let a failed restart crash the boot broadcast — an OEM ROM that
            // refuses the start should cost us the socket, not a boot-loop dialog.
            Log.e(TAG, "Boot restart failed", e)
        }
    }

    companion object {
        private const val TAG = "MizuneBoot"
    }
}
