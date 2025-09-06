from __future__ import absolute_import
import pytest
from simplecpreprocessor import preprocess
from simplecpreprocessor.filesystem import FakeFile
from simplecpreprocessor.exceptions import ParseError


def run_case(input_list, expected):
    ret = preprocess(input_list)
    output = "".join(ret)
    assert output == expected


def test_no_trailing_newline():
    f_obj = FakeFile("header.h", ["#ifdef foo\n",
                                  '#endif'])
    expected = ''
    run_case(f_obj, expected)


def test_multiline_define():
    f_obj = FakeFile("header.h", ["#define FOO \\\n",
                                  "\t1\n",
                                  "FOO\n"])
    expected = "\\\n\t1\n"
    run_case(f_obj, expected)


def test_define_simple__referential():
    f_obj = FakeFile("header.h", ["#define FOO FOO\n",
                                  "FOO\n"])
    expected = "FOO\n"
    run_case(f_obj, expected)


def test_expand_size_t():
    f_obj = FakeFile("header.h", ["__SIZE_TYPE__\n"])
    expected = "size_t\n"
    run_case(f_obj, expected)


def test_define_indirect__reference():
    f_obj = FakeFile("header.h", ["#define x (4 + y)\n",
                                  "#define y (2 * x)\n",
                                  "x\n", "y\n"])
    expected = "(4 + (2 * x))\n(2 * (4 + y))\n"
    run_case(f_obj, expected)


def test_define_indirect__reference_multiple():
    f_obj = FakeFile("header.h", ["#define I 1\n",
                                  "#define J I + 2\n",
                                  "#define K I + J\n",
                                  "I\n", "J\n", "K\n"])
    expected = "1\n1 + 2\n1 + 1 + 2\n"
    run_case(f_obj, expected)


def test_partial_match():
    f_obj = FakeFile("header.h", [
                     "#define FOO\n",
                     "FOOBAR\n"
                     ])
    expected = "FOOBAR\n"
    run_case(f_obj, expected)


def test_blank_define():
    f_obj = FakeFile("header.h", ["#define FOO\n",
                                  "FOO\n"])
    expected = "\n"
    run_case(f_obj, expected)


def test_define_parens():
    f_obj = FakeFile("header.h", ["#define FOO (x)\n",
                                  "FOO\n"])
    expected = "(x)\n"
    run_case(f_obj, expected)


def test_define_undefine():
    f_obj = FakeFile("header.h", ["#define FOO 1\n",
                                  "#undef FOO\n",
                                  "FOO\n"])
    expected = "FOO\n"
    run_case(f_obj, expected)


def test_complex_ignore():
    f_obj = FakeFile("header.h",
                     [
                         "#ifdef X\n",
                         "#define X 1\n",
                         "#ifdef X\n",
                         "#define X 2\n",
                         "#else\n",
                         "#define X 3\n",
                         "#endif\n",
                         "#define X 4\n",
                         "#endif\n",
                         "X\n"])
    expected = "X\n"
    run_case(f_obj, expected)


def test_extra_endif_causes_error():
    input_list = ["#endif\n"]
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(input_list))
    assert "Unexpected #endif" in str(excinfo)


def test_extra_else_causes_error():
    input_list = ["#else\n"]
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(input_list))
    assert "Unexpected #else" in str(excinfo.value)


