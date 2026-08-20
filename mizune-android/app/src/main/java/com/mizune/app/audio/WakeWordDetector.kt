package com.mizune.app.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

interface WakeWordListener {
    fun onWakeWordDetected()
    fun onCommandRecognized(command: String)
    fun onError(error: String)
    fun onReadyForSpeech()
    /** Any transcript the mic picks up — used for a live on-screen debug readout. */
    fun onHeard(text: String) {}
}

/**
 * Offline "Baka Mizune" wake word via Vosk, reading its OWN AudioRecord loop.
 *
 * Design (2026-07-16 rework):
 *  - WAKE phase is free-form recognition + a lab-validated fuzzy matcher (see the
 *    companion sets). Grammar mode was tried and is DEAD: baka/mizune are not in the
 *    model vocab, so a grammar recognizer only ever outputs [unk].
 *  - Owning the AudioRecord (instead of Vosk's SpeechService) gives us the raw wake
 *    utterance, enabling Voice Match: `wakeVerifier` gets the wake audio as WAV and
 *    decides (via the server's enrolled voiceprint) whether this is Master speaking.
 *  - `recordWav` records a calibration sample for enrollment (Settings screen).
 *
 * The model is bundled in assets/vosk-model-en and unpacked to filesDir on first use.
 */
class WakeWordDetector(private val context: Context, private val listener: WakeWordListener) {

    companion object {
        private const val SAMPLE_RATE = 16000
        private const val CHUNK = 1600                    // 100ms of 16k mono PCM16
        private const val RING_SECONDS = 2.5              // wake utterance snapshot
        private const val COMMAND_WINDOW_MS = 7000L

        /**
         * The fuzzy TEXT wake path — OFF.
         *
         * It is a false-positive machine in real conversation: the token sets below
         * contain everyday English ("but", "book", "back", "come", "soon", "june"), so
         * normal speech woke her repeatedly. Re-enabling this without first removing
         * those common words will bring the problem straight back.
         *
         * The acoustic DTW path is the real wake word — it matches Master's own
         * recordings, so it cannot fire on a stranger or on a word that merely rhymes.
         * Its only cost is that calibration must happen first, which is now enforced
         * rather than silently worked around.
         */
        private const val ALLOW_TEXT_WAKE = false

        // "baka"/"mizune" are NOT in the small-en vocab (grammar mode decodes them to
        // [unk] — lab-proven dead). Instead: free-form recognition + fuzzy sets derived
        // from what the model ACTUALLY hears for "Baka Mizune" (lab: "bach i'm a zune",
        // "barca amazon", "book on resume", "but came"...). Validated 8/8 positives,
        // 0/10 false-positives. Extend from the "heard:" notification readout.
        private val BAKA = setOf(
            "baka", "bach", "barca", "buck", "book", "but", "back", "bucket", "bacca",
            "bakka", "vodka", "pucker", "bhaka", "pakka", "bukhara", "parka", "become",
            "becker", "bother", "packer", "poker"
        )
        private val MIZU_STRONG = setOf(
            "mizune", "zune", "zooney", "amazon", "resume", "islam", "mizu",
            "museum", "mizzou", "missouri", "zuni", "resumes", "amazons"
        )
        private val MIZU_WEAK_ADJ = setOf(
            "came", "come", "soon", "zoo", "own", "june", "moon", "noon", "kama", "comma"
        )
    }

    // ── Acoustic wake (primary once calibrated) ─────────────────────────────────
    // Master's 3 "Baka Mizune" calibration recordings (saved on-device at enrollment)
    // are MFCC templates; the live mic ring is DTW-scored against them every ~300ms.
    // Language/accent-independent AND inherently voice-matched — it's HIS voice as the
    // template. Lab thresholds: same-voice wake 8-13, everything else 22+.
    // Public so the Settings self-test scores against the SAME number the live loop
    // fires on. A test with its own copy of the threshold can pass while the real wake
    // word fails, which would be worse than having no test.
    val WAKE_SCORE_FIRE = 16.0
    private val WAKE_SCORE_NEAR = 21.0

