"""Data Analysis Agent for Mizune."""
import os
import pandas as pd
from typing import Dict, Any, Optional


class DataAnalysisAgent:
    """Agent for analyzing data files."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _get_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate basic statistics."""
        stats = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "numeric_columns": [],
            "categorical_columns": []
        }

        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                stats["numeric_columns"].append(col)
                stats[f"{col}_mean"] = float(df[col].mean())
                stats[f"{col}_min"] = float(df[col].min())
                stats[f"{col}_max"] = float(df[col].max())
            else:
                stats["categorical_columns"].append(col)

        return stats

    def analyze_csv(self, file_path: str) -> Dict[str, Any]:
        """Analyze a CSV file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            df = pd.read_csv(file_path)
            stats = self._get_statistics(df)

            return {
                "success": True,
                "file_path": file_path,
                "statistics": stats,
                "preview": df.head(5).to_dict(orient="records")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_excel(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Analyze an Excel file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)

            stats = self._get_statistics(df)

            return {
                "success": True,
                "file_path": file_path,
                "statistics": stats,
                "preview": df.head(5).to_dict(orient="records")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate natural language summary."""
        if not data.get("success"):
            return f"Error: {data.get('error', 'Unknown error')}"

        stats = data.get("statistics", {})
        row_count = stats.get("row_count", 0)
        col_count = stats.get("column_count", 0)
        cols = stats.get("columns", [])

        summary = f"This dataset contains {row_count} rows and {col_count} columns. "
        summary += f"The columns are: {', '.join(cols[:5])}"
        if len(cols) > 5:
            summary += f" and {len(cols) - 5} more."

        numeric_cols = stats.get("numeric_columns", [])
        if numeric_cols:
            summary += " For numeric columns: "
            for col in numeric_cols[:3]:
                mean = stats.get(f"{col}_mean", 0)
                summary += f"{col} has an average of {mean:.2f}. "

        return summary