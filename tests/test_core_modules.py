"""Unit tests for Mizune AI core modules."""
import os
import tempfile
from unittest.mock import patch
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEmotionDetection(unittest.TestCase):
    """Tests for emotion detection module."""

    def test_detect_happy(self):
        from core.emotion import detect_emotion
        assert detect_emotion("I'm so happy today!") == "happy"

    def test_detect_sad(self):
        from core.emotion import detect_emotion
        assert detect_emotion("I feel so sad and lonely") == "sad"

    def test_detect_angry(self):
        from core.emotion import detect_emotion
        assert detect_emotion("I'm so angry and frustrated!") == "angry"

    def test_detect_blush(self):
        from core.emotion import detect_emotion
        assert detect_emotion("You're such a good girl!") == "blush"

    def test_detect_excited(self):
        from core.emotion import detect_emotion
        assert detect_emotion("Yay! This is so awesome!") == "excited"

    def test_detect_neutral(self):
        from core.emotion import detect_emotion
        result = detect_emotion("Please open the browser")
        assert result == "neutral"

    def test_detect_empty_string(self):
        from core.emotion import detect_emotion
        assert detect_emotion("") == "neutral"

    def test_apply_emotion_response(self):
        from core.emotion import apply_emotion_response
        result = apply_emotion_response("Hello!", "happy")
        assert result == "[EMOTION: happy] Hello!"

    def test_apply_emotion_response_no_duplicate(self):
        from core.emotion import apply_emotion_response
        result = apply_emotion_response("[EMOTION: sad] Hello!", "happy")
        assert result == "[EMOTION: sad] Hello!"

    def test_get_tts_settings(self):
        from core.emotion import get_tts_settings_for_emotion
        settings = get_tts_settings_for_emotion("happy")
        assert settings == {"rate": 0, "pitch": 0}

    def test_get_tts_settings_unknown(self):
        from core.emotion import get_tts_settings_for_emotion
        settings = get_tts_settings_for_emotion("unknown_emotion")
        assert settings == {"rate": 0, "pitch": 0}


class TestConfig(unittest.TestCase):
    """Tests for configuration module."""

    def test_default_config_exists(self):
        from core.config import DEFAULT_CONFIG
        assert "ai_model" in DEFAULT_CONFIG
        assert "gemini_api_key" in DEFAULT_CONFIG

    def test_load_config_missing_file(self):
        from core.config import load_config
        with patch('core.config.CONFIG_PATH', '/nonexistent/path.json'):
            config = load_config()
            assert config["ai_model"] == "gemini"

    def test_load_config_invalid_json(self):
        from core.config import load_config
        # Create a temp file, close it, then use it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write("{ invalid json }")
            f.flush()
            temp_path = f.name
        try:
            with patch('core.config.CONFIG_PATH', temp_path):
                config = load_config()
                assert config["ai_model"] == "gemini"
        finally:
            # Wait a bit for Windows to release the file
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_path)
            except:
                pass


class TestActions(unittest.TestCase):
    """Tests for action execution module."""

    def test_common_apps_defined(self):
        from core.actions import COMMON_APPS
        assert "brave" in COMMON_APPS
        assert "chrome" in COMMON_APPS
        assert "spotify" in COMMON_APPS

    @patch('core.actions.subprocess.Popen')
    @patch('core.actions.webbrowser.open')
    def test_open_app_url(self, mock_browser, mock_popen):
        from core.actions import open_app
        result = open_app("youtube")
        assert result == "Opening youtube now!"
        mock_browser.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    @patch('core.actions.webbrowser.open')
    def test_open_app_executable(self, mock_browser, mock_popen):
        from core.actions import open_app
        result = open_app("spotify")
        mock_popen.assert_called_once()

    def test_close_app_empty_target(self):
        from core.actions import close_app
        result = close_app("")
        assert result == "Please specify what to close."

    @patch('core.actions.subprocess.Popen')
    def test_close_app_executable(self, mock_popen):
        from core.actions import close_app
        result = close_app("notepad")
        assert result == "Closing notepad now!"

    @patch('core.actions.subprocess.Popen')
    def test_lock_pc(self, mock_popen):
        from core.actions import lock_pc
        result = lock_pc()
        assert result == "PC locked!"
        mock_popen.assert_called_once()

    @patch('core.actions.subprocess.Popen')
    def test_sleep_pc(self, mock_popen):
        from core.actions import sleep_pc
        result = sleep_pc()
        assert result == "PC going to sleep~"
        mock_popen.assert_called_once()


class TestAudio(unittest.TestCase):
    """Tests for audio module."""

    def test_detect_energy_level(self):
        from core.audio import detect_energy_level
        import numpy as np
        audio_bytes = np.array([0, 100, -100, 50], dtype=np.int16).tobytes()
        energy = detect_energy_level(audio_bytes)
        assert energy >= 0

    def test_detect_energy_level_empty(self):
        from core.audio import detect_energy_level
        energy = detect_energy_level(b"")
        assert energy == 0

    def test_normalize_audio(self):
        from core.audio import normalize_audio
        import numpy as np
        audio_bytes = np.array([0, 1000, -1000], dtype=np.int16).tobytes()
        result = normalize_audio(audio_bytes)
        assert len(result) > 0


if __name__ == "__main__":
    unittest.main()