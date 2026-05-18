"""Test ObsidianAgent."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestObsidianAgent(unittest.TestCase):
    """Tests for ObsidianAgent."""

    def test_create_note(self):
        """Test creating a note through agent."""
        from agents.new.obsidian_agent import ObsidianAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"obsidian_vault_path": tmpdir}
            agent = ObsidianAgent(config)
            result = agent.create_note("Meeting Notes", "Discussed project timeline")

            self.assertTrue(result["success"])
            self.assertIn("path", result)

    def test_list_folder(self):
        """Test listing notes in folder."""
        from agents.new.obsidian_agent import ObsidianAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"obsidian_vault_path": tmpdir}
            agent = ObsidianAgent(config)
            agent.create_note("Note 1", "Content 1", "Inbox")

            result = agent.list_folder("Inbox")
            self.assertTrue(result["success"])
            self.assertEqual(len(result["notes"]), 1)

    def test_no_vault_configured(self):
        """Test behavior when vault not configured."""
        from agents.new.obsidian_agent import ObsidianAgent

        config = {"obsidian_vault_path": ""}
        agent = ObsidianAgent(config)
        result = agent.create_note("Test", "Content")

        self.assertFalse(result["success"])
        self.assertIn("not configured", result["error"])


if __name__ == "__main__":
    unittest.main()