from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias, cast

if TYPE_CHECKING:
    from tree_sitter import Node

__all__ = [
    "TransformContext",
    "_camel_to_snake",
    "transform_expression",
]

LibraryMethodMap: TypeAlias = dict[str, str]
LibraryConfig: TypeAlias = dict[str, object]
TypeMap: TypeAlias = dict[str, str | None]
ExprTransformer: TypeAlias = Callable[["Node", "TransformContext"], str]

_MIN_CHILDREN_FOR_CONSTRUCTOR = 2
_MIN_CHILDREN_FOR_CALL = 2
_MIN_ARGS_FOR_BINARY_FUNC = 2
_TERNARY_CHILD_COUNT = 3


INDENT_UNIT: str = "    "


@dataclass(frozen=True)
class TransformContext:
    import_map: dict[str, object]
    indent_level: int = 0
    scope_vars: frozenset[str] = field(default_factory=frozenset[str])
    identifier_replacements: dict[str, str] = field(default_factory=dict)
    hoisted_lines: list[str] = field(default_factory=list)
    _arrow_counter: list[int] = field(default_factory=lambda: [0])

    @property
    def indent(self) -> str:
        return INDENT_UNIT * self.indent_level

    def indented(self) -> TransformContext:
        return TransformContext(
            import_map=self.import_map,
            indent_level=self.indent_level + 1,
            scope_vars=self.scope_vars,
            identifier_replacements=self.identifier_replacements,
            hoisted_lines=self.hoisted_lines,
            _arrow_counter=self._arrow_counter,
        )

    def with_replacements(self, replacements: dict[str, str]) -> TransformContext:
        return TransformContext(
            import_map=self.import_map,
            indent_level=self.indent_level,
            scope_vars=self.scope_vars,
            identifier_replacements={**self.identifier_replacements, **replacements},
            hoisted_lines=self.hoisted_lines,
            _arrow_counter=self._arrow_counter,
        )

    def next_arrow_id(self) -> int:
        current = self._arrow_counter[0]
        self._arrow_counter[0] = current + 1
        return current


_BIGJS_BINARY_METHODS: dict[str, str] = {
    "plus": "+",
    "add": "+",
    "minus": "-",
    "sub": "-",
    "mul": "*",
    "times": "*",
    "div": "/",
}

_BIGJS_COMPARISON_METHODS: dict[str, str] = {
    "eq": "==",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}

_BIGJS_STANDALONE_METHODS: frozenset[str] = frozenset({"toNumber", "abs", "toFixed", "round"})

_ALL_BIGJS_METHODS: frozenset[str] = (
    frozenset(_BIGJS_BINARY_METHODS)
    | frozenset(_BIGJS_COMPARISON_METHODS)
    | _BIGJS_STANDALONE_METHODS
)

_JS_OPERATOR_TO_PYTHON: dict[str, str] = {
    "===": "==",
    "!==": "!=",
    "||": "or",
    "&&": "and",
    "??": "if",
}

_ARRAY_METHOD_RENAMES: dict[str, str] = {
    "push": "append",
    "indexOf": "index",
}

_KNOWN_ARRAY_METHODS: frozenset[str] = frozenset(
    {
        "filter",
        "map",
        "reduce",
        "forEach",
        "includes",
        "findIndex",
        "find",
        "sort",
        "at",
        "keys",
        "getTime",
        "indexOf",
        "push",
    }
)

_NON_DICT_OBJECTS: frozenset[str] = frozenset(
    {
        "this",
        "console",
        "Logger",
        "Math",
        "Number",
        "JSON",
        "Object",
        "Array",
        "self",
    }
)

_BUILTIN_PROPS: frozenset[str] = frozenset(
    {
        "length",
        "prototype",
        "constructor",
    }
)

_UNARY_OPERATORS: frozenset[str] = frozenset(
    {
        "!",
        "-",
        "+",
        "~",
        "typeof",
        "void",
        "delete",
    }
)

_BINARY_OPERATORS: frozenset[str] = frozenset(
    {
        "===",
        "!==",
        "||",
        "&&",
        "??",
        "+",
        "-",
        "*",
        "/",
        "%",
        "==",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "instanceof",
        "in",
    }
)

_ASSIGNMENT_OPERATORS: frozenset[str] = frozenset(
    {
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
    }
)

_AUGMENTED_OPERATORS: frozenset[str] = frozenset(
    {
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
    }
)

_CAMEL_TO_SNAKE_PATTERN = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _camel_to_snake(name: str) -> str:
    return _CAMEL_TO_SNAKE_PATTERN.sub("_", name).lower()


def _node_text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def _get_named_children(node: Node) -> list[Node]:
    return [child for child in node.children if child.is_named and child.type != "comment"]


def _named_child_at(node: Node, index: int) -> Node | None:
    named = _get_named_children(node)
    return named[index] if index < len(named) else None


def _as_str_dict(raw: object) -> dict[str, object]:
    return cast("dict[str, object]", raw) if isinstance(raw, dict) else {}


def _extract_types_map(
    import_map: dict[str, object],
) -> dict[str, str | None]:
    entries = _as_str_dict(import_map.get("types"))
    return {k: (str(v) if v is not None else None) for k, v in entries.items()}


def _extract_library_config(import_map: dict[str, object], library_name: str) -> dict[str, object]:
    libs = _as_str_dict(import_map.get("libraries"))
    return _as_str_dict(libs.get(library_name))


