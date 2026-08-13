package com.mizune.app.audio

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.sqrt

/**
 * Tiny on-device DSP: MFCC features + DTW distance, for acoustic wake-word
 * template matching ("Baka Mizune" enrollment samples vs the live mic ring).
 *
 * Lab-validated (scratchpad acoustic_lab.py): same-speaker wake utterances score
 * 8-13, other phrases / other speakers 22+, so a threshold around 16 separates
 * cleanly. Both templates and probes run through THIS code, so absolute parity
 * with python_speech_features doesn't matter — internal consistency does.
 *
 * Frames: 25ms window / 10ms hop @ 16kHz, preemphasis 0.97, Hamming, 512-FFT,
 * 26 mel filters (0-8kHz), DCT-II -> 13 coeffs, c0 dropped, CMN per utterance.
 */
object MfccDtw {

    private const val SAMPLE_RATE = 16000
    private const val FRAME = 400      // 25ms
    private const val HOP = 160        // 10ms
    private const val NFFT = 512
    private const val NFILT = 26
    private const val NCEP = 13

    private val hamming = DoubleArray(FRAME) { 0.54 - 0.46 * cos(2 * PI * it / (FRAME - 1)) }
    private val melBank = buildMelBank()
    private val dctTable = Array(NCEP) { k ->
        DoubleArray(NFILT) { n -> cos(PI * k * (n + 0.5) / NFILT) }
    }

    // ── public API ──────────────────────────────────────────────────────────────

    /** MFCC feature matrix (frames x 12), c0 dropped, cepstral-mean-normalized. */
    fun features(pcm: ShortArray): Array<DoubleArray> {
        if (pcm.size < FRAME) return emptyArray()
        // Preemphasis
        val x = DoubleArray(pcm.size)
        x[0] = pcm[0].toDouble()
        for (i in 1 until pcm.size) x[i] = pcm[i] - 0.97 * pcm[i - 1]

        val nFrames = (pcm.size - FRAME) / HOP + 1
        val feats = Array(nFrames) { DoubleArray(NCEP - 1) }
        val re = DoubleArray(NFFT); val im = DoubleArray(NFFT)
        val power = DoubleArray(NFFT / 2 + 1)
        val logMel = DoubleArray(NFILT)

        for (f in 0 until nFrames) {
            java.util.Arrays.fill(re, 0.0); java.util.Arrays.fill(im, 0.0)
            val off = f * HOP
            for (i in 0 until FRAME) re[i] = x[off + i] * hamming[i]
            fft(re, im)
            for (i in power.indices) power[i] = (re[i] * re[i] + im[i] * im[i]) / NFFT
            for (m in 0 until NFILT) {
                var s = 0.0
                val bank = melBank[m]
                for (i in bank.indices) s += power[i] * bank[i]
                logMel[m] = ln(if (s < 1e-10) 1e-10 else s)
            }
            for (k in 1 until NCEP) {           // drop c0 (k=0)
                var s = 0.0
                val row = dctTable[k]
                for (n in 0 until NFILT) s += logMel[n] * row[n]
                feats[f][k - 1] = s * sqrt(2.0 / NFILT)
            }
        }
        cmn(feats)
        return feats
    }

    /** In-place cepstral mean normalization. */
    fun cmn(feats: Array<DoubleArray>) {
        if (feats.isEmpty()) return
        val dim = feats[0].size
        val mean = DoubleArray(dim)
        for (row in feats) for (d in 0 until dim) mean[d] += row[d]
        // Explicit get/set rather than `/=`: a stray space in `mean [d] /= ...` broke
        // the indexed-assignment resolution ("No set method providing array access").
        val nFrames = feats.size.toDouble()
        for (d in 0 until dim) mean[d] = mean[d] / nFrames
        for (row in feats) for (d in 0 until dim) row[d] -= mean[d]
    }

