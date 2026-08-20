package com.mizune.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.net.Uri
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.mizune.app.MainActivity
import com.mizune.app.R
import com.mizune.app.data.AppPreferences
import com.mizune.app.network.MizuneWebSocket
import com.mizune.app.network.MizuneWebSocketListener
import com.mizune.app.network.TaskItem
import com.mizune.app.ui.ConnectionState
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MizuneService : Service() {

    private val binder = LocalBinder()
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var appPreferences: AppPreferences
    private lateinit var webSocket: MizuneWebSocket

    private val uiListeners = mutableListOf<MizuneWebSocketListener>()
    private val listenersLock = Object()
    private var isAppInForeground = false
    private var lastConnectionState = ConnectionState.DISCONNECTED
    private var wakeWord: com.mizune.app.audio.WakeWordDetector? = null
    private var porcupine: com.mizune.app.audio.PorcupineWakeWord? = null
    private var serviceTts: com.mizune.app.audio.TtsPlayer? = null

    // Voice Match: HTTP base derived from the WS server URL, for /api/voice/*.
    @Volatile private var httpBase = ""
    // Last key handed to the socket, so a bare reconnect doesn't lose authentication.
    @Volatile private var currentApiKey = ""

    // ── Turn ownership ─────────────────────────────────────────────────────────
    // The server broadcasts EVERY frame to EVERY client and 20+ places speak with no
    // human involved — the proactive agent alone fires every 15 minutes. Without this
    // the phone spoke aloud, vibrated and notified for cron jobs, nightly self-review,
    // and her replies to other people's WhatsApp messages.
    //
    // It lives in the service, not the Activity, because the service owns the socket and
    // is the only place that sees ALL outbound traffic — typed messages, wake-word
    // commands, assist captures and camera turns. Tracking it in the Activity missed the
    // wake-word path entirely and would have muted replies Master actually asked for.
    //
    // A guard, not the fix: the frames still arrive. See
    // .scratch/hands-free-voice/tickets/12-who-is-a-turn-for.md
    @Volatile private var lastOutboundAt = 0L

    /** Called on every outbound turn, so its reply is recognised as ours. */
    fun markOutbound() { lastOutboundAt = System.currentTimeMillis() }

    /** True while a reply could still plausibly belong to something this phone sent. */
    fun awaitingReply(): Boolean =
        System.currentTimeMillis() - lastOutboundAt < AWAIT_REPLY_WINDOW_MS

    /**
     * The server's verdict on the frame being handled, when it has one.
     *
     * Snapshotted per inbound frame because the timing guess above cannot be right: a
     * subconscious tick landing inside the 90-second window is indistinguishable from a
     * real reply, and a slow reply arriving after it is thrown away. The server now
     * stamps each frame with the client whose turn produced it, which is an answer
     * rather than an estimate.
     *
     * Null on a backend that predates the stamp — the phone must keep working against
     * one, so [turnIsOurs] falls back rather than assuming.
     */
    @Volatile private var currentTurnOurs: Boolean? = null

    /**
     * Does the turn being handled belong to this phone? Server stamp first, timer second.
     *
     * Honest limit: the stamp is captured when the frame arrives, while the Activity
     * reads it one UI-thread hop later. Two frames of DIFFERENT origin inside a single
     * hop could therefore be judged by the wrong one. Bounded and rare — and strictly
     * better than a 90-second window that is wrong by construction.
     */
    fun turnIsOurs(): Boolean = currentTurnOurs ?: awaitingReply()

    /** The socket's verdict, or null if there is no socket yet / no stamp on the frame. */
    private fun frameOwnership(): Boolean? =
        if (::webSocket.isInitialized) webSocket.frameIsOurs() else null

    /**
     * Fan a frame out to the UI listeners. One bad subscriber never breaks the socket.
     *
     * Two defects in the old `synchronized(listenersLock) { uiListeners.forEach { … } }`,
     * repeated at seven call sites:
     *
     *  1. **No containment.** A listener that threw propagated out of the dispatch loop,
     *     past the remaining listeners, and into OkHttp's WebSocket callback thread —
     *     which is the thread that keeps the connection alive. One Compose state bug in
     *     the Activity could therefore take down the socket for the whole service, and
     *     the symptom ("she just stopped responding") looks nothing like the cause.
     *  2. **Arbitrary callbacks ran while holding the lock.** `onAudio` reaches into
     *     `pauseWakeWord()`, which touches the audio engine; holding a service-wide lock
     *     across that is a lock-ordering hazard, and a listener that removed itself
     *     mid-dispatch would deadlock or throw ConcurrentModificationException.
     *
     * Snapshot under the lock, dispatch outside it, contain each callback.
     */
    private fun dispatch(what: String, action: (MizuneWebSocketListener) -> Unit) {
        val snapshot = synchronized(listenersLock) { uiListeners.toList() }
        for (listener in snapshot) {
            try {
                action(listener)
            } catch (e: Throwable) {
                Log.e(TAG, "listener threw on $what — continuing", e)
            }
        }
    }
    private val voiceHttp by lazy {
        okhttp3.OkHttpClient.Builder()
            .connectTimeout(3, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(5, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }

    companion object {
        private const val TAG = "MizuneService"

        /** Identifies the running binary in logcat. Bump on every voice-loop change. */
        private const val BUILD_STAMP = "2026-08-17-harness-pass-1"
        private const val CHANNEL_ID = "mizune_persistent"
        private const val ALERT_CHANNEL_ID = "mizune_alerts"
        /** Silent channel for things she says that Master did NOT ask for. */
        private const val AMBIENT_CHANNEL_ID = "mizune_ambient"
        private const val NOTIFICATION_ID = 1

        /** How long a reply can still belong to a turn this phone started. Generous —
         *  a slow model turn runs tens of seconds — but bounded, so a turn that dies
         *  server-side can't leave the phone permanently "expecting" a reply. */
        private const val AWAIT_REPLY_WINDOW_MS = 90_000L

        /** Longest we'll stay deaf for one spoken reply before force-resuming the mic. */
        private const val MAX_SPEAK_MS = 60_000L

        /** Assist gesture (long-press power/home) or the Quick Settings tile fired:
         *  start listening for one command, exactly as the wake word does. */
        const val ACTION_ASSIST_LISTEN = "com.mizune.app.action.ASSIST_LISTEN"

        /** Set by [BootReceiver]. Android 14 forbids starting a *microphone* foreground
         *  service from BOOT_COMPLETED, so a boot start runs dataSync-only and leaves the
         *  wake word for later. Without this the service crashes on every reboot. */
        const val EXTRA_FROM_BOOT = "from_boot"
    }

    inner class LocalBinder : Binder() {
        fun getService(): MizuneService = this@MizuneService
    }

    override fun onCreate() {
        super.onCreate()
        // Which binary is actually running? Three voice fixes were judged by "it's still
        // happening" with no proof the phone had the fix on it. Bump BUILD_STAMP with
        // every voice change: `adb logcat -s MizuneService:D | grep BUILD_STAMP`.
        Log.d(TAG, "BUILD_STAMP: $BUILD_STAMP")
        appPreferences = AppPreferences(this)
        createNotificationChannels()
        // URL and key are one connection identity: changing either must rebuild the
        // socket, so they're collected together rather than racing in two collectors.
        serviceScope.launch {
            kotlinx.coroutines.flow.combine(
                appPreferences.serverUrl,
                appPreferences.apiKey
            ) { url, key -> url to key }
                .distinctUntilChanged()
                .collect { (newUrl, newKey) ->
                    if (::webSocket.isInitialized) {
                        webSocket.disconnect()
                    }
                    initializeWebSocket(newUrl, newKey)
                }
        }
        // The registry must lose a capability the moment its permission is revoked.
        // Without this, turning Accessibility off left `tap`/`read_screen` advertised
        // and the brain kept confidently dispatching actions that could not run.
        MizuneAccessibilityService.onStateChanged = {
            if (::webSocket.isInitialized) webSocket.sendRegistration()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val fromBoot = intent?.getBooleanExtra(EXTRA_FROM_BOOT, false) == true

        // A plain startForeground() claims EVERY type declared in the manifest —
        // including microphone, which Android 14 refuses to grant from BOOT_COMPLETED
        // and punishes with ForegroundServiceStartNotAllowedException. On a boot start
        // we therefore claim dataSync only: the socket comes up (that's what boot
        // survival is for) and the mic is picked up on the next foreground start.
        if (fromBoot && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            androidx.core.app.ServiceCompat.startForeground(
                this, NOTIFICATION_ID, createPersistentNotification(),
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(NOTIFICATION_ID, createPersistentNotification())
        }

        when {
            // An assist/tile start is a COMMAND to an already-running service, not a
            // cold start. It must not re-enter startWakeWord(): that allocates a fresh
            // Porcupine every time and leaks the previous one, and two engines then
            // fight over the microphone. This path is now hit on every gesture.
            intent?.action == ACTION_ASSIST_LISTEN -> {
                if (wakeWord == null) startWakeWord()   // cold start via the gesture
                startAssistCapture()
            }
            fromBoot -> {
                setWakeStatus("🔌 Reconnected after restart — open Mizune once for voice")
                Log.d(TAG, "Boot start: socket only, wake word deferred (mic FGS blocked at boot)")
            }
            else -> startWakeWord()
        }
        return START_STICKY
    }

    /**
     * One-shot listen, triggered by the assist gesture or the Quick Settings tile.
     * Deliberately reuses the wake-word capture path rather than adding a second audio
     * pipeline — that path already handles mic hand-off, the 7s window and the silence
     * cutoff, and it is the one that has been debugged on a real phone.
     */
    fun startAssistCapture() {
        val wake = wakeWord
        if (wake == null) {
            setWakeStatus("⚠ voice engine still starting — try again in a second")
            return
        }
        vibrateOnce()
        setWakeStatus("✨ Listening…")
        porcupine?.stop()                      // release the mic for the capture
        wake.captureCommandOnce(7000) { cmd ->
            if (!cmd.isNullOrBlank() && ::webSocket.isInitialized) {
                sendMessage(cmd)          // routed so the turn is marked as ours
                setWakeStatus("▶ running: $cmd")
            } else {
                setWakeStatus("🎙 \"Baka Mizune\" ready")
            }
            porcupine?.resume()
        }
    }

    override fun onBind(intent: Intent?): IBinder = binder

    /**
     * Start the wake word. Prefers Porcupine ("Baka Mizune", accurate, low-power) when
     * configured (AccessKey + baka_mizune.ppn present); otherwise falls back to Vosk
     * continuous fuzzy matching so it always does SOMETHING.
     */
    private fun startWakeWord() {
        if (wakeWord == null) {
            wakeWord = com.mizune.app.audio.WakeWordDetector(this, object : com.mizune.app.audio.WakeWordListener {
                override fun onWakeWordDetected() {
                    vibrateOnce()
                    setWakeStatus("✨ Baka Mizune — heard you!")
                }
                override fun onCommandRecognized(command: String) {
                    if (command.isNotBlank() && ::webSocket.isInitialized) {
                        sendMessage(command)   // routed so the turn is marked as ours
                        setWakeStatus("▶ running: $command")
                    }
                }
                override fun onHeard(text: String) {
                    if (text.isNotBlank()) setWakeStatus("🎙 heard: ${text.take(40)}")
                }
                override fun onError(error: String) {
                    Log.w(TAG, "WakeWord: $error"); setWakeStatus("⚠ wake: $error")
                }
                override fun onReadyForSpeech() { setWakeStatus("🎙 Listening for \"Baka Mizune\"…") }
            })
            // Voice Match: check the wake utterance against Master's enrolled voiceprint.
            // Fail-OPEN (server unreachable / not enrolled → proceed) so wake never bricks.
            wakeWord?.wakeVerifier = { wav, proceed ->
                val base = httpBase
                if (base.isBlank()) proceed(true) else {
                    val req = okhttp3.Request.Builder()
                        .url("$base/api/voice/verify")
                        .post(okhttp3.RequestBody.create("audio/wav".toMediaTypeOrNull(), wav))
                        .build()
                    voiceHttp.newCall(req).enqueue(object : okhttp3.Callback {
                        override fun onFailure(call: okhttp3.Call, e: java.io.IOException) = proceed(true)
                        override fun onResponse(call: okhttp3.Call, response: okhttp3.Response) {
                            val ok = try {
                                val body = response.body?.string() ?: "{}"
                                !org.json.JSONObject(body).optBoolean("enrolled", false) ||
                                    org.json.JSONObject(body).optBoolean("match", true)
                            } catch (_: Exception) { true }
                            response.close()
                            if (!ok) setWakeStatus("🚫 voice didn't match Master — ignored")
                            proceed(ok)
                        }
                    })
                }
            }
        }

        // Release any previous engine first. onStartCommand can run several times over a
        // service's life (server-URL change, re-bind, restart), and each unreleased
        // Porcupine holds a mic handle — they accumulate and eventually starve the wake
        // word that is supposed to be always-on.
        porcupine?.release()
        porcupine = com.mizune.app.audio.PorcupineWakeWord(this) { onPorcupineWake() }
        if (porcupine?.start() == true) {
            setWakeStatus("🎙 \"Baka Mizune\" ready (Porcupine)")
            Log.d(TAG, "Wake via Porcupine")
        } else {
            porcupine = null
            wakeWord?.startListening()          // Vosk fallback (until Rushi adds key + .ppn)
            setWakeStatus("⏳ Loading wake word (Vosk)…")
            Log.d(TAG, "Wake via Vosk fallback")
        }
    }

    /** Porcupine detected the wake word → hand the mic to Vosk to capture the command. */
    private fun onPorcupineWake() {
        vibrateOnce()
        setWakeStatus("✨ Baka Mizune — listening…")
        porcupine?.stop()                        // release mic
        wakeWord?.captureCommandOnce(7000) { cmd ->
            if (!cmd.isNullOrBlank() && ::webSocket.isInitialized) {
                sendMessage(cmd)          // routed so the turn is marked as ours
                setWakeStatus("▶ running: $cmd")
            } else {
                setWakeStatus("🎙 \"Baka Mizune\" ready")
            }
            porcupine?.resume()                  // reclaim mic for the next wake
        }
    }

    /** Pause/resume wake detection so it doesn't fight push-to-talk for the mic. */
    fun pauseWakeWord() { porcupine?.stop(); wakeWord?.pause() }
    fun resumeWakeWord() { if (porcupine != null) porcupine?.resume() else wakeWord?.resume() }

    /**
     * Speak, with the microphone deaf for the duration.
     *
     * The mic was live while she talked and there is no acoustic echo cancellation, so
     * she could hear her own voice — and a wake match on her own speech starts a turn,
     * which produces another spoken reply, which she hears again. That is a self-
     * sustaining loop and a strong candidate for "she activates for no reason".
     *
     * Production assistants solve this with AEC (subtracting the known playback signal
     * before the detector). We have no AEC, so we do the blunt version: go deaf while
     * speaking. We lose barge-in — she can't be interrupted mid-sentence — which is a
     * fair trade against her talking to herself.
     */
    private fun speakWithMicPaused(base64Mp3: String) {
        pauseWakeWord()
        var resumed = false
        val resumeOnce = {
            if (!resumed) { resumed = true; resumeWakeWord() }
        }
        // Watchdog: never let a playback that silently never finishes leave the wake
        // word off forever. Deaf-until-restart would be a worse bug than the one above.
        handler.postDelayed({ resumeOnce() }, MAX_SPEAK_MS)
        serviceTts?.playBase64(base64Mp3) {
            handler.post { resumeOnce() }
        }
    }

    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    private fun vibrateOnce() {
        try {
            val v = getSystemService(android.os.Vibrator::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                v?.vibrate(android.os.VibrationEffect.createOneShot(35, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
            else @Suppress("DEPRECATION") v?.vibrate(35)
        } catch (_: Exception) {}
    }

    override fun onDestroy() {
        super.onDestroy()
        MizuneAccessibilityService.onStateChanged = null
        wakeWord?.stopListening()
        wakeWord = null
        porcupine?.release()
        porcupine = null
        serviceTts?.release()
        serviceTts = null
        if (::webSocket.isInitialized) {
            webSocket.disconnect()
        }
        serviceScope.launch { /* allow cleanup */ }
    }

    private fun httpBaseFrom(url: String): String {
        var u = url.trim().trimEnd('/')
        u = when {
            u.startsWith("ws://", true) -> "http://" + u.substring(5)
            u.startsWith("wss://", true) -> "https://" + u.substring(6)
            u.startsWith("http://", true) || u.startsWith("https://", true) -> u
            else -> "http://$u"
        }
        return u.removeSuffix("/ws")
    }

    // ── Voice Match calibration (used by Settings) ──────────────────────────────

    private var enrollment: com.mizune.app.audio.VoiceEnrollment? = null

    /** Progress for the setup wizard: how many GOOD samples are banked so far. */
    fun enrolledCount(): Int = enrollment?.acceptedCount ?: 0

    /** Throw away every template and start calibration from scratch. */
    fun resetEnrollment() {
        enrollment?.reset()
        enrollment = null
    }

    /**
     * Record and JUDGE one calibration sample.
     *
     * The old version was a counter: it saved whatever the mic produced and incremented
     * a tally, so "3/3 calibrated" could be three clips of room tone and the wake word
     * would never fire. Every template is a permanent vote in the DTW match, so a bad
     * one is worse than no sample at all. [VoiceEnrollment] refuses those, and the
     * callback reports WHY so the wizard can ask again for a specific reason.
     */
    fun calibrateVoiceSample(onResult: (String) -> Unit) {
        val wake = wakeWord
        if (wake == null) { onResult("Wake engine not ready yet — try again in a moment."); return }
        val enroll = enrollment ?: com.mizune.app.audio.VoiceEnrollment(wake).also { enrollment = it }

        pauseWakeWord()
        enroll.recordSample { result ->
            resumeWakeWord()
            when (result) {
                is com.mizune.app.audio.VoiceEnrollment.Result.Accepted ->
                    onResult("✅ Sample ${result.accepted}/${result.needed} — say it again.")
                is com.mizune.app.audio.VoiceEnrollment.Result.Rejected ->
                    onResult("↻ ${result.reason}. ${result.hint} (${result.accepted}/${result.needed} kept)")
                is com.mizune.app.audio.VoiceEnrollment.Result.Complete -> {
                    // Only now is it worth telling the server: the on-device templates are
                    // what make the wake word fire, the server voiceprint only decides it
                    // was Master. Sending rejected clips would train it on noise.
                    onResult(
                        "✅ Calibrated — ${result.accepted} good samples " +
                            "(match spread ${"%.1f".format(result.spread)}). " +
                            "Lock your phone and say \"Baka Mizune\"."
                    )
                    syncEnrollmentToServer()
                }
                is com.mizune.app.audio.VoiceEnrollment.Result.Failed ->
                    onResult("⚠ ${result.message}")
            }
        }
    }

    /**
     * Live wake-word test: say it once, get a verdict and the actual match score.
     * Pauses the always-on loop so the test doesn't fight it for the microphone.
     */
    fun testWakeWord(onResult: (Boolean, String) -> Unit) {
        val wake = wakeWord
        if (wake == null) { onResult(false, "Wake engine not ready yet — try again in a moment."); return }
        val enroll = enrollment ?: com.mizune.app.audio.VoiceEnrollment(wake).also { enrollment = it }
        pauseWakeWord()
        enroll.testWake { r ->
            resumeWakeWord()
            onResult(r.passed, r.message)
        }
    }

    /**
     * What the wake word's health actually is, as checkable facts rather than a claim.
     * Each line is (label, ok) — the failure that started all this was invisible because
     * nothing ever showed which engine was really running.
     */
    fun wakeDiagnostics(): List<Pair<String, Boolean>> {
        val wake = wakeWord
        val templates = wake?.templateCount ?: 0
        val micOk = androidx.core.content.ContextCompat.checkSelfPermission(
            this, android.Manifest.permission.RECORD_AUDIO
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        return listOf(
            "Microphone permission" to micOk,
            "Voice engine running" to (wake != null),
            "Voice samples saved ($templates/${com.mizune.app.audio.VoiceEnrollment.NEEDED})"
                to (templates >= com.mizune.app.audio.VoiceEnrollment.NEEDED),
            // "some templates exist" is not the same as "the matcher is allowed to
            // fire" — a half-finished calibration used to report armed and then wake on
            // the room. Ask the detector, don't infer.
            "Acoustic wake armed" to (wake?.wakeArmed == true),
            "Connected to Mizune" to (lastConnectionState == ConnectionState.CONNECTED),
            "Accessibility (hands)" to MizuneAccessibilityService.isEnabled()
        )
    }

    /** Upload the accepted templates to the server voiceprint (best-effort). */
    private fun syncEnrollmentToServer() {
        val wake = wakeWord ?: return
        try {
            wake.templatesDir().listFiles { f -> f.name.endsWith(".wav") }
                ?.forEach { f -> postVoice("/api/voice/enroll", f.readBytes()) { } }
        } catch (e: Exception) {
            Log.w(TAG, "server voiceprint sync failed (wake word still works locally)", e)
        }
    }

    fun voiceStatus(onResult: (String) -> Unit) {
        val req = okhttp3.Request.Builder().url("${httpBase}/api/voice/status").build()
        voiceHttp.newCall(req).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: java.io.IOException) =
                onResult("Server unreachable")
            override fun onResponse(call: okhttp3.Call, response: okhttp3.Response) {
                val body = response.body?.string() ?: "{}"; response.close()
                val msg = try {
                    val j = org.json.JSONObject(body)
                    if (j.optBoolean("enrolled", false)) "✅ Enrolled (${j.optInt("samples")} samples)"
                    else "Not calibrated (${j.optInt("samples")}/3 samples)"
                } catch (_: Exception) { "Unknown" }
                onResult(msg)
            }
        })
    }

    fun resetVoiceProfile(onResult: (String) -> Unit) {
        resetEnrollment()
        postVoice("/api/voice/reset", ByteArray(0)) { onResult("Voice profile cleared.") }
    }

    private fun postVoice(path: String, bytes: ByteArray, onBody: (String) -> Unit) {
        val req = okhttp3.Request.Builder()
            .url("$httpBase$path")
            .post(okhttp3.RequestBody.create("audio/wav".toMediaTypeOrNull(), bytes))
            .build()
        voiceHttp.newCall(req).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: java.io.IOException) =
                onBody("{\"error\":\"${e.message}\"}")
            override fun onResponse(call: okhttp3.Call, response: okhttp3.Response) {
                val b = response.body?.string() ?: "{}"; response.close(); onBody(b)
            }
        })
    }

    private fun initializeWebSocket(serverUrl: String, apiKey: String = "") {
        httpBase = httpBaseFrom(serverUrl)
        currentApiKey = apiKey
        webSocket = MizuneWebSocket(object : MizuneWebSocketListener {
            override fun onConnected() {}
            override fun onDisconnected() {}

            override fun onConnectionStateChanged(state: ConnectionState) {
                lastConnectionState = state
                dispatch("connectionState") { it.onConnectionStateChanged(state) }
                updatePersistentNotification()
            }

            override fun onMessage(text: String, emotion: String) {
                currentTurnOurs = frameOwnership()
                dispatch("message") { it.onMessage(text, emotion) }
                if (!isAppInForeground) {
                    // Unsolicited speech lands silently. She still reaches Master — a
                    // proactive thought or a finished scheduled task is worth seeing —
                    // but it no longer buzzes his pocket every 15 minutes.
                    if (turnIsOurs()) showAlertNotification("Mizune", text)
                    else showAmbientNotification("Mizune", text)
                }
            }

            override fun onStateUpdate(valence: Double, arousal: Double) {
                dispatch("stateUpdate") { it.onStateUpdate(valence, arousal) }
            }

            override fun onStatusUpdate(status: String) {
                dispatch("statusUpdate") { it.onStatusUpdate(status) }
            }

            override fun onTaskList(tasks: List<TaskItem>) {
                dispatch("taskList") { it.onTaskList(tasks) }
            }

            override fun onAudio(base64Mp3: String) {
                currentTurnOurs = frameOwnership()
                dispatch("audio") { it.onAudio(base64Mp3) }
                // Hands-free: if the app isn't in the foreground (e.g. wake-word command
                // with the phone locked), the service plays her real voice itself.
                //
                // ONLY for a turn Master started. This is the line that made her talk out
                // loud from a pocket every 15 minutes: the proactive agent's reply carried
                // an audio frame like any other, and the service dutifully played it.
                if (!isAppInForeground && turnIsOurs()) {
                    if (serviceTts == null) serviceTts = com.mizune.app.audio.TtsPlayer(this@MizuneService)
                    speakWithMicPaused(base64Mp3)
                }
            }

            override fun onDeviceCommand(requestId: String, action: String, args: Map<String, String>) {
                currentTurnOurs = frameOwnership()
                val result = try {
                    when (action) {
                        "notify" -> {
                            val title = args["title"] ?: "Mizune"
                            val message = args["message"] ?: args["text"] ?: ""
                            showAlertNotification(title, message)
                            "Notification shown on phone."
                        }
                        "open_url" -> {
                            val url = args["url"] ?: ""
                            if (url.startsWith("http://") || url.startsWith("https://")) {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                // Optional: force a specific browser (e.g. Brave) instead of
                                // letting the URL deep-link into an app (YT Music app).
                                val browser = args["browser"] ?: args["package"]
                                val pkg = if (!browser.isNullOrBlank()) resolveBrowserPackage(browser) else null
                                if (pkg != null) intent.setPackage(pkg)
                                launchIntent(intent, "open $url" + if (pkg != null) " in $browser" else "")
                            } else "Refused: only http(s) URLs are allowed."
                        }
                        "open_app" -> {
                            val name = args["app_name"] ?: args["app"] ?: args["name"] ?: ""
                            val launch = resolveLaunchIntent(name)
                            if (launch == null) "Couldn't find an app matching '$name' on the phone."
                            else launchIntent(launch, "open $name")
                        }
                        "tap" -> {
                            val text = args["text"] ?: args["target"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("tap '$text'")
                            else if (MizuneAccessibilityService.instance?.tapByText(text) == true)
                                "Tapped '$text' on the phone."
                            else "Couldn't find '$text' on the current screen."
                        }
                        "type" -> {
                            val text = args["text"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("type text")
                            else if (MizuneAccessibilityService.instance?.typeText(text) == true)
                                "Typed the text on the phone."
                            else "No text field is focused on the phone right now."
                        }
                        "press" -> {
                            val key = args["key"] ?: args["button"] ?: ""
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("press $key")
                            else if (MizuneAccessibilityService.instance?.press(key) == true)
                                "Pressed $key on the phone."
                            else "Couldn't press '$key' (try: back, home, recents, notifications)."
                        }
                        "scroll" -> {
                            val dir = args["direction"] ?: "down"
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("scroll")
                            else if (MizuneAccessibilityService.instance?.scroll(dir) == true)
                                "Scrolled $dir on the phone."
                            else "Nothing scrollable on the current screen."
                        }
                        "media_play", "media_pause", "media_next" -> {
                            // A media-key event drives the ACTIVE media session (YT Music
                            // web player registers one) — far more reliable than hunting
                            // for a "play" button node in the page.
                            val am = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
                            val key = when (action) {
                                "media_play" -> android.view.KeyEvent.KEYCODE_MEDIA_PLAY
                                "media_pause" -> android.view.KeyEvent.KEYCODE_MEDIA_PAUSE
                                else -> android.view.KeyEvent.KEYCODE_MEDIA_NEXT
                            }
                            am.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, key))
                            am.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, key))
                            "Sent ${action.removePrefix("media_")} to the phone's media player."
                        }
                        "read_screen" -> {
                            if (!MizuneAccessibilityService.isEnabled())
                                needsAccessibility("read the screen")
                            else "SCREEN:\n" + (MizuneAccessibilityService.instance?.dumpScreen() ?: "(unreadable)")
                        }
                        "speak" -> {
                            // The one path that walked past every ownership check. Any
                            // caller able to address this device — a scheduled task, the
                            // dashboard, the proactive agent — could push a 'speak'
                            // command and get the loud alert channel, while the same
                            // words arriving as a normal 'speak' FRAME would have been
                            // routed to the silent ambient channel. Same rule for both,
                            // or the rule is just a detour.
                            val text = args["text"] ?: args["message"] ?: ""
                            dispatch("deviceCommand.speak") { it.onMessage(text, "neutral") }
                            if (!isAppInForeground) {
                                if (turnIsOurs()) showAlertNotification("Mizune", text)
                                else showAmbientNotification("Mizune", text)
                            }
                            "Shown on phone."
                        }
                        else -> "Unknown action '$action'. Phone supports: notify, open_url, open_app, tap, type, press, scroll, read_screen, speak, media_play, media_pause, media_next."
                    }
                } catch (e: Exception) {
                    Log.e("MizuneService", "Device command failed", e)
                    "Error executing $action on phone: ${e.message}"
                }
                webSocket.sendDeviceResult(requestId, result)
            }
        }, serverUrl, apiKey) { DeviceCapabilities.current() }

        webSocket.connect()
    }

    fun setAppInForeground(inForeground: Boolean) {
        isAppInForeground = inForeground
    }

    fun addListener(listener: MizuneWebSocketListener) {
        synchronized(listenersLock) {
            uiListeners.add(listener)
        }
        // Immediately sync current state
        listener.onConnectionStateChanged(lastConnectionState)
    }

    fun removeListener(listener: MizuneWebSocketListener) {
        synchronized(listenersLock) {
            uiListeners.remove(listener)
        }
    }

    private fun needsAccessibility(what: String): String =
        "I need the Accessibility permission to $what. Open the Mizune app once and tap " +
        "\"Enable Mizune's hands\" (Settings → Accessibility → Mizune → On). Then I can do it every time."

    /**
     * Launch an app/URL. Preferred path is the AccessibilityService — it's exempt from
     * the OEM background-launch blocking (OnePlus/OxygenOS etc.) that silently swallows
     * a plain foreground-service startActivity. Falls back to overlay-based launch, then
     * to a tappable notification — and reports HONESTLY which happened.
     */
    private fun launchIntent(intent: Intent, describe: String): String {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // 1. Accessibility (reliable everywhere)
        if (MizuneAccessibilityService.isEnabled() &&
            MizuneAccessibilityService.instance?.launch(intent) == true) {
            return "Done — opened it on the phone ($describe)."
        }
        // 2. Overlay-privileged direct launch (works on stock Android with permission)
        val canOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
                android.provider.Settings.canDrawOverlays(this)
        if (canOverlay) {
            try {
                startActivity(intent)
                // On OEM ROMs this can be silently dropped, so be honest, not boastful.
                return "Tried to $describe on the phone. If nothing appeared, enable " +
                    "Mizune's Accessibility permission and I'll do it reliably."
            } catch (_: Exception) { /* fall through */ }
        }
        // 3. Tappable notification fallback
        showLaunchNotification(intent, describe)
        return "I couldn't launch it directly (OEM background limits). I sent a tappable " +
            "notification — or enable Mizune's Accessibility permission for one-tap-free launches."
    }

    /** Resolve a browser name to its installed package (so a URL opens THERE, not in
     *  an app that claims the link). Falls back to null if the browser isn't installed. */
    private fun resolveBrowserPackage(name: String): String? {
        val pm = packageManager
        val q = name.trim().lowercase()
        val candidates = when {
            q.contains("brave") -> listOf("com.brave.browser", "com.brave.browser_beta")
            q.contains("chrome") -> listOf("com.android.chrome")
            q.contains("firefox") -> listOf("org.mozilla.firefox")
            q.contains("edge") -> listOf("com.microsoft.emmx")
            else -> listOf(q)
        }
        for (c in candidates) {
            try { pm.getPackageInfo(c, 0); return c } catch (_: Exception) {}
        }
        return null
    }

    /** Resolve a spoken app name (e.g. "brave", "spotify") to a launch intent. */
    private fun resolveLaunchIntent(name: String): Intent? {
        if (name.isBlank()) return null
        val pm = packageManager
        val query = name.trim().lowercase()
        // Common aliases → package hints
        val aliases = mapOf(
            "brave" to "com.brave", "chrome" to "com.android.chrome",
            "youtube" to "com.google.android.youtube", "yt music" to "com.google.android.apps.youtube.music",
            "youtube music" to "com.google.android.apps.youtube.music",
            "spotify" to "com.spotify", "whatsapp" to "com.whatsapp",
            "instagram" to "com.instagram", "maps" to "com.google.android.apps.maps",
            "gmail" to "com.google.android.gm"
        )
        val hint = aliases.entries.firstOrNull { query.contains(it.key) }?.value
        val installed = pm.getInstalledApplications(0)
        val match = installed.firstOrNull { app ->
            (hint != null && app.packageName.startsWith(hint)) ||
                pm.getApplicationLabel(app).toString().lowercase() == query ||
                pm.getApplicationLabel(app).toString().lowercase().contains(query)
        }
        return match?.let { pm.getLaunchIntentForPackage(it.packageName) }
    }

    private fun showLaunchNotification(intent: Intent, describe: String) {
        val pending = PendingIntent.getActivity(
            this, describe.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notif = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Mizune")
            .setContentText("Tap to $describe")
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setFullScreenIntent(pending, true)
            .setContentIntent(pending)
            .build()
        getSystemService(NotificationManager::class.java)
            .notify(describe.hashCode(), notif)
    }

    fun sendMessage(text: String) {
        if (::webSocket.isInitialized) {
            markOutbound()
            webSocket.sendMessage(text)
        }
    }

    fun sendVisionMessage(base64Image: String) {
        if (::webSocket.isInitialized) {
            markOutbound()
            webSocket.sendVisionMessage(base64Image)
        }
    }

    fun reconnectWithServer(serverUrl: String) {
        if (::webSocket.isInitialized) {
            webSocket.disconnect()
        }
        // Reuse the stored key: passing the default "" here would silently drop auth and
        // reconnect unauthenticated, which fails closed the moment ws_auth_required is on.
        initializeWebSocket(serverUrl, currentApiKey)
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val persistentChannel = NotificationChannel(
                CHANNEL_ID,
                "Mizune Connection",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Mizune connected in the background"
                setShowBadge(false)
            }

            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "Mizune Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifications for messages and reminders"
                setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION), null)
            }

            // Silent by design: no sound, no vibration, no heads-up. This is where
            // everything she says unprompted goes.
            val ambientChannel = NotificationChannel(
                AMBIENT_CHANNEL_ID,
                "Mizune Thoughts",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Things Mizune says on her own — proactive thoughts, " +
                    "finished tasks. Never makes a sound."
                setSound(null, null)
                enableVibration(false)
            }

            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannels(listOf(persistentChannel, alertChannel, ambientChannel))
        }
    }

    private fun createPersistentNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(wakeStatus)
            .setContentText("Status: ${lastConnectionState.label}")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setOnlyAlertOnce(true)
            .build()
    }

    @Volatile private var wakeStatus = "Mizune is awake"
    private var lastWakeUpdate = 0L
    private fun setWakeStatus(s: String) {
        wakeStatus = s
        val now = System.currentTimeMillis()
        if (now - lastWakeUpdate > 700) {   // throttle notification updates
            lastWakeUpdate = now
            updatePersistentNotification()
        }
    }

    private fun updatePersistentNotification() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, createPersistentNotification())
    }

    /** Unprompted speech: visible, never audible. One slot, so a chatty hour can't
     *  stack fifty notifications — the newest replaces the last. */
    private fun showAmbientNotification(title: String, message: String) {
        val pendingIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, AMBIENT_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(message.take(100))
            .setStyle(NotificationCompat.BigTextStyle().bigText(message.take(400)))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setSilent(true)
            .build()
        getSystemService(NotificationManager::class.java).notify(2, notification)
    }

    private fun showAlertNotification(title: String, message: String) {
        val pendingIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(message.take(100))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(System.currentTimeMillis().toInt(), notification)
    }
}
