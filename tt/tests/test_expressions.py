from __future__ import annotations

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from tt.expressions import TransformContext, transform_expression

TS_LANGUAGE = Language(tsts.language_typescript())

IMPORT_MAP_WITH_TYPES: dict[str, object] = {
    "types": {
        "PortfolioOrderItem": "dict",
        "PortfolioSnapshot": "dict",
        "TimelinePosition": "dict",
        "SymbolMetrics": "dict",
    },
    "libraries": {
        "big.js": {
            "module": "decimal",
            "mappings": {"Big": "Decimal"},
            "constructor": "Decimal",
        },
        "date-fns": {
            "module": "date_utils",
            "mappings": {
                "format": "format_date",
                "isBefore": "is_before",
                "differenceInDays": "difference_in_days",
                "addMilliseconds": "add_milliseconds",
                "eachYearOfInterval": "each_year_of_interval",
                "isThisYear": "is_this_year",
            },
        },
        "lodash": {
            "module": None,
            "mappings": {
                "cloneDeep": "copy.deepcopy",
                "sortBy": "sorted",
            },
        },
    },
    "constants": {"DATE_FORMAT": "yyyy-MM-dd"},
}


def _parse_expression(code: str) -> object:
    parser = Parser(TS_LANGUAGE)
    tree = parser.parse(code.encode("utf-8"))
    root = tree.root_node
    first_stmt = next((c for c in root.children if c.is_named), root)
    named = [c for c in first_stmt.children if c.is_named]
    if first_stmt.type == "lexical_declaration" and named:
        var_decl = named[0]
        decl_named = [c for c in var_decl.children if c.is_named]
        return decl_named[1] if len(decl_named) >= 2 else first_stmt  # noqa: PLR2004
    if first_stmt.type == "expression_statement" and named:
        return named[0]
    return first_stmt


def _ctx() -> TransformContext:
    return TransformContext(import_map=IMPORT_MAP_WITH_TYPES)


def _transform(code: str) -> str:
    node = _parse_expression(code)
    return transform_expression(node, _ctx())  # type: ignore[arg-type]


class TestBigJsConstructor:
    def test_new_big_zero(self) -> None:
        result = _transform("let x = new Big(0);")
        assert result == "Decimal(str(0))"

    def test_new_big_with_variable(self) -> None:
        result = _transform("let x = new Big(value);")
        assert result == "Decimal(str(value))"


class TestBigJsMethods:
    def test_plus(self) -> None:
        result = _transform("let x = a.plus(b);")
        assert "+" in result
        assert "Decimal(str(" in result

    def test_minus(self) -> None:
        result = _transform("let x = a.minus(b);")
        assert "-" in result

    def test_mul(self) -> None:
        result = _transform("let x = a.mul(b);")
        assert "*" in result

    def test_div(self) -> None:
        result = _transform("let x = a.div(b);")
        assert "/" in result

    def test_eq(self) -> None:
        result = _transform("let x = a.eq(0);")
        assert "==" in result

    def test_gt(self) -> None:
        result = _transform("let x = a.gt(0);")
        assert ">" in result

    def test_gte(self) -> None:
        result = _transform("let x = a.gte(0);")
        assert ">=" in result

    def test_lt(self) -> None:
        result = _transform("let x = a.lt(0);")
        assert "<" in result
        assert "<=" not in result

    def test_lte(self) -> None:
        result = _transform("let x = a.lte(0);")
        assert "<=" in result

    def test_to_number(self) -> None:
        result = _transform("let x = a.toNumber();")
        assert result == "float(a)"

    def test_abs(self) -> None:
        result = _transform("let x = a.abs();")
        assert result == "abs(a)"

    def test_to_fixed(self) -> None:
        result = _transform("let x = a.toFixed(2);")
        assert "2" in result
        assert "f" in result

    def test_chained_method(self) -> None:
        result = _transform("let x = a.mul(b).plus(c);")
        assert "+" in result
        assert "*" in result


class TestOperators:
    def test_strict_equality(self) -> None:
        result = _transform("let x = a === b;")
        assert "==" in result
        assert "===" not in result

    def test_strict_inequality(self) -> None:
        result = _transform("let x = a !== b;")
        assert "!=" in result
        assert "!==" not in result

    def test_logical_or(self) -> None:
        result = _transform("let x = a || b;")
        assert " or " in result

    def test_logical_and(self) -> None:
        result = _transform("let x = a && b;")
        assert " and " in result

    def test_logical_not(self) -> None:
        result = _transform("let x = !a;")
        assert "not " in result

    def test_nullish_coalescing(self) -> None:
        result = _transform("let x = a ?? b;")
        assert "is not None" in result

    def test_instanceof(self) -> None:
        result = _transform("let x = a instanceof Big;")
        assert "isinstance(a, Decimal)" in result


class TestTernary:
    def test_simple_ternary(self) -> None:
        result = _transform("let x = a ? b : c;")
        assert "if" in result
        assert "else" in result


class TestTemplateString:
    def test_template_with_expression(self) -> None:
        result = _transform("let x = `hello ${name}`;")
        assert result.startswith('f"')
        assert "name" in result
        assert "hello" in result


class TestStringTransform:
    def test_single_to_double_quotes(self) -> None:
        result = _transform("let x = 'test';")
        assert '"test"' in result


class TestPropertyAccess:
    def test_this_access(self) -> None:
        result = _transform("let x = this.myProp;")
        assert result == "self.my_prop"

    def test_domain_dict_access(self) -> None:
        result = _transform("let x = order.unitPrice;")
        assert '["unitPrice"]' in result

    def test_length_to_len(self) -> None:
        result = _transform("let x = arr.length;")
        assert result == "len(arr)"

    def test_number_epsilon(self) -> None:
        result = _transform("let x = Number.EPSILON;")
        assert "sys.float_info.epsilon" in result

    def test_optional_chaining(self) -> None:
        result = _transform("let x = a?.b;")
        assert "is not None" in result
        assert "None" in result


