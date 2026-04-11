#!/usr/bin/env python3
"""
detect_premade_calculator.py — detect pre-made implementation code in tt/scaffold.

The translator must actually produce implementation code from the TypeScript
source.  Storing the implementation as a static file inside tt/scaffold and
copying it verbatim into the output is "pre-made logic", not translation.

This check scans the **entire** scaffold (not just app/implementation/) so
that splitting domain logic into helper modules under app/lib/, app/utils/,
or any other path cannot evade detection.  Only the immutable wrapper layer
(``app/wrapper/`` and ``app/main.py``) is excluded — those files are
intentionally laid down verbatim by the translator and are checked for
byte-equality elsewhere.

Two-stage detection:

  1. Exact-file match — for each non-empty .py file under the translation
     output, check whether the same file exists byte-for-byte under the
     scaffold (excluding wrapper files).  If so, warn that the file is
     likely pre-made.

  2. Method-level block match — if no exact file matches, look for any
     method whose body shares more than MIN_DUP_LINES contiguous identical
     lines (ignoring leading whitespace) with a method in any scaffold file.

Usage:
  python detect_premade_calculator.py
  pytest detect_premade_calculator.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "translations" / "ghostfolio_pytx"
SCAFFOLD_ROOT = PROJECT_ROOT / "tt" / "tt" / "scaffold" / "ghostfolio_pytx"

# Files inside these scaffold-relative paths are exempt: they are the
# immutable wrapper layer that the translator copies verbatim from the
# example.  Wrapper integrity is enforced by detect_wrapper_modification.
_WRAPPER_PATHS = (
    Path("app") / "wrapper",
    Path("app") / "main.py",
)

# More than this many contiguous identical lines inside a single method body
# is flagged as pre-made block copying.
MIN_DUP_LINES = 5


def _is_wrapper(rel: Path) -> bool:
    """True if a scaffold-relative path belongs to the immutable wrapper layer."""
    for w in _WRAPPER_PATHS:
        if rel == w or rel.is_relative_to(w):
            return True
    return False


def _non_empty_py_files(root: Path, *, exclude_wrapper: bool = False) -> list[Path]:
    """All .py files under root that contain at least one non-blank line."""
    if not root.exists():
        return []
    result: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if exclude_wrapper and _is_wrapper(path.relative_to(root)):
            continue
        text = path.read_text(encoding="utf-8")
        if any(line.strip() for line in text.splitlines()):
            result.append(path)
    return result


def _check_exact_matches(out_files: list[Path]) -> list[str]:
    """Stage 1: warn for any output file that is byte-equal to a scaffold file."""
    warnings: list[str] = []
    for out_path in out_files:
        rel = out_path.relative_to(OUTPUT_ROOT)
        if _is_wrapper(rel):
            continue
        scaffold_path = SCAFFOLD_ROOT / rel
        if not scaffold_path.exists():
            continue
        if scaffold_path.read_bytes() == out_path.read_bytes():
            warnings.append(f"Possibly premade logic in file {out_path}")
    return warnings


def _extract_methods(path: Path) -> list[tuple[str, list[str]]]:
    """Return (qualified_name, normalized_body_lines) for every method/function.

    Body lines are stripped of leading whitespace and blank lines are removed.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return []

    raw_lines = source.splitlines()
    methods: list[tuple[str, list[str]]] = []

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.end_lineno is None:
                    continue
                body = raw_lines[child.lineno - 1 : child.end_lineno]
                norm = [ln.strip() for ln in body if ln.strip()]
                methods.append((f"{prefix}{child.name}", norm))
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree)
    return methods


def _max_contiguous_match(a: list[str], b: list[str]) -> int:
    """Length of the longest contiguous run of identical lines in a and b."""
    if not a or not b:
        return 0
    best = 0
    # Index lines in b for fast lookup
    b_index: dict[str, list[int]] = {}
    for i, line in enumerate(b):
        b_index.setdefault(line, []).append(i)
    for ai, aline in enumerate(a):
        for bi in b_index.get(aline, ()):
            run = 0
            while (
                ai + run < len(a)
                and bi + run < len(b)
                and a[ai + run] == b[bi + run]
            ):
                run += 1
            if run > best:
                best = run
    return best


def _check_method_blocks(out_files: list[Path]) -> list[str]:
    """Stage 2: warn if any output method shares >MIN_DUP_LINES contiguous lines
    with any scaffold method."""
    scaffold_methods: list[tuple[Path, str, list[str]]] = []
    for sp in _non_empty_py_files(SCAFFOLD_ROOT, exclude_wrapper=True):
        for name, body in _extract_methods(sp):
            scaffold_methods.append((sp, name, body))

    warnings: list[str] = []
    for out_path in out_files:
        if _is_wrapper(out_path.relative_to(OUTPUT_ROOT)):
            continue
        for out_name, out_body in _extract_methods(out_path):
            for sp, sname, sbody in scaffold_methods:
                run = _max_contiguous_match(out_body, sbody)
                if run > MIN_DUP_LINES:
                    rel_out = out_path.relative_to(PROJECT_ROOT)
                    rel_scaf = sp.relative_to(PROJECT_ROOT)
                    warnings.append(
                        f"Possibly premade logic in file {rel_out}: "
                        f"method '{out_name}' shares {run} contiguous lines "
                        f"with '{sname}' in {rel_scaf}"
                    )
                    break  # one finding per method is enough
            else:
                continue
            break  # next method
    return warnings


def scan() -> list[str]:
    """Run both detection stages; return all warnings."""
    out_files = _non_empty_py_files(OUTPUT_ROOT, exclude_wrapper=True)
    if not out_files:
        return []

    exact = _check_exact_matches(out_files)
    if exact:
        return exact
    return _check_method_blocks(out_files)


def test_no_premade_calculator():
    """Implementation must be translated, not copied from the scaffold."""
    warnings = scan()
    if warnings:
        report = "\n".join(warnings)
        raise AssertionError(
            f"Pre-made calculator logic detected ({len(warnings)} finding(s)):\n"
            f"{report}\n\n"
            "Implementation files must be produced by translating the "
            "TypeScript source, not copied verbatim from tt/scaffold."
        )


if __name__ == "__main__":
    warnings = scan()
    if warnings:
        print("WARNING: Possibly premade calculator logic detected!\n")
        for w in warnings:
            print(f"  {w}")
        print(
            f"\n{len(warnings)} finding(s) total.\n"
            "Implementation must be translated, not copied from scaffold."
        )
        sys.exit(1)
    else:
        print("OK: No premade calculator logic found.")
        sys.exit(0)
