"""Test LearningEngine."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLearningEngine(unittest.TestCase):
    """Tests for LearningEngine."""

    def test_record_command(self):
        """Test recording commands."""
        from learning.engine import LearningEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"learning_file": os.path.join(tmpdir, "learning.json")}
            engine = LearningEngine(config)

            engine.record_command("Open Spotify")
            engine.record_command("Play music")

            self.assertEqual(len(engine.command_history), 2)

    def test_app_preferences(self):
        """Test learning app preferences."""
        from learning.engine import LearningEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"learning_file": os.path.join(tmpdir, "learning.json")}
            engine = LearningEngine(config)

            engine.learn_app_preference("music", "Spotify")
            engine.learn_app_preference("music", "Spotify")
            engine.learn_app_preference("music", "YouTube")

            preferred = engine.get_preferred_app("music")
            self.assertEqual(preferred, "Spotify")

    def test_context(self):
        """Test conversation context."""
        from learning.engine import LearningEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"learning_file": os.path.join(tmpdir, "learning.json")}
            engine = LearningEngine(config)

            engine.update_context("current_project", "Mizune AI")
            result = engine.get_context("current_project")

            self.assertEqual(result, "Mizune AI")

    def test_stats(self):
        """Test getting stats."""
        from learning.engine import LearningEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"learning_file": os.path.join(tmpdir, "learning.json")}
            engine = LearningEngine(config)

            engine.record_command("Test command")

            stats = engine.get_stats()
            self.assertIn("commands_recorded", stats)


if __name__ == "__main__":
    unittest.main()