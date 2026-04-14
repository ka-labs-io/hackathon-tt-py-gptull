from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from tree_sitter import Node

from tt.expressions import INDENT_UNIT, TransformContext, transform_expression

__all__ = [
    "transform_statement",
    "transform_block",
]


MIN_PARENTHESIZED_CHILDREN: int = 3
MIN_DECLARATOR_CHILDREN_FOR_VALUE: int = 2
MIN_FOR_HEADER_PARTS: int = 2
MIN_BINARY_OPERANDS: int = 2
MIN_ASSIGNMENT_OPERANDS: int = 2


StatementTransformer: TypeAlias = Callable[["Node", TransformContext], list[str]]


def _node_text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def _child_by_type(node: Node, type_name: str) -> Node | None:
    return next(
        (child for child in node.children if child.type == type_name),
        None,
    )


def _children_by_type(node: Node, type_name: str) -> list[Node]:
    return [child for child in node.children if child.type == type_name]


def _named_children(node: Node) -> list[Node]:
    return [child for child in node.children if child.is_named]


def _strip_parenthesized(node: Node) -> Node:
    return (
        node.children[1]
        if node.type == "parenthesized_expression"
        and len(node.children) >= MIN_PARENTHESIZED_CHILDREN
        else node
    )


def _transform_object_pattern_binding(
    pattern_node: Node,
    source_expr: str,
    ctx: TransformContext,
) -> list[str]:
    return [
        line
        for child in pattern_node.children
        for line in _destructure_object_property(child, source_expr, ctx)
    ]


def _destructure_object_property(
    child: Node,
    source_expr: str,
    ctx: TransformContext,
) -> list[str]:
    if child.type == "shorthand_property_identifier_pattern":
        prop_name = _node_text(child)
        return [f'{ctx.indent}{prop_name} = {source_expr}["{prop_name}"]']
    if child.type == "pair_pattern":
        key_node = _child_by_type(child, "property_identifier")
        value_node = next(
            (c for c in child.children if c.type == "identifier"),
            None,
        )
        if key_node and value_node:
            key_name = _node_text(key_node)
            val_name = _node_text(value_node)
            return [f'{ctx.indent}{val_name} = {source_expr}["{key_name}"]']
    return []


def _transform_array_pattern_binding(
    pattern_node: Node,
    source_expr: str,
    ctx: TransformContext,
) -> list[str]:
    identifiers = [
        _node_text(child) for child in pattern_node.children if child.type == "identifier"
    ]
    return [f"{ctx.indent}{name} = {source_expr}[{idx}]" for idx, name in enumerate(identifiers)]


def _transform_declarator(
    declarator: Node,
    ctx: TransformContext,
) -> list[str]:
    named = _named_children(declarator)
    lhs = named[0] if named else None
    value_node = named[-1] if len(named) >= MIN_DECLARATOR_CHILDREN_FOR_VALUE else None

    type_ann = _child_by_type(declarator, "type_annotation")
    if type_ann and value_node and value_node.type == "type_annotation":
        value_node = None

    if lhs is None:
        return []

    if lhs.type == "object_pattern":
        source_expr = transform_expression(value_node, ctx) if value_node else "None"
        return _transform_object_pattern_binding(lhs, source_expr, ctx)

    if lhs.type == "array_pattern":
        source_expr = transform_expression(value_node, ctx) if value_node else "None"
        return _transform_array_pattern_binding(lhs, source_expr, ctx)

    var_name = _node_text(lhs)
    rhs = transform_expression(value_node, ctx) if value_node else "None"
    return [f"{ctx.indent}{var_name} = {rhs}"]


def _transform_lexical_declaration(node: Node, ctx: TransformContext) -> list[str]:
    declarators = _children_by_type(node, "variable_declarator")
    return [line for declarator in declarators for line in _transform_declarator(declarator, ctx)]


def _transform_variable_declaration(node: Node, ctx: TransformContext) -> list[str]:
    declarators = _children_by_type(node, "variable_declarator")
    return [line for declarator in declarators for line in _transform_declarator(declarator, ctx)]


