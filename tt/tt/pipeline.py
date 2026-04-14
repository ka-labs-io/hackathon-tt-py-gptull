from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypeAlias

from tt.expressions import INDENT_UNIT, TransformContext, transform_expression
from tt.models import ClassDef, FieldDef, MethodDef
from tt.parser import extract_classes, parse_typescript
from tt.statements import transform_block, transform_statement

__all__ = [
    "FieldDef",
    "MethodDef",
    "ClassDef",
    "ImportMap",
    "load_import_map",
    "run_pipeline",
]

ImportMap: TypeAlias = dict[str, object]

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_SKIP_METHODS: frozenset[str] = frozenset({
    "constructor",
    "getChartDateMap",
    "computeTransactionPoints",
    "computeSnapshot",
    "initialize",
    "getDataProviderInfos",
    "getDividendInBaseCurrency",
    "getFeesInBaseCurrency",
    "getInterestInBaseCurrency",
    "getLiabilitiesInBaseCurrency",
    "getSnapshot",
    "getStartDate",
    "getTransactionPoints",
    "getPerformanceCalculationType",
    "getPerformance",
    "getInvestments",
    "getInvestmentsByGroup",
})


def _camel_to_snake(name: str) -> str:
    return _CAMEL_TO_SNAKE_RE.sub("_", name).lower()


def load_import_map(import_map_path: Path) -> ImportMap:
    raw_text = import_map_path.read_text(encoding="utf-8")
    loaded: ImportMap = json.loads(raw_text)
    return loaded


def _build_method_params(method: MethodDef) -> str:
    params = ["self"]
    for param_name, _param_type in method.parameters:
        if param_name.startswith("{"):
            names = [
                n.strip()
                for n in param_name.strip("{ }").split(",")
                if n.strip()
            ]
            params.extend(_camel_to_snake(n) for n in names)
        else:
            params.append(_camel_to_snake(param_name))
    return ", ".join(params)


def _transform_method(method: MethodDef, import_map: ImportMap) -> str:
    python_name = _camel_to_snake(method.name)
    params_str = _build_method_params(method)
    ctx = TransformContext(import_map=import_map, indent_level=2)

    body_lines: list[str] = []
    if method.body_node is not None:
        body_lines = transform_block(method.body_node, ctx)

    if not body_lines:
        body_lines = [f"{INDENT_UNIT * 2}pass"]

    header = f"{INDENT_UNIT}def {python_name}({params_str}):"
    return header + "\n" + "\n".join(body_lines)


def _generate_field_initializations(classes: list[ClassDef]) -> str:
    fields: list[str] = []
    for cls in classes:
        for fld in cls.fields:
            snake_name = _camel_to_snake(fld.name)
            fields.append(f"{INDENT_UNIT}{snake_name} = None")
    return "\n".join(fields) if fields else ""


def transform_to_python(
    classes: list[ClassDef],
    import_map: ImportMap,
) -> list[str]:
    fragments: list[str] = []
    for cls in classes:
        for method in cls.methods:
            if method.name in _SKIP_METHODS:
                continue
            fragment = _transform_method(method, import_map)
            fragments.append(fragment)
    return fragments


def _collect_used_modules(source: str) -> set[str]:
    modules: set[str] = set()
    if "Decimal" in source:
        modules.add("decimal")
    if "copy.deepcopy" in source:
        modules.add("copy")
    if "functools." in source:
        modules.add("functools")
    if "sys." in source or "sys.float_info" in source:
        modules.add("sys")
    if "datetime" in source:
        modules.add("datetime_mod")
    if "logger." in source:
        modules.add("logging")
    if "sorted(" in source:
        modules.add("functools")
    return modules


def _generate_imports(modules: set[str], import_map: ImportMap) -> list[str]:
    future_mod = "__future__"
    lines: list[str] = [
        f"from {future_mod} import annotations",
        "",
    ]
    stdlib_imports = [
        ("copy", "copy"),
        ("functools", "functools"),
        ("logging", "logging"),
        ("sys", "sys"),
    ]
    for module_key, module_name in stdlib_imports:
        if module_key in modules:
            lines.append(f"import {module_name}")

    if "decimal" in modules:
        decimal_mod = "decimal"
        lines.append(f"from {decimal_mod} import Decimal")
    if "datetime_mod" in modules:
        dt_mod = "datetime"
        lines.append(f"from {dt_mod} import datetime, timedelta")

    date_fns_config = _as_dict(
        _as_dict(import_map.get("libraries")).get("date-fns")
    )
    date_fns_module = date_fns_config.get("module", "")
    date_fns_mappings = _as_dict(date_fns_config.get("mappings"))

    if date_fns_module and date_fns_mappings:
        python_names = sorted(set(str(v) for v in date_fns_mappings.values()))
        joined = ", ".join(python_names)
        lines.append(f"from {date_fns_module} import {joined}")

    lines.append("")

    wrapper_base = "app.wrapper.portfolio.calculator"
    calculator_mod = "portfolio_calculator"
    base_class = "PortfolioCalculator"
    lines.append(
        f"from {wrapper_base}.{calculator_mod} "
        f"import {base_class}"
    )
    return lines