class TestDateFunctions:
    def test_format(self) -> None:
        result = _transform("let x = format(date, 'yyyy-MM-dd');")
        assert "format_date" in result

    def test_is_before(self) -> None:
        result = _transform("let x = isBefore(a, b);")
        assert "is_before(a, b)" in result

    def test_difference_in_days(self) -> None:
        result = _transform("let x = differenceInDays(a, b);")
        assert "difference_in_days(a, b)" in result

    def test_add_milliseconds(self) -> None:
        result = _transform("let x = addMilliseconds(d, ms);")
        assert "add_milliseconds(d, ms)" in result

    def test_each_year_of_interval(self) -> None:
        result = _transform("let x = eachYearOfInterval(obj);")
        assert "each_year_of_interval(obj)" in result

    def test_is_this_year(self) -> None:
        result = _transform("let x = isThisYear(d);")
        assert "is_this_year(d)" in result


class TestLodash:
    def test_clone_deep(self) -> None:
        result = _transform("let x = cloneDeep(obj);")
        assert "copy.deepcopy(obj)" in result

    def test_sort_by(self) -> None:
        result = _transform("let x = sortBy(arr, fn);")
        assert "sorted(arr, key=fn)" in result


class TestArrayMethods:
    def test_push(self) -> None:
        result = _transform("let x = arr.push(item);")
        assert "append" in result

    def test_filter(self) -> None:
        result = _transform("let x = arr.filter(fn);")
        assert "for x in" in result
        assert "if" in result

    def test_map(self) -> None:
        result = _transform("let x = arr.map(fn);")
        assert "for x in" in result

    def test_includes(self) -> None:
        result = _transform("let x = arr.includes(val);")
        assert "in" in result

    def test_find_index(self) -> None:
        result = _transform("let x = arr.findIndex(fn);")
        assert "enumerate" in result
        assert "next" in result

    def test_at(self) -> None:
        result = _transform("let x = arr.at(-1);")
        assert "arr[" in result
        assert "-1" in result

    def test_get_time(self) -> None:
        result = _transform("let x = d.getTime();")
        assert "timestamp" in result


class TestArrowFunction:
    def test_simple_arrow(self) -> None:
        result = _transform("let x = arr.filter((item) => { return item > 0; });")
        assert "lambda" in result or "for" in result

    def test_destructured_param(self) -> None:
        result = _transform("let x = arr.filter(({ type }) => { return type === 'BUY'; });")
        assert "lambda" in result or "for" in result


class TestObjectLiteral:
    def test_object_with_pairs(self) -> None:
        result = _transform("let x = { a: 1, b: 2 };")
        assert '"a": 1' in result
        assert '"b": 2' in result

    def test_shorthand_property(self) -> None:
        result = _transform("let x = { myVar };")
        assert '"myVar"' in result
        assert "my_var" in result


class TestArrayLiteral:
    def test_simple_array(self) -> None:
        result = _transform("let x = [1, 2, 3];")
        assert result == "[1, 2, 3]"


class TestAssignment:
    def test_simple_assignment(self) -> None:
        result = _transform("x = 5;")
        assert "x = 5" in result

    def test_augmented_add(self) -> None:
        result = _transform("x += 1;")
        assert "+=" in result


class TestParenthesized:
    def test_parens(self) -> None:
        result = _transform("let x = (a + b);")
        assert "(" in result
        assert ")" in result


class TestUpdateExpression:
    def test_increment(self) -> None:
        result = _transform("x++;")
        assert "+= 1" in result

    def test_decrement(self) -> None:
        result = _transform("x--;")
        assert "-= 1" in result


class TestIdentifier:
    def test_camel_to_snake(self) -> None:
        result = _transform("let x = myVariable;")
        assert result == "my_variable"

    def test_undefined_to_none(self) -> None:
        result = _transform("let x = undefined;")
        assert result == "None"

    def test_constant_preserved(self) -> None:
        result = _transform("let x = DATE_FORMAT;")
        assert result == "DATE_FORMAT"


class TestLiterals:
    def test_this(self) -> None:
        result = _transform("let x = this;")
        assert result == "self"

    def test_true(self) -> None:
        result = _transform("let x = true;")
        assert result == "True"

    def test_false(self) -> None:
        result = _transform("let x = false;")
        assert result == "False"

    def test_null(self) -> None:
        result = _transform("let x = null;")
        assert result == "None"

    def test_number(self) -> None:
        result = _transform("let x = 42;")
        assert result == "42"


class TestConsoleAndLogger:
    def test_console_log(self) -> None:
        result = _transform("console.log('test');")
        assert "print(" in result

    def test_logger_warn(self) -> None:
        result = _transform("Logger.warn('msg', 'ctx');")
        assert "logger.warning(" in result


class TestNewExpression:
    def test_new_date_no_args(self) -> None:
        result = _transform("let x = new Date();")
        assert "datetime.now()" in result

    def test_new_date_with_arg(self) -> None:
        result = _transform("let x = new Date(str);")
        assert "datetime.fromisoformat" in result


class TestSubscript:
    def test_subscript(self) -> None:
        result = _transform("let x = arr[0];")
        assert "arr[0]" in result


class TestObjectStaticMethods:
    def test_object_keys(self) -> None:
        result = _transform("let x = Object.keys(obj);")
        assert "list(obj.keys())" in result