def _extract_condition_expression(node: Node, ctx: TransformContext) -> str:
    paren = _child_by_type(node, "parenthesized_expression")
    inner = _strip_parenthesized(paren) if paren else None
    return transform_expression(inner, ctx) if inner else "True"


def _extract_consequence_block(node: Node) -> Node | None:
    return _child_by_type(node, "statement_block")


def _transform_if_branch(
    node: Node,
    ctx: TransformContext,
    keyword: str,
) -> list[str]:
    condition = _extract_condition_expression(node, ctx)
    consequence = _extract_consequence_block(node)
    lines = [f"{ctx.indent}{keyword} {condition}:"]
    if consequence:
        lines.extend(transform_block(consequence, ctx.indented()))
    if not consequence or len(transform_block(consequence, ctx.indented())) == 0:
        lines.append(f"{ctx.indented().indent}pass")
    return lines


def _transform_else_clause(
    else_clause: Node,
    ctx: TransformContext,
) -> list[str]:
    nested_if = _child_by_type(else_clause, "if_statement")
    if nested_if:
        return _transform_if_branch(nested_if, ctx, "elif") + _transform_elif_chain(nested_if, ctx)

    block = _child_by_type(else_clause, "statement_block")
    lines = [f"{ctx.indent}else:"]
    if block:
        block_lines = transform_block(block, ctx.indented())
        lines.extend(block_lines if block_lines else [f"{ctx.indented().indent}pass"])
    else:
        lines.append(f"{ctx.indented().indent}pass")
    return lines


def _transform_elif_chain(node: Node, ctx: TransformContext) -> list[str]:
    else_clause = _child_by_type(node, "else_clause")
    return _transform_else_clause(else_clause, ctx) if else_clause else []


def _transform_if_statement(node: Node, ctx: TransformContext) -> list[str]:
    lines = _transform_if_branch(node, ctx, "if")
    lines.extend(_transform_elif_chain(node, ctx))
    return lines


def _split_for_in_at_of(node: Node) -> tuple[list[Node], list[Node]]:
    before_of: list[Node] = []
    after_of: list[Node] = []
    seen_of = False
    for child in node.children:
        if child.type == "of":
            seen_of = True
            continue
        if seen_of:
            after_of.append(child)
        else:
            before_of.append(child)
    return before_of, after_of


def _extract_for_of_variable(node: Node) -> str:
    before_of, _ = _split_for_in_at_of(node)
    named_before = [c for c in before_of if c.is_named]

    for part in named_before:
        if part.type == "array_pattern":
            names = [_node_text(c) for c in part.children if c.type == "identifier"]
            return ", ".join(names)
        if part.type == "object_pattern":
            names = [
                _node_text(c)
                for c in part.children
                if c.type == "shorthand_property_identifier_pattern"
            ]
            return ", ".join(names)
        if part.type == "identifier":
            return _node_text(part)

    return "_"


def _extract_for_of_iterable(node: Node, ctx: TransformContext) -> str:
    _, after_of = _split_for_in_at_of(node)
    named_after = [c for c in after_of if c.is_named and c.type != "statement_block"]
    return transform_expression(named_after[0], ctx) if named_after else "[]"


def _transform_for_in_statement(node: Node, ctx: TransformContext) -> list[str]:
    variable = _extract_for_of_variable(node)
    iterable = _extract_for_of_iterable(node, ctx)
    body = _child_by_type(node, "statement_block")
    lines = [f"{ctx.indent}for {variable} in {iterable}:"]
    if body:
        body_lines = transform_block(body, ctx.indented())
        lines.extend(body_lines if body_lines else [f"{ctx.indented().indent}pass"])
    else:
        lines.append(f"{ctx.indented().indent}pass")
    return lines


def _extract_for_init_var(init_node: Node) -> tuple[str, str] | None:
    if init_node.type != "lexical_declaration":
        return None

    declarators = _children_by_type(init_node, "variable_declarator")
    if len(declarators) != 1:
        return None

    decl_named = _named_children(declarators[0])
    var_ident = decl_named[0] if decl_named else None
    init_value_node = (
        decl_named[-1] if len(decl_named) >= MIN_DECLARATOR_CHILDREN_FOR_VALUE else None
    )

    type_ann = _child_by_type(declarators[0], "type_annotation")
    if type_ann and init_value_node and init_value_node.type == "type_annotation":
        init_value_node = None

    if var_ident is None:
        return None
    return _node_text(var_ident), _node_text(init_value_node) if init_value_node else "0"


