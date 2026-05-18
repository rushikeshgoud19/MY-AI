"""Test DataAnalysisAgent."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDataAnalysisAgent(unittest.TestCase):
    """Tests for DataAnalysisAgent."""

    def test_analyze_csv(self):
        """Test analyzing a CSV file."""
        from agents.new.data_analysis_agent import DataAnalysisAgent

        # Create test CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age,salary\n")
            f.write("Alice,30,50000\n")
            f.write("Bob,25,45000\n")
            f.write("Charlie,35,60000\n")
            tmpfile = f.name

        try:
            agent = DataAnalysisAgent({})
            result = agent.analyze_csv(tmpfile)

            self.assertTrue(result["success"])
            self.assertIn("statistics", result)
            self.assertEqual(result["statistics"]["row_count"], 3)
        finally:
            os.unlink(tmpfile)

    def test_generate_summary(self):
        """Test generating natural language summary."""
        from agents.new.data_analysis_agent import DataAnalysisAgent

        agent = DataAnalysisAgent({})
        data = {
            "success": True,
            "statistics": {
                "row_count": 10,
                "column_count": 3,
                "columns": ["name", "age", "salary"],
                "numeric_columns": ["age", "salary"],
                "age_mean": 30.0,
                "salary_mean": 50000.0
            }
        }

        summary = agent.generate_summary(data)
        self.assertIn("10 rows", summary)
        self.assertIn("3 columns", summary)


if __name__ == "__main__":
    unittest.main()