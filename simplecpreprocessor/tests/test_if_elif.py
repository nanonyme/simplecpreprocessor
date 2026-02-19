"""Tests for #if and #elif directives."""
from __future__ import absolute_import
import pytest
from simplecpreprocessor import preprocess
from simplecpreprocessor.filesystem import FakeFile
from simplecpreprocessor.exceptions import ParseError


def run_case(input_list, expected):
    ret = preprocess(input_list)
    output = "".join(ret)
    assert output == expected


def test_if_true_simple():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_false_simple():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "X\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_if_with_expression():
    f_obj = FakeFile("header.h", [
        "#if 2 + 3\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_comparison_true():
    f_obj = FakeFile("header.h", [
        "#if 5 > 3\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_comparison_false():
    f_obj = FakeFile("header.h", [
        "#if 3 > 5\n",
        "X\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_if_with_defined_true():
    f_obj = FakeFile("header.h", [
        "#define FOO\n",
        "#if defined(FOO)\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_defined_false():
    f_obj = FakeFile("header.h", [
        "#if defined(FOO)\n",
        "X\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_if_with_defined_no_parens():
    f_obj = FakeFile("header.h", [
        "#define BAR\n",
        "#if defined BAR\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_logical_and_true():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#define B\n",
        "#if defined(A) && defined(B)\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_logical_and_false():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#if defined(A) && defined(B)\n",
        "X\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_if_with_logical_or_true():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#if defined(A) || defined(B)\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_logical_not():
    f_obj = FakeFile("header.h", [
        "#if !defined(FOO)\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_else_true():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "X\n",
        "#else\n",
        "Y\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_else_false():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "X\n",
        "#else\n",
        "Y\n",
        "#endif\n"
    ])
    expected = "Y\n"
    run_case(f_obj, expected)


def test_elif_first_true():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "A\n",
        "#elif 1\n",
        "B\n",
        "#endif\n"
    ])
    expected = "A\n"
    run_case(f_obj, expected)


def test_elif_second_true():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 1\n",
        "B\n",
        "#endif\n"
    ])
    expected = "B\n"
    run_case(f_obj, expected)


def test_elif_all_false():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 0\n",
        "B\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_elif_multiple():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 0\n",
        "B\n",
        "#elif 1\n",
        "C\n",
        "#endif\n"
    ])
    expected = "C\n"
    run_case(f_obj, expected)


def test_elif_with_else():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 0\n",
        "B\n",
        "#else\n",
        "C\n",
        "#endif\n"
    ])
    expected = "C\n"
    run_case(f_obj, expected)


def test_elif_with_defined():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif defined(FOO)\n",
        "B\n",
        "#else\n",
        "C\n",
        "#endif\n"
    ])
    expected = "C\n"
    run_case(f_obj, expected)


def test_elif_with_defined_true():
    f_obj = FakeFile("header.h", [
        "#define FOO\n",
        "#if 0\n",
        "A\n",
        "#elif defined(FOO)\n",
        "B\n",
        "#else\n",
        "C\n",
        "#endif\n"
    ])
    expected = "B\n"
    run_case(f_obj, expected)


def test_nested_if():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "#if 1\n",
        "X\n",
        "#endif\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_nested_if_outer_false():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "#if 1\n",
        "X\n",
        "#endif\n",
        "#endif\n"
    ])
    expected = ""
    run_case(f_obj, expected)


def test_if_left_open_causes_error():
    f_obj = FakeFile("header.h", ["#if 1\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    s = str(excinfo.value)
    assert "if" in s.lower()
    assert "left open" in s


def test_elif_without_if():
    f_obj = FakeFile("header.h", ["#elif 1\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "Unexpected #elif" in str(excinfo.value)


def test_elif_after_else():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "X\n",
        "#else\n",
        "Y\n",
        "#elif 1\n",
        "Z\n",
        "#endif\n"
    ])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "#elif after #else" in str(excinfo.value)


def test_else_after_else():
    """Test that #else after #else raises an error."""
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "X\n",
        "#else\n",
        "Y\n",
        "#else\n",
        "Z\n",
        "#endif\n"
    ])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "#else after #else" in str(excinfo.value)


def test_if_with_parentheses():
    f_obj = FakeFile("header.h", [
        "#if (1 + 2) * 3\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_complex_expression():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#if defined(A) && (1 + 1 == 2)\n",
        "X\n",
        "#endif\n"
    ])
    expected = "X\n"
    run_case(f_obj, expected)


def test_if_with_define_expansion():
    f_obj = FakeFile("header.h", [
        "#if 1\n",
        "#define X value\n",
        "#endif\n",
        "X\n"
    ])
    expected = "value\n"
    run_case(f_obj, expected)


def test_elif_stops_at_first_true():
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 1\n",
        "B\n",
        "#elif 1\n",
        "C\n",
        "#endif\n"
    ])
    expected = "B\n"
    run_case(f_obj, expected)


def test_if_with_invalid_expression():
    """Test #if with syntax error in expression."""
    f_obj = FakeFile("header.h", [
        "#if 1 (\n",
        "X\n",
        "#endif\n"
    ])
    with pytest.raises(ParseError, match="Error evaluating #if"):
        "".join(preprocess(f_obj))


def test_elif_with_invalid_expression():
    """Test #elif with syntax error in expression."""
    f_obj = FakeFile("header.h", [
        "#if 0\n",
        "A\n",
        "#elif 1 / 0\n",
        "B\n",
        "#endif\n"
    ])
    with pytest.raises(ParseError, match="Error evaluating #elif"):
        "".join(preprocess(f_obj))