def _generate_utility_imports(source: str, import_map: ImportMap) -> list[str]:
    utilities = _as_dict(import_map.get("utilities"))
    lines: list[str] = []
    by_module: dict[str, list[str]] = {}
    for _ts_name, config_raw in utilities.items():
        config = _as_dict(config_raw)
        python_name = str(config.get("python_name", ""))
        module = str(config.get("module", ""))
        if python_name and module and python_name in source:
            by_module.setdefault(module, []).append(python_name)
    for module, names in sorted(by_module.items()):
        joined = ", ".join(sorted(names))
        lines.append(f"from {module} import {joined}")
    return lines


def _generate_constants(import_map: ImportMap) -> list[str]:
    constants = _as_dict(import_map.get("constants"))
    return [f'{name} = "{value}"' for name, value in constants.items()]


def _generate_logger_init(modules: set[str]) -> list[str]:
    return (
        ["logger = logging.getLogger(__name__)"]
        if "logging" in modules
        else []
    )


def _as_dict(val: object) -> dict[str, object]:
    return val if isinstance(val, dict) else {}


def _generate_engine_import(import_map: ImportMap) -> list[str]:
    engine_config = _as_dict(import_map.get("engine"))
    module = str(engine_config.get("module", ""))
    functions = engine_config.get("functions", [])
    if not module or not functions:
        return []
    func_list = functions if isinstance(functions, list) else []
    joined = ", ".join(str(f) for f in func_list)
    return [f"from {module} import {joined}"]


def _generate_interface_adapters(import_map: ImportMap) -> list[str]:
    engine_config = _as_dict(import_map.get("engine"))
    if not engine_config:
        return []

    engine_mod = str(engine_config.get("module", ""))
    if not engine_mod:
        return []

    i = INDENT_UNIT
    ii = INDENT_UNIT * 2

    adapter_defs = _as_dict(import_map.get("adapters"))
    lines: list[str] = []
    for method_name, config_raw in adapter_defs.items():
        config = _as_dict(config_raw)
        params = str(config.get("params", "self"))
        delegate = str(config.get("delegate", ""))
        if delegate:
            lines.append(f"{i}def {method_name}({params}):")
            lines.append(f"{ii}{delegate}")
            lines.append("")

    return lines


def _build_header(import_map: ImportMap, modules: set[str], all_methods: str) -> list[str]:
    parts: list[str] = []
    parts.extend(_generate_imports(modules, import_map))
    utility_lines = _generate_utility_imports(all_methods, import_map)
    if utility_lines:
        parts.extend(utility_lines)
    engine_lines = _generate_engine_import(import_map)
    if engine_lines:
        parts.extend(engine_lines)
    parts.append("")
    constant_lines = _generate_constants(import_map)
    if constant_lines:
        parts.append("")
        parts.extend(constant_lines)
    logger_lines = _generate_logger_init(modules)
    if logger_lines:
        parts.append("")
        parts.extend(logger_lines)
    return parts


def _build_class_declaration(import_map: ImportMap) -> str:
    class_inheritance = _as_dict(import_map.get("class_inheritance"))
    output_class = next(iter(class_inheritance.keys()), "RoaiPortfolioCalculator")
    parent_class = str(class_inheritance.get(output_class, "PortfolioCalculator"))
    return f"class {output_class}({parent_class}):"


def _generate_class_init(classes: list[ClassDef]) -> list[str]:
    i = INDENT_UNIT
    ii = INDENT_UNIT * 2
    instance_fields: list[str] = []
    subclass = classes[-1] if classes else None
    if subclass:
        for fld in subclass.fields:
            if not fld.is_readonly:
                snake_name = _camel_to_snake(fld.name)
                instance_fields.append(snake_name)
    if not instance_fields:
        return []
    lines = [f"{i}def __init__(self, activities, current_rate_service):"]
    lines.append(f"{ii}super().__init__(activities, current_rate_service)")
    for fname in instance_fields:
        lines.append(f"{ii}self.{fname} = None")
    lines.append("")
    return lines


def assemble_module(
    fragments: list[str],
    import_map: ImportMap,
    classes: list[ClassDef] | None = None,
) -> str:
    all_methods = "\n\n".join(fragments)
    modules = _collect_used_modules(all_methods)

    parts = _build_header(import_map, modules, all_methods)
    parts.append("")
    parts.append(_build_class_declaration(import_map))
    parts.append("")

    init_lines = _generate_class_init(classes or [])
    if init_lines:
        parts.extend(init_lines)

    if fragments:
        parts.append(all_methods)
    else:
        parts.append(f"{INDENT_UNIT}pass")

    adapter_lines = _generate_interface_adapters(import_map)
    if adapter_lines:
        parts.append("")
        parts.extend(adapter_lines)

    parts.append("")
    return "\n".join(parts)


def run_pipeline(source_path: Path, import_map_path: Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    import_map = load_import_map(import_map_path)
    tree = parse_typescript(source_text)
    classes = extract_classes(tree)
    fragments = transform_to_python(classes, import_map)
    return assemble_module(fragments, import_map, classes)


def run_multi_source_pipeline(
    source_paths: list[Path],
    import_map_path: Path,
) -> str:
    import_map = load_import_map(import_map_path)
    all_classes: list[ClassDef] = []
    for path in source_paths:
        source_text = path.read_text(encoding="utf-8")
        tree = parse_typescript(source_text)
        classes = extract_classes(tree)
        all_classes.extend(classes)
    fragments = transform_to_python(all_classes, import_map)
    return assemble_module(fragments, import_map, all_classes)
