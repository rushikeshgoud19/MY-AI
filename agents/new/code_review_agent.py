"""Code Review Agent for Mizune."""
import os
import re
from typing import Dict, Any, List


class CodeReviewAgent:
    """Agent for code quality analysis and improvement suggestions."""

    # Common anti-patterns for different languages
    ANTIPATTERNS = {
        "python": [
            (r"for\s+.*\s+in\s+range\(len\(", "Use enumerate() instead of range(len())"),
            (r"\.append\([^)]*\)[\s\S]*?\.append\(", "Consider list comprehension for multiple appends"),
            (r"except\s*:\s*$", "Bare except clause - catch specific exceptions"),
            (r"import\s+\*", "Wildcard imports are discouraged"),
            (r"print\(", "Use logging instead of print for production code"),
        ],
        "javascript": [
            (r"var\s+", "Use 'let' or 'const' instead of 'var'"),
            (r"==\s+null", "Use === for strict equality"),
            (r"console\.log\(", "Use proper logging for production"),
            (r"eval\(", "Avoid using eval() - security risk"),
            (r"\.innerHTML\s*=", "Use textContent instead of innerHTML to prevent XSS"),
        ],
        "general": [
            (r"//TODO", "TODO comment found"),
            (r"//FIXME", "FIXME comment found"),
            (r"password\s*=", "Hardcoded password detected"),
            (r"api[_-]?key\s*=", "Hardcoded API key detected"),
            (r"secret\s*=", "Hardcoded secret detected"),
        ]
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def review_file(self, file_path: str) -> Dict[str, Any]:
        """Review a code file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            language = self._detect_language(file_path)
            antipatterns = self.detect_antipatterns(code, language)
            complexity = self.calculate_complexity(code)
            suggestions = self.suggest_improvements(code, language)

            return {
                "success": True,
                "file_path": file_path,
                "language": language,
                "issues": antipatterns,
                "complexity": complexity,
                "suggestions": suggestions,
                "line_count": len(code.split('\n'))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
        }
        return lang_map.get(ext, "unknown")

    def detect_antipatterns(self, code: str, language: str = "general") -> List[Dict[str, Any]]:
        """Detect code anti-patterns."""
        issues = []

        # Check language-specific patterns
        if language in self.ANTIPATTERNS:
            for pattern, message in self.ANTIPATTERNS[language]:
                matches = re.finditer(pattern, code, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    issues.append({
                        "type": "anti-pattern",
                        "message": message,
                        "line": line_num,
                        "severity": "warning"
                    })

        # Check general patterns
        for pattern, message in self.ANTIPATTERNS["general"]:
            matches = re.finditer(pattern, code, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issues.append({
                    "type": "security",
                    "message": message,
                    "line": line_num,
                    "severity": "warning"
                })

        return issues

    def calculate_complexity(self, code: str) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        lines = code.split('\n')

        # Count functions/methods
        functions = len(re.findall(r'def\s+\w+\s*\(|function\s+\w+\s*\(', code))

        # Count classes
        classes = len(re.findall(r'class\s+\w+', code))

        # Count conditionals
        conditionals = len(re.findall(r'\bif\b|\belse\b|\belif\b|\bswitch\b', code))

        # Count loops
        loops = len(re.findall(r'\bfor\b|\bwhile\b|\bdo\b', code))

        # Simple cyclomatic complexity estimate
        complexity_score = 1 + conditionals + loops

        return {
            "lines": len(lines),
            "functions": functions,
            "classes": classes,
            "conditionals": conditionals,
            "loops": loops,
            "complexity_score": complexity_score,
            "rating": "low" if complexity_score < 10 else "medium" if complexity_score < 20 else "high"
        }

    def suggest_improvements(self, code: str, language: str = "general") -> List[str]:
        """Suggest code improvements."""
        suggestions = []

        lines = len(code.split('\n'))
        if lines > 500:
            suggestions.append(f"File has {lines} lines - consider splitting into smaller modules")

        # Check for long functions
        function_matches = re.finditer(r'def\s+(\w+)\s*\([^)]*\):', code)
        for match in function_matches:
            func_name = match.group(1)
            start = match.end()
            # Find function body (rough estimate)
            body = code[start:start+500]
            if body.count('\n') > 50:
                suggestions.append(f"Function '{func_name}' is long - consider refactoring")

        # Check for magic numbers
        magic_numbers = re.findall(r'\b\d{2,}\b', code)
        if len(magic_numbers) > 5:
            suggestions.append(f"Found {len(magic_numbers)} numeric literals - consider using named constants")

        if not suggestions:
            suggestions.append("Code looks good! No major improvements needed.")

        return suggestions