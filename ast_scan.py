#!/usr/bin/env python3
"""
AST Code Quality Scanner for hermes_cli modules - Optimized version.
Scans target files for documentation gaps, security patterns, and complexity metrics.
"""

import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

def scan_file(filepath: str) -> Dict[str, Any]:
    """Scan a single Python file and return quality metrics."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {'error': str(e), 'file': os.path.basename(filepath)}

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {'error': f"Syntax error: {e}", 'file': os.path.basename(filepath)}

    functions = []
    classes = []
    functions_without_docstrings = []
    all_security_issues = []
    complexity_sum = 0
    max_complexity = 0
    high_complexity_funcs = []

    # Visit all nodes efficiently
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Get docstring
            has_doc = False
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                has_doc = True

            # Count arguments
            args = node.args
            num_args = len(args.args) + len(args.kwonlyargs)
            if args.vararg:
                num_args += 1
            if args.kwarg:
                num_args += 1

            # Calculate cyclomatic complexity
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1

            complexity_sum += complexity
            max_complexity = max(max_complexity, complexity)

            if complexity > 10:
                high_complexity_funcs.append({
                    'name': node.name,
                    'complexity': complexity,
                    'line': node.lineno
                })

            # Count statements
            num_returns = sum(1 for child in ast.walk(node) if isinstance(child, ast.Return))
            num_if = sum(1 for child in ast.walk(node) if isinstance(child, ast.If))
            num_loops = sum(1 for child in ast.walk(node) if isinstance(child, (ast.For, ast.While)))
            num_try = sum(1 for child in ast.walk(node) if isinstance(child, ast.Try))

            # Get line numbers
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
            loc = end_line - node.lineno + 1

            func_info = {
                'name': node.name,
                'line': node.lineno,
                'end_line': end_line,
                'has_docstring': has_doc,
                'cyclomatic_complexity': complexity,
                'lines_of_code': loc,
                'num_args': num_args,
                'num_returns': num_returns,
                'num_if_statements': num_if,
                'num_loops': num_loops,
                'num_try_except': num_try,
            }

            functions.append(func_info)

            if not has_doc:
                functions_without_docstrings.append({
                    'name': node.name,
                    'line': node.lineno
                })

            # Security check
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id in ['eval', 'exec']:
                        all_security_issues.append(f"Dangerous {child.func.id}() at line {child.lineno}")
                    elif isinstance(child.func, ast.Attribute):
                        if child.func.attr in ['system', 'popen'] and isinstance(child.func.value, ast.Name):
                            if child.func.value.id in ['os', 'subprocess']:
                                all_security_issues.append(f"System call {child.func.value.id}.{child.func.attr}() at line {child.lineno}")

        elif isinstance(node, ast.ClassDef):
            has_doc = False
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                has_doc = True

            methods = []
            class_no_doc = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_has_doc = False
                    if item.body and isinstance(item.body[0], ast.Expr) and isinstance(item.body[0].value, ast.Constant) and isinstance(item.body[0].value.value, str):
                        method_has_doc = True
                    methods.append({'name': item.name, 'has_docstring': method_has_doc})
                    if not method_has_doc:
                        class_no_doc.append(f"{node.name}.{item.name}")

            classes.append({
                'name': node.name,
                'line': node.lineno,
                'has_docstring': has_doc,
                'total_methods': len(methods),
                'methods_without_docstrings': class_no_doc
            })
            functions_without_docstrings.extend([{'name': m, 'line': 0} for m in class_no_doc])

    # Calculate metrics
    total_functions = len(functions)
    functions_with_docstrings = sum(1 for f in functions if f['has_docstring'])
    total_classes = len(classes)
    classes_with_docstrings = sum(1 for c in classes if c['has_docstring'])

    source_lines = source.splitlines()
    total_loc = len(source_lines)
    code_lines = sum(1 for line in source_lines if line.strip() and not line.strip().startswith('#'))

    avg_complexity = complexity_sum / total_functions if total_functions > 0 else 0

    return {
        'file': os.path.basename(filepath),
        'full_path': filepath,
        'total_lines': total_loc,
        'code_lines': code_lines,
        'total_functions': total_functions,
        'functions_with_docstrings': functions_with_docstrings,
        'functions_without_docstrings_list': functions_without_docstrings,
        'docstring_coverage_percent': (functions_with_docstrings / total_functions * 100) if total_functions > 0 else 100,
        'total_classes': total_classes,
        'classes_with_docstrings': classes_with_docstrings,
        'avg_cyclomatic_complexity': round(avg_complexity, 2),
        'max_cyclomatic_complexity': max_complexity,
        'high_complexity_functions': high_complexity_funcs,
        'security_issues': all_security_issues,
    }

def generate_governance_recommendations(scan_results: List[Dict]) -> List[Dict]:
    """Generate governance recommendations based on scan results."""
    recommendations = []

    for result in scan_results:
        if 'error' in result:
            continue

        file = result['file']

        if result['docstring_coverage_percent'] < 80:
            recommendations.append({
                'priority': 'HIGH',
                'file': file,
                'category': 'Documentation',
                'issue': f"Low docstring coverage: {result['docstring_coverage_percent']:.1f}%",
                'action': f"Add docstrings to {len(result['functions_without_docstrings_list'])} undocumented functions",
                'count': len(result['functions_without_docstrings_list'])
            })

        if result['high_complexity_functions']:
            recommendations.append({
                'priority': 'MEDIUM',
                'file': file,
                'category': 'Complexity',
                'issue': f"{len(result['high_complexity_functions'])} functions with complexity > 10",
                'action': "Refactor high-complexity functions",
                'functions': result['high_complexity_functions'][:5]
            })

        if result['security_issues']:
            recommendations.append({
                'priority': 'HIGH',
                'file': file,
                'category': 'Security',
                'issue': f"{len(result['security_issues'])} potential security issues",
                'action': "Review and fix security vulnerabilities",
                'issues': result['security_issues'][:5]
            })

        if result['total_lines'] > 2000:
            recommendations.append({
                'priority': 'LOW',
                'file': file,
                'category': 'Maintainability',
                'issue': f"Large file: {result['total_lines']} lines",
                'action': "Consider splitting into smaller modules"
            })

    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))

    return recommendations

def main():
    """Main entry point."""
    base_dir = Path(__file__).parent / 'hermes_cli'
    target_files = ['main.py', 'auth.py', 'gateway.py', 'config.py', 'models.py']

    scan_results = []

    for filename in target_files:
        filepath = base_dir / filename
        if filepath.exists():
            print(f"Scanning {filename}...", flush=True)
            result = scan_file(str(filepath))
            scan_results.append(result)
            print(f"  Functions: {result.get('total_functions', 0)}, Coverage: {result.get('docstring_coverage_percent', 0):.1f}%", flush=True)

    recommendations = generate_governance_recommendations(scan_results)

    report = {
        'scan_metadata': {
            'tool': 'AST Code Quality Scanner',
            'target_files': target_files,
            'total_files_scanned': len([r for r in scan_results if 'error' not in r])
        },
        'summary': {
            'total_functions': sum(r.get('total_functions', 0) for r in scan_results if 'error' not in r),
            'total_functions_with_docstrings': sum(r.get('functions_with_docstrings', 0) for r in scan_results if 'error' not in r),
            'total_classes': sum(r.get('total_classes', 0) for r in scan_results if 'error' not in r),
            'total_classes_with_docstrings': sum(r.get('classes_with_docstrings', 0) for r in scan_results if 'error' not in r),
            'total_security_issues': sum(len(r.get('security_issues', [])) for r in scan_results if 'error' not in r),
            'total_high_complexity_functions': sum(len(r.get('high_complexity_functions', [])) for r in scan_results if 'error' not in r),
            'average_docstring_coverage': 0
        },
        'file_results': scan_results,
        'governance_recommendations': recommendations
    }

    total_funcs = report['summary']['total_functions']
    total_docs = report['summary']['total_functions_with_docstrings']
    if total_funcs > 0:
        report['summary']['average_docstring_coverage'] = round(total_docs / total_funcs * 100, 2)

    output_file = Path(__file__).parent / 'code_quality_report.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport written to: {output_file}")

    print("\n=== CODE QUALITY SUMMARY ===")
    print(f"Files scanned: {report['scan_metadata']['total_files_scanned']}")
    print(f"Total functions: {report['summary']['total_functions']}")
    print(f"Functions with docstrings: {report['summary']['total_functions_with_docstrings']}")
    print(f"Docstring coverage: {report['summary']['average_docstring_coverage']}%")
    print(f"Total classes: {report['summary']['total_classes']}")
    print(f"Security issues: {report['summary']['total_security_issues']}")
    print(f"High complexity functions: {report['summary']['total_high_complexity_functions']}")

    print("\n=== TOP GOVERNANCE RECOMMENDATIONS ===")
    for i, rec in enumerate(recommendations[:10], 1):
        print(f"\n{i}. [{rec['priority']}] {rec['file']} - {rec['category']}")
        print(f"   Issue: {rec['issue']}")
        print(f"   Action: {rec['action']}")

    return report

if __name__ == '__main__':
    main()