def _extract_for_upper_bound(cond_node: Node, ctx: TransformContext) -> str | None:
    if cond_node.type != "binary_expression":
        return None
    cond_children = _named_children(cond_node)
    return (
        transform_expression(cond_children[-1], ctx)
        if len(cond_children) >= MIN_BINARY_OPERANDS
        else None
    )


def _extract_c_style_for_range(node: Node, ctx: TransformContext) -> tuple[str, str, str] | None:
    named = [c for c in node.children if c.is_named and c.type not in ("statement_block",)]
    if len(named) < MIN_FOR_HEADER_PARTS:
        return None

    var_info = _extract_for_init_var(named[0])
    upper_bound = _extract_for_upper_bound(named[1], ctx)
    if var_info is None or upper_bound is None:
        return None

    return var_info[0], var_info[1], upper_bound


def _transform_for_statement(node: Node, ctx: TransformContext) -> list[str]:
    body = _child_by_type(node, "statement_block")

    range_parts = _extract_c_style_for_range(node, ctx)
    if range_parts:
        var_name, start_val, upper_bound = range_parts
        range_expr = (
            f"range({upper_bound})" if start_val == "0" else f"range({start_val}, {upper_bound})"
        )
        lines = [f"{ctx.indent}for {var_name} in {range_expr}:"]
    else:
        lines = [f"{ctx.indent}for _ in range(0):"]

    if body:
        body_lines = transform_block(body, ctx.indented())
        lines.extend(body_lines if body_lines else [f"{ctx.indented().indent}pass"])
    else:
        lines.append(f"{ctx.indented().indent}pass")
    return lines


def _transform_while_statement(node: Node, ctx: TransformContext) -> list[str]:
    condition = _extract_condition_expression(node, ctx)
    body = _child_by_type(node, "statement_block")
    lines = [f"{ctx.indent}while {condition}:"]
    if body:
        body_lines = transform_block(body, ctx.indented())
        lines.extend(body_lines if body_lines else [f"{ctx.indented().indent}pass"])
    else:
        lines.append(f"{ctx.indented().indent}pass")
    return lines


def _transform_return_statement(node: Node, ctx: TransformContext) -> list[str]:
    named = _named_children(node)
    return_value = named[0] if named else None
    expr = transform_expression(return_value, ctx) if return_value else ""
    return [f"{ctx.indent}return {expr}".rstrip()]


def _transform_expression_statement(node: Node, ctx: TransformContext) -> list[str]:
    named = _named_children(node)
    expr_node = named[0] if named else None
    if expr_node is None:
        return []

    if expr_node.type == "assignment_expression":
        return _transform_assignment_expression(expr_node, ctx)

    if expr_node.type == "augmented_assignment_expression":
        return _transform_augmented_assignment(expr_node, ctx)

    return [f"{ctx.indent}{transform_expression(expr_node, ctx)}"]


def _transform_assignment_expression(node: Node, ctx: TransformContext) -> list[str]:
    named = _named_children(node)
    lhs_node = named[0] if named else None
    rhs_node = named[1] if len(named) >= MIN_ASSIGNMENT_OPERANDS else None
    lhs = transform_expression(lhs_node, ctx) if lhs_node else "_"
    rhs = transform_expression(rhs_node, ctx) if rhs_node else "None"
    return [f"{ctx.indent}{lhs} = {rhs}"]


def _transform_augmented_assignment(node: Node, ctx: TransformContext) -> list[str]:
    named = _named_children(node)
    lhs_node = named[0] if named else None
    rhs_node = named[1] if len(named) >= MIN_ASSIGNMENT_OPERANDS else None
    lhs = transform_expression(lhs_node, ctx) if lhs_node else "_"
    rhs = transform_expression(rhs_node, ctx) if rhs_node else "0"

    operator_node = next(
        (
            child
            for child in node.children
            if not child.is_named and child.type in ("+=", "-=", "*=", "/=", "%=", "**=")
        ),
        None,
    )
    op = _node_text(operator_node) if operator_node else "+="
    return [f"{ctx.indent}{lhs} {op} {rhs}"]


