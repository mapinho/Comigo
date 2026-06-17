#!/usr/bin/env python3
"""
Code Reviewer CLI Tool
Analyzes local files for common errors, style violations, and potential bugs.
Supports Python (AST-based deep analysis) and general text files (regex/heuristic-based).
"""

import ast
import os
import re
import sys
import argparse
from typing import List, Dict, Any, Tuple, Set

# --- CONSTANTS & CONFIGURATION ---
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", 
    ".vscode", ".devcontainer", "dist", "build", ".mypy_cache", ".pytest_cache"
}

BUILTINS_TO_CHECK = {
    "id", "type", "input", "open", "sum", "min", "max", "list", 
    "dict", "set", "tuple", "str", "int", "float", "bool", "all", "any"
}

# Regex patterns
SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UPPER_CASE_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)


# --- PYTHON AST VISITOR FOR DEEP ANALYSIS ---
class PythonReviewVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, content: str):
        self.filename = filename
        self.content_lines = content.splitlines()
        self.issues: List[Dict[str, Any]] = []
        
        # Track imports and usage
        # Format: {imported_name: (line_no, alias_name_or_original)}
        self.imported_names: Dict[str, Tuple[int, str]] = {}
        self.used_names: Set[str] = set()
        
        # Track all function names to avoid false positive unused variable triggers
        self.defined_functions: Set[str] = set()
        self.defined_classes: Set[str] = set()

    def add_issue(self, category: str, line: int, col: int, message: str, severity: str = "warning"):
        self.issues.append({
            "file": self.filename,
            "line": line,
            "col": col,
            "category": category,
            "message": message,
            "severity": severity
        })

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_names[name] = (node.lineno, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module == "__future__":
            return
        for alias in node.names:
            if alias.name == "*":
                self.add_issue(
                    "Style", node.lineno, node.col_offset,
                    f"Wildcard import used: 'from {node.module} import *'. This pollutes the namespace.",
                    "warning"
                )
            else:
                name = alias.asname or alias.name
                self.imported_names[name] = (node.lineno, f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # We also want to record attribute access if it matches pdb.set_trace, etc.
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.defined_functions.add(node.name)
        
        # Check docstring
        docstring = ast.get_docstring(node)
        is_private = node.name.startswith("_") and not (node.name.startswith("__") and node.name.endswith("__"))
        if not docstring and not is_private:
            self.add_issue(
                "Documentation", node.lineno, node.col_offset,
                f"Missing docstring for public function/method '{node.name}'.",
                "info"
            )

        # Check naming convention
        if not SNAKE_CASE_RE.match(node.name) and not (node.name.startswith("__") and node.name.endswith("__")):
            self.add_issue(
                "Style", node.lineno, node.col_offset,
                f"Function name '{node.name}' should follow snake_case convention.",
                "warning"
            )

        # Check parameter count
        total_args = len(node.args.args) + len(node.args.kwonlyargs)
        if node.args.vararg:
            total_args += 1
        if node.args.kwarg:
            total_args += 1
        if total_args > 5:
            self.add_issue(
                "Complexity", node.lineno, node.col_offset,
                f"Function '{node.name}' has too many arguments ({total_args} > 5). Consider refactoring.",
                "warning"
            )

        # Check function length
        if hasattr(node, "end_lineno") and node.end_lineno:
            length = node.end_lineno - node.lineno + 1
            if length > 50:
                self.add_issue(
                    "Complexity", node.lineno, node.col_offset,
                    f"Function '{node.name}' is too long ({length} lines > 50). Consider splitting it.",
                    "warning"
                )

        # Check mutable default arguments
        self._check_mutable_defaults(node.args.defaults, node.lineno)
        self._check_mutable_defaults(node.args.kw_defaults, node.lineno)

        self.generic_visit(node)

    def _check_mutable_defaults(self, defaults: List[ast.expr], lineno: int):
        for default in defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.add_issue(
                    "Error-prone", lineno, default.col_offset,
                    "Using mutable default argument (list, dict, or set). This shares state across calls.",
                    "error"
                )
            elif isinstance(default, ast.Call):
                # Check for list(), dict(), set()
                if isinstance(default.func, ast.Name) and default.func.id in {"list", "dict", "set"}:
                    self.add_issue(
                        "Error-prone", lineno, default.col_offset,
                        f"Using mutable default argument call {default.func.id}(). This shares state across calls.",
                        "error"
                    )

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defined_classes.add(node.name)
        
        # Check docstring
        docstring = ast.get_docstring(node)
        if not docstring and not node.name.startswith("_"):
            self.add_issue(
                "Documentation", node.lineno, node.col_offset,
                f"Missing docstring for public class '{node.name}'.",
                "info"
            )

        # Check naming convention
        if not PASCAL_CASE_RE.match(node.name):
            self.add_issue(
                "Style", node.lineno, node.col_offset,
                f"Class name '{node.name}' should follow PascalCase convention.",
                "warning"
            )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Check for empty/bare except handler
        is_empty = False
        if len(node.body) == 1:
            item = node.body[0]
            if isinstance(item, ast.Pass):
                is_empty = True
            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                # Just a docstring/string literal
                is_empty = True

        if is_empty:
            # Check if it catches everything
            catches_all = False
            if node.type is None:
                catches_all = True
            elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
                catches_all = True
            
            if catches_all:
                self.add_issue(
                    "Error-prone", node.lineno, node.col_offset,
                    "Empty except block catching Exception/BaseException. This hides bugs/errors.",
                    "error"
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check for shadowing builtins
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                if name in BUILTINS_TO_CHECK:
                    self.add_issue(
                        "Error-prone", node.lineno, target.col_offset,
                        f"Variable '{name}' shadows a Python built-in name. This can lead to unexpected behavior.",
                        "warning"
                    )
                # Check variable naming style
                if not SNAKE_CASE_RE.match(name) and not UPPER_CASE_RE.match(name):
                    self.add_issue(
                        "Style", node.lineno, target.col_offset,
                        f"Variable '{name}' should follow snake_case or UPPER_CASE convention.",
                        "info"
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for breakpoint() or print() or pdb.set_trace()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name == "breakpoint":
                self.add_issue(
                    "Debug-leftover", node.lineno, node.col_offset,
                    "Active 'breakpoint()' found. Remove debug triggers before production.",
                    "error"
                )
            elif func_name == "print":
                self.add_issue(
                    "Debug-leftover", node.lineno, node.col_offset,
                    "Standard 'print()' function found. Prefer structured logging over print statements.",
                    "info"
                )
        elif isinstance(node.func, ast.Attribute):
            # Check for pdb.set_trace()
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "pdb" and node.func.attr == "set_trace":
                self.add_issue(
                    "Debug-leftover", node.lineno, node.col_offset,
                    "Active 'pdb.set_trace()' found. Remove debug triggers before production.",
                    "error"
                )
        self.generic_visit(node)

    def finalize_and_get_issues(self) -> List[Dict[str, Any]]:
        # Check for unused imports
        for imported, (line, full_path) in self.imported_names.items():
            if imported not in self.used_names:
                # Double-check if imported is referenced in __all__
                # Simple check for safety: if '__all__' is defined, we skip warning if name is in file content
                # For simplicity, if we don't see it used as Name, flag it
                # Skip if it is a common pattern like '__init__.py' and imported is just being re-exported
                is_init = self.filename.endswith("__init__.py")
                if not is_init:
                    self.add_issue(
                        "Unused-import", line, 0,
                        f"Imported name '{imported}' ({full_path}) is unused in this file.",
                        "warning"
                    )
        return self.issues


# --- GENERAL TEXT/REGEX-BASED FILE ANALYSIS ---
def analyze_general_file(filename: str, content: str) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    lines = content.splitlines()
    ext = os.path.splitext(filename)[1].lower()

    for idx, line in enumerate(lines, 1):
        # Rule 1: Line length limit
        if len(line) > 120:
            # Skip long lines in SVG, Markdown or JSON, which naturally have long lines
            if ext not in {".svg", ".json", ".md", ".ipynb", ".xlsx", ".csv"}:
                issues.append({
                    "file": filename,
                    "line": idx,
                    "col": 120,
                    "category": "Style",
                    "message": f"Line exceeds 120 characters ({len(line)} characters).",
                    "severity": "info"
                })

        # Rule 2: Trailing whitespaces
        if line.rstrip() != line:
            # Skip if empty trailing whitespace is in markdown (used for line break)
            if not (ext == ".md" and line.endswith("  ")):
                issues.append({
                    "file": filename,
                    "line": idx,
                    "col": len(line),
                    "category": "Style",
                    "message": "Line has trailing whitespaces.",
                    "severity": "info"
                })

        # Rule 3: TODO / FIXME detector
        todo_match = TODO_RE.search(line)
        if todo_match:
            issues.append({
                "file": filename,
                "line": idx,
                "col": todo_match.start() + 1,
                "category": "Todo",
                "message": f"Found unresolved task marker: '{todo_match.group(1)}' in line.",
                "severity": "info"
            })

        # Rule 4: Tab characters inside file (prefer spaces)
        if "\t" in line:
            if ext not in {".tsv", ".mk", "makefile", "Makefile"}:
                issues.append({
                    "file": filename,
                    "line": idx,
                    "col": line.find("\t") + 1,
                    "category": "Style",
                    "message": "Line contains Tab character. Use spaces for indentation.",
                    "severity": "warning"
                })

        # Rule 5: JS/TS specific console.log
        if ext in {".js", ".jsx", ".ts", ".tsx"}:
            if "console.log" in line:
                issues.append({
                    "file": filename,
                    "line": idx,
                    "col": line.find("console.log") + 1,
                    "category": "Debug-leftover",
                    "message": "Found console.log(). Prefer a structured logging library or remove before production.",
                    "severity": "info"
                })

    return issues


# --- FILE PARSING ROUTER ---
def review_file(file_path: str) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    
    # Try reading file safely
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return [{
            "file": file_path,
            "line": 0,
            "col": 0,
            "category": "System",
            "message": f"Failed to read file: {e}",
            "severity": "error"
        }]

    ext = os.path.splitext(file_path)[1].lower()

    # If Python, do deep AST analysis + generic text analysis
    if ext == ".py":
        # 1. Check syntax first by trying to parse it
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = PythonReviewVisitor(file_path, content)
            visitor.visit(tree)
            issues.extend(visitor.finalize_and_get_issues())
        except SyntaxError as se:
            issues.append({
                "file": file_path,
                "line": se.lineno or 0,
                "col": se.offset or 0,
                "category": "Syntax-Error",
                "message": f"Syntax Error: {se.msg}",
                "severity": "error"
            })
        
        # 2. General text checks for python files too (todo, trailing whitespace, long lines, etc.)
        issues.extend(analyze_general_file(file_path, content))
    else:
        # Non-python files just get generic regex and text audits
        issues.extend(analyze_general_file(file_path, content))

    return issues


# --- DISCOVER FILES ---
def find_files_to_review(targets: List[str], exclude_dirs: Set[str]) -> List[str]:
    files_to_review: List[str] = []
    for target in targets:
        if os.path.isfile(target):
            files_to_review.append(target)
        elif os.path.isdir(target):
            for root, dirs, files in os.walk(target):
                # Filter out excluded directories in place to prevent os.walk from entering them
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    # Filter out common binary/ignored file formats
                    ext = os.path.splitext(file)[1].lower()
                    if ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".sql", ".sh", ".yml", ".yaml", ".md", ".json"}:
                        files_to_review.append(os.path.join(root, file))
        else:
            print(f"⚠️ Target path not found: {target}", file=sys.stderr)
    return sorted(files_to_review)


# --- FORMAT OUTPUTS ---
def format_markdown_report(all_issues: List[Dict[str, Any]], elapsed_time: float) -> str:
    if not all_issues:
        return "✨ **Clean Code Review! No issues, warnings, or style violations detected.** ✨"

    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in all_issues:
        by_file.setdefault(issue["file"], []).append(issue)

    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in all_issues:
        sev = issue["severity"].lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["warning"] += 1

    report = []
    report.append("# Code Review Analysis Report")
    report.append(f"Analyzed {len(by_file)} files in {elapsed_time:.2f} seconds.")
    report.append(f"**Summary:** 🔴 {counts['error']} Errors | 🟡 {counts['warning']} Warnings | 🔵 {counts['info']} Info items\n")

    # Group by file
    for file, file_issues in sorted(by_file.items()):
        # Sort issues by line number
        file_issues.sort(key=lambda x: (x["line"], x["col"]))
        
        # Relative path if possible
        rel_path = os.path.relpath(file) if os.path.isabs(file) else file
        report.append(f"### 📄 `{rel_path}` ({len(file_issues)} issues)")
        
        for issue in file_issues:
            severity_emoji = "🔴" if issue["severity"] == "error" else ("🟡" if issue["severity"] == "warning" else "🔵")
            cat = issue["category"]
            line = issue["line"]
            col = issue["col"]
            msg = issue["message"]
            
            report.append(f"- {severity_emoji} **[{cat}]** Line {line}:{col} - {msg}")
        report.append("")

    return "\n".join(report)


# --- MAIN ---
def main():
    import time
    start_time = time.time()

    parser = argparse.ArgumentParser(description="Static code analyzer for common errors, style, and debug leftovers.")
    parser.add_argument("targets", nargs="*", default=["."], help="Files or folders to analyze. Defaults to current directory.")
    parser.add_argument("--exclude", nargs="*", help="Directories to ignore in addition to defaults.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    parser.add_argument("--markdown", action="store_true", default=True, help="Output results in a formatted Markdown report (default).")
    
    args = parser.parse_args()

    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    if args.exclude:
        exclude_dirs.update(args.exclude)

    files = find_files_to_review(args.targets, exclude_dirs)
    
    all_issues: List[Dict[str, Any]] = []
    for file in files:
        # Avoid analyzing the reviewer script itself to prevent recursion self-auditing reports
        if os.path.basename(file) == "review.py":
            continue
        all_issues.extend(review_file(file))

    elapsed = time.time() - start_time

    if args.json:
        import json
        print(json.dumps({
            "elapsed_seconds": elapsed,
            "total_issues": len(all_issues),
            "issues": all_issues
        }, indent=2))
    else:
        print(format_markdown_report(all_issues, elapsed))


if __name__ == "__main__":
    main()
