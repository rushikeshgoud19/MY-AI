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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.mizune.app.data.AppPreferences
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    connectionState: ConnectionState,
    appPreferences: AppPreferences,
    onBack: () -> Unit,
    onCalibrateVoice: ((String) -> Unit) -> Unit = { it("Service not connected") },
    onVoiceStatus: ((String) -> Unit) -> Unit = { it("Service not connected") },
    onResetVoice: ((String) -> Unit) -> Unit = { it("Service not connected") },
    onTestWakeWord: ((Boolean, String) -> Unit) -> Unit = { it(false, "Service not connected") },
    onWakeDiagnostics: () -> List<Pair<String, Boolean>> = { emptyList() }
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var serverUrl by remember { mutableStateOf(AppPreferences.DEFAULT_SERVER_URL) }
    var apiKey by remember { mutableStateOf("") }
    var theme by remember { mutableStateOf(AppPreferences.DEFAULT_THEME) }
    var notificationsEnabled by remember { mutableStateOf(true) }
    var voiceId by remember { mutableStateOf(AppPreferences.DEFAULT_VOICE_ID) }

    // Load current preferences once
    LaunchedEffect(Unit) {
        appPreferences.serverUrl.collect { serverUrl = it }
    }
    LaunchedEffect(Unit) {
        appPreferences.apiKey.collect { apiKey = it }
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

                // Sent on the socket as ?key=. Set this BEFORE turning on
                // ws_auth_required server-side, or the phone gets locked out.
                OutlinedTextField(
                    value = apiKey,
                    onValueChange = { apiKey = it },
                    label = { Text("API key (optional)") },
                    placeholder = { Text("dashboard_api_key from config.json") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done
                    ),
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
                                appPreferences.setApiKey(apiKey)
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4FC3F7))
                    ) {
                        Text("Save", color = Color.Black)
                    }
                }
            }

            // Wake-word self-test. Exists because the failure was INVISIBLE: the engine
            // fell back silently and nothing on screen ever said so. Facts, then a live
            // try that scores against the real firing threshold.
            SettingsCard(title = "Wake word — does it work?") {
                var checks by remember { mutableStateOf(onWakeDiagnostics()) }
                var testState by remember { mutableStateOf("") }
                var testPassed by remember { mutableStateOf<Boolean?>(null) }
                var testing by remember { mutableStateOf(false) }

                checks.forEach { (label, ok) ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(vertical = 3.dp)
                    ) {
                        Text(
                            text = if (ok) "✅" else "❌",
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = label,
                            color = if (ok) Color.White else Color(0xFFFF8A80),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                if (testState.isNotBlank()) {
                    Text(
                        text = testState,
                        color = when (testPassed) {
                            true -> Color(0xFF81C784)
                            false -> Color(0xFFFF8A80)
                            null -> Color.White
                        },
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Button(
                        enabled = !testing,
                        onClick = {
                            testing = true
                            testPassed = null
                            testState = "🎙 Say \"Baka Mizune\" now…"
                            onTestWakeWord { passed, msg ->
                                testing = false
                                testPassed = passed
                                testState = (if (passed) "✅ " else "❌ ") + msg
                                checks = onWakeDiagnostics()
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4FC3F7))
                    ) {
                        Text(if (testing) "Listening…" else "Test it now", color = Color.Black)
                    }
                    TextButton(onClick = { checks = onWakeDiagnostics(); testState = "" }) {
                        Text("Refresh", color = Color.White.copy(alpha = 0.6f))
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "This proves she recognises your voice saying the phrase. It " +
                        "can't prove the service survives overnight in your pocket — " +
                        "that's a battery-manager question.",
                    color = Color.White.copy(alpha = 0.5f),
                    style = MaterialTheme.typography.bodySmall
                )
            }

            // Replace Google Assistant. Android gives no API to set this — only the user
            // can, in Settings — so the honest move is to take them straight there.
            SettingsCard(title = "Replace Google Assistant") {
                Text(
                    text = "Make Mizune the phone's assistant, so long-pressing the " +
                        "power button wakes her instead of Google.",
                    color = Color.White.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = {
                        // ACTION_VOICE_INPUT_SETTINGS is the assistant picker on stock
                        // Android. OEM ROMs bury it, so fall back to the top-level
                        // Settings app rather than crashing on ActivityNotFoundException.
                        val candidates = listOf(
                            android.provider.Settings.ACTION_VOICE_INPUT_SETTINGS,
                            "android.settings.MANAGE_DEFAULT_APPS_SETTINGS",
                            android.provider.Settings.ACTION_SETTINGS
                        )
                        for (a in candidates) {
                            try {
                                context.startActivity(
                                    android.content.Intent(a)
                                        .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                                break
                            } catch (_: Exception) { /* try the next one */ }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4FC3F7))
                ) {
                    Text("Set Mizune as assistant", color = Color.Black)
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Pick \"Mizune\" under Digital assistant app. Also add her " +
                        "Quick Settings tile from the notification shade's edit menu.",
                    color = Color.White.copy(alpha = 0.5f),
                    style = MaterialTheme.typography.bodySmall
                )
            }

            // Voice Match calibration (Google-Assistant-style: only Master's voice wakes her)
            SettingsCard(title = "Voice Match") {
                var voiceMatchStatus by remember { mutableStateOf("…") }
                var recording by remember { mutableStateOf(false) }
                LaunchedEffect(Unit) { onVoiceStatus { voiceMatchStatus = it } }

                Text(
                    text = voiceMatchStatus,
                    color = Color.White,
                    style = MaterialTheme.typography.bodyMedium
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Record yourself saying \"Baka Mizune\" 3 times. After that, " +
                        "only your voice can wake her.",
                    color = Color.White.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Button(
                        enabled = !recording,
                        onClick = {
                            recording = true
                            voiceMatchStatus = "🎙 Recording… say \"Baka Mizune\" now!"
                            onCalibrateVoice { result ->
                                recording = false
                                voiceMatchStatus = result
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4FC3F7))
                    ) {
                        Text(if (recording) "Recording…" else "Record sample", color = Color.Black)
                    }
                    TextButton(onClick = { onResetVoice { voiceMatchStatus = it } }) {
                        Text("Reset", color = Color.White.copy(alpha = 0.6f))
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
