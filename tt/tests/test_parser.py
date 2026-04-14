from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tt.parser import extract_classes, parse_typescript

if TYPE_CHECKING:
    from tt.pipeline import ClassDef

TS_SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "projects/ghostfolio/apps/api/src/app/portfolio/calculator"
    "/roai/portfolio-calculator.ts"
)


@pytest.fixture(name="source_text")
def _source_text() -> str:
    return TS_SOURCE_PATH.read_text(encoding="utf-8")


@pytest.fixture(name="parsed_classes")
def _parsed_classes(source_text: str) -> list[ClassDef]:
    tree = parse_typescript(source_text)
    return extract_classes(tree)


def test_parse_returns_tree(source_text: str) -> None:
    tree = parse_typescript(source_text)
    assert tree.root_node is not None
    assert tree.root_node.type == "program"


def test_single_class_extracted(parsed_classes: list[ClassDef]) -> None:
    assert len(parsed_classes) == 1


def test_class_name(parsed_classes: list[ClassDef]) -> None:
    assert parsed_classes[0].name == "RoaiPortfolioCalculator"


def test_class_is_exported(parsed_classes: list[ClassDef]) -> None:
    assert parsed_classes[0].is_exported is True


def test_class_parent(parsed_classes: list[ClassDef]) -> None:
    assert parsed_classes[0].parent_class == "PortfolioCalculator"


def test_field_count(parsed_classes: list[ClassDef]) -> None:
    assert len(parsed_classes[0].fields) == 1


def test_field_name_and_access(parsed_classes: list[ClassDef]) -> None:
    chart_dates_field = parsed_classes[0].fields[0]
    assert chart_dates_field.name == "chartDates"
    assert chart_dates_field.access_modifier == "private"
    assert chart_dates_field.ts_type == "string[]"


EXPECTED_METHOD_COUNT = 3


def test_method_count(parsed_classes: list[ClassDef]) -> None:
    assert len(parsed_classes[0].methods) == EXPECTED_METHOD_COUNT


def test_method_names(parsed_classes: list[ClassDef]) -> None:
    method_names = tuple(m.name for m in parsed_classes[0].methods)
    assert method_names == (
        "calculateOverallPerformance",
        "getPerformanceCalculationType",
        "getSymbolMetrics",
    )


def test_method_access_modifiers(parsed_classes: list[ClassDef]) -> None:
    access_modifiers = tuple(m.access_modifier for m in parsed_classes[0].methods)
    assert access_modifiers == ("protected", "protected", "protected")


def test_calculate_overall_performance_params(parsed_classes: list[ClassDef]) -> None:
    method = parsed_classes[0].methods[0]
    assert len(method.parameters) == 1
    param_name, param_type = method.parameters[0]
    assert param_name == "positions"
    assert param_type == "TimelinePosition[]"


def test_calculate_overall_performance_return_type(
    parsed_classes: list[ClassDef],
) -> None:
    method = parsed_classes[0].methods[0]
    assert method.return_type == "PortfolioSnapshot"


def test_get_performance_calculation_type_no_params(
    parsed_classes: list[ClassDef],
) -> None:
    method = parsed_classes[0].methods[1]
    assert len(method.parameters) == 0


def test_get_symbol_metrics_destructured_params(
    parsed_classes: list[ClassDef],
) -> None:
    method = parsed_classes[0].methods[2]
    assert len(method.parameters) == 1
    param_name, _ = method.parameters[0]
    assert "chartDateMap" in param_name
    assert "symbol" in param_name


def test_get_symbol_metrics_return_type(parsed_classes: list[ClassDef]) -> None:
    method = parsed_classes[0].methods[2]
    assert method.return_type == "SymbolMetrics"


def test_method_body_nodes_are_present(parsed_classes: list[ClassDef]) -> None:
    assert all(m.body_node is not None for m in parsed_classes[0].methods)


def test_no_methods_are_static(parsed_classes: list[ClassDef]) -> None:
    assert all(m.is_static is False for m in parsed_classes[0].methods)


SIMPLE_TS_SOURCE = """
export class Greeter extends Base {
    public readonly greeting: string;
    private count: number;
    static create(name: string): Greeter { return new Greeter(); }
    public greet(who: string): string { return this.greeting; }
}
"""


def test_simple_class_name() -> None:
    classes = extract_classes(parse_typescript(SIMPLE_TS_SOURCE))
    assert classes[0].name == "Greeter"


def test_simple_class_parent() -> None:
    classes = extract_classes(parse_typescript(SIMPLE_TS_SOURCE))
    assert classes[0].parent_class == "Base"


def test_simple_field_readonly() -> None:
    classes = extract_classes(parse_typescript(SIMPLE_TS_SOURCE))
    greeting_field = next(f for f in classes[0].fields if f.name == "greeting")
    assert greeting_field.is_readonly is True
    assert greeting_field.access_modifier == "public"
    assert greeting_field.ts_type == "string"


def test_simple_static_method() -> None:
    classes = extract_classes(parse_typescript(SIMPLE_TS_SOURCE))
    create_method = next(m for m in classes[0].methods if m.name == "create")
    assert create_method.is_static is True
    assert create_method.return_type == "Greeter"


def test_simple_method_parameter() -> None:
    classes = extract_classes(parse_typescript(SIMPLE_TS_SOURCE))
    greet_method = next(m for m in classes[0].methods if m.name == "greet")
    assert greet_method.parameters == (("who", "string"),)


def test_non_exported_class() -> None:
    source = "class Internal { public run(): void {} }"
    classes = extract_classes(parse_typescript(source))
    assert len(classes) == 1
    assert classes[0].is_exported is False
    assert classes[0].name == "Internal"


def test_class_without_extends() -> None:
    source = "class Standalone { }"
    classes = extract_classes(parse_typescript(source))
    assert classes[0].parent_class is None


def test_empty_source_yields_no_classes() -> None:
    classes = extract_classes(parse_typescript(""))
    assert classes == []


EXPECTED_MULTIPLE_CLASS_COUNT = 2


def test_multiple_classes() -> None:
    source = "class A {} class B extends A {}"
    classes = extract_classes(parse_typescript(source))
    assert len(classes) == EXPECTED_MULTIPLE_CLASS_COUNT
    assert classes[0].name == "A"
    assert classes[1].name == "B"
    assert classes[1].parent_class == "A"


def test_field_without_type_annotation() -> None:
    source = "class Foo { private logger = 42; }"
    classes = extract_classes(parse_typescript(source))
    assert len(classes[0].fields) == 1
    assert classes[0].fields[0].name == "logger"
    assert classes[0].fields[0].ts_type == ""
