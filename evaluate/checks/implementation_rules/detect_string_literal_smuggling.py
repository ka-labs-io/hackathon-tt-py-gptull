#!/usr/bin/env python3
"""
detect_string_literal_smuggling.py — detect implementation code hidden as
string literals inside the translator.

A common evasion of ``detect_code_block_copying`` is to wrap each output
line in a ``lines.append("...")`` call inside the translator.  The
translator's raw source line is then ``lines.append("def foo():")`` while
the emitted output line is ``def foo():`` — they are different normalized
lines, so the line-by-line copying detector misses the match.  But the
string literal *value* ``def foo():`` is exactly the line that appears
verbatim in the output, which is just templated copying with extra steps.

This check walks every .py file under ``tt/tt/`` (excluding the wrapper
layer), collects every string-constant value, splits multi-line strings
on newlines, normalizes each piece, and counts how many of those pieces
appear verbatim in the translation output.  Files whose string literals
contribute more than ``MAX_SMUGGLED_LINES`` matching lines are flagged.

A handful of legitimate matches are allowed for boilerplate (a single
``from __future__ import annotations`` header, etc.); the threshold is
set well below the size of any meaningful pre-written class or stub.

Usage:
  python detect_string_literal_smuggling.py
  pytest detect_string_literal_smuggling.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"
TRANSLATION_ROOT = PROJECT_ROOT / "translations" / "ghostfolio_pytx"

# More than this many string-literal lines from a single tt file matching
# verbatim output lines is treated as smuggled implementation code.
MAX_SMUGGLED_LINES = 5

# Lines shorter than this many characters are ignored — they catch trivial
# tokens like ``)``, ``""`` or ``pass`` that legitimately overlap.
MIN_LINE_LENGTH = 4

# Wrapper folder is excluded: those files are intentionally laid down
# verbatim by the translator copy step and have their own integrity check.
_WRAPPER_ROOT = TT_ROOT / "scaffold" / "ghostfolio_pytx" / "app" / "wrapper"


def _normalize(line: str) -> str:
    return line.strip()


def _output_line_set() -> set[str]:
    """Collect every normalized non-trivial line from the translation output."""
    if not TRANSLATION_ROOT.exists():
        return set()
    out: set[str] = set()
    for path in TRANSLATION_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = _normalize(raw)
            if (
                stripped
                and not stripped.startswith("#")
                and len(stripped) >= MIN_LINE_LENGTH
            ):
                out.add(stripped)
    return out


def _tt_files() -> list[Path]:
    if not TT_ROOT.exists():
        return []
    files: list[Path] = []
    for path in sorted(TT_ROOT.rglob("*.py")):
        if not path.is_file():
            continue
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_relative_to(_WRAPPER_ROOT):
            continue
        files.append(path)
    return files


def _string_constants(tree: ast.AST) -> list[tuple[int, str]]:
    """Return (lineno, value) for every string constant in the AST."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value))
    return out


def _matching_lines(
    constants: list[tuple[int, str]],
    output_lines: set[str],
) -> list[tuple[int, str]]:
    """For each string constant, return (lineno, line) for any of its split
    lines that appear verbatim in the output."""
    matches: list[tuple[int, str]] = []
    for lineno, value in constants:
        for piece in value.splitlines():
            stripped = _normalize(piece)
            if (
                stripped
                and len(stripped) >= MIN_LINE_LENGTH
                and stripped in output_lines
            ):
                matches.append((lineno, stripped))
    return matches


def scan() -> list[str]:
    """Walk tt/ string literals and flag files with too many matching pieces."""
    output_lines = _output_line_set()
    if not output_lines:
        return []

    violations: list[str] = []
    for path in _tt_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue

        constants = _string_constants(tree)
        matches = _matching_lines(constants, output_lines)
        if len(matches) > MAX_SMUGGLED_LINES:
            sample = matches[0]
            violations.append(
                f"{path.relative_to(PROJECT_ROOT)}: {len(matches)} string-literal "
                f"lines appear verbatim in translation output (max "
                f"{MAX_SMUGGLED_LINES}). First match at line {sample[0]}: "
                f"{sample[1]!r} — implementation code must be derived from the "
                "TypeScript source, not stored as string templates"
            )
    return violations


def test_no_string_literal_smuggling():
    """tt must not embed implementation code as string literals."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"String-literal smuggling detected ({len(violations)} finding(s)):\n"
            f"{report}\n\n"
            "Wrapping output lines in append(...) calls inside the translator "
            "is just pre-written templating with extra syntax — the same "
            "lines still ship to the output verbatim."
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Possible string-literal smuggling in tt/!\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} finding(s) total.\n"
            "Implementation code must be derived from the TS source, "
            "not stored as templates."
        )
        sys.exit(1)
    else:
        print("OK: No string-literal smuggling detected.")
        sys.exit(0)
