"""Test CodeReviewAgent."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCodeReviewAgent(unittest.TestCase):
    """Tests for CodeReviewAgent."""

    def test_detect_language(self):
        """Test language detection."""
        from agents.new.code_review_agent import CodeReviewAgent

        agent = CodeReviewAgent({})

        self.assertEqual(agent._detect_language("test.py"), "python")
        self.assertEqual(agent._detect_language("test.js"), "javascript")
        self.assertEqual(agent._detect_language("test.java"), "java")

    def test_calculate_complexity(self):
        """Test complexity calculation."""
        from agents.new.code_review_agent import CodeReviewAgent

        agent = CodeReviewAgent({})
        code = """
def hello():
    if True:
        for i in range(10):
            print(i)
"""

        complexity = agent.calculate_complexity(code)

        self.assertEqual(complexity["functions"], 1)
        self.assertGreater(complexity["conditionals"], 0)

    def test_suggest_improvements(self):
        """Test improvement suggestions."""
        from agents.new.code_review_agent import CodeReviewAgent

        agent = CodeReviewAgent({})

        # Test with code that has issues
        code = "x = 42\ny = 100\nz = 999"  # Magic numbers
        suggestions = agent.suggest_improvements(code)

        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)


if __name__ == "__main__":
    unittest.main()