import os
import sys
import unittest
import importlib.util

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Load server.py module explicitly as server_app to avoid collision with the 'server' directory
server_file_path = os.path.join(parent_dir, "server.py")
spec = importlib.util.spec_from_file_location("server_app", server_file_path)
server_app = importlib.util.module_from_spec(spec)
sys.modules["server_app"] = server_app
spec.loader.exec_module(server_app)


class TestObsidianConfig(unittest.TestCase):
    """Tests for Obsidian configuration."""

    def test_obsidian_config_loaded(self):
        """Test that obsidian config is loaded from config.json."""
        cfg = server_app.CFG
        # Should exist in merged config
        self.assertIn("obsidian_vault_path", cfg)


if __name__ == "__main__":
    unittest.main()