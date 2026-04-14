from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

__all__ = [
    "transform_expression",
]


def _node_text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def transform_expression(node: Node | None) -> str:
    if node is None:
        return "None"
    return _node_text(node)
