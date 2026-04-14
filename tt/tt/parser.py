from __future__ import annotations

from typing import TYPE_CHECKING

import tree_sitter as ts
import tree_sitter_typescript as tst

from tt.models import ClassDef, FieldDef, MethodDef

if TYPE_CHECKING:
    from tree_sitter import Node, Tree

__all__ = [
    "parse_typescript",
    "extract_classes",
]

_TYPESCRIPT_LANGUAGE: ts.Language = ts.Language(tst.language_typescript())


def parse_typescript(source: str) -> Tree:
    parser = ts.Parser(_TYPESCRIPT_LANGUAGE)
    return parser.parse(bytes(source, "utf-8"))


def extract_classes(tree: Tree) -> list[ClassDef]:
    return list(
        map(
            _build_class_def,
            _find_class_declarations(tree.root_node),
        )
    )


def _find_class_declarations(root: Node) -> list[tuple[Node, bool]]:
    return [
        _classify_class_node(child)
        for child in root.named_children
        if child.type in ("class_declaration", "abstract_class_declaration", "export_statement")
        and _extract_class_node(child) is not None
    ]


def _classify_class_node(node: Node) -> tuple[Node, bool]:
    is_exported = node.type == "export_statement"
    class_node = _extract_class_node(node)
    assert class_node is not None
    return (class_node, is_exported)


def _extract_class_node(node: Node) -> Node | None:
    return (
        node
        if node.type in ("class_declaration", "abstract_class_declaration")
        else _first_child_of_type(node, "class_declaration")
        or _first_child_of_type(node, "abstract_class_declaration")
    )


def _build_class_def(class_info: tuple[Node, bool]) -> ClassDef:
    class_node, is_exported = class_info
    name = _node_text(class_node.child_by_field_name("name"))
    parent_class = _extract_parent_class(class_node)
    body = class_node.child_by_field_name("body")
    body_children = body.named_children if body else []
    fields = tuple(
        _build_field_def(child)
        for child in body_children
        if child.type == "public_field_definition"
    )
    methods = tuple(
        _build_method_def(child)
        for child in body_children
        if child.type == "method_definition"
    )
    return ClassDef(
        name=name,
        parent_class=parent_class,
        fields=fields,
        methods=methods,
        is_exported=is_exported,
    )


def _extract_parent_class(class_node: Node) -> str | None:
    heritage = _first_child_of_type(class_node, "class_heritage")
    extends_clause = (
        _first_child_of_type(heritage, "extends_clause") if heritage else None
    )
    return (
        _node_text(_first_named_child_after_keyword(extends_clause, "extends"))
        if extends_clause
        else None
    )


def _first_named_child_after_keyword(node: Node, keyword: str) -> Node | None:
    found_keyword = False
    for child in node.children:
        if found_keyword and child.is_named:
            return child
        if child.type == keyword:
            found_keyword = True
    return None


def _build_field_def(node: Node) -> FieldDef:
    access_modifier = _extract_access_modifier(node)
    is_readonly = _has_child_of_type(node, "readonly")
    name = _node_text(_first_child_of_type(node, "property_identifier"))
    ts_type = _extract_type_annotation(node)
    return FieldDef(
        name=name,
        ts_type=ts_type,
        access_modifier=access_modifier,
        is_readonly=is_readonly,
    )


def _build_method_def(node: Node) -> MethodDef:
    access_modifier = _extract_access_modifier(node)
    is_static = _has_child_of_type(node, "static")
    name = _node_text(node.child_by_field_name("name"))
    parameters = _extract_parameters(node.child_by_field_name("parameters"))
    return_type = _extract_type_annotation(node)
    body_node = node.child_by_field_name("body")
    return MethodDef(
        name=name,
        parameters=parameters,
        return_type=return_type,
        body_node=body_node,
        access_modifier=access_modifier,
        is_static=is_static,
    )


def _extract_access_modifier(node: Node) -> str:
    modifier_node = _first_child_of_type(node, "accessibility_modifier")
    return _node_text(modifier_node) if modifier_node else "public"


def _has_child_of_type(node: Node, node_type: str) -> bool:
    return any(child.type == node_type for child in node.children)


def _extract_type_annotation(node: Node) -> str:
    type_annotation = _first_child_of_type(node, "type_annotation")
    return (
        _node_text(type_annotation).lstrip(": ").strip()
        if type_annotation
        else ""
    )


def _extract_parameters(
    params_node: Node | None,
) -> tuple[tuple[str, str], ...]:
    return (
        tuple(
            _extract_single_parameter(child)
            for child in params_node.named_children
            if child.type in ("required_parameter", "optional_parameter")
        )
        if params_node
        else ()
    )


def _extract_single_parameter(param_node: Node) -> tuple[str, str]:
    pattern_node = param_node.child_by_field_name("pattern")
    param_name = _extract_parameter_name(pattern_node) if pattern_node else ""
    param_type = _extract_type_annotation(param_node)
    return (param_name, param_type)


def _extract_parameter_name(pattern_node: Node) -> str:
    return (
        _node_text(pattern_node)
        if pattern_node.type != "object_pattern"
        else _extract_destructured_names(pattern_node)
    )


def _extract_destructured_names(object_pattern: Node) -> str:
    names = [
        _node_text(child)
        for child in object_pattern.named_children
        if child.type == "shorthand_property_identifier_pattern"
    ]
    return "{ " + ", ".join(names) + " }"


def _first_child_of_type(node: Node, node_type: str) -> Node | None:
    return next(
        (child for child in node.children if child.type == node_type),
        None,
    )


def _node_text(node: Node | None) -> str:
    return node.text.decode("utf-8") if node and node.text else ""
