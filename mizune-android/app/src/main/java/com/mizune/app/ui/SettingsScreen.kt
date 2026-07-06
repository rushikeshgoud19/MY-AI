package com.mizune.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.mizune.app.data.AppPreferences
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    connectionState: ConnectionState,
    appPreferences: AppPreferences,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var serverUrl by remember { mutableStateOf(AppPreferences.DEFAULT_SERVER_URL) }
    var theme by remember { mutableStateOf(AppPreferences.DEFAULT_THEME) }
    var notificationsEnabled by remember { mutableStateOf(true) }
    var voiceId by remember { mutableStateOf(AppPreferences.DEFAULT_VOICE_ID) }

    // Load current preferences once
    LaunchedEffect(Unit) {
        appPreferences.serverUrl.collect { serverUrl = it }
    }
    LaunchedEffect(Unit) {
        appPreferences.theme.collect { theme = it }
    }
    LaunchedEffect(Unit) {
        appPreferences.notificationsEnabled.collect { notificationsEnabled = it }
    }
    LaunchedEffect(Unit) {
        appPreferences.voiceId.collect { voiceId = it }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings", color = Color.White) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFF1E1E2E))
            )
        },
        containerColor = Color(0xFF1E1E2E)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            // Server URL
            SettingsCard(title = "Server") {
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it },
                    label = { Text("Server URL") },
                    placeholder = { Text("mizune.centralindia.cloudapp.azure.com") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = Color(0xFF4FC3F7),
                        unfocusedBorderColor = Color.White.copy(alpha = 0.3f),
                        focusedLabelColor = Color(0xFF4FC3F7),
                        unfocusedLabelColor = Color.White.copy(alpha = 0.7f)
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(12.dp)
                                .clip(CircleShape)
                                .background(connectionState.color)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = connectionState.label,
                            color = Color.White,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }

                    Button(
                        onClick = {
                            scope.launch {
                                appPreferences.setServerUrl(serverUrl)
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4FC3F7))
                    ) {
                        Text("Save", color = Color.Black)
                    }
                }
            }

            // Voice
            SettingsCard(title = "Voice") {
                val voices = listOf(
                    "en-US-AriaNeural" to "Aria (US)",
                    "en-US-GuyNeural" to "Guy (US)",
                    "en-GB-SoniaNeural" to "Sonia (UK)",
                    "en-IN-NeerjaNeural" to "Neerja (IN)",
                    "ja-JP-NanamiNeural" to "Nanami (JP)"
                )

                Text(
                    text = "TTS Voice",
                    color = Color.White.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(8.dp))

                voices.forEach { (id, label) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                scope.launch {
                                    appPreferences.setVoiceId(id)
                                }
                            }
                            .padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = voiceId == id,
                            onClick = {
                                scope.launch {
                                    appPreferences.setVoiceId(id)
                                }
                            },
                            colors = RadioButtonDefaults.colors(selectedColor = Color(0xFF4FC3F7))
                        )
                        Text(text = label, color = Color.White)
                    }
                }
            }

            // Theme
            SettingsCard(title = "Appearance") {
                val themes = listOf("dark" to "Dark", "amoled" to "AMOLED Black")
                Text(
                    text = "Theme",
                    color = Color.White.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(8.dp))

                themes.forEach { (id, label) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                scope.launch {
                                    appPreferences.setTheme(id)
                                }
                            }
                            .padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = theme == id,
                            onClick = {
                                scope.launch {
                                    appPreferences.setTheme(id)
                                }
                            },
                            colors = RadioButtonDefaults.colors(selectedColor = Color(0xFF4FC3F7))
                        )
                        Text(text = label, color = Color.White)
                    }
                }
            }

            // Notifications
            SettingsCard(title = "Notifications") {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Enable notifications",
                        color = Color.White,
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Switch(
                        checked = notificationsEnabled,
                        onCheckedChange = {
                            scope.launch {
                                appPreferences.setNotificationsEnabled(it)
                            }
                        },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color(0xFF4FC3F7),
                            checkedTrackColor = Color(0xFF4FC3F7).copy(alpha = 0.5f)
                        )
                    )
                }
            }

            // About
            SettingsCard(title = "About") {
                Text(
                    text = "Mizune AI Companion",
                    color = Color.White,
                    style = MaterialTheme.typography.bodyLarge
                )
                Text(
                    text = "Version 1.0.0",
                    color = Color.White.copy(alpha = 0.6f),
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = Color(0xFF282A36).copy(alpha = 0.8f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = title,
                color = Color(0xFF4FC3F7),
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(12.dp))
            content()
        }
    }
}