def _transform_switch_statement(node: Node, ctx: TransformContext) -> list[str]:
    condition_expr = _extract_condition_expression(node, ctx)
    switch_body = _child_by_type(node, "switch_body")
    if switch_body is None:
        return [f"{ctx.indent}pass"]

    cases = _children_by_type(switch_body, "switch_case")
    default = _child_by_type(switch_body, "switch_default")

    lines: list[str] = []
    for idx, case_node in enumerate(cases):
        case_value_nodes = [
            c for c in case_node.children if c.is_named and c.type != "break_statement"
        ]
        case_value = transform_expression(case_value_nodes[0], ctx) if case_value_nodes else "None"
        keyword = "if" if idx == 0 else "elif"
        lines.append(f"{ctx.indent}{keyword} {condition_expr} == {case_value}:")

        case_body_nodes = [
            c for c in case_node.children if c.is_named and c.type not in ("break_statement",)
        ]
        body_statements = case_body_nodes[1:] if len(case_body_nodes) > 1 else []
        if body_statements:
            for stmt_node in body_statements:
                lines.extend(transform_statement(stmt_node, ctx.indented()))
        else:
            lines.append(f"{ctx.indented().indent}pass")

    if default:
        lines.append(f"{ctx.indent}else:")
        default_body = [c for c in default.children if c.is_named and c.type != "break_statement"]
        if default_body:
            for stmt_node in default_body:
                lines.extend(transform_statement(stmt_node, ctx.indented()))
        else:
            lines.append(f"{ctx.indented().indent}pass")

    return lines


def _transform_try_statement(node: Node, ctx: TransformContext) -> list[str]:
    try_block = _child_by_type(node, "statement_block")
    catch_clause = _child_by_type(node, "catch_clause")

    lines = [f"{ctx.indent}try:"]
    if try_block:
        try_lines = transform_block(try_block, ctx.indented())
        lines.extend(try_lines if try_lines else [f"{ctx.indented().indent}pass"])
    else:
        lines.append(f"{ctx.indented().indent}pass")

    if catch_clause:
        catch_param = _child_by_type(catch_clause, "identifier")
        param_name = _node_text(catch_param) if catch_param else "e"
        lines.append(f"{ctx.indent}except Exception as {param_name}:")
        catch_block = _child_by_type(catch_clause, "statement_block")
        if catch_block:
            catch_lines = transform_block(catch_block, ctx.indented())
            lines.extend(catch_lines if catch_lines else [f"{ctx.indented().indent}pass"])
        else:
            lines.append(f"{ctx.indented().indent}pass")

    return lines


def _transform_break_statement(_node: Node, ctx: TransformContext) -> list[str]:
    return [f"{ctx.indent}break"]


def _transform_continue_statement(_node: Node, ctx: TransformContext) -> list[str]:
    return [f"{ctx.indent}continue"]


STATEMENT_DISPATCH: dict[str, StatementTransformer] = {
    "lexical_declaration": _transform_lexical_declaration,
    "variable_declaration": _transform_variable_declaration,
    "if_statement": _transform_if_statement,
    "for_in_statement": _transform_for_in_statement,
    "for_statement": _transform_for_statement,
    "while_statement": _transform_while_statement,
    "return_statement": _transform_return_statement,
    "expression_statement": _transform_expression_statement,
    "switch_statement": _transform_switch_statement,
    "try_statement": _transform_try_statement,
    "break_statement": _transform_break_statement,
    "continue_statement": _transform_continue_statement,
}


def transform_statement(node: Node, context: TransformContext) -> list[str]:
    handler = STATEMENT_DISPATCH.get(node.type)
    if handler:
        return handler(node, context)
    return [f"{context.indent}{_node_text(node)}"]


def transform_block(node: Node, context: TransformContext) -> list[str]:
    return [
        line
        for child in node.children
        if child.is_named
        for line in transform_statement(child, context)
    ]
