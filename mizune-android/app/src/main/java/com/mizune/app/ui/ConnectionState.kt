package com.mizune.app.ui

import androidx.compose.ui.graphics.Color

enum class ConnectionState(val label: String, val color: Color) {
    CONNECTED("Connected", Color(0xFF4CAF50)),
    CONNECTING("Connecting", Color(0xFFFFC107)),
    RECONNECTING("Reconnecting", Color(0xFFFF9800)),
    DISCONNECTED("Disconnected", Color(0xFFF44336))
}
