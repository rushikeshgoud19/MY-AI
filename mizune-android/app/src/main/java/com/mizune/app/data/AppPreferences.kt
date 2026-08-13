package com.mizune.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.mizune.app.BuildConfig
import com.mizune.app.ui.ConnectionState
import com.mizune.app.ui.SlimeEmotion
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.distinctUntilChanged

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "mizune_prefs")

class AppPreferences(private val context: Context) {

    companion object {
        // Set `mizune.serverUrl` in local.properties (gitignored). Not a literal here:
        // the address was sitting in a public repo, reachable by anyone who read it.
        val DEFAULT_SERVER_URL: String = BuildConfig.DEFAULT_SERVER_URL
        const val DEFAULT_THEME = "dark"
        const val DEFAULT_VOICE_ID = "en-US-AriaNeural"

        private val SERVER_URL = stringPreferencesKey("server_url")
        private val API_KEY = stringPreferencesKey("api_key")
        private val THEME = stringPreferencesKey("theme")
        private val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        private val VOICE_ID = stringPreferencesKey("voice_id")
        private val LAST_MESSAGE = stringPreferencesKey("last_message")
        private val CONNECTION_STATE = stringPreferencesKey("connection_state")
        private val WIDGET_EMOTION = stringPreferencesKey("widget_emotion")
    }

    val serverUrl: Flow<String> = context.dataStore.data.map { prefs ->
        val stored = prefs[SERVER_URL]
        // Self-heal: phones that saved the dead centralindia hostname (VM moved to
        // UAE North) would stay broken forever since a stored pref beats the default.
        if (stored.isNullOrBlank() || stored.contains("centralindia")) DEFAULT_SERVER_URL else stored
    }.distinctUntilChanged()

    /** Dashboard API key, sent on the socket as ?key=. Empty until Master sets it —
     *  harmless while the server runs with ws_auth_required=false. */
    val apiKey: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[API_KEY] ?: ""
    }.distinctUntilChanged()

    val theme: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[THEME] ?: DEFAULT_THEME
    }.distinctUntilChanged()

    val notificationsEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[NOTIFICATIONS_ENABLED] ?: true
    }.distinctUntilChanged()

    val voiceId: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[VOICE_ID] ?: DEFAULT_VOICE_ID
    }.distinctUntilChanged()

    val lastMessage: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[LAST_MESSAGE] ?: ""
    }.distinctUntilChanged()

    val connectionState: Flow<ConnectionState> = context.dataStore.data.map { prefs ->
        ConnectionState.entries.find { it.name == prefs[CONNECTION_STATE] } ?: ConnectionState.DISCONNECTED
    }.distinctUntilChanged()

    val widgetEmotion: Flow<SlimeEmotion> = context.dataStore.data.map { prefs ->
        SlimeEmotion.entries.find { it.name == prefs[WIDGET_EMOTION] } ?: SlimeEmotion.CALM
    }.distinctUntilChanged()

    suspend fun setServerUrl(url: String) {
        context.dataStore.edit { prefs ->
            prefs[SERVER_URL] = url.trim().trimEnd('/')
        }
    }

    suspend fun setApiKey(key: String) {
        context.dataStore.edit { prefs ->
            prefs[API_KEY] = key.trim()
        }
    }

    suspend fun setTheme(theme: String) {
        context.dataStore.edit { prefs ->
            prefs[THEME] = theme
        }
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[NOTIFICATIONS_ENABLED] = enabled
        }
    }

    suspend fun setVoiceId(voiceId: String) {
        context.dataStore.edit { prefs ->
            prefs[VOICE_ID] = voiceId
        }
    }

    suspend fun setLastMessage(message: String) {
        context.dataStore.edit { prefs ->
            prefs[LAST_MESSAGE] = message
        }
    }

    suspend fun setConnectionState(state: ConnectionState) {
        context.dataStore.edit { prefs ->
            prefs[CONNECTION_STATE] = state.name
        }
    }

    suspend fun setWidgetEmotion(emotion: SlimeEmotion) {
        context.dataStore.edit { prefs ->
            prefs[WIDGET_EMOTION] = emotion.name
        }
    }
}
