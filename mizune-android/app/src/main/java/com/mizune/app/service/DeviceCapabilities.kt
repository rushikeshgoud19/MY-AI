package com.mizune.app.service

/**
 * THE CONTRACT. The one place that says what this phone can actually do.
 *
 * Written because the registry drifted from reality: the socket registered a hardcoded
 * four (notify/open_url/open_app/speak) while the executor in [MizuneService] handled
 * twelve, so `tap`, `type`, `press`, `scroll` and `read_screen` ran fine but were never
 * advertised — and the brain's tool description hardcoded its own third list. Three
 * places, three answers. Generating the registration from this table keeps the phone's
 * claim and the phone's behaviour in sync by construction.
 *
 * Rule: an action belongs here ONLY if [MizuneService.onDeviceCommand] has a real branch
 * for it, and it is reported available ONLY when its precondition currently holds.
 * Adding a name here without an executor branch re-creates the exact bug this fixes.
 */
object DeviceCapabilities {

    /** An action the phone exposes, plus the runtime condition that makes it real. */
    private data class Capability(
        val action: String,
        /** Null = always available; otherwise evaluated fresh at every registration. */
        val available: (() -> Boolean)? = null
    )

    private val ALL = listOf(
        // Always available — no special grant needed.
        Capability("notify"),
        Capability("speak"),
        // These degrade gracefully (accessibility → overlay → tappable notification),
        // so they are always offered; launchIntent() reports honestly which path ran.
        Capability("open_url"),
        Capability("open_app"),

        // Accessibility-gated. These vanish from the registry the moment Master turns
        // the service off, which is what makes the kill switch meaningful.
        Capability("tap") { MizuneAccessibilityService.isEnabled() },
        Capability("type") { MizuneAccessibilityService.isEnabled() },
        Capability("press") { MizuneAccessibilityService.isEnabled() },
        Capability("scroll") { MizuneAccessibilityService.isEnabled() },
        Capability("read_screen") { MizuneAccessibilityService.isEnabled() },

        // Media keys. HONEST BOUNDARY: the executor dispatches a media-key event and the
        // phone genuinely accepts it, but nothing reads the player's state back — so
        // "dispatched" is all this claims, NOT "audio is playing". Until a
        // MediaController seals before/after playback state, treat a success here as
        // "the key was delivered". Do not upgrade this comment without upgrading the code.
        Capability("media_play"),
        Capability("media_pause"),
        Capability("media_next")
    )

    /** The capability list to register right now, reflecting current runtime grants. */
    fun current(): List<String> =
        ALL.filter { it.available?.invoke() ?: true }.map { it.action }

    /** Every action the executor understands, grant or no grant — for diagnostics. */
    fun all(): List<String> = ALL.map { it.action }
}
