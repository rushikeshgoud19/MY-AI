"""Test obsidian configuration."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestObsidianConfig(unittest.TestCase):
    """Tests for Obsidian configuration."""

    def test_obsidian_config_loaded(self):
        """Test that obsidian config is loaded from config.json."""
        import server
        cfg = server.CFG
        # Should exist in merged config
        self.assertIn("obsidian_vault_path", cfg)


if __name__ == "__main__":
    unittest.main()