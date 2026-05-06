#!/usr/bin/env python3
"""AST-based code quality analyzer for Hermes CLI modules."""

import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


def calculate_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity of a function."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def analyze_function(func_node: ast.FunctionDef, filename: str) -> Dict[str, Any]:
    """Analyze a single function definition."""
    has_docstring = ast.get_docstring(func_node) is not None
    complexity = calculate_complexity(func_node)

    # Check for security patterns
    security_issues = []

    for node in ast.walk(func_node):
        # Check for hardcoded secrets
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(keyword in node.value.lower() for keyword in ['password', 'secret', 'api_key', 'token']):
                if len(node.value) > 10:  # Likely a real value, not a placeholder
                    security_issues.append({
                        'type': 'potential_hardcoded_secret',
                        'line': node.lineno,
                        'description': 'Potential hardcoded secret detected'
                    })

        # Check for shell injection risks
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ['os.system', 'subprocess.call', 'subprocess.run']:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if ';' in arg.value or '&&' in arg.value or '|' in arg.value:
                            security_issues.append({
                                'type': 'shell_injection_risk',
                                'line': node.lineno,
                                'description': 'Potential shell injection in system call'
                            })

        # Check for eval/exec usage
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
                security_issues.append({
                    'type': 'unsafe_eval_exec',
                    'line': node.lineno,
                    'description': 'Use of eval() or exec() detected'
                })

    return {
        'name': func_node.name,
        'line': func_node.lineno,
        'has_docstring': has_docstring,
        'complexity': complexity,
        'args_count': len(func_node.args.args),
        'security_issues': security_issues,
        'is_async': isinstance(func_node, ast.AsyncFunctionDef)
    }


def analyze_class(class_node: ast.ClassDef, filename: str) -> Dict[str, Any]:
    """Analyze a class definition."""
    methods = []
    for node in ast.walk(class_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.col_offset > class_node.col_offset:  # Only direct methods
                methods.append(analyze_function(node, filename))

    return {
        'name': class_node.name,
        'line': class_node.lineno,
        'has_docstring': ast.get_docstring(class_node) is not None,
        'methods': methods,
        'method_count': len(methods)
    }


def analyze_file(filepath: str) -> Dict[str, Any]:
    """Analyze a single Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {'error': f'Syntax error: {e}', 'filepath': filepath}

    functions = []
    classes = []
    imports = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(analyze_function(node, filepath))
        elif isinstance(node, ast.ClassDef):
            classes.append(analyze_class(node, filepath))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                module = node.module or ''
                for alias in node.names:
                    imports.append(f'{module}.{alias.name}' if module else alias.name)

    # Calculate file-level metrics
    total_functions = len(functions) + sum(len(c['methods']) for c in classes)
    functions_without_docstrings = (
        sum(1 for f in functions if not f['has_docstring']) +
        sum(1 for c in classes for m in c['methods'] if not m['has_docstring'])
    )

    return {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'functions': functions,
        'classes': classes,
        'imports': imports,
        'metrics': {
            'total_functions': total_functions,
            'functions_without_docstrings': functions_without_docstrings,
            'docstring_coverage': (
                (total_functions - functions_without_docstrings) / total_functions * 100
                if total_functions > 0 else 100
            ),
            'avg_complexity': (
                sum(f['complexity'] for f in functions) / len(functions)
                if functions else 0
            ),
            'max_complexity': (
                max(f['complexity'] for f in functions)
                if functions else 0
            ),
            'total_security_issues': (
                sum(len(f['security_issues']) for f in functions) +
                sum(len(m['security_issues']) for c in classes for m in c['methods'])
            ),
            'class_count': len(classes),
            'import_count': len(imports)
        }
    }


def generate_governance_recommendations(analysis_results: List[Dict]) -> List[Dict]:
    """Generate governance priority recommendations based on analysis."""
    recommendations = []

    for result in analysis_results:
        if 'error' in result:
            continue

        filename = result['filename']
        metrics = result['metrics']

        # HIGH priority: Low docstring coverage
        if metrics['docstring_coverage'] < 50:
            recommendations.append({
                'priority': 'HIGH',
                'file': filename,
                'issue': 'Low docstring coverage',
                'value': f"{metrics['docstring_coverage']:.1f}%",
                'recommendation': 'Add docstrings to all public functions and classes'
            })

        # HIGH priority: High complexity functions
        for func in result['functions']:
            if func['complexity'] > 15:
                recommendations.append({
                    'priority': 'HIGH',
                    'file': filename,
                    'issue': 'High complexity function',
                    'value': f"{func['name']} (complexity: {func['complexity']})",
                    'recommendation': 'Refactor function to reduce cyclomatic complexity'
                })

        # MEDIUM priority: Security issues
        for func in result['functions']:
            for issue in func['security_issues']:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'file': filename,
                    'issue': 'Security concern',
                    'value': f"{func['name']}: {issue['type']} at line {issue['line']}",
                    'recommendation': issue['description']
                })

        # MEDIUM priority: Moderate docstring coverage
        if 50 <= metrics['docstring_coverage'] < 80:
            recommendations.append({
                'priority': 'MEDIUM',
                'file': filename,
                'issue': 'Moderate docstring coverage',
                'value': f"{metrics['docstring_coverage']:.1f}%",
                'recommendation': 'Improve documentation coverage for better maintainability'
            })

        # LOW priority: General code quality
        if metrics['class_count'] > 5 and metrics['docstring_coverage'] < 90:
            recommendations.append({
                'priority': 'LOW',
                'file': filename,
                'issue': 'Code quality improvement',
                'value': f"{metrics['class_count']} classes, {metrics['docstring_coverage']:.1f}% docstrings",
                'recommendation': 'Consider comprehensive documentation review'
            })

    return sorted(recommendations, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[x['priority']])


def main():
    """Main entry point."""
    base_dir = Path('/workspace/rigs/32c6c066-3630-409b-9f13-9c84dec5f780/worktrees/gt__maple__eaecd20f/hermes_cli')
    target_files = ['main.py', 'auth.py', 'gateway.py', 'config.py', 'models.py']

    results = []
    for filename in target_files:
        filepath = base_dir / filename
        if filepath.exists():
            analysis = analyze_file(str(filepath))
            results.append(analysis)
        else:
            results.append({'error': 'File not found', 'filepath': str(filepath)})

    # Generate governance recommendations
    recommendations = generate_governance_recommendations(results)

    # Compile final report
    report = {
        'metadata': {
            'analyzer': 'Sage Code Quality Analyzer',
            'target_files': target_files,
            'base_directory': str(base_dir)
        },
        'files': results,
        'summary': {
            'total_files_analyzed': len([r for r in results if 'error' not in r]),
            'total_functions': sum(r.get('metrics', {}).get('total_functions', 0) for r in results if 'error' not in r),
            'total_classes': sum(r.get('metrics', {}).get('class_count', 0) for r in results if 'error' not in r),
            'average_docstring_coverage': (
                sum(r.get('metrics', {}).get('docstring_coverage', 0) for r in results if 'error' not in r) /
                len([r for r in results if 'error' not in r])
                if any('error' not in r for r in results) else 0
            ),
            'total_security_issues': sum(r.get('metrics', {}).get('total_security_issues', 0) for r in results if 'error' not in r)
        },
        'governance_recommendations': recommendations
    }

    # Output JSON report
    print(json.dumps(report, indent=2))

    # Save to file
    output_path = Path('/workspace/rigs/32c6c066-3630-409b-9f13-9c84dec5f780/worktrees/gt__maple__eaecd20f/code_quality_report.json')
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == '__main__':
    main()
