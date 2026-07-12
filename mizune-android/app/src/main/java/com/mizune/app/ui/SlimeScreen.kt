package com.mizune.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.camera.core.ImageCapture
import com.mizune.app.ChatMessage
import com.mizune.app.network.TaskItem
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay

@Composable
fun SlimeScreen(
    emotion: SlimeEmotion,
    mizuneMessage: String,
    chatHistory: List<ChatMessage>,
    isThinking: Boolean,
    connectionState: ConnectionState,
    isRecording: Boolean,
    recordingAmplitude: Int = 0,
    tasks: List<TaskItem> = emptyList(),
    shortcutAction: String? = null,
    onShortcutHandled: () -> Unit = {},
    onSendMessage: (String) -> Unit,
    onStartRecording: () -> Unit,
    onStopRecording: () -> Unit,
    onCancelRecording: () -> Unit,
    onCaptureVision: (String) -> Unit,
    onOpenSettings: () -> Unit = {}
) {
    var isSidebarOpen by remember { mutableStateOf(false) }
    var isVisionMode by remember { mutableStateOf(false) }
    var inputText by remember { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }
    val imageCapture = remember { ImageCapture.Builder().build() }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    LaunchedEffect(shortcutAction) {
        when (shortcutAction) {
            "vision_mode" -> {
                isVisionMode = true
                onShortcutHandled()
            }
            "quick_note" -> {
                focusRequester.requestFocus()
                onShortcutHandled()
            }
            "voice_chat" -> {
                delay(500)
                onStartRecording()
                onShortcutHandled()
            }
        }
    }

    if (!isVisionMode) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF1E1E2E))
        ) {
            SlimeRenderer(
                emotion = emotion,
                isRecording = isRecording,
                modifier = Modifier.fillMaxSize()
            )

            AnimatedVisibility(
                visible = isSidebarOpen,
                enter = slideInHorizontally(initialOffsetX = { -it }) + fadeIn(),
                exit = slideOutHorizontally(targetOffsetX = { -it }) + fadeOut(),
                modifier = Modifier.zIndex(2f)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .width(300.dp)
                        .background(Color(0xFF282A36).copy(alpha = 0.85f))
                        .blur(16.dp)
                )

                Column(
                    modifier = Modifier
                        .fillMaxHeight()
                        .width(300.dp)
                        .padding(16.dp)
                        .zIndex(3f)
                ) {
                    Text("Chat History", style = MaterialTheme.typography.titleLarge, color = Color.White)
                    Spacer(modifier = Modifier.height(16.dp))

                    LazyColumn(modifier = Modifier.fillMaxSize()) {
                        items(chatHistory) { msg ->
                            Box(
                                modifier = Modifier.fillMaxWidth(),
                                contentAlignment = if (msg.isUser) Alignment.CenterEnd else Alignment.CenterStart
                            ) {
                                Card(
                                    modifier = Modifier
                                        .padding(vertical = 4.dp)
                                        .widthIn(max = 240.dp),
                                    shape = RoundedCornerShape(16.dp),
                                    colors = CardDefaults.cardColors(
                                        containerColor = if (msg.isUser) Color(0xFF42A5F5).copy(alpha = 0.8f) else Color.White.copy(alpha = 0.15f)
                                    )
                                ) {
                                    if (msg.isUser) {
                                        Text(
                                            text = msg.text,
                                            modifier = Modifier.padding(12.dp),
                                            color = Color.White,
                                            style = MaterialTheme.typography.bodyMedium
                                        )
                                    } else {
                                        MarkdownText(
                                            text = msg.text,
                                            modifier = Modifier.padding(12.dp),
                                            color = Color.White,
                                            style = MaterialTheme.typography.bodyMedium
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if (isSidebarOpen) {
                Box(modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.3f))
                    .pointerInput(Unit) {
                        detectTapGestures(onTap = { isSidebarOpen = false })
                    }
                    .zIndex(1f)
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp)
                    .zIndex(0f),
                verticalArrangement = Arrangement.SpaceBetween,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = { isSidebarOpen = true },
                        modifier = Modifier
                            .background(Color.White.copy(alpha = 0.1f), CircleShape)
                            .clip(CircleShape)
                    ) {
                        Icon(Icons.Filled.Menu, contentDescription = "Menu", tint = Color.White)
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        IconButton(
                            onClick = { isVisionMode = true },
                            modifier = Modifier
                                .background(Color.White.copy(alpha = 0.1f), CircleShape)
                                .clip(CircleShape)
                        ) {
                            Icon(Icons.Filled.CameraAlt, contentDescription = "Vision Mode", tint = Color.White)
                        }

                        IconButton(
                            onClick = onOpenSettings,
                            modifier = Modifier
                                .background(Color.White.copy(alpha = 0.1f), CircleShape)
                                .clip(CircleShape)
                        ) {
                            Icon(Icons.Filled.Settings, contentDescription = "Settings", tint = Color.White)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Chat Bubble / Typing indicator
                AnimatedVisibility(visible = mizuneMessage.isNotBlank() || isThinking) {
                    Card(
                        modifier = Modifier
                            .widthIn(max = 320.dp)
                            .padding(bottom = 16.dp),
                        shape = RoundedCornerShape(24.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF282A36).copy(alpha = 0.8f))
                    ) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            if (isThinking && mizuneMessage.isBlank()) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = "Thinking",
                                        style = MaterialTheme.typography.bodyLarge,
                                        color = Color.White
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    TypingIndicator()
                                }
                            } else {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = emotionToEmoji(emotion),
                                        style = MaterialTheme.typography.bodyLarge
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    MarkdownText(
                                        text = if (isThinking) "Thinking..." else mizuneMessage,
                                        color = Color.White,
                                        style = MaterialTheme.typography.bodyLarge
                                    )
                                }
                            }
                        }
                    }
                }

                // Task progress cards
                AnimatedVisibility(visible = tasks.isNotEmpty()) {
                    TaskListCard(tasks = tasks)
                }

                Spacer(modifier = Modifier.weight(1f))

                Row(
                    modifier = Modifier.padding(bottom = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(connectionState.color)
                    )
                    Text(
                        text = connectionState.label,
                        style = MaterialTheme.typography.labelSmall,
                        color = connectionState.color
                    )
                }

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = { Text("Message Mizune...", color = Color.White.copy(alpha = 0.5f)) },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = Color(0xFF282A36).copy(alpha = 0.8f),
                            unfocusedContainerColor = Color(0xFF282A36).copy(alpha = 0.8f),
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF4FC3F7),
                            unfocusedBorderColor = Color.White.copy(alpha = 0.3f)
                        ),
                        modifier = Modifier
                            .weight(1f)
                            .focusRequester(focusRequester)
                    )

                    Crossfade(targetState = inputText.isBlank(), label = "inputAction") { isBlank ->
                        if (isBlank) {
                            val buttonScale by animateFloatAsState(if (isRecording) 1.2f else 1.0f, label = "buttonScale")
                            val buttonAlpha by animateFloatAsState(if (isRecording) 1.0f else 0.8f, label = "buttonAlpha")
                            val buttonColor = if (isRecording) Color(0xFFFF5252) else Color(0xFF4FC3F7)

                            Box(
                                modifier = Modifier
                                    .size(56.dp)
                                    .scale(buttonScale)
                                    .alpha(buttonAlpha)
                                    .clip(CircleShape)
                                    .background(buttonColor)
                                    .pointerInput(Unit) {
                                        detectTapGestures(
                                            onPress = {
                                                val startJob = scope.launch {
                                                    kotlinx.coroutines.delay(300)
                                                    onStartRecording()
                                                }

                                                val released = tryAwaitRelease()

                                                if (released) {
                                                    if (startJob.isActive) {
                                                        startJob.cancel()
                                                    } else {
                                                        onStopRecording()
                                                    }
                                                } else {
                                                    startJob.cancel()
                                                    onCancelRecording()
                                                }
                                            }
                                        )
                                    },
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.PlayArrow,
                                    contentDescription = "Hold to Talk",
                                    tint = Color.White,
                                    modifier = Modifier.size(28.dp)
                                )
                            }

                            if (isRecording) {
                                Spacer(modifier = Modifier.width(8.dp))
                                WaveformBars(amplitude = recordingAmplitude)
                            }
                        } else {
                            IconButton(
                                onClick = {
                                    if (inputText.isNotBlank()) {
                                        onSendMessage(inputText)
                                        inputText = ""
                                    }
                                },
                                modifier = Modifier
                                    .size(56.dp)
                                    .background(Color(0xFF4FC3F7), CircleShape)
                                    .clip(CircleShape)
                            ) {
                                Icon(Icons.Filled.Send, contentDescription = "Send", tint = Color.White)
                            }
                        }
                    }
                }
            }
        }
    } else {
        VisionModeScreen(
            imageCapture = imageCapture,
            mizuneMessage = mizuneMessage,
            isThinking = isThinking,
            onBack = { isVisionMode = false },
            onCapture = { b64 ->
                onCaptureVision(b64)
            }
        )
    }
}