def _extract_library_mappings(import_map: dict[str, object], library_name: str) -> dict[str, str]:
    config = _extract_library_config(import_map, library_name)
    entries = _as_str_dict(config.get("mappings"))
    return {k: str(v) for k, v in entries.items()}


def _extract_constants(
    import_map: dict[str, object],
) -> dict[str, str]:
    entries = _as_str_dict(import_map.get("constants"))
    return {k: str(v) for k, v in entries.items()}


def _extract_all_class_mappings(
    import_map: dict[str, object],
) -> dict[str, str]:
    libs = _as_str_dict(import_map.get("libraries"))
    result: dict[str, str] = {}
    for lib_config_raw in libs.values():
        lib_config = _as_str_dict(lib_config_raw)
        mappings = _as_str_dict(lib_config.get("mappings"))
        for ts_name, py_name in mappings.items():
            if ts_name[0:1].isupper():
                result[ts_name] = str(py_name)
    return result


def _is_bigjs_constructor(node: Node) -> bool:
    named = _get_named_children(node)
    return (
        node.type == "new_expression"
        and len(named) >= _MIN_CHILDREN_FOR_CONSTRUCTOR
        and _node_text(named[0]) == "Big"
    )


def _is_date_constructor(node: Node) -> bool:
    named = _get_named_children(node)
    return node.type == "new_expression" and len(named) >= 1 and _node_text(named[0]) == "Date"


def _get_arguments_nodes(node: Node) -> list[Node]:
    args_node = next(
        (c for c in node.children if c.type == "arguments"),
        None,
    )
    return _get_named_children(args_node) if args_node is not None else []


def _get_member_property(node: Node) -> str:
    prop_node = next(
        (c for c in node.children if c.type == "property_identifier"),
        None,
    )
    return _node_text(prop_node) if prop_node is not None else ""


def _has_optional_chain(node: Node) -> bool:
    return any(child.type == "optional_chain" for child in node.children)


def _is_bigjs_method_call(node: Node) -> bool:
    return (
        node.type == "call_expression"
        and len(node.children) >= _MIN_CHILDREN_FOR_CALL
        and node.children[0].type == "member_expression"
        and _get_member_property(node.children[0]) in _ALL_BIGJS_METHODS
    )


def _is_known_date_function(name: str, import_map: dict[str, object]) -> bool:
    return name in _extract_library_mappings(import_map, "date-fns")


def _is_known_lodash_function(name: str, import_map: dict[str, object]) -> bool:
    return name in _extract_library_mappings(import_map, "lodash")


def _looks_like_domain_property_access(
    obj_node: Node,
    prop_name: str,
) -> bool:
    obj_text = _node_text(obj_node)
    return (
        obj_text not in _NON_DICT_OBJECTS
        and prop_name not in _BUILTIN_PROPS
        and prop_name not in _ALL_BIGJS_METHODS
        and prop_name not in _ARRAY_METHOD_RENAMES
        and prop_name not in _KNOWN_ARRAY_METHODS
    )


def _transform_bigjs_constructor(node: Node, ctx: TransformContext) -> str:
    args = _get_arguments_nodes(node)
    inner = transform_expression(args[0], ctx) if args else "0"
    return f"Decimal(str({inner}))"


def _transform_date_constructor(node: Node, ctx: TransformContext) -> str:
    args = _get_arguments_nodes(node)
    return (
        f"datetime.fromisoformat({transform_expression(args[0], ctx)})"
        if args
        else "datetime.now()"
    )


