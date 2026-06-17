---
name: code-reviewer
description: Analyzes local files for common errors, style violations, and potential bugs. Use when Gemini CLI needs to inspect code quality, audit Python files, or review changes for coding standards and best practices.
---

# Code Reviewer

## Overview

The Code Reviewer skill enables Gemini CLI to perform fast, automated static analysis of local files. It identifies common programming errors, design complexity, style violations, and left-over debug statements to ensure a high-quality codebase.

## Quick Start

You can invoke the automated review script to analyze files and directories in the workspace.

### Core Command

To run a full audit on the current workspace:
```bash
python <path-to-skill>/scripts/review.py .
```

To run an audit on a specific file or folder:
```bash
python <path-to-skill>/scripts/review.py path/to/file_or_dir.py
```

### Options

- **JSON Output** (`--json`): Get a structured JSON representation of the issues. Excellent for machine-readable analysis.
  ```bash
  python <path-to-skill>/scripts/review.py . --json
  ```
- **Exclude Directories** (`--exclude`): Ignore additional directories (in addition to standard defaults like `.venv`, `.git`, etc.).
  ```bash
  python <path-to-skill>/scripts/review.py . --exclude build tests/fixtures
  ```

---

## Workflow Decision Tree

When a user requests a code review or you need to verify code changes, follow this workflow:

```
                  [Code Review Request]
                            │
              1. Identify files to review
              (git status or specified paths)
                            │
                            ▼
              2. Run the review.py script
                            │
                            ▼
              3. Analyze output report
             /                        \
    (Issues Found)              (No Issues Found)
          /                              \
         ▼                                ▼
4. Propose surgical fixes          5. Report "Clean Code"
  and explain patterns                      and finalize!
         │
         ▼
6. Re-run review.py to verify
```

### Step 1: Identify Files
Determine which files need review.
- If the user specified a file/directory, target those.
- If the user wants a general review or you want to check your own changes, use `git status` to find modified/added files.

### Step 2: Run Analysis
Run the `review.py` script targeting the identified paths.

### Step 3: Present Findings
Format the findings nicely for the user. Highlight:
- 🔴 **Errors**: High risk, bugs, or fatal code issues (mutable defaults, empty exception blocks, syntax errors).
- 🟡 **Warnings**: Non-fatal but problematic code (unused imports, wildcard imports, too many parameters).
- 🔵 **Info**: Style or formatting hints (trailing whitespaces, long lines, missing docstrings).

### Step 4: Fix and Verify
Apply targeted, surgical fixes to address the identified issues, then re-run the `review.py` script to verify that the issues have been successfully resolved.

---

## Reference Patterns & Guidelines

For detailed information on the specific code issues caught by this reviewer and instructions on how to refactor them, refer directly to:

- **[Common Code Quality & Style Patterns](references/common-patterns.md)**: A comprehensive guide covering mutable default arguments, bare exceptions, shadowing python built-ins, and leftover debug statements.