    /**
     * Below this ring RMS the room is quiet and scoring is skipped entirely.
     *
     * Not an optimisation — a correctness fix. Digital silence floors every mel bin at
     * `ln(1e-10)` ([MfccDtw]), so the log-mel vector is constant, the cepstra come out
     * near zero, and CMN flattens what little is left. A flat matrix is not *far* from
     * anything: silence scored as a mediocre match rather than "no match", and a
     * mediocre match under a loose threshold is a wake. It also happens to remove the
     * 300ms DTW pass in a quiet room, which is most of the battery complaint.
     *
     * 300 sits well under speech at arm's length (~1500+) and well over room tone
     * (~40-150) on the VOICE_RECOGNITION source, which already applies gain control.
     */
    private val WAKE_RMS_GATE = 300.0

    /**
     * Templates needed before the acoustic path is allowed to fire.
     *
     * One template is not a voiceprint, it is a coincidence generator: [acousticScore]
     * takes the MINIMUM over every template, so a lone mediocre sample has nothing to
     * outvote it and matches half the room. A half-finished calibration used to arm the
     * wake word anyway, because the loop only checked the list was non-empty.
     */
    private val MIN_TEMPLATES = 3

    @Volatile private var acousticTemplates: List<Array<DoubleArray>> = emptyList()
    private var templateFrames = 0

    /** How many acoustic templates are loaded — 0 means the acoustic path cannot fire. */
    val templateCount: Int get() = acousticTemplates.size

    /** True when there are enough templates to trust a match. See [MIN_TEMPLATES]. */
    val wakeArmed: Boolean get() = acousticTemplates.size >= MIN_TEMPLATES && templateFrames > 0

    fun templatesDir() = File(context.filesDir, "wake_templates")

    /** Decode a 16k mono PCM16 WAV body (44-byte header) to samples. */
    fun wavToPcm(wav: ByteArray): ShortArray {
        if (wav.size <= 44) return ShortArray(0)
        val pcm = ShortArray((wav.size - 44) / 2)
        ByteBuffer.wrap(wav, 44, pcm.size * 2).order(ByteOrder.LITTLE_ENDIAN)
            .asShortBuffer().get(pcm)
        return pcm
    }

    /** Enrollment WAVs on disk, as MFCC templates. One decoder, used by everything. */
    fun loadTemplateFeatures(): List<Array<DoubleArray>> =
        templatesDir().listFiles { f -> f.name.endsWith(".wav") }
            ?.sortedBy { it.name }
            ?.mapNotNull { f ->
                MfccDtw.features(MfccDtw.trimSilence(wavToPcm(f.readBytes())))
                    .takeIf { it.size >= 20 }
            } ?: emptyList()

    /** (Re)load enrollment WAVs → MFCC templates. Called at start and after calibration. */
    fun reloadTemplates() {
        try {
            val loaded = loadTemplateFeatures()
            acousticTemplates = loaded
            templateFrames = if (loaded.isEmpty()) 0 else loaded.sumOf { it.size } / loaded.size
            Log.d("WakeWord", "acoustic templates: ${loaded.size} (avg $templateFrames frames)" +
                if (loaded.size < MIN_TEMPLATES) " — NOT ARMED, need $MIN_TEMPLATES" else " — armed")
        } catch (e: Exception) {
            Log.e("WakeWord", "template load failed", e)
            acousticTemplates = emptyList()
            templateFrames = 0
        }
    }

    /**
     * The one scorer. Min DTW distance of the suffix of [full] (3 window scales) against
     * every template.
     *
     * Public because the Settings self-test MUST score through this exact function. It
     * used to run its own simpler match — min over templates only, no window scales —
     * so the live loop, minimising over 3x as many candidates, always scored LOWER on
     * identical audio. The test could pass while the loop fired on the room, and the
     * test was structurally blind to it. A self-test that doesn't share the scorer is
     * worse than no self-test: it vouches for behaviour it cannot see.
     */
    fun scoreFeatures(full: Array<DoubleArray>): Double {
        val templates = acousticTemplates
        if (templates.size < MIN_TEMPLATES || templateFrames == 0 || full.isEmpty())
            return Double.MAX_VALUE
        var best = Double.MAX_VALUE
        for (scale in doubleArrayOf(0.9, 1.1, 1.3)) {
            val want = (templateFrames * scale).toInt()
            if (want <= 0 || full.size < want / 2) continue
            val from = maxOf(0, full.size - want)
            val win = Array(full.size - from) { full[from + it].clone() }
            MfccDtw.cmn(win)
            for (t in templates) best = minOf(best, MfccDtw.dtw(win, t))
        }
        return best
    }

