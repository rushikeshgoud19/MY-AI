"""Test ProjectManagerAgent."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProjectManagerAgent(unittest.TestCase):
    """Tests for ProjectManagerAgent."""

    def test_add_task(self):
        """Test adding a task."""
        from agents.new.project_manager_agent import ProjectManagerAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"tasks_file": os.path.join(tmpdir, "tasks.json")}
            agent = ProjectManagerAgent(config)

            result = agent.add_task("Review PR", "2026-05-20", "Mizune")

            self.assertTrue(result["success"])
            self.assertEqual(result["task"]["title"], "Review PR")

    def test_list_tasks(self):
        """Test listing tasks."""
        from agents.new.project_manager_agent import ProjectManagerAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"tasks_file": os.path.join(tmpdir, "tasks.json")}
            agent = ProjectManagerAgent(config)

            agent.add_task("Task 1", project="Work")
            agent.add_task("Task 2", project="Work")

            result = agent.list_tasks(project="Work")
            self.assertTrue(result["success"])
            self.assertEqual(result["count"], 2)

    def test_update_task(self):
        """Test updating task status."""
        from agents.new.project_manager_agent import ProjectManagerAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"tasks_file": os.path.join(tmpdir, "tasks.json")}
            agent = ProjectManagerAgent(config)

            result = agent.add_task("Test Task")
            task_id = result["task"]["id"]

            update_result = agent.update_task(task_id, "completed")
            self.assertTrue(update_result["success"])
            self.assertEqual(update_result["task"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()