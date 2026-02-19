from __future__ import absolute_import
from simplecpreprocessor import preprocess
from simplecpreprocessor.filesystem import FakeFile


def run_case(input_list, expected):
    ret = preprocess(input_list)
    output = "".join(ret)
    assert output == expected


def test_function_macro_simple():
    """Test basic function-like macro with one parameter."""
    f_obj = FakeFile("header.h", [
        "#define SQUARE(x) ((x) * (x))\n",
        "SQUARE(5)\n"])
    expected = "((5) * (5))\n"
    run_case(f_obj, expected)


def test_function_macro_two_params():
    """Test function-like macro with two parameters."""
    f_obj = FakeFile("header.h", [
        "#define MAX(a, b) ((a) > (b) ? (a) : (b))\n",
        "MAX(1, 2)\n"])
    expected = "((1) > (2) ? (1) : (2))\n"
    run_case(f_obj, expected)


def test_function_macro_three_params():
    """Test function-like macro with three parameters."""
    f_obj = FakeFile("header.h", [
        "#define ADD3(a, b, c) ((a) + (b) + (c))\n",
        "ADD3(1, 2, 3)\n"])
    expected = "((1) + (2) + (3))\n"
    run_case(f_obj, expected)


def test_function_macro_no_params():
    """Test function-like macro with no parameters."""
    f_obj = FakeFile("header.h", [
        "#define FUNC() 42\n",
        "FUNC()\n"])
    expected = "42\n"
    run_case(f_obj, expected)


def test_function_macro_with_expression():
    """Test function-like macro with expression arguments."""
    f_obj = FakeFile("header.h", [
        "#define DOUBLE(x) ((x) * 2)\n",
        "DOUBLE(3 + 4)\n"])
    expected = "((3 + 4) * 2)\n"
    run_case(f_obj, expected)


def test_function_macro_not_called():
    """Test that function-like macro name without () is not expanded."""
    f_obj = FakeFile("header.h", [
        "#define SQUARE(x) ((x) * (x))\n",
        "SQUARE\n"])
    expected = "SQUARE\n"
    run_case(f_obj, expected)


def test_function_macro_whitespace_before_paren():
    """Test function-like macro with whitespace before opening paren."""
    f_obj = FakeFile("header.h", [
        "#define SQUARE(x) ((x) * (x))\n",
        "SQUARE (5)\n"])
    # With whitespace before (, it should still be treated as a call
    expected = "((5) * (5))\n"
    run_case(f_obj, expected)


def test_object_like_macro_with_parens_in_body():
    """Test object-like macro with parentheses in body."""
    f_obj = FakeFile("header.h", [
        "#define FOO (x)\n",
        "FOO\n"])
    expected = "(x)\n"
    run_case(f_obj, expected)


def test_function_macro_nested_calls():
    """Test nested function-like macro calls."""
    f_obj = FakeFile("header.h", [
        "#define DOUBLE(x) ((x) * 2)\n",
        "DOUBLE(DOUBLE(3))\n"])
    expected = "((((3) * 2)) * 2)\n"
    run_case(f_obj, expected)


def test_function_macro_multiple_on_line():
    """Test multiple function-like macro calls on one line."""
    f_obj = FakeFile("header.h", [
        "#define ADD(a, b) ((a) + (b))\n",
        "ADD(1, 2) ADD(3, 4)\n"])
    expected = "((1) + (2)) ((3) + (4))\n"
    run_case(f_obj, expected)


def test_function_macro_empty_arg():
    """Test function-like macro with empty argument."""
    f_obj = FakeFile("header.h", [
        "#define FUNC(x, y) x y\n",
        "FUNC(a, )\n"])
    # The space between x and y in the body is preserved
    expected = "a \n"
    run_case(f_obj, expected)


def test_function_macro_redefine():
    """Test redefining a function-like macro."""
    f_obj = FakeFile("header.h", [
        "#define FUNC(x) (x)\n",
        "FUNC(1)\n",
        "#undef FUNC\n",
        "#define FUNC(x) ((x) * 2)\n",
        "FUNC(2)\n"])
    expected = "(1)\n((2) * 2)\n"
    run_case(f_obj, expected)