@Composable
private fun WaveformBars(amplitude: Int) {
    val normalized = (amplitude / 32767f).coerceIn(0f, 1f)
    val barCount = 5
    val infiniteTransition = rememberInfiniteTransition(label = "waveform")

    Row(
        horizontalArrangement = Arrangement.spacedBy(3.dp),
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.height(24.dp)
    ) {
        repeat(barCount) { index ->
            val phaseOffset = index * 0.4f
            val animatedScale by infiniteTransition.animateFloat(
                initialValue = 0.2f,
                targetValue = 0.2f + (normalized * 0.8f),
                animationSpec = infiniteRepeatable(
                    animation = tween(400, easing = FastOutSlowInEasing),
                    repeatMode = RepeatMode.Reverse
                ),
                label = "bar$index"
            )

            val height = (8 + (16 * (animatedScale + phaseOffset).coerceIn(0f, 1f))).dp
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .height(height)
                    .clip(RoundedCornerShape(2.dp))
                    .background(Color.White.copy(alpha = 0.8f))
            )
        }
    }
}

@Composable
private fun VisionModeScreen(
    imageCapture: ImageCapture,
    mizuneMessage: String,
    isThinking: Boolean,
    onBack: () -> Unit,
    onCapture: (String) -> Unit
) {
    val context = LocalContext.current

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        CameraPreview(
            imageCapture = imageCapture,
            modifier = Modifier.fillMaxSize()
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
                .zIndex(1f),
            verticalArrangement = Arrangement.SpaceBetween,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Start
            ) {
                IconButton(
                    onClick = onBack,
                    modifier = Modifier
                        .background(Color.White.copy(alpha = 0.1f), CircleShape)
                        .clip(CircleShape)
                ) {
                    Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                }
            }

            if (mizuneMessage.isNotBlank() || isThinking) {
                Card(
                    modifier = Modifier
                        .widthIn(max = 320.dp)
                        .padding(bottom = 16.dp),
                    shape = RoundedCornerShape(24.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF282A36).copy(alpha = 0.8f))
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text(
                            text = if (isThinking) "Thinking..." else mizuneMessage,
                            style = MaterialTheme.typography.bodyLarge,
                            color = Color.White
                        )
                    }
                }
            } else {
                Spacer(modifier = Modifier.height(16.dp))
            }

            Spacer(modifier = Modifier.weight(1f))

            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.8f))
                    .pointerInput(Unit) {
                        detectTapGestures(onTap = {
                            captureImageAsBase64(context, imageCapture,
                                onSuccess = { b64 -> onCapture(b64) },
                                onError = { _ -> android.widget.Toast.makeText(context, "Capture failed", android.widget.Toast.LENGTH_SHORT).show() }
                            )
                        })
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.CameraAlt,
                    contentDescription = "Take Photo",
                    tint = Color.Black,
                    modifier = Modifier.size(36.dp)
                )
            }

            Text(
                text = "Show Mizune",
                style = MaterialTheme.typography.labelMedium,
                color = Color.White,
                modifier = Modifier.padding(top = 16.dp, bottom = 16.dp)
            )
        }
    }
}

@Composable
private fun TypingIndicator() {
    val infiniteTransition = rememberInfiniteTransition(label = "typing")
    val delays = listOf(0, 150, 300)

    Row(
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        delays.forEach { delay ->
            val alpha by infiniteTransition.animateFloat(
                initialValue = 0.2f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(600, delayMillis = delay, easing = FastOutSlowInEasing),
                    repeatMode = RepeatMode.Reverse
                ),
                label = "dot$delay"
            )

            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = alpha))
            )
        }
    }
}

@Composable
private fun TaskListCard(tasks: List<TaskItem>) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 12.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF282A36).copy(alpha = 0.9f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Tasks",
                style = MaterialTheme.typography.titleSmall,
                color = Color(0xFF4FC3F7)
            )
            Spacer(modifier = Modifier.height(8.dp))
            tasks.take(5).forEach { task ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val statusColor = when (task.status.lowercase()) {
                        "completed" -> Color(0xFF4CAF50)
                        "running" -> Color(0xFFFFC107)
                        "failed" -> Color(0xFFF44336)
                        else -> Color.White.copy(alpha = 0.4f)
                    }

                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(statusColor)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = task.description,
                        color = Color.White,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
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
