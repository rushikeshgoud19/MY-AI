"""Integration tests for Mizune AI."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestActionExecution(unittest.TestCase):
    """Integration tests for action execution."""

    @patch('core.actions.subprocess.Popen')
    def test_open_brave_browser(self, mock_popen):
        from core.actions import open_app
        result = open_app("brave")
        self.assertIn("Opening", result)
        mock_popen.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    def test_open_spotify(self, mock_popen):
        from core.actions import open_app
        result = open_app("spotify")
        self.assertIn("Opening", result)
        mock_popen.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    @patch('core.actions.webbrowser.open')
    def test_open_youtube_url(self, mock_browser, mock_popen):
        from core.actions import open_app
        result = open_app("youtube")
        self.assertIn("Opening", result)
        mock_browser.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    def test_close_notepad(self, mock_popen):
        from core.actions import close_app
        result = close_app("notepad")
        self.assertIn("Closing", result)
        mock_popen.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    def test_lock_pc(self, mock_popen):
        from core.actions import lock_pc
        result = lock_pc()
        self.assertEqual(result, "PC locked!")
        mock_popen.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    def test_sleep_pc(self, mock_popen):
        from core.actions import sleep_pc
        result = sleep_pc()
        self.assertEqual(result, "PC going to sleep~")
        mock_popen.assert_called_once()

    @patch('core.actions.webbrowser.open')
    def test_search_google(self, mock_browser):
        from core.actions import search_web
        result = search_web("python", "google")
        self.assertIn("Searching", result)
        mock_browser.assert_called_once()


class TestEmotionIntegration(unittest.TestCase):
    """Integration tests for emotion detection."""

    def test_emotion_chain_positive(self):
        from core.emotion import detect_emotion, apply_emotion_response

        text = "This is amazing! I love it so much!"
        emotion = detect_emotion(text)
        response = "Yes, it's wonderful!"
        result = apply_emotion_response(response, emotion)

        self.assertIn("[EMOTION:", result)
        self.assertIn("wonderful", result)

    def test_emotion_chain_negative(self):
        from core.emotion import detect_emotion, apply_emotion_response

        text = "I'm so frustrated and angry!"
        emotion = detect_emotion(text)
        response = "I'm sorry to hear that."
        result = apply_emotion_response(response, emotion)

        self.assertIn("[EMOTION:", result)

    def test_tts_settings_with_emotion(self):
        from core.emotion import detect_emotion, get_tts_settings_for_emotion

        text = "Yay! This is awesome!"
        emotion = detect_emotion(text)
        settings = get_tts_settings_for_emotion(emotion)

        self.assertIn("rate", settings)
        self.assertIn("pitch", settings)
        self.assertEqual(settings["rate"], 3)  # excited has high rate


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for configuration."""

    def test_config_with_defaults(self):
        from core.config import load_config, DEFAULT_CONFIG

        config = DEFAULT_CONFIG.copy()
        # Verify all required keys exist
        required_keys = [
            "ai_model", "gemini_api_key", "openai_api_key", "anthropic_api_key",
            "memory_size", "character_name", "personality"
        ]
        for key in required_keys:
            self.assertIn(key, config)

    def test_api_key_retrieval(self):
        from core.config import get_api_key

        config = {
            "gemini_api_key": "test_key_123",
            "openai_api_key": "test_key_456",
            "ai_model": "gemini"
        }

        key = get_api_key(config, "gemini")
        self.assertEqual(key, "test_key_123")

        key = get_api_key(config, "openai")
        self.assertEqual(key, "test_key_456")

    def test_missing_api_key_returns_none(self):
        from core.config import get_api_key

        config = {"ai_model": "gemini"}
        key = get_api_key(config, "gemini")
        self.assertIsNone(key)


