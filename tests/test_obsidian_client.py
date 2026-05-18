"""Test Obsidian client."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestObsidianClient(unittest.TestCase):
    """Tests for ObsidianClient."""

    def test_create_note(self):
        """Test creating a note."""
        from obsidian.client import ObsidianClient

        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObsidianClient(tmpdir)
            result = client.create_note("Test Note", "This is test content", "Inbox")

            self.assertTrue(os.path.exists(result["path"]))
            with open(result["path"]) as f:
                content = f.read()
                self.assertIn("Test Note", content)

    def test_list_notes(self):
        """Test listing notes in a folder."""
        from obsidian.client import ObsidianClient

        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObsidianClient(tmpdir)
            client.create_note("Note 1", "Content 1", "Inbox")
            client.create_note("Note 2", "Content 2", "Inbox")

            notes = client.list_notes("Inbox")
            self.assertEqual(len(notes), 2)

    def test_search_vault(self):
        """Test searching notes."""
        from obsidian.client import ObsidianClient

        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObsidianClient(tmpdir)
            client.create_note("Meeting", "Discussed project timeline", "Inbox")

            results = client.search_vault("project")
            self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()