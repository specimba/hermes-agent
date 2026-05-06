#!/usr/bin/env python3
"""
AST-based code quality scanner for hermes_cli modules.
Generates structured JSON report with docstring gaps, complexity metrics, and security analysis.
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


class FunctionQualityVisitor(ast.NodeVisitor):
    """AST visitor to collect function/method quality metrics."""

    def __init__(self, file_path: str, repo_root: Path):
        self.file_path = Path(file_path).relative_to(repo_root).as_posix()
        self.functions: List[Dict[str, Any]] = []
        self._current_class: Optional[str] = None
        self.imports: Dict[str, Any] = {}  # Track imported names: alias -> module or (module, name)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Enter class context to track method ownership."""
        prev_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process synchronous function definitions."""
        self._process_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Process asynchronous function definitions."""
        self._process_function(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Track import statements and their aliases."""
        for alias in node.names:
            key = alias.asname if alias.asname else alias.name
            self.imports[key] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from-import statements and their aliases."""
        if node.module is None:
            return
        for alias in node.names:
            key = alias.asname if alias.asname else alias.name
            self.imports[key] = (node.module, alias.name)
        self.generic_visit(node)

    def _process_function(self, node: ast.AST) -> None:
        """Extract metrics for a single function/method."""
        # Get function name with class context if applicable
        func_name = node.name if not self._current_class else f"{self._current_class}.{node.name}"
        
        # Docstring check
        has_docstring = ast.get_docstring(node) is not None
        
        # Cyclomatic complexity
        complexity = self._compute_cyclomatic_complexity(node)
        
        # Security patterns
        security_issues = self._check_security_patterns(node)
        
        # Public/private status
        is_public = not node.name.startswith('_')
        
        self.functions.append({
            "file": self.file_path,
            "function": func_name,
            "line": node.lineno,
            "has_docstring": has_docstring,
            "cyclomatic_complexity": complexity,
            "complexity_category": self._categorize_complexity(complexity),
            "is_public": is_public,
            "security_issues": security_issues,
            "priority_score": self._compute_priority_score(has_docstring, is_public, complexity, security_issues)
        })

    def _compute_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a function node."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Decision points that increase complexity
            if isinstance(child, (ast.If,)):
                complexity += 1
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.While):
                complexity += 1
            elif isinstance(child, (ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.Try):
                # Each except handler is a decision point
                complexity += len(child.handlers)
            elif isinstance(child, ast.BoolOp):
                # Each additional boolean operand adds a decision point
                complexity += len(child.values) - 1
            elif isinstance(child, ast.IfExp):  # Ternary expression
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 1
            # Handle Python 3.10+ match/case
            elif isinstance(child, ast.Match):
                complexity += len(child.cases)
        
        return complexity

    def _categorize_complexity(self, complexity: int) -> str:
        """Categorize complexity into low/medium/high."""
        if complexity < 10:
            return "low"
        elif complexity < 20:
            return "medium"
        else:
            return "high"

    def _resolve_call(self, func_node: ast.AST) -> Optional[tuple]:
        """Resolve a function call node to (module, function_name) if possible."""
        if isinstance(func_node, ast.Name):
            name = func_node.id
            if name in ("eval", "exec"):
                return (None, name)
            if name in self.imports:
                imported = self.imports[name]
                if isinstance(imported, tuple):
                    return (imported[0], imported[1])
            return None
        elif isinstance(func_node, ast.Attribute):
            if not isinstance(func_node.value, ast.Name):
                return None
            module_alias = func_node.value.id
            func_name = func_node.attr
            if module_alias in self.imports:
                imported = self.imports[module_alias]
                if isinstance(imported, str):
                    return (imported, func_name)
            return (module_alias, func_name)
        return None

    def _check_security_patterns(self, node: ast.AST) -> List[str]:
        """Detect common security anti-patterns in function AST."""
        issues = []
        
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            
            func_info = self._resolve_call(child.func)
            if func_info is None:
                continue
            
            module, func_name = func_info
            
            # Check eval/exec
            if module is None and func_name in ("eval", "exec"):
                issues.append(f"uses {func_name}()")
            
            # Check os.system
            if module == "os" and func_name == "system":
                issues.append("uses os.system()")
            
            # Check subprocess with shell=True
            if module == "subprocess" and func_name in ("call", "run", "Popen"):
                for keyword in child.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        issues.append(f"subprocess.{func_name}() with shell=True")
            
            # Check pickle usage
            if module == "pickle" and func_name in ("load", "loads"):
                issues.append("uses pickle.load/loads (insecure deserialization)")
        
        return list(set(issues))  # Deduplicate

    def _compute_priority_score(self, has_docstring: bool, is_public: bool, complexity: int, security_issues: List[str]) -> int:
        """Compute priority score (higher = more urgent to fix)."""
        score = 0
        # Docstring gap priority
        if not has_docstring:
            score += 30 if is_public else 10
        # Complexity priority
        if complexity >= 20:
            score += 25
        elif complexity >= 10:
            score += 15
        # Security priority
        if security_issues:
            score += 40
        return score


def scan_file(file_path: str, repo_root: Path) -> List[Dict[str, Any]]:
    """Scan a single Python file and return function metrics."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=file_path)
        visitor = FunctionQualityVisitor(file_path, repo_root)
        visitor.visit(tree)
        return visitor.functions
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        import traceback
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []


def generate_report(target_files: List[str], output_path: str, repo_root: Path) -> Dict[str, Any]:
    """Generate full quality report for target files."""
    all_functions = []
    for file_path in target_files:
        if not os.path.exists(file_path):
            print(f"Warning: Target file not found: {file_path}", file=sys.stderr)
            continue
        all_functions.extend(scan_file(file_path, repo_root))
    
    # Calculate summary statistics
    total_functions = len(all_functions)
    missing_docstrings = [f for f in all_functions if not f["has_docstring"]]
    total_missing = len(missing_docstrings)
    
    # Complexity distribution
    complexity_dist = {
        "low": len([f for f in all_functions if f["complexity_category"] == "low"]),
        "medium": len([f for f in all_functions if f["complexity_category"] == "medium"]),
        "high": len([f for f in all_functions if f["complexity_category"] == "high"])
    }
    
    # Security issues summary
    funcs_with_security_issues = [f for f in all_functions if f["security_issues"]]
    security_issue_counts = {}
    for f in funcs_with_security_issues:
        for issue in f["security_issues"]:
            security_issue_counts[issue] = security_issue_counts.get(issue, 0) + 1
    
    # Governance priority: sort by priority score descending
    governance_priorities = sorted(
        [f for f in all_functions if f["priority_score"] > 0],
        key=lambda x: x["priority_score"],
        reverse=True
    )
    
    report = {
        "metadata": {
            "scan_targets": [Path(f).relative_to(repo_root).as_posix() for f in target_files],
            "total_functions_scanned": total_functions,
            "total_missing_docstrings": total_missing,
            "scan_tool": "code_quality_ast_scan.py (Phase A1 baseline)"
        },
        "summary": {
            "docstring_gap": {
                "total_missing": total_missing,
                "public_missing": len([f for f in missing_docstrings if f["is_public"]]),
                "private_missing": len([f for f in missing_docstrings if not f["is_public"]])
            },
            "complexity_distribution": complexity_dist,
            "security_issues": {
                "functions_with_issues": len(funcs_with_security_issues),
                "issue_type_counts": security_issue_counts
            }
        },
        "governance_priorities": governance_priorities[:50],  # Top 50 priorities
        "all_functions": all_functions
    }
    
    # Write JSON report
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report


if __name__ == "__main__":
    # Target files relative to repo root
    REPO_ROOT = Path(__file__).parent.parent
    TARGET_FILES = [
        REPO_ROOT / "hermes_cli" / "main.py",
        REPO_ROOT / "hermes_cli" / "auth.py",
        REPO_ROOT / "hermes_cli" / "gateway.py",
        REPO_ROOT / "hermes_cli" / "config.py",
        REPO_ROOT / "hermes_cli" / "models.py"
    ]
    TARGET_FILES = [str(p) for p in TARGET_FILES]
    
    OUTPUT_PATH = REPO_ROOT / "code_quality_report.json"
    
    print(f"Scanning {len(TARGET_FILES)} target files...")
    report = generate_report(TARGET_FILES, str(OUTPUT_PATH), REPO_ROOT)
    
    print(f"Scan complete. Report written to {OUTPUT_PATH}")
    print(f"Total functions scanned: {report['metadata']['total_functions_scanned']}")
    print(f"Total missing docstrings: {report['metadata']['total_missing_docstrings']}")
    print(f"Governance priorities (top 5):")
    for i, p in enumerate(report["governance_priorities"][:5], 1):
        print(f"  {i}. {p['function']} ({p['file'].split('/')[-1]}:{p['line']}) - Score: {p['priority_score']}")