def test_ifdef_left_open_causes_error():
    f_obj = FakeFile("header.h", ["#ifdef FOO\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    s = str(excinfo.value)
    assert "ifdef" in s
    assert "left open" in s


def test_ifndef_left_open_causes_error():
    f_obj = FakeFile("header.h", ["#ifndef FOO\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    s = str(excinfo.value)
    assert "ifndef" in s
    assert "left open" in s


def test_unsupported_pragma():
    f_obj = FakeFile("header.h", ["#pragma bogus\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "Unsupported pragma" in str(excinfo.value)


def test_else_left_open_causes_error():
    f_obj = FakeFile("header.h", ["#ifdef FOO\n", "#else\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    s = str(excinfo.value)
    assert "else" in s
    assert "left open" in s


def test_unexpected_macro_gives_parse_error():
    f_obj = FakeFile("header.h", ["#something_unsupported foo bar\n"])
    with pytest.raises(ParseError):
        "".join(preprocess(f_obj))


def test_ifndef_unfulfilled_define_ignored():
    f_obj = FakeFile("header.h", ["#define FOO\n", "#ifndef FOO\n",
                                  "#define BAR 1\n",
                                  "#endif\n", "BAR\n"])
    expected = "BAR\n"
    run_case(f_obj, expected)


def test_ifdef_unfulfilled_define_ignored():
    f_obj = FakeFile("header.h", ["#ifdef FOO\n",
                                  "#define BAR 1\n",
                                  "#endif\n", "BAR\n"])
    expected = "BAR\n"
    run_case(f_obj, expected)


def test_ifndef_fulfilled_define_allowed():
    f_obj = FakeFile("header.h", ["#ifndef FOO\n",
                                  "#define BAR 1\n",
                                  "#endif\n",
                                  "BAR\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_fulfilled_ifdef_define_allowed():
    f_obj = FakeFile("header.h", ["#define FOO\n",
                                  "#ifdef FOO\n",
                                  "#define BAR 1\n",
                                  "#endif\n",
                                  "BAR\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_define_inside_ifndef():
    f_obj = FakeFile("header.h", ["#ifndef MODULE\n",
                                  "#define MODULE\n",
                                  "#ifdef BAR\n",
                                  "5\n",
                                  "#endif\n",
                                  "1\n",
                                  "#endif\n"])

    expected = "1\n"
    run_case(f_obj, expected)


def test_ifdef_else_undefined():
    f_obj = FakeFile("header.h", [
        "#ifdef A\n",
        "#define X 1\n",
        "#else\n",
        "#define X 0\n",
        "#endif\n",
        "X\n"])
    expected = "0\n"
    run_case(f_obj, expected)


def test_ifdef_else_defined():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#ifdef A\n",
        "#define X 1\n",
        "#else\n",
        "#define X 0\n",
        "#endif\n",
        "X\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_ifndef_else_undefined():
    f_obj = FakeFile("header.h", [
        "#ifndef A\n",
        "#define X 1\n",
        "#else\n",
        "#define X 0\n",
        "#endif\n",
        "X\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_ifndef_else_defined():
    f_obj = FakeFile("header.h", [
        "#define A\n",
        "#ifndef A\n",
        "#define X 1\n",
        "#else\n",
        "#define X 0\n",
        "#endif\n",
        "X\n"])
    expected = "0\n"
    run_case(f_obj, expected)


def test_lines_normalized():
    f_obj = FakeFile("header.h", ["foo\r\n", "bar\r\n"])
    expected = "foo\nbar\n"
    run_case(f_obj, expected)


def test_lines_normalize_custom():
    f_obj = FakeFile("header.h", ["foo\n", "bar\n"])
    expected = "foo\r\nbar\r\n"
    ret = preprocess(f_obj, line_ending="\r\n")
    assert "".join(ret) == expected


def test_define_with_comment():
    f_obj = FakeFile("header.h", [
        "#define FOO 1 // comment\n",
        "FOO\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_ifdef_with_comment():
    f_obj = FakeFile("header.h", [
        "#define FOO\n",
        "#ifdef FOO // comment\n",
        "1\n",
        "#endif\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_tab_macro_indentation():
    f_obj = FakeFile("header.h", [
        "\t#define FOO 1\n",
        "\tFOO\n"])
    expected = "\t1\n"
    run_case(f_obj, expected)


def test_malformed_undef_with_whitespace_only():
    f_obj = FakeFile("header.h", ["#undef    \n"])
    run_case(f_obj, expected="")


def test_process_undef_not_defined():
    f_obj = FakeFile("header.h", ["#undef FOO\n", "FOO"])
    run_case(f_obj, expected="FOO")


def test_space_pragma_pack_passthrough():
    instructions = (
        "#pragma pack(push, 8)\n",
        "#pragma pack(pop)\n"
    )
    f_obj = FakeFile("header.h", instructions)
    expected = "".join(instructions)
    run_case(f_obj, expected)


def test_repeated_macro():
    f_obj = FakeFile("header.h", [
        '#define A value\n'
        'A A\n', ])
    ret = preprocess(f_obj)
    assert "".join(ret) == "value value\n"
