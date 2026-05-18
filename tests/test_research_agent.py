"""Test ResearchAgent."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResearchAgent(unittest.TestCase):
    """Tests for ResearchAgent."""

    def test_summarize_text(self):
        """Test text summarization."""
        from agents.new.research_agent import ResearchAgent

        agent = ResearchAgent({})
        text = "This is the first sentence. This is the second sentence. This is the third sentence."

        summary = agent.summarize_text(text, max_length=50)

        self.assertIn("first", summary)
        self.assertLessEqual(len(summary), 53)  # 50 + "..."

    def test_compile_sources(self):
        """Test compiling sources."""
        from agents.new.research_agent import ResearchAgent

        agent = ResearchAgent({})
        sources = [
            {"title": "Python Docs", "url": "https://docs.python.org"},
            {"title": "MDN Web Docs", "url": "https://developer.mozilla.org"}
        ]

        result = agent.compile_sources(sources)

        self.assertIn("## Sources", result)
        self.assertIn("Python Docs", result)
        self.assertIn("MDN Web Docs", result)


if __name__ == "__main__":
    unittest.main()