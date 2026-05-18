"""Test WorkflowEngine."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkflowEngine(unittest.TestCase):
    """Tests for WorkflowEngine."""

    def test_add_workflow(self):
        """Test adding a workflow."""
        from workflows.engine import WorkflowEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"workflows_dir": tmpdir}
            engine = WorkflowEngine(config)

            workflow = {
                "name": "Test Workflow",
                "actions": [{"type": "speak", "text": "Hello"}]
            }

            result = engine.add_workflow(workflow)

            self.assertTrue(result["success"])
            self.assertIn("Test Workflow", engine.workflows)

    def test_list_workflows(self):
        """Test listing workflows."""
        from workflows.engine import WorkflowEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"workflows_dir": tmpdir}
            engine = WorkflowEngine(config)

            engine.add_workflow({"name": "Workflow 1", "actions": []})
            engine.add_workflow({"name": "Workflow 2", "actions": []})

            result = engine.list_workflows()

            self.assertTrue(result["success"])
            self.assertEqual(len(result["workflows"]), 2)

    def test_execute_workflow(self):
        """Test executing a workflow."""
        from workflows.engine import WorkflowEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"workflows_dir": tmpdir}
            engine = WorkflowEngine(config)

            workflow = {
                "name": "Test",
                "actions": [
                    {"type": "speak", "text": "Hello"},
                    {"type": "note", "content": "Test note"}
                ]
            }
            engine.add_workflow(workflow)

            result = engine.execute_workflow("Test")

            self.assertTrue(result["success"])
            self.assertEqual(len(result["results"]), 2)


if __name__ == "__main__":
    unittest.main()