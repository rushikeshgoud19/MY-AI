"""Test FileOrganizerAgent."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFileOrganizerAgent(unittest.TestCase):
    """Tests for FileOrganizerAgent."""

    def test_organize_folder(self):
        """Test organizing files by type."""
        from agents.new.file_organizer_agent import FileOrganizerAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            open(os.path.join(tmpdir, "doc1.txt"), "w").close()
            open(os.path.join(tmpdir, "image1.jpg"), "w").close()
            open(os.path.join(tmpdir, "data.csv"), "w").close()

            agent = FileOrganizerAgent({})
            result = agent.organize_folder(tmpdir, "by_type")

            self.assertTrue(result["success"])
            self.assertGreaterEqual(result["files_moved"], 3)

    def test_get_category(self):
        """Test file category detection."""
        from agents.new.file_organizer_agent import FileOrganizerAgent

        agent = FileOrganizerAgent({})
        self.assertEqual(agent._get_category("test.py"), "Code")
        self.assertEqual(agent._get_category("image.png"), "Images")
        self.assertEqual(agent._get_category("data.csv"), "Data")


if __name__ == "__main__":
    unittest.main()