    /** Score raw PCM exactly as the live loop scores its mic ring. */
    fun scorePcm(pcm: ShortArray): Double = scoreFeatures(MfccDtw.features(pcm))

    /** RMS of the whole ring — the loudness the score was produced at. */
    private fun ringRms(ring: ArrayDeque<ShortArray>): Double {
        var sumSq = 0.0
        var n = 0
        for (c in ring) for (s in c) { val v = s.toDouble(); sumSq += v * v; n++ }
        return if (n == 0) 0.0 else kotlin.math.sqrt(sumSq / n)
    }

    /** Min DTW score of ring-suffix windows (3 scales) vs all templates. */
    private fun acousticScore(ring: ArrayDeque<ShortArray>): Double {
        if (!wakeArmed) return Double.MAX_VALUE
        val maxWinSamples = (templateFrames * 1.3).toInt() * 160 + 400
        var total = 0
        val chunks = mutableListOf<ShortArray>()
        for (c in ring.reversed()) {
            chunks.add(0, c); total += c.size
            if (total >= maxWinSamples) break
        }
        if (total < templateFrames * 160 / 2) return Double.MAX_VALUE
        val suffix = ShortArray(total)
        var off = 0
        for (c in chunks) { System.arraycopy(c, 0, suffix, off, c.size); off += c.size }
        return scoreFeatures(MfccDtw.features(suffix))
    }

    /** null = no wake. Else the same-breath command remainder (possibly ""). The wake
     *  phrase is said FIRST, so the baka-token must be at position 0 or 1 — this is
     *  what kills false fires like "buy me a book on amazon". */
    private fun detectWake(text: String): String? {
        val toks = text.split(Regex("\\s+")).filter { it.isNotBlank() }
        for (i in 0 until minOf(2, toks.size)) {
            if (toks[i] !in BAKA) continue
            for (j in i + 1 until minOf(i + 4, toks.size)) {
                val tj = toks[j]
                if (tj in MIZU_STRONG || (tj in MIZU_WEAK_ADJ && j == i + 1)) {
                    return toks.drop(j + 1).joinToString(" ")
                }
            }
        }
        return null
    }

    private var model: Model? = null
    @Volatile private var running = false
    @Volatile private var paused = false
    private var loopThread: Thread? = null
    private var lastFired = 0L

