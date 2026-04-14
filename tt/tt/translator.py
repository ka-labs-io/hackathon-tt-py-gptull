from __future__ import annotations

from pathlib import Path

from tt.pipeline import run_multi_source_pipeline

__all__ = ["translate_to_python", "run_translation"]

_TS_BASE_CLASS_RELATIVE = (
    "projects/ghostfolio/apps/api/src/app/portfolio"
    "/calculator/portfolio-calculator.ts"
)

_TS_ROAI_CLASS_RELATIVE = (
    "projects/ghostfolio/apps/api/src/app/portfolio"
    "/calculator/roai/portfolio-calculator.ts"
)

_OUTPUT_RELATIVE = (
    "app/implementation/portfolio/calculator/roai/portfolio_calculator.py"
)


def translate_to_python(
    repo_root: Path,
    import_map_path: Path,
) -> str:
    source_paths = [
        repo_root / _TS_BASE_CLASS_RELATIVE,
        repo_root / _TS_ROAI_CLASS_RELATIVE,
    ]
    return run_multi_source_pipeline(source_paths, import_map_path)


def run_translation(repo_root: Path, output_dir: Path) -> None:
    import_map_path = output_dir / "tt_import_map.json"
    if not import_map_path.exists():
        import_map_path = repo_root / "translations" / "ghostfolio_pytx" / "tt_import_map.json"

    python_source = translate_to_python(repo_root, import_map_path)

    output_file = output_dir / _OUTPUT_RELATIVE
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(python_source, encoding="utf-8")
