"""
Automated Docstring Fixer

Analyzes code files for docstring gaps and automatically generates
appropriate docstrings based on function signatures, AST analysis,
and governance decisions from KAIJU.
"""

import ast
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path


@dataclass
class DocstringIssue:
    """Represents a docstring gap or quality issue."""
    file_path: str
    line_number: int
    item_name: str
    item_type: str  # "function", "class", "method"
    issue_type: str  # "missing", "incomplete", "malformed"
    current_docstring: Optional[str] = None
    suggested_docstring: Optional[str] = None
    confidence: float = 0.0
    severity: str = "medium"  # "low", "medium", "high"


@dataclass
class DocstringFixResult:
    """Result of docstring fixing operation."""
    file_path: str
    issues_found: int = 0
    issues_fixed: int = 0
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    git_diff_hash: str = ""


class DocstringFixer:
    """
    Automated docstring analysis and fixing tool.

    Scans Python files for docstring gaps and generates
    appropriate docstrings using AST analysis.
    """

    # Docstring templates by item type
    TEMPLATES = {
        "function": '""{description}\n\nArgs:\n{args}\n\nReturns:\n{returns}\n"""',
        "class": '""{description}\n\nAttributes:\n{attributes}\n"""',
        "method": '""{description}\n\nArgs:\n{args}\n\nReturns:\n{returns}\n"""',
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.max_line_length = self.config.get("max_line_length", 88)
        self.include_type_hints = self.config.get("include_type_hints", True)

    def analyze_file(self, file_path: str) -> List[DocstringIssue]:
        """
        Analyze a Python file for docstring issues.

        Args:
            file_path: Path to the Python file

        Returns:
            List of docstring issues found
        """
        issues = []
        path = Path(file_path)

        if not path.exists() or path.suffix != ".py":
            return issues

        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)
            issues.extend(self._analyze_ast(tree, file_path, source))

        except SyntaxError as e:
            issues.append(DocstringIssue(
                file_path=file_path,
                line_number=e.lineno or 0,
                item_name="<syntax_error>",
                item_type="function",
                issue_type="malformed",
                severity="high",
                confidence=1.0,
            ))
        except Exception as e:
            pass  # Skip files that can't be read

        return issues

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: str,
        source: str
    ) -> List[DocstringIssue]:
        """Analyze AST for docstring issues."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                issue = self._check_function_docstring(node, file_path, source)
                if issue:
                    issues.append(issue)

            elif isinstance(node, ast.ClassDef):
                issue = self._check_class_docstring(node, file_path, source)
                if issue:
                    issues.append(issue)

        return issues

    def _check_function_docstring(
        self,
        node: ast.FunctionDef,
        file_path: str,
        source: str
    ) -> Optional[DocstringIssue]:
        """Check if a function has an adequate docstring."""
        # Get the docstring if present
        docstring = ast.get_docstring(node)

        # Check if docstring is missing
        if docstring is None:
            return DocstringIssue(
                file_path=file_path,
                line_number=node.lineno,
                item_name=node.name,
                item_type="method" if self._is_method(node) else "function",
                issue_type="missing",
                severity=self._assess_severity(node),
                confidence=0.9,
                suggested_docstring=self._generate_function_docstring(node),
            )

        # Check if docstring is too short/incomplete
        if len(docstring.strip()) < 10:
            return DocstringIssue(
                file_path=file_path,
                line_number=node.lineno,
                item_name=node.name,
                item_type="method" if self._is_method(node) else "function",
                issue_type="incomplete",
                current_docstring=docstring,
                severity="medium",
                confidence=0.7,
                suggested_docstring=self._generate_function_docstring(node),
            )

        return None

    def _check_class_docstring(
        self,
        node: ast.ClassDef,
        file_path: str,
        source: str
    ) -> Optional[DocstringIssue]:
        """Check if a class has an adequate docstring."""
        docstring = ast.get_docstring(node)

        if docstring is None:
            return DocstringIssue(
                file_path=file_path,
                line_number=node.lineno,
                item_name=node.name,
                item_type="class",
                issue_type="missing",
                severity=self._assess_severity(node),
                confidence=0.85,
                suggested_docstring=self._generate_class_docstring(node),
            )

        return None

    def _is_method(self, node: ast.FunctionDef) -> bool:
        """Check if a function is actually a method (inside a class)."""
        # Simple heuristic: check if parent is a ClassDef
        # In a full implementation, we'd track parent nodes during traversal
        return False  # Simplified for now

    def _assess_severity(self, node: ast.AST) -> str:
        """Assess the severity of a missing docstring."""
        if isinstance(node, ast.FunctionDef):
            # Public functions are higher severity
            if not node.name.startswith("_"):
                return "high"
            elif node.name.startswith("__") and node.name.endswith("__"):
                return "low"  # dunder methods
            else:
                return "medium"

        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                return "high"
            return "medium"

        return "low"

    def _generate_function_docstring(self, node: ast.FunctionDef) -> str:
        """Generate a docstring for a function based on its signature."""
        description = f"{node.name} function."

        # Build args section
        args_lines = []
        for arg in node.args.args:
            arg_name = arg.arg
            arg_type = ""
            if self.include_type_hints and arg.annotation:
                arg_type = f": {ast.unparse(arg.annotation)}" if hasattr(ast, 'unparse') else ""
            args_lines.append(f"    {arg_name}{arg_type}: Description of {arg_name}")

        args_section = "\n".join(args_lines) if args_lines else "    None"

        # Build returns section
        returns = "    Description of return value"
        if self.include_type_hints and node.returns:
            return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else ""
            returns = f"    {return_type}: Description of return value"

        template = self.TEMPLATES["method" if self._is_method(node) else "function"]
        return template.format(
            description=description,
            args=args_section,
            returns=returns,
        )

    def _generate_class_docstring(self, node: ast.ClassDef) -> str:
        """Generate a docstring for a class."""
        description = f"{node.name} class."

        # Build attributes section from __init__ if available
        attributes = "    Description of attributes"
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                attr_lines = []
                for stmt in item.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                                attr_lines.append(f"    {target.attr}: Description of {target.attr}")
                if attr_lines:
                    attributes = "\n".join(attr_lines)

        template = self.TEMPLATES["class"]
        return template.format(
            description=description,
            attributes=attributes,
        )

    async def fix_issues(
        self,
        issues: List[DocstringIssue],
        auto_approve: bool = False,
        trust_score: float = 0.5
    ) -> List[DocstringFixResult]:
        """
        Fix docstring issues automatically.

        Args:
            issues: List of issues to fix
            auto_approve: Whether to auto-approve all fixes
            trust_score: Trust score of the requesting agent

        Returns:
            List of fix results
        """
        results = []

        # Group issues by file
        by_file: Dict[str, List[DocstringIssue]] = {}
        for issue in issues:
            if issue.file_path not in by_file:
                by_file[issue.file_path] = []
            by_file[issue.file_path].append(issue)

        for file_path, file_issues in by_file.items():
            result = await self._fix_file(file_path, file_issues, auto_approve, trust_score)
            results.append(result)

        return results

    async def _fix_file(
        self,
        file_path: str,
        issues: List[DocstringIssue],
        auto_approve: bool,
        trust_score: float
    ) -> DocstringFixResult:
        """Fix issues in a single file."""
        result = DocstringFixResult(
            file_path=file_path,
            issues_found=len(issues),
        )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            changes_made = []
            for issue in issues:
                # Check if we should fix this issue
                if not auto_approve and issue.confidence < self.min_confidence:
                    continue

                if issue.suggested_docstring and trust_score >= 0.5:
                    # Apply the fix
                    success = self._apply_fix(lines, issue)
                    if success:
                        changes_made.append({
                            "line": issue.line_number,
                            "item": issue.item_name,
                            "type": issue.item_type,
                            "action": "added docstring",
                        })

            # Write back if changes were made
            if changes_made:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                result.issues_fixed = len(changes_made)
                result.changes_made = changes_made

                # Generate hash of changes
                with open(file_path, "r", encoding="utf-8") as f:
                    new_content = f.read()
                result.git_diff_hash = hashlib.sha256(new_content.encode()).hexdigest()[:16]

        except Exception as e:
            result.error_message = str(e)

        return result

    def _apply_fix(self, lines: List[str], issue: DocstringIssue) -> bool:
        """Apply a docstring fix to the source lines."""
        if not issue.suggested_docstring:
            return False

        try:
            # Find the line where the function/class is defined
            line_idx = issue.line_number - 1  # Convert to 0-indexed

            if line_idx < 0 or line_idx >= len(lines):
                return False

            # Get the indentation of the definition line
            def_line = lines[line_idx]
            indent = len(def_line) - len(def_line.lstrip())

            # Build the docstring with proper indentation
            docstring_lines = issue.suggested_docstring.split("\n")
            indented_docstring = "\n".join(
                " " * (indent + 4) + line if line.strip() else ""
                for line in docstring_lines
            )

            # Insert the docstring after the definition line
            # Find the end of the definition (colon)
            insert_idx = line_idx + 1

            # Add proper spacing
            new_lines = [
                lines[insert_idx - 1],  # Definition line
                "\n" if insert_idx < len(lines) and lines[insert_idx].strip() else "",
                " " * (indent + 4) + '"""' + "\n",
            ]

            for doc_line in docstring_lines:
                if doc_line.strip():
                    new_lines.append(" " * (indent + 4) + doc_line + "\n")
                else:
                    new_lines.append("\n")

            new_lines.append(" " * (indent + 4) + '"""\n')

            # Replace in lines
            lines[insert_idx:insert_idx] = new_lines[1:]

            return True

        except Exception:
            return False

    def generate_governance_proposal(
        self,
        issues: List[DocstringIssue],
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Generate a governance proposal for fixing docstring issues.

        Args:
            issues: List of docstring issues
            agent_id: ID of the proposing agent

        Returns:
            Proposal dictionary for KAIJU evaluation
        """
        high_severity = [i for i in issues if i.severity == "high"]
        medium_severity = [i for i in issues if i.severity == "medium"]
        low_severity = [i for i in issues if i.severity == "low"]

        files_affected = list(set(i.file_path for i in issues))

        return {
            "agent_id": agent_id,
            "action_type": "docstring_fix",
            "target_files": files_affected,
            "issues_summary": {
                "total": len(issues),
                "high": len(high_severity),
                "medium": len(medium_severity),
                "low": len(low_severity),
            },
            "estimated_tokens": len(issues) * 100,  # Rough estimate
            "justification": f"Automated docstring improvement: {len(issues)} issues found across {len(files_affected)} files",
            "proposed_changes": {
                "add_missing_docstrings": True,
                "improve_incomplete": True,
                "issues": [
                    {
                        "file": i.file_path,
                        "line": i.line_number,
                        "item": i.item_name,
                        "type": i.issue_type,
                        "severity": i.severity,
                    }
                    for i in issues
                ],
            },
        }
