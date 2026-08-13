package com.mizune.app.audio

import android.util.Log
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sqrt

/**
 * Enrolment for the acoustic wake word — the part that actually decides whether
 * "Baka Mizune" ever fires.
 *
 * The old flow was a counter, not a calibration: record 2.5s, write the file, add one to
 * a tally, stop at three. It could not tell speech from silence, Master from a passing
 * bus, or a good sample from one that would poison the templates — so "3/3 calibrated"
 * meant nothing, and a bad set made the wake word *worse* than none at all. Every
 * template is a permanent vote in the DTW match; a bad one is not neutral.
 *
 * So this gates every sample on four checks and refuses the ones that would hurt:
 *
 *  1. **Loud enough** — RMS above a floor, or it is room tone.
 *  2. **Not clipped** — too close to the mic distorts the spectrum MFCC depends on.
 *  3. **Actually a phrase** — enough frames survive silence-trimming to be "Baka Mizune",
 *     and not so many that a whole sentence got recorded.
 *  4. **Consistent with what came before** — DTW distance against already-accepted
 *     samples. This is the check that makes it *his* voice rather than any voice, and
 *     it is why rejection messages can be specific instead of "try again".
 *
 * Thresholds come from the lab numbers recorded in [MfccDtw]: same-speaker wake
 * utterances score 8-13, different phrases or speakers 22+. ACCEPT_MAX sits at 18 —
 * inside the gap, tolerant of a cold or a noisy room, well clear of a wrong phrase.
 */
class VoiceEnrollment(private val detector: WakeWordDetector) {

    sealed class Result {
        /** Sample kept. [accepted] of [needed] done. */
        data class Accepted(val accepted: Int, val needed: Int, val score: Double?) : Result()
        /** Sample refused — [reason] is short for the UI, [hint] tells him what to change. */
        data class Rejected(val reason: String, val hint: String, val accepted: Int, val needed: Int) : Result()
        /** Enough good samples. [spread] is the mean pairwise DTW distance — lower is tighter. */
        data class Complete(val accepted: Int, val spread: Double) : Result()
        /** Something broke that isn't the user's fault. */
        data class Failed(val message: String) : Result()
    }

    companion object {
        private const val TAG = "VoiceEnroll"
        const val NEEDED = 3

        private const val RECORD_MS = 2500L
        /** Below this RMS the clip is room tone, not a spoken phrase. */
        private const val RMS_FLOOR = 450.0
        /** Fraction of samples at full scale that means the mic is clipping. */
        private const val CLIP_RATIO = 0.02
        /** MFCC frames (10ms hop) surviving silence-trim: ~0.4s to ~2.0s of speech. */
        private const val MIN_FRAMES = 40
        private const val MAX_FRAMES = 200
        /** DTW distance to already-accepted samples. See class doc for why 18. */
        private const val ACCEPT_MAX = 18.0
    }

    /** MFCC features of samples accepted in THIS run, for the consistency check. */
    private val accepted = mutableListOf<Array<DoubleArray>>()

    val acceptedCount: Int get() = accepted.size

    /** Wipe every template on disk and start the run over. */
    fun reset() {
        accepted.clear()
        try {
            detector.templatesDir().listFiles()?.forEach { it.delete() }
            detector.reloadTemplates()
        } catch (e: Exception) {
            Log.e(TAG, "reset failed", e)
        }
    }

    /**
     * Record one sample, judge it, and keep it only if it passes. Safe to call again
     * immediately after a rejection — that is the whole point of the design.
     */
    fun recordSample(onResult: (Result) -> Unit) {
        detector.recordWav(RECORD_MS) { wav ->
            if (wav == null || wav.size <= 44) {
                onResult(Result.Failed("Recording failed — check the microphone permission."))
                return@recordWav
            }
            val pcm = wavToPcm(wav)
            val verdict = judge(pcm)
            if (verdict != null) {
                onResult(Result.Rejected(verdict.first, verdict.second, accepted.size, NEEDED))
                return@recordWav
            }

            val feats = MfccDtw.features(MfccDtw.trimSilence(pcm))

            // A calibration run REPLACES the template set; it never appends to it.
            //
            // This is the bug that made her fire on nothing. `accepted` lives in memory,
            // so on a fresh process it is empty while the directory still holds the
            // previous run's WAVs. The first sample of every later run therefore skipped
            // the consistency check entirely — nothing to compare against — and was
            // written beside the good ones. `WakeWordDetector.scoreFeatures` takes the
            // MINIMUM over every template, so one loose sample is not diluted by the
            // three good ones: it wins the minimum and drags the score under the
            // threshold for whatever the room happens to be doing. Nothing capped the
            // directory either, so the files accumulated forever, one per calibration.
            //
            // Wiping first makes the in-memory list and the disk set the same thing
            // again, which is the assumption every check below is written against.
            // A finished run must not be appended to either — a fourth sample would sit
            // beside three that were validated as a set, without ever being checked
            // against a full one. Recording again starts a new set.
            if (accepted.size >= NEEDED) accepted.clear()
            if (accepted.isEmpty()) {
                try {
                    detector.templatesDir().listFiles()?.forEach { it.delete() }
                } catch (e: Exception) {
                    Log.w(TAG, "could not clear old templates", e)
                }
            }

            // Consistency: compare against samples already accepted this run. The first
            // sample has nothing to compare to and sets the reference — which is exactly
            // why a bad first sample used to poison everything after it, and why the
            // absolute checks above have to run before this one.
            var score: Double? = null
            if (accepted.isNotEmpty()) {
                score = accepted.minOf { MfccDtw.dtw(feats, it) }
                if (score > ACCEPT_MAX) {
                    onResult(
                        Result.Rejected(
                            "That sounded different from your other samples",
                            "Say \"Baka Mizune\" the same way each time — same pace, " +
                                "same distance from the phone.",
                            accepted.size, NEEDED
                        )
                    )
                    return@recordWav
                }
            }

            try {
                File(detector.templatesDir().apply { mkdirs() },
                    "sample_${System.currentTimeMillis()}.wav").writeBytes(wav)
                accepted.add(feats)
                detector.reloadTemplates()
            } catch (e: Exception) {
                Log.e(TAG, "template write failed", e)
                onResult(Result.Failed("Couldn't save that sample: ${e.message}"))
                return@recordWav
            }

            if (accepted.size >= NEEDED) {
                onResult(Result.Complete(accepted.size, meanSpread()))
            } else {
                onResult(Result.Accepted(accepted.size, NEEDED, score))
            }
        }
    }

