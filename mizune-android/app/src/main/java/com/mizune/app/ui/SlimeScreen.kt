package com.mizune.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import com.mizune.app.ChatMessage
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.gestures.awaitFirstDown

@Composable
fun SlimeScreen(
    emotion: SlimeEmotion,
    mizuneMessage: String,
    chatHistory: List<ChatMessage>,
    isThinking: Boolean,
    connectionStatus: String,
    isRecording: Boolean,
    onSendMessage: (String) -> Unit,
    onStartRecording: () -> Unit,
    onStopRecording: () -> Unit
) {
    var isSidebarOpen by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF1E1E2E)) // Dark space background
    ) {
        // 1. Slime Renderer taking full background
        SlimeRenderer(
            emotion = emotion,
            isRecording = isRecording,
            modifier = Modifier.fillMaxSize()
        )
        
        // 2. Sidebar Overlay
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
                    .blur(16.dp) // extra glassmorphism
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
                                Text(
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
        
        // Click outside sidebar to close
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

        // 3. UI Overlay
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
                .zIndex(0f),
            verticalArrangement = Arrangement.SpaceBetween,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Top Bar with Sidebar toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Start
            ) {
                IconButton(
                    onClick = { isSidebarOpen = true },
                    modifier = Modifier
                        .background(Color.White.copy(alpha = 0.1f), CircleShape)
                        .clip(CircleShape)
                ) {
                    Icon(Icons.Filled.Menu, contentDescription = "Menu", tint = Color.White)
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))

            // Chat Bubble (Glassmorphism)
            if (mizuneMessage.isNotBlank() || isThinking) {
                Box(
                    modifier = Modifier
                        .widthIn(max = 320.dp)
                        .clip(RoundedCornerShape(24.dp))
                        .background(Color.White.copy(alpha = 0.15f))
                        .blur(8.dp) // Blur for frosted glass
                )
                
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
            }

            Spacer(modifier = Modifier.weight(1f))

            Text(
                text = connectionStatus,
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.5f),
                modifier = Modifier.padding(bottom = 8.dp)
            )

            val buttonScale by animateFloatAsState(if (isRecording) 1.2f else 1.0f, label = "buttonScale")
            val buttonAlpha by animateFloatAsState(if (isRecording) 1.0f else 0.8f, label = "buttonAlpha")
            val buttonColor = if (isRecording) Color(0xFFFF5252) else Color(0xFF4FC3F7)

            Box(
                modifier = Modifier
                    .size(80.dp)
                    .scale(buttonScale)
                    .alpha(buttonAlpha)
                    .clip(CircleShape)
                    .background(buttonColor)
                    .pointerInput(Unit) {
                        awaitPointerEventScope {
                            while (true) {
                                val down =  awaitFirstDown()
                                onStartRecording()
                                
                                // Wait for up or cancellation
                                do {
                                    val event = awaitPointerEvent()
                                } while (event.changes.any { it.pressed })
                                
                                onStopRecording()
                            }
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.PlayArrow,
                    contentDescription = "Hold to Talk",
                    tint = Color.White,
                    modifier = Modifier.size(36.dp)
                )
            }
            
            Text(
                text = if (isRecording) "Listening..." else "Hold to Talk",
                style = MaterialTheme.typography.labelMedium,
                color = Color.White.copy(alpha = 0.8f),
                modifier = Modifier.padding(top = 16.dp, bottom = 16.dp)
            )
        }
    }
}
