from __future__ import annotations

import tree_sitter_typescript as tst
from tree_sitter import Language, Parser

from tt.expressions import TransformContext
from tt.statements import transform_block, transform_statement

_EMPTY_MAP: dict[str, object] = {}

TS_LANGUAGE = Language(tst.language_typescript())


def _parse_first_statement(code: str) -> object:
    parser = Parser(TS_LANGUAGE)
    tree = parser.parse(code.encode("utf-8"))
    named = [c for c in tree.root_node.children if c.is_named]
    assert len(named) >= 1, f"Expected at least 1 statement, got {len(named)}"
    return named[0]


def _parse_all_statements(code: str) -> list[object]:
    parser = Parser(TS_LANGUAGE)
    tree = parser.parse(code.encode("utf-8"))
    return [c for c in tree.root_node.children if c.is_named]


class TestTransformContext:
    def test_default_indent_level(self) -> None:
        ctx = TransformContext(import_map=_EMPTY_MAP)
        assert ctx.indent_level == 0
        assert ctx.indent == ""

    def test_indented_creates_child_context(self) -> None:
        ctx = TransformContext(import_map=_EMPTY_MAP, indent_level=0)
        child = ctx.indented()
        assert child.indent_level == 1
        assert child.indent == "    "

    def test_double_indented(self) -> None:
        expected_level = 2
        ctx = TransformContext(import_map=_EMPTY_MAP).indented().indented()
        assert ctx.indent_level == expected_level
        assert ctx.indent == "        "

    def test_frozen(self) -> None:
        import pytest  # noqa: PLC0415

        ctx = TransformContext(import_map=_EMPTY_MAP)
        with pytest.raises(AttributeError):
            ctx.indent_level = 5  # type: ignore[misc]