    /** Outcome of a live wake test. [score] is the DTW distance — lower is a better match. */
    data class TestResult(
        val passed: Boolean,
        val score: Double,
        val threshold: Double,
        val message: String
    )

    /**
     * Say it once and find out. Records a clip and scores it against the saved templates
     * with the SAME threshold the always-on loop fires on ([WakeWordDetector.WAKE_SCORE_FIRE]),
     * so a pass here means the real wake word would have fired on that utterance.
     *
     * Honest limit: this proves the *matcher*, not the always-on loop — it cannot tell
     * you the OEM battery manager won't kill the service in your pocket overnight. It
     * answers "does she recognise my voice saying this", which is the part that was broken.
     */
    fun testWake(onResult: (TestResult) -> Unit) {
        if (!detector.wakeArmed) {
            onResult(TestResult(false, Double.MAX_VALUE, detector.WAKE_SCORE_FIRE,
                "Only ${detector.templateCount}/$NEEDED voice samples — finish calibration, " +
                    "or she can never wake."))
            return
        }
        detector.recordWav(RECORD_MS) { wav ->
            if (wav == null || wav.size <= 44) {
                onResult(TestResult(false, Double.MAX_VALUE, detector.WAKE_SCORE_FIRE,
                    "Recording failed — check the microphone permission."))
                return@recordWav
            }
            val pcm = wavToPcm(wav)
            judge(pcm)?.let { (reason, hint) ->
                onResult(TestResult(false, Double.MAX_VALUE, detector.WAKE_SCORE_FIRE,
                    "$reason. $hint"))
                return@recordWav
            }
            // Score through the detector's OWN scorer, not a copy of it. The copy that
            // used to live here minimised over templates only; the live loop minimises
            // over 3 window scales x N templates, so it always scored lower on the same
            // audio. A pass here could coexist with a loop firing on the room, and this
            // test had no way to show it.
            val score = detector.scorePcm(MfccDtw.trimSilence(pcm))
            val threshold = detector.WAKE_SCORE_FIRE
            val passed = score < threshold
            onResult(
                TestResult(
                    passed, score, threshold,
                    if (passed) "She heard you. Match %.1f (fires under %.0f).".format(score, threshold)
                    else "Not close enough — %.1f, needs under %.0f. Re-calibrate, or say it the way you did when calibrating."
                        .format(score, threshold)
                )
            )
        }
    }

    /** Absolute quality gates. Returns null when the clip is good, else (reason, hint). */
    private fun judge(pcm: ShortArray): Pair<String, String>? {
        if (pcm.size < 8000) return "That was too short" to "Hold the button and say the whole phrase."

        var sumSq = 0.0
        var clipped = 0
        for (s in pcm) {
            val v = s.toDouble()
            sumSq += v * v
            if (v >= 32000 || v <= -32000) clipped++
        }
        val rms = sqrt(sumSq / pcm.size)

        if (rms < RMS_FLOOR)
            return "Too quiet — I could barely hear that" to
                "Speak up a little, or move somewhere less noisy."
        if (clipped.toDouble() / pcm.size > CLIP_RATIO)
            return "Too loud — that came out distorted" to
                "Hold the phone a bit further away and say it normally."

        val frames = MfccDtw.features(MfccDtw.trimSilence(pcm)).size
        if (frames < MIN_FRAMES)
            return "I didn't hear a full phrase" to
                "Say \"Baka Mizune\" right after the countdown."
        if (frames > MAX_FRAMES)
            return "That was longer than a wake phrase" to
                "Just \"Baka Mizune\" on its own — nothing after it."
        return null
    }

    /** Mean pairwise DTW distance across accepted samples — the tightness of the set. */
    private fun meanSpread(): Double {
        if (accepted.size < 2) return 0.0
        var total = 0.0
        var n = 0
        for (i in accepted.indices) for (j in i + 1 until accepted.size) {
            total += MfccDtw.dtw(accepted[i], accepted[j]); n++
        }
        return if (n == 0) 0.0 else total / n
    }

    private fun wavToPcm(wav: ByteArray): ShortArray {
        val pcm = ShortArray((wav.size - 44) / 2)
        ByteBuffer.wrap(wav, 44, pcm.size * 2).order(ByteOrder.LITTLE_ENDIAN)
            .asShortBuffer().get(pcm)
        return pcm
    }
}