def _transform_bigjs_binary_method(
    obj_expr: str,
    method_name: str,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    operator = _BIGJS_BINARY_METHODS[method_name]
    arg_expr = transform_expression(args[0], ctx) if args else "Decimal(0)"
    return f"({obj_expr} {operator} Decimal(str({arg_expr})))"


def _transform_bigjs_comparison_method(
    obj_expr: str,
    method_name: str,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    operator = _BIGJS_COMPARISON_METHODS[method_name]
    arg_expr = transform_expression(args[0], ctx) if args else "Decimal(0)"
    return f"({obj_expr} {operator} Decimal(str({arg_expr})))"


def _transform_bigjs_to_number(obj_expr: str) -> str:
    return f"float({obj_expr})"


def _transform_bigjs_abs(obj_expr: str) -> str:
    return f"abs({obj_expr})"


def _transform_bigjs_to_fixed(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    precision = transform_expression(args[0], ctx) if args else "0"
    return f'f"{{({obj_expr}):.{precision}f}}"'


def _transform_bigjs_round(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    precision = transform_expression(args[0], ctx) if args else "0"
    return f"round({obj_expr}, {precision})"


def _dispatch_bigjs_method(
    obj_expr: str,
    method_name: str,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    if method_name in _BIGJS_BINARY_METHODS:
        return _transform_bigjs_binary_method(obj_expr, method_name, args, ctx)
    if method_name in _BIGJS_COMPARISON_METHODS:
        return _transform_bigjs_comparison_method(obj_expr, method_name, args, ctx)
    standalone_dispatch: dict[str, Callable[..., str]] = {
        "toNumber": lambda: _transform_bigjs_to_number(obj_expr),
        "abs": lambda: _transform_bigjs_abs(obj_expr),
        "toFixed": lambda: _transform_bigjs_to_fixed(obj_expr, args, ctx),
        "round": lambda: _transform_bigjs_round(obj_expr, args, ctx),
    }
    handler = standalone_dispatch.get(method_name)
    return handler() if handler is not None else obj_expr


def _transform_bigjs_method(node: Node, ctx: TransformContext) -> str:
    member_expr = node.children[0]
    obj_node = _named_child_at(member_expr, 0)
    method_name = _get_member_property(member_expr)
    args = _get_arguments_nodes(node)
    obj_expr = transform_expression(obj_node, ctx) if obj_node is not None else ""
    return _dispatch_bigjs_method(obj_expr, method_name, args, ctx)


def _transform_date_function_call(func_name: str, args: list[Node], ctx: TransformContext) -> str:
    date_mappings = _extract_library_mappings(ctx.import_map, "date-fns")
    python_name = date_mappings.get(func_name, _camel_to_snake(func_name))
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"{python_name}({', '.join(arg_strs)})"


def _transform_lodash_clone_deep(args: list[Node], ctx: TransformContext) -> str:
    return f"copy.deepcopy({transform_expression(args[0], ctx)})" if args else "copy.deepcopy(None)"


def _transform_lodash_sort_by(args: list[Node], ctx: TransformContext) -> str:
    arr_expr = transform_expression(args[0], ctx)
    key_expr = transform_expression(args[1], ctx)
    return f"sorted({arr_expr}, key={key_expr})"


def _transform_lodash_function_call(func_name: str, args: list[Node], ctx: TransformContext) -> str:
    lodash_mappings = _extract_library_mappings(ctx.import_map, "lodash")
    python_name = lodash_mappings.get(func_name, _camel_to_snake(func_name))

    if func_name == "cloneDeep" and args:
        return _transform_lodash_clone_deep(args, ctx)

    if func_name == "sortBy" and len(args) >= _MIN_ARGS_FOR_BINARY_FUNC:
        return _transform_lodash_sort_by(args, ctx)

    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"{python_name}({', '.join(arg_strs)})"


def _extract_object_pattern_props(arrow_node: Node) -> list[str]:
    params_node = next(
        (c for c in arrow_node.children if c.type == "formal_parameters"),
        None,
    )
    if params_node is None:
        return []
    required_params = [c for c in params_node.children if c.type == "required_parameter"]
    if len(required_params) != 1:
        return []
    inner = _get_named_children(required_params[0])
    if not inner or inner[0].type != "object_pattern":
        return []
    return [
        _node_text(child)
        for child in inner[0].children
        if child.type == "shorthand_property_identifier_pattern"
    ]


def _extract_arrow_body_expression(arrow_node: Node) -> Node | None:
    body_node = _find_arrow_body(arrow_node)
    if body_node is None:
        return None
    if body_node.type == "statement_block":
        return _find_single_return(body_node)
    return body_node


def _inline_destructured_arrow(
    arrow_node: Node,
    iter_var: str,
    ctx: TransformContext,
) -> str | None:
    props = _extract_object_pattern_props(arrow_node)
    if props:
        body_expr_node = _extract_arrow_body_expression(arrow_node)
        if body_expr_node is None:
            return None
        replacements = {prop: f"{iter_var}['{prop}']" for prop in props}
        inlined_ctx = ctx.with_replacements(replacements)
        return transform_expression(body_expr_node, inlined_ctx)
    return _inline_simple_arrow(arrow_node, iter_var, ctx)


def _inline_simple_arrow(
    arrow_node: Node,
    iter_var: str,
    ctx: TransformContext,
) -> str | None:
    body_expr_node = _extract_arrow_body_expression(arrow_node)
    if body_expr_node is None:
        return None
    params_node = next(
        (c for c in arrow_node.children if c.type == "formal_parameters"),
        None,
    )
    param_names = _extract_arrow_param_identifiers(params_node) if params_node else []
    if len(param_names) != 1:
        return None
    replacements = {param_names[0]: iter_var}
    inlined_ctx = ctx.with_replacements(replacements)
    return transform_expression(body_expr_node, inlined_ctx)


def _extract_arrow_param_identifiers(params_node: Node) -> list[str]:
    identifiers: list[str] = []
    for child in params_node.children:
        if child.type == "required_parameter":
            inner = _get_named_children(child)
            if inner and inner[0].type == "identifier":
                identifiers.append(_node_text(inner[0]))
        elif child.type == "identifier":
            identifiers.append(_node_text(child))
    return identifiers


def _array_push(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    arg_expr = transform_expression(args[0], ctx)
    return f"{obj_expr}.append({arg_expr})"


def _array_filter(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    inlined = (
        _inline_destructured_arrow(args[0], "x", ctx)
        if args[0].type == "arrow_function"
        else None
    )
    if inlined is not None:
        return f"[x for x in {obj_expr} if {inlined}]"
    cb = transform_expression(args[0], ctx)
    return f"[x for x in {obj_expr} if {cb}(x)]"


def _array_map(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    inlined = (
        _inline_destructured_arrow(args[0], "x", ctx)
        if args[0].type == "arrow_function"
        else None
    )
    if inlined is not None:
        return f"[{inlined} for x in {obj_expr}]"
    cb = transform_expression(args[0], ctx)
    return f"[{cb}(x) for x in {obj_expr}]"


def _array_reduce(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    cb = transform_expression(args[0], ctx)
    init = transform_expression(args[1], ctx)
    return f"functools.reduce({cb}, {obj_expr}, {init})"


def _array_for_each(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    inlined = (
        _inline_destructured_arrow(args[0], "x", ctx)
        if args[0].type == "arrow_function"
        else None
    )
    if inlined is not None:
        return f"[{inlined} for x in {obj_expr}]"
    cb = transform_expression(args[0], ctx)
    return f"[{cb}(x) for x in {obj_expr}]"


def _array_includes(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    arg_expr = transform_expression(args[0], ctx)
    return f"({arg_expr} in {obj_expr})"


def _array_find_index(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    inlined = (
        _inline_destructured_arrow(args[0], "x", ctx)
        if args[0].type == "arrow_function"
        else None
    )
    if inlined is not None:
        return f"next((i for i, x in enumerate({obj_expr}) if {inlined}), -1)"
    cb = transform_expression(args[0], ctx)
    return f"next((i for i, x in enumerate({obj_expr}) if {cb}(x)), -1)"


def _array_find(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    inlined = (
        _inline_destructured_arrow(args[0], "x", ctx)
        if args[0].type == "arrow_function"
        else None
    )
    if inlined is not None:
        return f"next((x for x in {obj_expr} if {inlined}), None)"
    cb = transform_expression(args[0], ctx)
    return f"next((x for x in {obj_expr} if {cb}(x)), None)"


def _array_sort_with_cmp(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    cb = transform_expression(args[0], ctx)
    return f"sorted({obj_expr}, key=functools.cmp_to_key({cb}))"


def _array_at(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    idx = transform_expression(args[0], ctx)
    return f"{obj_expr}[{idx}]"


def _array_index_of(obj_expr: str, args: list[Node], ctx: TransformContext) -> str:
    arg_expr = transform_expression(args[0], ctx)
    return f"{obj_expr}.index({arg_expr})"


def _array_get_time(
    obj_expr: str,
    args: list[Node],  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return f"int({obj_expr}.timestamp() * 1000)"


def _array_keys(
    obj_expr: str,
    args: list[Node],  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return f"list({obj_expr}.keys())"


def _array_sort_no_arg(
    obj_expr: str,
    args: list[Node],  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return f"sorted({obj_expr})"


_ArrayMethodHandler: TypeAlias = Callable[[str, list["Node"], "TransformContext"], str]

_ARRAY_METHOD_DISPATCH: dict[str, _ArrayMethodHandler] = {
    "push": _array_push,
    "filter": _array_filter,
    "map": _array_map,
    "forEach": _array_for_each,
    "includes": _array_includes,
    "findIndex": _array_find_index,
    "find": _array_find,
    "at": _array_at,
    "indexOf": _array_index_of,
    "getTime": _array_get_time,
    "keys": _array_keys,
}


def _transform_array_method_call(
    obj_expr: str,
    method_name: str,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    if method_name == "reduce" and len(args) >= _MIN_ARGS_FOR_BINARY_FUNC:
        return _array_reduce(obj_expr, args, ctx)

    if method_name == "sort" and args:
        return _array_sort_with_cmp(obj_expr, args, ctx)

    if method_name == "sort" and not args:
        return _array_sort_no_arg(obj_expr, args, ctx)

    handler = _ARRAY_METHOD_DISPATCH.get(method_name)
    if handler is not None and args:
        return handler(obj_expr, args, ctx)
    if handler is not None:
        return handler(obj_expr, args, ctx)

    python_name = _ARRAY_METHOD_RENAMES.get(method_name, _camel_to_snake(method_name))
    arg_strs = [transform_expression(a, ctx) for a in args]
    joined = ", ".join(arg_strs)
    return f"{obj_expr}.{python_name}({joined})" if joined else f"{obj_expr}.{python_name}()"


def _transform_call_on_identifier(
    callee: Node,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    func_name = _node_text(callee)

    if _is_known_date_function(func_name, ctx.import_map):
        return _transform_date_function_call(func_name, args, ctx)

    if _is_known_lodash_function(func_name, ctx.import_map):
        return _transform_lodash_function_call(func_name, args, ctx)

    python_name = _camel_to_snake(func_name)
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"{python_name}({', '.join(arg_strs)})"


def _transform_console_call(args: list[Node], ctx: TransformContext) -> str:
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"print({', '.join(arg_strs)})"


def _transform_logger_call(method_name: str, args: list[Node], ctx: TransformContext) -> str:
    python_level = {
        "warn": "warning",
        "error": "error",
        "log": "info",
    }.get(method_name, method_name)
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"logger.{python_level}({', '.join(arg_strs)})"


def _transform_object_static_call(method_name: str, args: list[Node], ctx: TransformContext) -> str:
    arg_strs = [transform_expression(a, ctx) for a in args]
    dispatch: dict[str, Callable[[], str]] = {
        "keys": lambda: f"list({arg_strs[0]}.keys())",
        "values": lambda: f"list({arg_strs[0]}.values())",
        "entries": lambda: f"list({arg_strs[0]}.items())",
        "assign": lambda: "{" + ", ".join(f"**{a}" for a in arg_strs) + "}",
    }
    handler = dispatch.get(method_name) if arg_strs else None
    return handler() if handler is not None else ", ".join(arg_strs)


def _transform_call_on_member(
    callee: Node,
    args: list[Node],
    ctx: TransformContext,
) -> str:
    obj_node = _named_child_at(callee, 0)
    method_name = _get_member_property(callee)

    if obj_node is not None and _node_text(obj_node) == "console":
        return _transform_console_call(args, ctx)

    if obj_node is not None and _node_text(obj_node) == "Logger":
        return _transform_logger_call(method_name, args, ctx)

    if obj_node is not None and _node_text(obj_node) == "Object":
        return _transform_object_static_call(method_name, args, ctx)

    obj_expr = transform_expression(obj_node, ctx) if obj_node is not None else ""

    if method_name in _KNOWN_ARRAY_METHODS:
        return _transform_array_method_call(obj_expr, method_name, args, ctx)

    if method_name == "toFixed":
        return _transform_bigjs_to_fixed(obj_expr, args, ctx)

    python_method = _camel_to_snake(method_name)
    arg_strs = [transform_expression(a, ctx) for a in args]
    joined = ", ".join(arg_strs)
    return f"{obj_expr}.{python_method}({joined})" if joined else f"{obj_expr}.{python_method}()"


def _transform_call_expression(node: Node, ctx: TransformContext) -> str:
    named = _get_named_children(node)
    callee = named[0] if named else None
    args = _get_arguments_nodes(node)

    if callee is not None and _is_bigjs_method_call(node):
        return _transform_bigjs_method(node, ctx)

    if callee is not None and callee.type == "identifier":
        return _transform_call_on_identifier(callee, args, ctx)

    if callee is not None and callee.type == "member_expression":
        return _transform_call_on_member(callee, args, ctx)

    callee_expr = transform_expression(callee, ctx) if callee is not None else ""
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"{callee_expr}({', '.join(arg_strs)})"


def _transform_new_expression(node: Node, ctx: TransformContext) -> str:
    if _is_bigjs_constructor(node):
        return _transform_bigjs_constructor(node, ctx)
    if _is_date_constructor(node):
        return _transform_date_constructor(node, ctx)
    named = _get_named_children(node)
    class_name = _node_text(named[0]) if named else ""
    args = _get_arguments_nodes(node)
    arg_strs = [transform_expression(a, ctx) for a in args]
    return f"{class_name}({', '.join(arg_strs)})"


def _transform_member_this_access(prop_name: str) -> str:
    return f"self.{_camel_to_snake(prop_name)}"


def _transform_member_number_epsilon() -> str:
    return "sys.float_info.epsilon"


def _transform_member_length(obj_node: Node, ctx: TransformContext) -> str:
    obj_expr = transform_expression(obj_node, ctx)
    return f"len({obj_expr})"


def _transform_member_optional_access(obj_expr: str, prop_name: str) -> str:
    return f"({obj_expr}.get({prop_name!r}) if {obj_expr} is not None else None)"


def _transform_member_dict_access(obj_expr: str, prop_name: str) -> str:
    return f'{obj_expr}["{prop_name}"]'


def _resolve_special_member(
    obj_text: str,
    prop_name: str,
) -> str | None:
    if obj_text == "this":
        return _transform_member_this_access(prop_name)
    if obj_text == "Number" and prop_name == "EPSILON":
        return _transform_member_number_epsilon()
    return None


def _extract_class_type_names(
    import_map: dict[str, object],
) -> frozenset[str]:
    types_map = _extract_types_map(import_map)
    return frozenset(
        name for name, mapped in types_map.items()
        if mapped is not None and mapped != "dict" and mapped != "str"
    )


def _is_upper_constant(name: str) -> bool:
    return name == name.upper() and "_" in name


def _resolve_member_with_object(
    obj_node: Node,
    prop_name: str,
    is_optional: bool,
    ctx: TransformContext,
) -> str:
    obj_text = _node_text(obj_node)
    class_type_names = _extract_class_type_names(ctx.import_map)
    if obj_text in class_type_names:
        py_prop = prop_name if _is_upper_constant(prop_name) else _camel_to_snake(prop_name)
        return f"{obj_text}.{py_prop}"

    obj_expr = transform_expression(obj_node, ctx)

    if is_optional:
        return _transform_member_optional_access(obj_expr, prop_name)

    types_map = _extract_types_map(ctx.import_map)
    has_dict_types = any(types_map.get(t) == "dict" for t in types_map)
    if has_dict_types and _looks_like_domain_property_access(obj_node, prop_name):
        return _transform_member_dict_access(obj_expr, prop_name)

    return f"{obj_expr}.{_camel_to_snake(prop_name)}"


def _transform_member_expression(node: Node, ctx: TransformContext) -> str:
    obj_node = _named_child_at(node, 0)
    prop_name = _get_member_property(node)
    is_optional = _has_optional_chain(node)

    if obj_node is None:
        return prop_name

    special = _resolve_special_member(_node_text(obj_node), prop_name)
    if special is not None:
        return special

    if prop_name == "length":
        return _transform_member_length(obj_node, ctx)

    return _resolve_member_with_object(obj_node, prop_name, is_optional, ctx)


def _skip_optional_chain_children(node: Node) -> list[Node]:
    return [child for child in node.children if child.is_named and child.type != "optional_chain"]


def _transform_subscript_expression(node: Node, ctx: TransformContext) -> str:
    is_optional = _has_optional_chain(node)
    non_chain_named = _skip_optional_chain_children(node)
    obj_node = non_chain_named[0] if non_chain_named else None
    index_node = non_chain_named[1] if len(non_chain_named) > 1 else None
    obj_expr = transform_expression(obj_node, ctx) if obj_node is not None else ""
    idx_expr = transform_expression(index_node, ctx) if index_node is not None else ""
    is_numeric = (
        index_node is not None
        and index_node.type in ("number", "unary_expression")
    )
    if is_optional:
        return f"({obj_expr}.get({idx_expr}) if {obj_expr} is not None else None)"
    if is_numeric:
        return f"{obj_expr}[{idx_expr}]"
    return f"{obj_expr}.get({idx_expr})"


def _find_operator_token(node: Node, valid_ops: frozenset[str]) -> str:
    op_node = next(
        (c for c in node.children if not c.is_named and _node_text(c).strip() in valid_ops),
        None,
    )
    return _node_text(op_node).strip() if op_node is not None else ""


def _transform_binary_expression(node: Node, ctx: TransformContext) -> str:
    left_node = _named_child_at(node, 0)
    right_node = _named_child_at(node, 1)
    ts_operator = _find_operator_token(node, _BINARY_OPERATORS)

    left_expr = transform_expression(left_node, ctx) if left_node is not None else ""
    right_expr = transform_expression(right_node, ctx) if right_node is not None else ""

    if ts_operator == "??":
        if left_node is not None and left_node.type == "subscript_expression":
            has_chain = _has_optional_chain(left_node)
            non_chain = _skip_optional_chain_children(left_node)
            obj_sub = non_chain[0] if non_chain else None
            idx_sub = non_chain[1] if len(non_chain) > 1 else None
            obj_sub_expr = transform_expression(obj_sub, ctx) if obj_sub else ""
            idx_sub_expr = transform_expression(idx_sub, ctx) if idx_sub else ""
            if has_chain:
                return f"({obj_sub_expr}.get({idx_sub_expr}, {right_expr}) if {obj_sub_expr} is not None else {right_expr})"
            return f"{obj_sub_expr}.get({idx_sub_expr}, {right_expr})"
        if left_node is not None and left_node.type == "member_expression":
            obj_mem = _named_child_at(left_node, 0)
            prop_mem = _get_member_property(left_node)
            obj_mem_expr = transform_expression(obj_mem, ctx) if obj_mem else ""
            if _looks_like_domain_property_access(obj_mem, prop_mem) if obj_mem else False:
                return f"{obj_mem_expr}.get('{prop_mem}', {right_expr})"
        return f"({left_expr} if {left_expr} is not None else {right_expr})"

    if ts_operator == "instanceof":
        return f"isinstance({left_expr}, {right_expr})"

    py_op = _JS_OPERATOR_TO_PYTHON.get(ts_operator, ts_operator)
    return f"({left_expr} {py_op} {right_expr})"


def _transform_unary_expression(node: Node, ctx: TransformContext) -> str:
    operand = _named_child_at(node, 0)
    ts_op = _find_operator_token(node, _UNARY_OPERATORS)
    operand_expr = transform_expression(operand, ctx) if operand is not None else ""

    if ts_op == "!":
        return f"(not {operand_expr})"
    if ts_op == "typeof":
        return f"type({operand_expr}).__name__"
    return f"({ts_op}{operand_expr})"


def _transform_ternary_expression(node: Node, ctx: TransformContext) -> str:
    condition = _named_child_at(node, 0)
    consequent = _named_child_at(node, 1)
    alternate = _named_child_at(node, _TERNARY_CHILD_COUNT - 1)

    cond_expr = transform_expression(condition, ctx) if condition is not None else ""
    cons_expr = transform_expression(consequent, ctx) if consequent is not None else ""
    alt_expr = transform_expression(alternate, ctx) if alternate is not None else ""
    return f"({cons_expr} if {cond_expr} else {alt_expr})"


def _transform_template_string(node: Node, ctx: TransformContext) -> str:
    parts: list[str] = []
    for child in node.children:
        if child.type == "string_fragment":
            parts.append(_node_text(child))
        elif child.type == "template_substitution":
            inner_nodes = _get_named_children(child)
            if inner_nodes:
                expr_str = transform_expression(inner_nodes[0], ctx)
                parts.append("{" + expr_str + "}")
    content = "".join(parts)
    quote = '"""' if "\n" in content else '"'
    return f"f{quote}" + content + f"{quote}"


def _transform_string(
    node: Node,
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    raw = _node_text(node)
    return raw.replace("'", '"') if raw.startswith("'") else raw


def _transform_arrow_function(node: Node, ctx: TransformContext) -> str:
    params_node = next(
        (c for c in node.children if c.type == "formal_parameters"),
        None,
    )
    body_node = _find_arrow_body(node)

    destructured_fields = _extract_destructured_fields(params_node) if params_node else []

    if destructured_fields:
        param_name = "_item"
        replacements = {
            field: f"{param_name}['{field}']"
            for field in destructured_fields
        }
        body_ctx = ctx.with_replacements(replacements)
        body_expr = _resolve_arrow_body(body_node, body_ctx, params_node)
        if body_expr is None:
            return _hoist_arrow_as_function(body_node, params_node, [param_name], ctx)
        return f"lambda {param_name}: {body_expr}"

    param_names = _extract_arrow_params(params_node) if params_node is not None else []
    joined_params = ", ".join(param_names)

    body_expr = _resolve_arrow_body(body_node, ctx, params_node)
    if body_expr is None:
        return _hoist_arrow_as_function(body_node, params_node, param_names, ctx)
    return f"lambda {joined_params}: {body_expr}"


def _resolve_arrow_body(
    body_node: Node | None,
    ctx: TransformContext,
    _params_node: Node | None = None,
) -> str | None:
    if body_node is None:
        return "None"
    if body_node.type == "statement_block":
        return_node = _find_single_return(body_node)
        if return_node is not None:
            return transform_expression(return_node, ctx)
        return None
    return transform_expression(body_node, ctx)


def _has_object_pattern_param(params_node: Node | None) -> bool:
    if params_node is None:
        return False
    return any(
        _get_named_children(child)[0].type == "object_pattern"
        for child in params_node.children
        if child.type == "required_parameter" and _get_named_children(child)
    )


def _extract_object_pattern_keys(params_node: Node) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for child in params_node.children:
        if child.type != "required_parameter":
            continue
        inner = _get_named_children(child)
        if not inner or inner[0].type != "object_pattern":
            continue
        for pat_child in inner[0].children:
            if pat_child.type == "shorthand_property_identifier_pattern":
                original_name = _node_text(pat_child)
                keys.append((original_name, _camel_to_snake(original_name)))
    return keys


def _build_destructure_lines(
    keys: list[tuple[str, str]],
    param_name: str,
    ctx: TransformContext,
) -> list[str]:
    return [
        f'{ctx.indent}{snake_name} = {param_name}["{original_name}"]'
        for original_name, snake_name in keys
    ]


def _hoist_arrow_as_function(
    body_node: Node | None,
    params_node: Node | None,
    param_names: list[str],
    ctx: TransformContext,
) -> str:
    from tt.statements import transform_block  # noqa: PLC0415

    func_id = ctx.next_arrow_id()
    func_name = f"_arrow_fn_{func_id}"

    if _has_object_pattern_param(params_node) and params_node is not None:
        func_param = "_obj"
        sig_line = f"{ctx.indent}def {func_name}({func_param}):"
        pattern_keys = _extract_object_pattern_keys(params_node)
        destructure_lines = _build_destructure_lines(
            pattern_keys, func_param, ctx.indented()
        )
    else:
        joined_params = ", ".join(param_names)
        sig_line = f"{ctx.indent}def {func_name}({joined_params}):"
        destructure_lines = []

    body_lines = transform_block(body_node, ctx.indented()) if body_node else []
    fallback_body = [f"{ctx.indented().indent}pass"]

    ctx.hoisted_lines.append(sig_line)
    ctx.hoisted_lines.extend(destructure_lines)
    ctx.hoisted_lines.extend(body_lines if body_lines else fallback_body)
    ctx.hoisted_lines.append("")

    return func_name


def _extract_destructured_fields(params_node: Node) -> list[str]:
    for child in params_node.children:
        if child.type == "required_parameter":
            inner = _get_named_children(child)
            if inner and inner[0].type == "object_pattern":
                return _get_object_pattern_field_names(inner[0])
    return []


def _get_object_pattern_field_names(node: Node) -> list[str]:
    names: list[str] = []
    for child in node.children:
        if child.type == "shorthand_property_identifier_pattern":
            names.append(_node_text(child))
        elif child.type == "pair_pattern":
            key_node = next(
                (c for c in child.children if c.type == "property_identifier"),
                None,
            )
            if key_node:
                names.append(_node_text(key_node))
    return names


def _find_arrow_body(node: Node) -> Node | None:
    return next(
        (
            child
            for child in node.children
            if child.type == "statement_block"
            or (child.is_named and child.type != "formal_parameters")
        ),
        None,
    )


def _extract_arrow_params(params_node: Node) -> list[str]:
    params: list[str] = []
    for child in params_node.children:
        if child.type == "required_parameter":
            _extract_required_param(child, params)
        elif child.type == "identifier":
            params.append(_camel_to_snake(_node_text(child)))
    return params if params else ["x"]


def _extract_required_param(child: Node, params: list[str]) -> None:
    inner = _get_named_children(child)
    if inner and inner[0].type == "object_pattern":
        params.append(_transform_object_pattern_param(inner[0]))
    elif inner and inner[0].type == "identifier":
        params.append(_camel_to_snake(_node_text(inner[0])))
    else:
        params.append(_camel_to_snake(_node_text(child)))


def _transform_object_pattern_param(node: Node) -> str:
    keys: list[str] = []
    for child in node.children:
        if child.type == "shorthand_property_identifier_pattern":
            keys.append(_camel_to_snake(_node_text(child)))
        elif child.type == "pair_pattern":
            named = _get_named_children(child)
            if named:
                keys.append(_camel_to_snake(_node_text(named[0])))
    return ", ".join(keys) if len(keys) == 1 else f"({', '.join(keys)})"


def _find_single_return(block_node: Node) -> Node | None:
    stmts = [c for c in block_node.children if c.type == "return_statement"]
    all_stmts = [c for c in block_node.children if c.is_named]
    if len(stmts) == 1 and len(all_stmts) == 1:
        named = _get_named_children(stmts[0])
        return named[0] if named else None
    return None


def _transform_object(node: Node, ctx: TransformContext) -> str:
    entries: list[str] = []
    for child in node.children:
        _transform_object_entry(child, entries, ctx)
    return "{" + ", ".join(entries) + "}"


def _transform_object_entry(child: Node, entries: list[str], ctx: TransformContext) -> None:
    if child.type == "pair":
        named = _get_named_children(child)
        if len(named) >= _MIN_CHILDREN_FOR_CONSTRUCTOR:
            key = _node_text(named[0])
            val = transform_expression(named[1], ctx)
            entries.append(f'"{key}": {val}')
    elif child.type == "shorthand_property_identifier":
        name = _node_text(child)
        python_name = _camel_to_snake(name)
        entries.append(f'"{name}": {python_name}')
    elif child.type == "spread_element":
        named = _get_named_children(child)
        if named:
            spread_expr = transform_expression(named[0], ctx)
            entries.append(f"**{spread_expr}")


def _transform_array(node: Node, ctx: TransformContext) -> str:
    elements = [transform_expression(child, ctx) for child in node.children if child.is_named]
    return "[" + ", ".join(elements) + "]"


def _transform_subscript_as_target(node: Node, ctx: TransformContext) -> str:
    non_chain_named = _skip_optional_chain_children(node)
    obj_node = non_chain_named[0] if non_chain_named else None
    index_node = non_chain_named[1] if len(non_chain_named) > 1 else None
    obj_expr = transform_expression(obj_node, ctx) if obj_node is not None else ""
    idx_expr = transform_expression(index_node, ctx) if index_node is not None else ""
    return f"{obj_expr}[{idx_expr}]"


def _transform_lhs(node: Node | None, ctx: TransformContext) -> str:
    if node is None:
        return ""
    if node.type == "subscript_expression":
        return _transform_subscript_as_target(node, ctx)
    return transform_expression(node, ctx)


def _transform_assignment_expression(node: Node, ctx: TransformContext) -> str:
    left = _named_child_at(node, 0)
    right = _named_child_at(node, 1)
    left_expr = _transform_lhs(left, ctx)
    right_expr = transform_expression(right, ctx) if right is not None else ""
    op = _find_operator_token(node, _ASSIGNMENT_OPERATORS)
    op = op if op else "="
    return f"{left_expr} {op} {right_expr}"


def _transform_augmented_assignment(node: Node, ctx: TransformContext) -> str:
    left = _named_child_at(node, 0)
    right = _named_child_at(node, 1)
    left_expr = _transform_lhs(left, ctx)
    right_expr = transform_expression(right, ctx) if right is not None else ""
    op = _find_operator_token(node, _AUGMENTED_OPERATORS)
    op = op if op else "+="
    return f"{left_expr} {op} {right_expr}"


def _transform_parenthesized_expression(node: Node, ctx: TransformContext) -> str:
    inner = _named_child_at(node, 0)
    inner_expr = transform_expression(inner, ctx) if inner is not None else ""
    return f"({inner_expr})"


def _transform_update_expression(node: Node, ctx: TransformContext) -> str:
    operand = _named_child_at(node, 0)
    operand_expr = transform_expression(operand, ctx) if operand is not None else ""
    raw = _node_text(node)
    op = "+=" if "++" in raw else "-="
    return f"{operand_expr} {op} 1"


def _transform_spread_element(node: Node, ctx: TransformContext) -> str:
    inner = _named_child_at(node, 0)
    inner_expr = transform_expression(inner, ctx) if inner is not None else ""
    return f"*{inner_expr}"


def _transform_type_strip(node: Node, ctx: TransformContext) -> str:
    inner = _named_child_at(node, 0)
    return transform_expression(inner, ctx) if inner is not None else ""


def _transform_identifier(
    node: Node,
    ctx: TransformContext,
) -> str:
    name = _node_text(node)
    if name in ctx.identifier_replacements:
        return ctx.identifier_replacements[name]
    if name in ("undefined", "null"):
        return "None"
    constants = _extract_constants(ctx.import_map)
    if name in constants:
        return name
    class_mappings = _extract_all_class_mappings(ctx.import_map)
    if name in class_mappings:
        return class_mappings[name]
    return _camel_to_snake(name)


def _transform_this(
    node: Node,  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return "self"


def _transform_number(
    node: Node,
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return _node_text(node)


def _transform_true(
    node: Node,  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return "True"


def _transform_false(
    node: Node,  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return "False"


def _transform_null(
    node: Node,  # noqa: ARG001
    ctx: TransformContext,  # noqa: ARG001
) -> str:
    return "None"


def _transform_fallback(node: Node, ctx: TransformContext) -> str:  # noqa: ARG001
    return _node_text(node)


_EXPRESSION_DISPATCH: dict[str, ExprTransformer] = {
    "call_expression": _transform_call_expression,
    "new_expression": _transform_new_expression,
    "member_expression": _transform_member_expression,
    "subscript_expression": _transform_subscript_expression,
    "binary_expression": _transform_binary_expression,
    "unary_expression": _transform_unary_expression,
    "ternary_expression": _transform_ternary_expression,
    "template_string": _transform_template_string,
    "string": _transform_string,
    "arrow_function": _transform_arrow_function,
    "object": _transform_object,
    "array": _transform_array,
    "assignment_expression": _transform_assignment_expression,
    "augmented_assignment_expression": _transform_augmented_assignment,
    "parenthesized_expression": _transform_parenthesized_expression,
    "update_expression": _transform_update_expression,
    "spread_element": _transform_spread_element,
    "as_expression": _transform_type_strip,
    "non_null_expression": _transform_type_strip,
    "satisfies_expression": _transform_type_strip,
    "identifier": _transform_identifier,
    "this": _transform_this,
    "number": _transform_number,
    "true": _transform_true,
    "false": _transform_false,
    "null": _transform_null,
    "undefined": _transform_null,
}


def transform_expression(node: Node | None, ctx: TransformContext) -> str:
    if node is None:
        return ""
    if node.type == "comment":
        return ""
    handler = _EXPRESSION_DISPATCH.get(node.type, _transform_fallback)
    return handler(node, ctx)
