package com.mizune.app.widget

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.*
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.provideContent
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.appwidget.cornerRadius
import androidx.glance.layout.*
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import com.mizune.app.MainActivity
import com.mizune.app.data.AppPreferences
import com.mizune.app.ui.ConnectionState
import com.mizune.app.ui.SlimeEmotion
import kotlinx.coroutines.flow.first

class MizuneWidget : GlanceAppWidget() {

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val prefs = AppPreferences(context)
        val lastMessage = prefs.lastMessage.first()
        val connectionState = prefs.connectionState.first()
        val emotion = prefs.widgetEmotion.first()

        provideContent {
            WidgetContent(
                lastMessage = lastMessage,
                connectionState = connectionState,
                emotion = emotion
            )
        }
    }
}

class MizuneWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = MizuneWidget()
}

@Composable
private fun WidgetContent(
    lastMessage: String,
    connectionState: ConnectionState,
    emotion: SlimeEmotion
) {
    Box(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(Color(0xFF1E1E2E)))
            .padding(16.dp)
            .clickable(actionStartActivity(android.content.Intent().apply { component = android.content.ComponentName("com.mizune.app", "com.mizune.app.MainActivity") }))
    ) {
        Column(
            modifier = GlanceModifier.fillMaxSize(),
            verticalAlignment = Alignment.Vertical.CenterVertically
        ) {
            Row(
                modifier = GlanceModifier.fillMaxWidth(),
                horizontalAlignment = Alignment.Horizontal.Start,
                verticalAlignment = Alignment.Vertical.CenterVertically
            ) {
                Text(
                    text = emotionToEmoji(emotion),
                    style = TextStyle(fontSize = 24.sp)
                )
                Spacer(GlanceModifier.width(8.dp))
                Box(
                    modifier = GlanceModifier
                        .size(10.dp)
                        .background(ColorProvider(connectionState.color))
                        .cornerRadius(5.dp)
                ) {}
                Spacer(GlanceModifier.width(6.dp))
                Text(
                    text = connectionState.label,
                    style = TextStyle(
                        color = ColorProvider(connectionState.color),
                        fontSize = 12.sp
                    )
                )
            }

            Spacer(GlanceModifier.height(8.dp))

            Text(
                text = lastMessage.ifBlank { "Mizune is waiting, Master~" },
                style = TextStyle(
                    color = ColorProvider(Color(0xFFFFFFFF)),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                ),
                maxLines = 2
            )

            Spacer(GlanceModifier.height(12.dp))

            Text(
                text = "Tap to chat",
                style = TextStyle(
                    color = ColorProvider(Color(0xFF4FC3F7)),
                    fontSize = 12.sp
                )
            )
        }
    }
}

private fun emotionToEmoji(emotion: SlimeEmotion): String {
    return when (emotion) {
        SlimeEmotion.HAPPY -> "😊"
        SlimeEmotion.EXCITED -> "🤩"
        SlimeEmotion.ANGRY -> "😠"
        SlimeEmotion.SAD -> "😢"
        SlimeEmotion.PATTED -> "😳"
        SlimeEmotion.PLAYFUL -> "😜"
        SlimeEmotion.THINKING -> "🤔"
        SlimeEmotion.SPEAKING -> "🗣️"
        SlimeEmotion.CALM -> "🙂"
    }
}
