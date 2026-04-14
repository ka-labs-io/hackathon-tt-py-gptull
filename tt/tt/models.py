from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

__all__ = [
    "FieldDef",
    "MethodDef",
    "ClassDef",
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
