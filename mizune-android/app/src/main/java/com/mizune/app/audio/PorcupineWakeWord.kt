package com.mizune.app.audio

import android.content.Context
import android.util.Log
import ai.picovoice.porcupine.PorcupineManager
import ai.picovoice.porcupine.PorcupineManagerCallback
import com.mizune.app.BuildConfig
import java.io.File

/**
 * "Baka Mizune" wake word via Picovoice Porcupine — a purpose-built, on-device,
 * low-power wake engine (no beep, high accuracy, works for any custom phrase). This is
 * what makes Mizune's wake word Alexa/Google-grade instead of a mis-hearing STT hack.
 *
 * Requires two user-supplied inputs (see handoff W.2 Option A):
 *   • Picovoice AccessKey  → local.properties `picovoice.key=...` → BuildConfig.PICOVOICE_KEY
 *   • Custom keyword file  → app/src/main/assets/baka_mizune.ppn
 * If either is missing, isAvailable() is false and the caller falls back to Vosk.
 */
class PorcupineWakeWord(
    private val context: Context,
    private val onWake: () -> Unit
) {
    private var manager: PorcupineManager? = null
    private val accessKey: String = BuildConfig.PICOVOICE_KEY
    private val keywordAsset = "baka_mizune.ppn"

    fun isConfigured(): Boolean =
        accessKey.isNotBlank() && assetExists(keywordAsset)

    fun start(): Boolean {
        if (!isConfigured()) return false
        if (manager != null) return true
        return try {
            val ppnPath = copyAssetToFiles(keywordAsset)
            manager = PorcupineManager.Builder()
                .setAccessKey(accessKey)
                .setKeywordPath(ppnPath)
                .setSensitivity(0.7f)   // 0..1 — higher = more sensitive (fewer misses)
                .build(context, PorcupineManagerCallback { onWake() })
            manager?.start()
            Log.d(TAG, "Porcupine 'Baka Mizune' listening")
            true
        } catch (e: Throwable) {
            Log.e(TAG, "Porcupine start failed", e)
            manager = null
            false
        }
    }

    fun stop() {
        try { manager?.stop() } catch (_: Exception) {}
    }

    fun resume() {
        try { manager?.start() } catch (e: Exception) { Log.w(TAG, "Porcupine resume failed", e) }
    }

    fun release() {
        try { manager?.stop(); manager?.delete() } catch (_: Exception) {}
        manager = null
    }

    private fun assetExists(name: String): Boolean =
        try { (context.assets.list("")?.contains(name)) == true } catch (_: Exception) { false }

    private fun copyAssetToFiles(name: String): String {
        val out = File(context.filesDir, name)
        context.assets.open(name).use { input -> out.outputStream().use { input.copyTo(it) } }
        return out.absolutePath
    }

    companion object { private const val TAG = "PorcupineWake" }
}
