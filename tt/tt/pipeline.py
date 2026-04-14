from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from tree_sitter import Node, Tree

__all__ = [
    "FieldDef",
    "MethodDef",
    "ClassDef",
    "ImportMap",
    "load_import_map",
    "parse_typescript",
    "extract_definitions",
    "transform_to_python",
    "assemble_module",
    "run_pipeline",
]


@dataclass(frozen=True)
class FieldDef:
    name: str
    ts_type: str
    access_modifier: str
    is_readonly: bool = False


@dataclass(frozen=True)
class MethodDef:
    name: str
    parameters: tuple[tuple[str, str], ...]
    return_type: str
    body_node: Node | None = field(default=None, compare=False, repr=False)
    access_modifier: str = "public"
    is_static: bool = False


@dataclass(frozen=True)
class ClassDef:
    name: str
    parent_class: str | None
    fields: tuple[FieldDef, ...]
    methods: tuple[MethodDef, ...]
    is_exported: bool = True


ImportMap: TypeAlias = dict[str, object]


def load_import_map(import_map_path: Path) -> ImportMap:
    raw_text = import_map_path.read_text(encoding="utf-8")
    loaded: ImportMap = json.loads(raw_text)
    return loaded


def parse_typescript(source: str) -> Tree:
    raise NotImplementedError


def extract_definitions(tree: Tree) -> list[ClassDef]:
    raise NotImplementedError


def transform_to_python(
    classes: list[ClassDef],
    import_map: ImportMap,
) -> list[str]:
    raise NotImplementedError


def assemble_module(
    fragments: list[str],
    import_map: ImportMap,
) -> str:
    raise NotImplementedError


def run_pipeline(source_path: Path, import_map_path: Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    import_map = load_import_map(import_map_path)
    tree = parse_typescript(source_text)
    classes = extract_definitions(tree)
    fragments = transform_to_python(classes, import_map)
    return assemble_module(fragments, import_map)
