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
    }

    // We don't react to events; we act on command from the WebSocket handler.
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    override fun onDestroy() {
        if (instance == this) instance = null
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

    /** Tap the first clickable element whose text/description contains [text]. */
    fun tapByText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val query = text.trim()
        val matches = root.findAccessibilityNodeInfosByText(query) ?: emptyList()
        for (node in matches) {
            var target: AccessibilityNodeInfo? = node
            while (target != null && !target.isClickable) target = target.parent
            if (target?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true) return true
        }
        return false
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
    }
}
