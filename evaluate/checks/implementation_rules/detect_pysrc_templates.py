#!/usr/bin/env python3
"""
detect_pysrc_templates.py — detect .pysrc (or similar) template files in tt/
that bypass .py-based rule checks.

Storing Python implementation code in non-.py files (e.g. .pysrc, .pytmpl,
.py.src, .txt) and copying/renaming them to .py at translate time is a way
to evade financial-logic, domain-identifier, and code-block-copying checks
that only scan *.py files.

This check flags any file under tt/ whose content looks like Python source
but uses a non-.py extension.

Usage:
  python detect_pysrc_templates.py
  pytest detect_pysrc_templates.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"

# Extensions that are legitimately non-Python
SAFE_EXTENSIONS = frozenset({
    ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cfg",
    ".ini", ".lock", ".keep", ".gitignore", ".egg-info",
})

# Known Python-like extensions used to bypass checks
SUSPICIOUS_EXTENSIONS = frozenset({
    ".pysrc", ".pytmpl", ".py.src", ".pysource", ".pytemplate",
    ".py_template", ".py_src",
})


def _looks_like_python(content: str) -> bool:
    """Check if file content is valid Python source code."""
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def scan() -> list[str]:
    """Scan tt/ for non-.py files containing Python source code."""
    if not TT_ROOT.exists():
        return []

    violations: list[str] = []

    for path in sorted(TT_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".py":
            continue
        if path.suffix in SAFE_EXTENSIONS:
            continue
        # Skip .venv and __pycache__
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if "egg-info" in str(path):
            continue

        # Check for known suspicious extensions
        if path.suffix in SUSPICIOUS_EXTENSIONS:
            violations.append(
                f"{path}: file uses suspicious extension '{path.suffix}' "
                "— Python implementation must use .py extension so that "
                "rule checks can scan it"
            )
            continue

        # For other unknown extensions, check if content is valid Python
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        if len(content) > 100 and _looks_like_python(content):
            violations.append(
                f"{path}: non-.py file contains valid Python source "
                f"({len(content)} chars) — rename to .py so rule checks "
                "can scan it"
            )

    return violations


def test_no_pysrc_templates():
    """tt must not use non-.py files to hide Python implementation code."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Template file bypass detected ({len(violations)} finding(s)):\n"
            f"{report}\n\n"
            "Python implementation code must use .py extension so that "
            "automated rule checks (financial logic, domain identifiers, "
            "code block copying) can properly scan it."
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Non-.py Python template files found in tt/!\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} finding(s) total.\n"
            "Python code must use .py extension for rule check coverage."
        )
        sys.exit(1)
    else:
        print("OK: No template file bypasses found in tt/.")
        sys.exit(0)
