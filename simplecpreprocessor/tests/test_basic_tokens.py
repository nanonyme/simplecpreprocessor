from __future__ import absolute_import
from simplecpreprocessor import preprocess
from simplecpreprocessor.filesystem import FakeFile


def run_case(input_list, expected):
    ret = preprocess(input_list)
    output = "".join(ret)
    assert output == expected


def test_define():
    f_obj = FakeFile("header.h", ["#define FOO 1\n",
                                  "FOO\n"])
    expected = "1\n"
    run_case(f_obj, expected)


def test_define_no_trailing_newline():
    f_obj = FakeFile("header.h", ["#define FOO 1\n",
                                  "FOO"])
    expected = "1"
    run_case(f_obj, expected)


def test_string_token_special_characters():
    line = '"!/-*+"\n'
    f_obj = FakeFile("header.h", [line])
    expected = line
    run_case(f_obj, expected)


def test_char_token_simple():
    f_obj = FakeFile("header.h", ["#define F 1\n",
                                  "'F'\n"])
    expected = "'F'\n"
    run_case(f_obj, expected)


def test_commented_quote():
    text = "// 'foo\n"
    f_obj = FakeFile("header.h", [text])
    run_case(f_obj, "\n")


def test_multiline_commented_quote():
    lines = [" /* \n",
             " 'foo */\n"]
    f_obj = FakeFile("header.h", lines)
    run_case(f_obj, "\n")


def test_string_token_with_single_quote():
    f_obj = FakeFile("header.h", ["#define FOO 1\n",
                                  '"FOO\'"\n'])
    expected = '"FOO\'"\n'
    run_case(f_obj, expected)


def test_wchar_string():
    f_obj = FakeFile("header.h", ["#define L 1\n",
                                  'L"FOO"\n'])
    expected = 'L"FOO"\n'
    run_case(f_obj, expected)


def test_string_folding():
    f_obj = FakeFile("header.h", ['const char* foo = "meep";\n'])
    ret = preprocess(f_obj, fold_strings_to_null=True)
    assert "".join(ret) == "const char* foo = NULL;\n"


def test_string_folding_inside_condition():
    f_obj = FakeFile("header.h", [
        '#ifndef FOO\n',
        'const char* foo = "meep";\n',
        "#endif\n"
    ])
    ret = preprocess(f_obj, fold_strings_to_null=True)
    assert "".join(ret) == "const char* foo = NULL;\n"