    /** Path-length-normalized DTW distance between two feature matrices. */
    fun dtw(a: Array<DoubleArray>, b: Array<DoubleArray>): Double {
        val n = a.size; val m = b.size
        if (n == 0 || m == 0) return Double.MAX_VALUE
        val prev = DoubleArray(m + 1) { Double.MAX_VALUE }
        val cur = DoubleArray(m + 1)
        prev[0] = 0.0
        for (i in 1..n) {
            cur[0] = Double.MAX_VALUE
            val ai = a[i - 1]
            for (j in 1..m) {
                var d = 0.0
                val bj = b[j - 1]
                for (k in ai.indices) { val diff = ai[k] - bj[k]; d += diff * diff }
                d = sqrt(d)
                cur[j] = d + minOf(prev[j], cur[j - 1], prev[j - 1])
            }
            System.arraycopy(cur, 0, prev, 0, m + 1)
        }
        return prev[m] / (n + m)
    }

    /** Energy-based trim of leading/trailing silence (10ms frames). */
    fun trimSilence(pcm: ShortArray, threshRatio: Double = 0.06): ShortArray {
        val nFrames = pcm.size / HOP
        if (nFrames == 0) return pcm
        val energy = DoubleArray(nFrames)
        var maxE = 0.0
        for (f in 0 until nFrames) {
            var s = 0.0
            for (i in 0 until HOP) { val v = pcm[f * HOP + i].toDouble(); s += v * v }
            energy[f] = sqrt(s / HOP)
            if (energy[f] > maxE) maxE = energy[f]
        }
        val thresh = maxOf(maxE * threshRatio, 1.0)
        var first = -1; var last = -1
        for (f in 0 until nFrames) if (energy[f] > thresh) { if (first < 0) first = f; last = f }
        if (first < 0) return pcm
        return pcm.copyOfRange(first * HOP, minOf((last + 1) * HOP, pcm.size))
    }

    // ── internals ───────────────────────────────────────────────────────────────

    /** Iterative radix-2 FFT, in place on [re]/[im] (length must be power of 2). */
    private fun fft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        var j = 0
        for (i in 0 until n - 1) {
            if (i < j) {
                var t = re[i]; re[i] = re[j]; re[j] = t
                t = im[i]; im[i] = im[j]; im[j] = t
            }
            var k = n / 2
            while (k <= j) { j -= k; k /= 2 }
            j += k
        }
        var len = 2
        while (len <= n) {
            val ang = -2 * PI / len
            val wr = cos(ang); val wi = kotlin.math.sin(ang)
            var i = 0
            while (i < n) {
                var curWr = 1.0; var curWi = 0.0
                for (k2 in 0 until len / 2) {
                    val ur = re[i + k2]; val ui = im[i + k2]
                    val vr = re[i + k2 + len / 2] * curWr - im[i + k2 + len / 2] * curWi
                    val vi = re[i + k2 + len / 2] * curWi + im[i + k2 + len / 2] * curWr
                    re[i + k2] = ur + vr; im[i + k2] = ui + vi
                    re[i + k2 + len / 2] = ur - vr; im[i + k2 + len / 2] = ui - vi
                    val nWr = curWr * wr - curWi * wi
                    curWi = curWr * wi + curWi * wr
                    curWr = nWr
                }
                i += len
            }
            len *= 2
        }
    }

    private fun mel(f: Double) = 2595.0 * kotlin.math.log10(1.0 + f / 700.0)
    private fun imel(m: Double) = 700.0 * (Math.pow(10.0, m / 2595.0) - 1.0)

    private fun buildMelBank(): Array<DoubleArray> {
        val lowMel = mel(0.0); val highMel = mel(SAMPLE_RATE / 2.0)
        val points = DoubleArray(NFILT + 2) { lowMel + (highMel - lowMel) * it / (NFILT + 1) }
        val bins = IntArray(NFILT + 2) { ((NFFT + 1) * imel(points[it]) / SAMPLE_RATE).toInt() }
        return Array(NFILT) { m ->
            val bank = DoubleArray(NFFT / 2 + 1)
            for (i in bins[m] until bins[m + 1]) {
                if (i in bank.indices && bins[m + 1] != bins[m])
                    bank[i] = (i - bins[m]).toDouble() / (bins[m + 1] - bins[m])
            }
            for (i in bins[m + 1] until bins[m + 2]) {
                if (i in bank.indices && bins[m + 2] != bins[m + 1])
                    bank[i] = (bins[m + 2] - i).toDouble() / (bins[m + 2] - bins[m + 1])
            }
            bank
        }
    }
}