    /**
     * Voice Match hook. Given the wake utterance (16k mono PCM16 WAV) call back with
     * true = proceed (it's Master / not enrolled / verify unavailable) or false = ignore.
     * Null = no verification (always proceed).
     */
    @Volatile var wakeVerifier: ((wav: ByteArray, proceed: (Boolean) -> Unit) -> Unit)? = null

    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())

    fun startListening() {
        if (running) return
        if (model != null) { startLoop(); return }
        Thread {
            try {
                val dir = copyAssetModel()
                model = Model(dir.absolutePath)
                Log.d("WakeWord", "Vosk model loaded from ${dir.absolutePath}")
                mainHandler.post { startLoop(); listener.onReadyForSpeech() }
            } catch (e: Throwable) {
                Log.e("WakeWord", "Vosk model load failed", e)
                val msg = "${e.javaClass.simpleName}: ${e.message}"
                mainHandler.post { listener.onError(msg) }
            }
        }.start()
    }

    fun stopListening() {
        running = false
        loopThread?.join(1500)
        loopThread = null
    }

    fun pause() { paused = true }        // loop releases the mic while paused
    fun resume() {
        paused = false
        if (!running && model != null) startLoop()
    }

    // ── The mic loop ────────────────────────────────────────────────────────────

    private fun startLoop() {
        if (running) return
        val m = model ?: return
        reloadTemplates()
        running = true
        loopThread = Thread {
            try { micLoop(m) } catch (e: Throwable) {
                Log.e("WakeWord", "mic loop died", e)
                mainHandler.post { listener.onError("wake loop: ${e.message}") }
            } finally { running = false }
        }.apply { name = "MizuneWakeLoop"; start() }
    }

    @SuppressLint("MissingPermission")
    private fun newAudioRecord(): AudioRecord {
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        return AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION, SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuf, CHUNK * 4)
        )
    }

    private fun micLoop(m: Model) {
        val wakeRec = Recognizer(m, SAMPLE_RATE.toFloat())
        var freeRec: Recognizer? = null                   // created per command window
        var commandDeadline = 0L
        val ring = ArrayDeque<ShortArray>()               // last ~2.5s for Voice Match
        val ringMax = (SAMPLE_RATE * RING_SECONDS / CHUNK).toInt()
        var record: AudioRecord? = null
        val buf = ShortArray(CHUNK)
        var chunksSinceScore = 0

        fun releaseMic() { record?.let { try { it.stop(); it.release() } catch (_: Exception) {} }; record = null }

        try {
            while (running) {
                if (paused) { releaseMic(); Thread.sleep(120); continue }
                if (record == null) {
                    val r = newAudioRecord()
                    if (r.state != AudioRecord.STATE_INITIALIZED) {
                        try { r.release() } catch (_: Exception) {}
                        mainHandler.post { listener.onError("mic unavailable") }
                        Thread.sleep(1000)
                        continue
                    }
                    r.startRecording()
                    record = r
                }
                val n = record!!.read(buf, 0, CHUNK)
                if (n <= 0) { Thread.sleep(30); continue }

                ring.addLast(buf.copyOf(n))
                while (ring.size > ringMax) ring.removeFirst()

                val bytes = shortsToBytes(buf, n)

                if (freeRec == null && wakeArmed) {
                    // WAKE phase — ACOUSTIC (calibrated): DTW-score the ring suffix
                    // against Master's own recordings every 3 chunks (~300ms). No ASR,
                    // no server round-trip, voice-matched by construction.
                    if (++chunksSinceScore >= 3) {
                        chunksSinceScore = 0
                        val rms = ringRms(ring)
                        // Energy gate FIRST: a quiet room must not reach the matcher at
                        // all. See WAKE_RMS_GATE — silence is not a large DTW distance,
                        // it is a flat feature matrix that scores like a mediocre match.
                        val score = if (rms < WAKE_RMS_GATE) Double.MAX_VALUE
                                    else acousticScore(ring)
                        val now = System.currentTimeMillis()
                        // Every pass, not just near-misses. WAKE_SCORE_FIRE = 16.0 came
                        // from the python lab (acoustic_lab.py) and was never measured
                        // through this Kotlin path on this phone, so the live
                        // distribution is the only thing that can justify it. Logged
                        // beside the RMS it was produced at, so speech and room tone are
                        // separable in one line.
                        if (rms < WAKE_RMS_GATE) {
                            Log.d("WakeWord", "SCORE quiet rms=%.0f (gate %.0f)"
                                .format(rms, WAKE_RMS_GATE))
                        } else {
                            Log.d("WakeWord", "SCORE %.2f rms=%.0f tframes=%d fire<%.1f"
                                .format(score, rms, templateFrames, WAKE_SCORE_FIRE))
                        }
                        if (score < WAKE_SCORE_FIRE && now - lastFired > 2500) {
                            lastFired = now
                            mainHandler.post {
                                listener.onHeard("wake! score ${"%.1f".format(score)}")
                                listener.onWakeWordDetected()
                            }
                            freeRec = Recognizer(m, SAMPLE_RATE.toFloat())
                            commandDeadline = now + COMMAND_WINDOW_MS
                        } else if (score < WAKE_SCORE_NEAR) {
                            // near-miss readout = live tuning data
                            mainHandler.post { listener.onHeard("near: ${"%.1f".format(score)}") }
                        }
                    }
                } else if (freeRec == null && !ALLOW_TEXT_WAKE) {
                    // WAKE phase — NOT CALIBRATED, and the text fallback is off.
                    //
                    // This branch used to run the fuzzy matcher and it fired constantly on
                    // ordinary speech: BAKA contains "but"/"book"/"back"/"become" and
                    // MIZU_WEAK_ADJ contains "come"/"soon"/"june"/"own", so "but I'll come
                    // later" or "back soon" was a wake word. The lab's "0/10 false
                    // positives" was ten chosen phrases, not conversation.
                    //
                    // Waking at random is worse than not waking: it interrupts, it records,
                    // and it made the app impossible to test. So with no templates she
                    // stays deliberately deaf and says why. Calibrate → the acoustic path
                    // above takes over, and it is voice-matched by construction.
                    //
                    // Skipping acceptWaveForm() also stops running a full ASR model on the
                    // mic forever, which was the other half of the battery complaint.
                    if (++chunksSinceScore >= 50) {          // ~5s
                        chunksSinceScore = 0
                        val have = acousticTemplates.size
                        mainHandler.post {
                            listener.onHeard(
                                "wake word off — $have/$MIN_TEMPLATES voice samples " +
                                    "(Settings → Voice Match)"
                            )
                        }
                    }
                } else if (freeRec == null) {
                    // WAKE phase — TEXT fallback (opt-in only; see ALLOW_TEXT_WAKE).
                    val final = wakeRec.acceptWaveForm(bytes, bytes.size)
                    val text = extract(if (final) wakeRec.result else wakeRec.partialResult)
                    if (text.isNotBlank()) mainHandler.post { listener.onHeard(text) }
                    val now = System.currentTimeMillis()
                    val sameBreath = detectWake(text)
                    if (sameBreath != null && now - lastFired > 2000) {
                        lastFired = now
                        wakeRec.reset()
                        mainHandler.post { listener.onWakeWordDetected() }
                        val wakeWav = pcmToWav(ring.toList())
                        if (!verifyBlocking(wakeWav)) {
                            mainHandler.post { listener.onHeard("(voice not recognized — ignored)") }
                        } else if (sameBreath.isNotBlank()) {
                            // One-breath: "baka mizune play shakira" — command included.
                            mainHandler.post { listener.onCommandRecognized(sameBreath) }
                        } else {
                            freeRec = Recognizer(m, SAMPLE_RATE.toFloat())
                            commandDeadline = System.currentTimeMillis() + COMMAND_WINDOW_MS
                        }
                    }
                } else {
                    // COMMAND phase (free-form)
                    val final = freeRec!!.acceptWaveForm(bytes, bytes.size)
                    if (final) {
                        val cmd = extract(freeRec!!.result)
                        if (cmd.isNotBlank()) {
                            endCommand(freeRec!!); freeRec = null
                            mainHandler.post { listener.onCommandRecognized(cmd) }
                        }
                    } else {
                        val partial = extract(freeRec!!.partialResult)
                        if (partial.isNotBlank()) mainHandler.post { listener.onHeard(partial) }
                    }
                    if (freeRec != null && System.currentTimeMillis() > commandDeadline) {
                        val cmd = extract(freeRec!!.finalResult)
                        endCommand(freeRec!!); freeRec = null
                        if (cmd.isNotBlank()) mainHandler.post { listener.onCommandRecognized(cmd) }
                    }
                }
            }
        } finally {
            releaseMic()
            try { wakeRec.close() } catch (_: Exception) {}
            try { freeRec?.close() } catch (_: Exception) {}
        }
    }

    private fun endCommand(rec: Recognizer) { try { rec.close() } catch (_: Exception) {} }

    /** Run the Voice Match verifier synchronously (loop thread), fail-OPEN on timeout. */
    private fun verifyBlocking(wav: ByteArray): Boolean {
        val v = wakeVerifier ?: return true
        val latch = java.util.concurrent.CountDownLatch(1)
        val result = java.util.concurrent.atomic.AtomicBoolean(true)
        try {
            v(wav) { ok -> result.set(ok); latch.countDown() }
            latch.await(2, java.util.concurrent.TimeUnit.SECONDS)
        } catch (e: Exception) {
            Log.w("WakeWord", "voice verify failed open: ${e.message}")
        }
        return result.get()
    }

    private fun extract(json: String?): String = try {
        val o = JSONObject(json ?: "{}")
        val t = o.optString("text", "")
        (if (t.isNotBlank()) t else o.optString("partial", "")).lowercase().trim()
    } catch (_: Exception) { "" }

    // ── Calibration recording (Settings → "Calibrate voice") ───────────────────

    /**
     * Record `ms` of raw mic audio and return it as a 16k mono WAV. Caller must
     * pause the wake loop first (mic conflict) and resume after.
     */
    @SuppressLint("MissingPermission")
    fun recordWav(ms: Long, onDone: (ByteArray?) -> Unit) {
        Thread {
            var rec: AudioRecord? = null
            try {
                Thread.sleep(250)                       // let the wake loop free the mic
                rec = newAudioRecord()
                rec.startRecording()
                val chunks = mutableListOf<ShortArray>()
                val buf = ShortArray(CHUNK)
                val until = System.currentTimeMillis() + ms
                while (System.currentTimeMillis() < until) {
                    val n = rec.read(buf, 0, CHUNK)
                    if (n > 0) chunks.add(buf.copyOf(n))
                }
                mainHandler.post { onDone(pcmToWav(chunks)) }
            } catch (e: Throwable) {
                Log.e("WakeWord", "recordWav failed", e)
                mainHandler.post { onDone(null) }
            } finally {
                rec?.let { try { it.stop(); it.release() } catch (_: Exception) {} }
            }
        }.start()
    }

    // ── One-shot command capture (Porcupine hand-off path only) ────────────────

    fun captureCommandOnce(timeoutMs: Long = 7000L, onDone: (String?) -> Unit) {
        Thread {
            try {
                if (model == null) { val dir = copyAssetModel(); model = Model(dir.absolutePath) }
                Thread.sleep(250)   // let the previous holder release the mic
                val rec = Recognizer(model, SAMPLE_RATE.toFloat())
                val svc = SpeechService(rec, SAMPLE_RATE.toFloat())
                val done = java.util.concurrent.atomic.AtomicBoolean(false)
                val finish: (String?) -> Unit = { result ->
                    if (done.compareAndSet(false, true)) {
                        // The Recognizer holds native memory of its own; shutting the
                        // SpeechService down does not free it. One assist gesture per
                        // leak adds up over a service that is meant to run for days.
                        try { svc.stop(); svc.shutdown() } catch (_: Exception) {}
                        try { rec.close() } catch (_: Exception) {}
                        mainHandler.post { onDone(result) }
                    }
                }
                svc.startListening(object : RecognitionListener {
                    override fun onPartialResult(h: String?) {}
                    override fun onResult(h: String?) {
                        val t = try { JSONObject(h ?: "{}").optString("text").trim() } catch (_: Exception) { "" }
                        if (t.isNotBlank()) finish(t)
                    }
                    override fun onFinalResult(h: String?) {
                        val t = try { JSONObject(h ?: "{}").optString("text").trim() } catch (_: Exception) { "" }
                        finish(if (t.isNotBlank()) t else null)
                    }
                    override fun onError(e: Exception?) { finish(null) }
                    override fun onTimeout() { finish(null) }
                })
                mainHandler.postDelayed({ finish(null) }, timeoutMs)
            } catch (e: Throwable) {
                mainHandler.post { onDone(null) }
            }
        }.start()
    }

    // ── Helpers ─────────────────────────────────────────────────────────────────

    private fun shortsToBytes(src: ShortArray, n: Int): ByteArray {
        val bb = ByteBuffer.allocate(n * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (i in 0 until n) bb.putShort(src[i])
        return bb.array()
    }

    /** Wrap raw 16k mono PCM16 chunks in a WAV container. */
    private fun pcmToWav(chunks: List<ShortArray>): ByteArray {
        val total = chunks.sumOf { it.size }
        val dataSize = total * 2
        val out = ByteArrayOutputStream(44 + dataSize)
        val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        h.put("RIFF".toByteArray()).putInt(36 + dataSize).put("WAVE".toByteArray())
        h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
        h.putInt(SAMPLE_RATE).putInt(SAMPLE_RATE * 2).putShort(2).putShort(16)
        h.put("data".toByteArray()).putInt(dataSize)
        out.write(h.array())
        for (c in chunks) out.write(shortsToBytes(c, c.size))
        return out.toByteArray()
    }

    /** Copy the bundled model from assets/vosk-model-en → filesDir (once). Returns the dir. */
    private fun copyAssetModel(): File {
        val dest = File(context.filesDir, "vosk-model-en")
        val marker = File(dest, "conf/model.conf")
        if (marker.exists()) return dest
        copyAssetDir("vosk-model-en", dest)
        if (!marker.exists()) throw IllegalStateException("model incomplete after copy (missing conf/model.conf)")
        return dest
    }

    private fun copyAssetDir(assetPath: String, dest: File) {
        val children = context.assets.list(assetPath) ?: emptyArray()
        if (children.isEmpty()) {
            dest.parentFile?.mkdirs()
            context.assets.open(assetPath).use { input ->
                dest.outputStream().use { input.copyTo(it) }
            }
        } else {
            dest.mkdirs()
            for (child in children) copyAssetDir("$assetPath/$child", File(dest, child))
        }
    }
}