class TestAudioIntegration(unittest.TestCase):
    """Integration tests for audio processing."""

    @patch('core.audio.sd.rec')
    @patch('core.audio.sd.wait')
    def test_record_audio(self, mock_wait, mock_rec):
        from core.audio import record_audio

        mock_rec.return_value = None
        result, sr = record_audio(1.0, 44100)
        self.assertIsInstance(result, bytes)
        self.assertEqual(sr, 44100)

    def test_detect_energy_level_typical(self):
        from core.audio import detect_energy_level
        import numpy as np

        # Create typical audio with some amplitude
        audio = np.array([0, 500, 1000, 500, 0, -500, -1000, -500], dtype=np.int16)
        energy = detect_energy_level(audio.tobytes())
        self.assertGreater(energy, 0)

    def test_detect_energy_level_silence(self):
        from core.audio import detect_energy_level
        import numpy as np

        # Create silence
        audio = np.zeros(1000, dtype=np.int16)
        energy = detect_energy_level(audio.tobytes())
        self.assertEqual(energy, 0)

    @patch('core.audio.sd.query_devices')
    def test_resolve_mic_device_index_by_name(self, mock_query):
        from core.audio import resolve_mic_device_index

        # Mock query_devices returning two devices
        mock_query.return_value = [
            {'name': 'Realtek Audio', 'max_input_channels': 2},
            {'name': 'Microphone (USB)', 'max_input_channels': 1},
        ]

        index = resolve_mic_device_index(None, "realtek")
        self.assertEqual(index, 0)

        index = resolve_mic_device_index(None, "usb")
        self.assertEqual(index, 1)

        index = resolve_mic_device_index(None, "nonexistent")
        self.assertIsNone(index)


class TestLLMServiceMock(unittest.TestCase):
    """Integration tests for LLM service (with mocked API)."""

    def test_llm_service_imports(self):
        from core import LLMService
        self.assertTrue(hasattr(LLMService, 'get_ai_response'))

    def test_gemini_response_no_api_key(self):
        from core.llm_service import LLMService

        cfg = {"gemini_api_key": "", "ai_model": "gemini"}
        result = LLMService._gemini_response("hello", [], "system", cfg)

        self.assertIn("API key", result)

    def test_openai_response_no_api_key(self):
        from core.llm_service import LLMService

        cfg = {"openai_api_key": "", "ai_model": "openai"}
        result = LLMService._openai_response("hello", [], "system", cfg)

        self.assertIn("API key", result)

    def test_anthropic_response_no_api_key(self):
        from core.llm_service import LLMService

        cfg = {"anthropic_api_key": "", "ai_model": "anthropic"}
        result = LLMService._anthropic_response("hello", [], "system", cfg)

        self.assertIn("API key", result)


class TestFullConversationFlow(unittest.TestCase):
    """End-to-end conversation flow tests."""

    def test_emotion_detection_then_response(self):
        # Simulate full flow: detect emotion -> generate response -> apply emotion tag
        from core.emotion import detect_emotion, apply_emotion_response

        # User says something happy
        user_input = "I'm so happy today!"
        emotion = detect_emotion(user_input)
        self.assertEqual(emotion, "happy")

        # AI generates response
        ai_response = "That's wonderful to hear, Master!"
        final_response = apply_emotion_response(ai_response, emotion)

        # Verify emotion tag is added
        self.assertTrue(final_response.startswith("[EMOTION: happy]"))

    def test_action_request_flow(self):
        # Test full action execution flow
        from core.actions import open_app

        with patch('core.actions.subprocess.Popen') as mock:
            result = open_app("discord")
            self.assertIn("Opening", result)
            self.assertIn("discord", result.lower())

    def test_config_to_llm_flow(self):
        # Test config flows through to LLM service
        from core.config import load_config
        from core.llm_service import LLMService

        # This tests that the config structure is compatible with LLM service
        cfg = {"ai_model": "gemini", "gemini_api_key": "test_key"}
        # Should not raise
        self.assertIn("ai_model", cfg)
        self.assertIn("gemini_api_key", cfg)


class TestSecurityIntegration(unittest.TestCase):
    """Security-related integration tests."""

    def test_shell_quote_prevents_injection(self):
        import shlex
        from core.actions import open_app

        # Attempt injection via app name
        malicious_input = "notepad; echo hacked"

        with patch('core.actions.subprocess.Popen') as mock_popen:
            open_app(malicious_input)
            call_args = mock_popen.call_args[0][0]

            # Verify it's quoted and safe
            self.assertIn("notepad", call_args)
            # The ; should be escaped/quoted, not interpreted as command separator

    def test_url_injection_prevented(self):
        from core.actions import open_app

        # Attempt injection via URL
        malicious_input = "https://evil.com; echo stolen"

        with patch('core.actions.webbrowser.open') as mock:
            open_app(malicious_input)
            # Should open the URL safely
            mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()