package com.mizune.app.service

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Gives Mizune real hands on the phone. An AccessibilityService is exempt from the
 * background Activity-launch restrictions that silently block a normal foreground
 * service on OEM ROMs (OnePlus/OxygenOS, MIUI, ColorOS...), and can also tap, type
 * and scroll inside any app — the basis for launching apps, playing media, and
 * filling forms reliably.
 *
 * The user must enable it once: Settings → Accessibility → Mizune → On.
 */
class MizuneAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        instance = this
        Log.d(TAG, "Mizune accessibility service connected")
        onStateChanged?.invoke()
    }

    // We don't react to events; we act on command from the WebSocket handler.
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    override fun onDestroy() {
        if (instance == this) instance = null
        // Tell the registry the hands are gone BEFORE the process forgets, so the
        // capability disappears instead of lingering as a claim the phone can't honour.
        onStateChanged?.invoke()
        super.onDestroy()
    }

    /** Launch any app/URL intent — exempt from background-launch blocking. */
    fun launch(intent: Intent): Boolean = try {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        true
    } catch (e: Exception) {
        Log.e(TAG, "launch failed", e); false
    }

    /** Tap the BEST element whose text OR content-description matches [text].
     *  The old first-match walk grabbed whatever contained the word first in the tree
     *  ("Google Play", "Playlist", "Play next"...) — on YT Music that meant tapping the
     *  wrong thing and music never started. Now every match is scored: exact label wins
     *  outright, then clickable nodes, then the shortest label (most button-like).
     *  Falls back to a coordinate gesture-tap when the node reports non-clickable. */
    fun tapByText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val query = text.trim().lowercase()
        val matches = mutableListOf<AccessibilityNodeInfo>()
        collectMatches(root, query, matches)
        val candidate = matches.minByOrNull { node ->
            val t = node.text?.toString()?.trim()?.lowercase() ?: ""
            val d = node.contentDescription?.toString()?.trim()?.lowercase() ?: ""
            val label = if (t.contains(query)) t else d
            var score = label.length              // shorter label = more button-like
            if (label == query) score -= 10_000   // exact match ("play") wins outright
            if (node.isClickable) score -= 1_000
            score
        } ?: return false
        // 1. Try a real click on the node or its nearest clickable ancestor.
        var target: AccessibilityNodeInfo? = candidate
        while (target != null && !target.isClickable) target = target.parent
        if (target?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true) return true
        // 2. Fallback: tap the centre of the matched node's bounds.
        return tapNodeCenter(candidate)
    }

    private fun collectMatches(node: AccessibilityNodeInfo?, query: String, out: MutableList<AccessibilityNodeInfo>) {
        if (node == null) return
        val t = node.text?.toString()?.trim()?.lowercase()
        val d = node.contentDescription?.toString()?.trim()?.lowercase()
        if ((t != null && t.contains(query)) || (d != null && d.contains(query))) out.add(node)
        for (i in 0 until node.childCount) collectMatches(node.getChild(i), query, out)
    }

    private fun tapNodeCenter(node: AccessibilityNodeInfo): Boolean {
        val rect = android.graphics.Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() <= 0 || rect.height() <= 0) return false
        return tapXY(rect.exactCenterX(), rect.exactCenterY())
    }

    /** Dispatch a raw tap at screen coordinates — the last-resort, works on anything. */
    fun tapXY(x: Float, y: Float): Boolean {
        val path = android.graphics.Path().apply { moveTo(x, y) }
        val gesture = android.accessibilityservice.GestureDescription.Builder()
            .addStroke(android.accessibilityservice.GestureDescription.StrokeDescription(path, 0, 60))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    /** Type into the currently focused editable field (e.g. a form field). */
    fun typeText(text: String): Boolean {
        val node = findFocusedEditable(rootInActiveWindow) ?: return false
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun findFocusedEditable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.isEditable && node.isFocused) return node
        for (i in 0 until node.childCount) {
            findFocusedEditable(node.getChild(i))?.let { return it }
        }
        return null
    }

    /**
     * Read the current screen as a compact list of interactable elements so the brain
     * can decide the next tap. This is Mizune's "eyes" — turns blind tapping into
     * sighted operation for multi-step tasks.
     */
    fun dumpScreen(): String {
        val root = rootInActiveWindow ?: return "(screen is empty or not readable)"
        val lines = mutableListOf<String>()
        val pkg = root.packageName?.toString() ?: "?"
        lines.add("app: $pkg")
        collect(root, lines, 0)
        val body = lines.take(60).joinToString("\n")   // cap so it never bloats the prompt
        return body
    }

    private fun collect(node: AccessibilityNodeInfo?, out: MutableList<String>, depth: Int) {
        if (node == null || depth > 25) return
        val text = node.text?.toString()?.trim()
        val desc = node.contentDescription?.toString()?.trim()
        val label = when {
            !text.isNullOrEmpty() -> text
            !desc.isNullOrEmpty() -> desc
            else -> null
        }
        if (label != null && label.length in 1..80) {
            val kind = when {
                node.isEditable -> "field"
                node.isClickable -> "button"
                else -> "text"
            }
            out.add("[$kind] $label")
        }
        for (i in 0 until node.childCount) collect(node.getChild(i), out, depth + 1)
    }

    /** Global navigation: back / home / recents / notifications. */
    fun press(action: String): Boolean {
        val code = when (action.trim().lowercase()) {
            "back" -> GLOBAL_ACTION_BACK
            "home" -> GLOBAL_ACTION_HOME
            "recents" -> GLOBAL_ACTION_RECENTS
            "notifications" -> GLOBAL_ACTION_NOTIFICATIONS
            else -> return false
        }
        return performGlobalAction(code)
    }

    /** Scroll the first scrollable container forward/backward. */
    fun scroll(direction: String): Boolean {
        val node = findScrollable(rootInActiveWindow) ?: return false
        val action = if (direction.trim().lowercase() == "up")
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        else AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        return node.performAction(action)
    }

    private fun findScrollable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.isScrollable) return node
        for (i in 0 until node.childCount) {
            findScrollable(node.getChild(i))?.let { return it }
        }
        return null
    }

    companion object {
        private const val TAG = "MizuneA11y"
        @Volatile
        var instance: MizuneAccessibilityService? = null
        fun isEnabled(): Boolean = instance != null

        /** Set by [MizuneService] to re-register capabilities when this grant flips.
         *  Held as a lambda rather than a service reference so it can't leak the Service. */
        @Volatile
        var onStateChanged: (() -> Unit)? = null
    }
}