class TestVariableDeclarations:
    def test_const_number(self) -> None:
        node = _parse_first_statement("const x = 1;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x = 1"]

    def test_let_number(self) -> None:
        node = _parse_first_statement("let y = 2;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["y = 2"]

    def test_typed_declaration_stripped(self) -> None:
        node = _parse_first_statement("const x: number = 42;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x = 42"]

    def test_let_typed_declaration_stripped(self) -> None:
        node = _parse_first_statement("let y: string = 'hello';")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ['y = "hello"']

    def test_uninitialized_declaration(self) -> None:
        node = _parse_first_statement("let x: number;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x = None"]

    def test_const_with_expression(self) -> None:
        node = _parse_first_statement("const z = a + b;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["z = (a + b)"]

    def test_indented_declaration(self) -> None:
        node = _parse_first_statement("const x = 1;")
        ctx = TransformContext(import_map=_EMPTY_MAP, indent_level=2)
        result = transform_statement(node, ctx)  # type: ignore[arg-type]
        assert result == ["        x = 1"]


class TestObjectDestructuring:
    def test_simple_destructuring(self) -> None:
        node = _parse_first_statement("const { a, b } = obj;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ['a = obj["a"]', 'b = obj["b"]']

    def test_renamed_destructuring(self) -> None:
        node = _parse_first_statement("const { a: renamed } = obj;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ['renamed = obj["a"]']

    def test_mixed_destructuring(self) -> None:
        node = _parse_first_statement("const { a, b: other } = obj;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ['a = obj["a"]', 'other = obj["b"]']


class TestArrayDestructuring:
    def test_array_destructuring(self) -> None:
        node = _parse_first_statement("const [key, value] = pair;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["key = pair[0]", "value = pair[1]"]


class TestIfStatement:
    def test_simple_if(self) -> None:
        node = _parse_first_statement("if (cond) { foo(); }")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "if cond:"
        assert any("foo()" in line for line in result)

    def test_if_else(self) -> None:
        node = _parse_first_statement("if (cond) { foo(); } else { bar(); }")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "if cond:"
        assert "else:" in result

    def test_if_elif_else(self) -> None:
        code = "if (a) { foo(); } else if (b) { bar(); } else { baz(); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "if a:"
        assert any("elif b:" in line for line in result)
        assert "else:" in result


class TestForOfLoop:
    def test_simple_for_of(self) -> None:
        node = _parse_first_statement("for (const item of items) { process(item); }")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "for item in items:"

    def test_for_of_with_destructuring(self) -> None:
        code = "for (const [key, value] of entries) { use(key); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "for key, value in entries:"


class TestForCStyleLoop:
    def test_simple_c_style_for(self) -> None:
        code = "for (let i = 0; i < n; i++) { process(i); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "for i in range(n):"

    def test_c_style_for_with_augmented_update(self) -> None:
        code = "for (let i = 0; i < n; i += 1) { process(i); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "for i in range(n):"

    def test_c_style_for_nonzero_start(self) -> None:
        code = "for (let i = 5; i < n; i++) { process(i); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "for i in range(5, n):"


class TestWhileLoop:
    def test_simple_while(self) -> None:
        node = _parse_first_statement("while (running) { tick(); }")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "while running:"
        assert any("tick()" in line for line in result)


class TestReturnStatement:
    def test_return_expression(self) -> None:
        node = _parse_first_statement("return result;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["return result"]

    def test_return_void(self) -> None:
        node = _parse_first_statement("return;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["return"]

    def test_return_complex_expression(self) -> None:
        node = _parse_first_statement("return a + b;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["return (a + b)"]


class TestExpressionStatement:
    def test_function_call(self) -> None:
        node = _parse_first_statement("foo();")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["foo()"]

    def test_method_call(self) -> None:
        node = _parse_first_statement("obj.method();")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["obj.method()"]


class TestAssignmentExpression:
    def test_simple_assignment(self) -> None:
        node = _parse_first_statement("x = y;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x = y"]

    def test_member_assignment(self) -> None:
        node = _parse_first_statement("obj.prop = value;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["obj.prop = value"]

    def test_augmented_plus_equals(self) -> None:
        node = _parse_first_statement("x += 1;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x += 1"]

    def test_augmented_minus_equals(self) -> None:
        node = _parse_first_statement("x -= 5;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["x -= 5"]


class TestSwitchStatement:
    def test_switch_to_if_elif(self) -> None:
        code = "switch(val) { case 1: break; case 2: break; default: break; }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert any("if val == 1:" in line for line in result)
        assert any("elif val == 2:" in line for line in result)
        assert "else:" in result


class TestTryCatch:
    def test_try_catch(self) -> None:
        code = "try { foo(); } catch (e) { bar(); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "try:"
        assert any("except Exception as e:" in line for line in result)

    def test_try_catch_named_param(self) -> None:
        code = "try { foo(); } catch (err) { bar(); }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert any("except Exception as err:" in line for line in result)


class TestBreakContinue:
    def test_break(self) -> None:
        node = _parse_first_statement("break;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["break"]

    def test_continue(self) -> None:
        node = _parse_first_statement("continue;")
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result == ["continue"]


class TestTransformBlock:
    def test_multiple_statements(self) -> None:
        code = "{ const x = 1; const y = 2; }"
        parser = Parser(TS_LANGUAGE)
        tree = parser.parse(code.encode("utf-8"))
        block_node = tree.root_node.children[0]
        result = transform_block(block_node, TransformContext(import_map=_EMPTY_MAP, indent_level=1))  # type: ignore[arg-type]
        assert result == ["    x = 1", "    y = 2"]


class TestNestedBlocks:
    def test_if_with_nested_for(self) -> None:
        code = "if (cond) { for (const x of arr) { use(x); } }"
        node = _parse_first_statement(code)
        result = transform_statement(node, TransformContext(import_map=_EMPTY_MAP))  # type: ignore[arg-type]
        assert result[0] == "if cond:"
        assert any("for x in arr:" in line for line in result)
        assert any("use(x)" in line for line in result)

    def test_deeply_nested_indentation(self) -> None:
        code = "if (a) { if (b) { foo(); } }"
        node = _parse_first_statement(code)
        ctx = TransformContext(import_map=_EMPTY_MAP, indent_level=0)
        result = transform_statement(node, ctx)  # type: ignore[arg-type]
        assert result[0] == "if a:"
        assert "    if b:" in result
        assert "        foo()" in result
