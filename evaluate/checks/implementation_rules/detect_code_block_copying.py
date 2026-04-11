#!/usr/bin/env python3
"""
detect_code_block_copying.py — detect verbatim code blocks from tt/ inside
translated output.

The tt tool must translate TypeScript source to Python — not copy pre-written
Python code into the translation output.  This check finds contiguous blocks
of MIN_BLOCK_LINES or more lines from any tt/ Python file (including scaffold)
that appear verbatim in the translated output, after stripping leading
whitespace from each line.

This catches cases where the scaffold or translator embeds domain logic that
ends up in the output unchanged, even when it is not a complete function.

Usage:
  python detect_code_block_copying.py
  pytest detect_code_block_copying.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"
_PROJECT = os.environ.get("PROJECT_NAME", "ghostfolio")
TRANSLATION_ROOT = PROJECT_ROOT / "translations" / f"{_PROJECT}_pytx"

# Minimum number of contiguous matching lines to flag as a copied block.
MIN_BLOCK_LINES = 10


def _normalized_lines(path: Path) -> list[str]:
    """Return non-empty lines with leading whitespace stripped."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _build_line_index(
    files: list[Path],
) -> dict[str, list[tuple[Path, int]]]:
    """Map each normalized line to [(file, original_lineno), ...]."""
    index: dict[str, list[tuple[Path, int]]] = {}
    for path in files:
        for i, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            stripped = raw_line.strip()
            if stripped and not stripped.startswith("#"):
                index.setdefault(stripped, []).append((path, i + 1))
    return index


def _extract_blocks(lines: list[str], min_len: int) -> list[tuple[int, int]]:
    """Return (start_idx, length) of all contiguous non-trivial blocks >= min_len.

    Slides a window over the lines and yields every maximal contiguous block.
    """
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        # Skip trivial lines (empty, pass, single-keyword)
        if len(lines[i]) < 4 or lines[i] in ("pass", "return", "break", "continue"):
            i += 1
            continue
        start = i
        i += 1
        while i < len(lines) and len(lines[i]) >= 4:
            i += 1
        length = i - start
        if length >= min_len:
            blocks.append((start, length))
    return blocks


def scan() -> list[str]:
    """Find blocks from tt/ that appear in translated output."""
    if not TT_ROOT.exists() or not TRANSLATION_ROOT.exists():
        return []

    # Exclude only the wrapper folder: those files are intentionally laid
    # down in the translation output by _copy_wrapper() (see tt/tt/cli.py),
    # so matches there are not "copying" — they are the canonical wrapper
    # being placed. Everything else under tt/tt/ (including scaffold domain
    # code) MUST be scanned: scaffold must not ship pre-written Python that
    # ends up verbatim in the translation output.
    wrapper_root = TT_ROOT / "scaffold" / "ghostfolio_pytx" / "app" / "wrapper"
    tt_files = sorted(
        p for p in TT_ROOT.rglob("*.py")
        if p.is_file() and not p.is_relative_to(wrapper_root)
    )
    # Exclude .venv from translated output
    tx_files = sorted(
        p for p in TRANSLATION_ROOT.rglob("*.py")
        if p.is_file() and ".venv" not in p.parts
    )

    if not tt_files or not tx_files:
        return []

    # Build a set of all normalized lines in translated output for fast lookup
    tx_line_set: set[str] = set()
    tx_line_locations: dict[str, tuple[Path, int]] = {}
    for path in tx_files:
        for i, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            stripped = raw_line.strip()
            if stripped and not stripped.startswith("#"):
                tx_line_set.add(stripped)
                if stripped not in tx_line_locations:
                    tx_line_locations[stripped] = (path, i + 1)

    violations: list[str] = []

    for tt_path in tt_files:
        lines = _normalized_lines(tt_path)
        raw_lines = tt_path.read_text(encoding="utf-8").splitlines()

        # Find contiguous blocks of lines that ALL exist in the translation
        i = 0
        while i < len(lines):
            if lines[i] not in tx_line_set:
                i += 1
                continue

            # Start of a potential matching block
            start = i
            while i < len(lines) and lines[i] in tx_line_set:
                i += 1
            block_len = i - start

            if block_len >= MIN_BLOCK_LINES:
                # Find the original line number in the tt file
                # (lines list skips blanks/comments, so map back)
                orig_lineno = _find_original_lineno(raw_lines, lines[start])
                tx_path, tx_lineno = tx_line_locations.get(
                    lines[start], (Path("?"), 0)
                )
                violations.append(
                    f"{tt_path}:{orig_lineno}: {block_len}-line block "
                    f"appears verbatim in translated output "
                    f"({tx_path.relative_to(TRANSLATION_ROOT)}:{tx_lineno}) "
                    f"— tt must not copy pre-written code into translations"
                )

    return violations


def _find_original_lineno(raw_lines: list[str], target: str) -> int:
    """Find the 1-based line number of target in raw_lines."""
    for i, line in enumerate(raw_lines):
        if line.strip() == target:
            return i + 1
    return 1


def test_no_code_block_copying():
    """tt must not copy verbatim code blocks into translated output."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Code block copying detected ({len(violations)} finding(s)):\n{report}"
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Code blocks from tt/ found in translated output!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: No copied code blocks found.")
        sys.exit(0)
