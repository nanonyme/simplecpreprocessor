from __future__ import absolute_import
import pytest
import ntpath
from simplecpreprocessor import preprocess
from simplecpreprocessor.core import Preprocessor, Tag
from simplecpreprocessor.exceptions import ParseError, UnsupportedPlatform
from simplecpreprocessor.platform import (calculate_platform_constants,
                                          extract_platform_spec)
from simplecpreprocessor.filesystem import FakeFile, FakeHandler
from simplecpreprocessor import tokens, exceptions
import posixpath
import os
import cProfile
from pstats import Stats
import platform
import mock

profiler = None

extract_platform_spec_path = ("simplecpreprocessor.platform."
                              "extract_platform_spec"
                              )


def setup_module(module):
    if "PROFILE" in os.environ:
        module.profiler = cProfile.Profile()
        module.profiler.enable()


def teardown_module(module):
    if module.profiler is not None:
        module.profiler.disable()
        p = Stats(module.profiler)
        p.strip_dirs()
        p.print_stats()


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


def test_invalid_include():
    f_obj = FakeFile("header.h", ["#include bogus\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "Invalid include" in str(excinfo.value)


def test_include_local_file_with_subdirectory():
    other_header = "somedirectory/other.h"
    f_obj = FakeFile("header.h", ['#include "%s"\n' % other_header])
    handler = FakeHandler({other_header: ["1\n"]})
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "1\n"


def test_include_local_file_with_subdirectory_windows():
    with mock.patch("os.path", ntpath):
        other_header = "somedirectory/other.h"
        f_obj = FakeFile("foo\\header.h", ['#include "%s"\n' % other_header])
        handler = FakeHandler({f"foo/{other_header}": ["1\n"]})
        ret = preprocess(f_obj, header_handler=handler)
        assert "".join(ret) == "1\n"


def test_include_local_precedence():
    other_header = "other.h"
    path = "bogus"
    f_obj = FakeFile("header.h", ['#include "%s"\n' % other_header])
    handler = FakeHandler({other_header: ["1\n"],
                           "%s/%s" % (path, other_header): ["2\n"]},
                          include_paths=[path])
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "1\n"


def test_include_local_fallback():
    other_header = "other.h"
    path = "bogus"
    f_obj = FakeFile("header.h", ['#include "%s"\n' % other_header])
    handler = FakeHandler({"%s/%s" % (path, other_header): ["2\n"]},
                          include_paths=[path])
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "2\n"


def test_ifdef_file_guard():
    other_header = "somedirectory/other.h"
    f_obj = FakeFile("header.h",
                     ['#include "%s"\n' % other_header])
    handler = FakeHandler({other_header: ["1\n"]})
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "1\n"


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


def test_include_with_path_list():
    f_obj = FakeFile("header.h", ['#include <other.h>\n'])
    directory = "subdirectory"
    handler = FakeHandler({posixpath.join(directory,
                                          "other.h"): ["1\n"]})
    include_paths = [directory]
    ret = preprocess(f_obj, include_paths=include_paths,
                     header_handler=handler)
    assert "".join(ret) == "1\n"


def test_include_preresolved():
    f_obj = FakeFile("header.h", ['#include <other.h>\n'])
    header = "other.h"
    path = posixpath.join("subdirectory", header)
    handler = FakeHandler({path: ["1\n"]})
    handler.resolved[header] = path
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "1\n"


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


def test_include_with_path_list_with_subdirectory():
    header_file = posixpath.join("nested", "other.h")
    include_path = "somedir"
    f_obj = FakeFile("header.h", ['#include <%s>\n' % header_file])
    handler = FakeHandler({posixpath.join(include_path,
                                          header_file): ["1\n"]})
    include_paths = [include_path]
    ret = preprocess(f_obj, include_paths=include_paths,
                     header_handler=handler)
    assert "".join(ret) == "1\n"


def test_include_missing_local_file():
    other_header = posixpath.join("somedirectory", "other.h")
    f_obj = FakeFile("header.h", ['#include "%s"\n' % other_header])
    handler = FakeHandler({})
    with pytest.raises(ParseError):
        "".join(preprocess(f_obj, header_handler=handler))


def test_ignore_include_path():
    f_obj = FakeFile("header.h", ['#include <other.h>\n'])
    handler = FakeHandler({posixpath.join("subdirectory",
                                          "other.h"): ["1\n"]})
    paths = ["subdirectory"]
    ignored = ["other.h"]
    ret = preprocess(f_obj, include_paths=paths,
                     header_handler=handler,
                     ignore_headers=ignored)
    assert "".join(ret) == ""


def test_pragma_once():
    f_obj = FakeFile("header.h", [
                     """#include "other.h"\n""",
                     """#include "other.h"\n""",
                     "X\n"])
    handler = FakeHandler({"other.h": [
        "#pragma once\n",
        "#ifdef X\n",
        "#define X 2\n",
        "#else\n",
        "#define X 1\n",
        "#endif\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "1\n"
    assert preprocessor.skip_file("other.h")


def test_fullfile_guard_ifdef_skip():
    f_obj = FakeFile("header.h", ["""#include "other.h"\n""",
                                  "1\n"])
    handler = FakeHandler({"other.h": [
        "#ifdef X\n",
        "#endif\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "1\n"
    assert preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_fullfile_guard_ifdef_noskip():
    f_obj = FakeFile("header.h", ["""#include "other.h"\n""",
                                  "#define X 1\n",
                                  "1\n"])
    handler = FakeHandler({"other.h": [
        "#ifdef X\n",
        "#endif\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "1\n"
    assert not preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_fullfile_guard_ifndef_skip():
    f_obj = FakeFile("header.h", ["""#include "other.h"\n""",
                                  "#define X\n",
                                  "done\n"])
    handler = FakeHandler({"other.h": [
        "#ifndef X\n",
        "#endif\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "done\n"
    assert preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_fullfile_guard_ifndef_noskip():
    f_obj = FakeFile("header.h", ["""#include "other.h"\n""",
                                  "done\n"])
    handler = FakeHandler({"other.h": [
        "#ifndef X\n",
        "#endif\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "done\n"
    assert not preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_no_fullfile_guard_ifdef():
    f_obj = FakeFile("header.h", ["#define X\n",
                                  """#include "other.h"\n""",
                                  "done\n"])
    handler = FakeHandler({"other.h": [
        "#ifdef X\n",
        "#undef X\n",
        "#endif\n",
        "foo\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "foo\ndone\n"
    assert preprocessor.include_once == {}
    assert not preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_no_fullfile_guard_ifndef():
    f_obj = FakeFile("header.h", ["""#include "other.h"\n""",
                                  "done\n"])
    handler = FakeHandler({"other.h": [
        "#ifndef X\n",
        "#define X\n",
        "#endif\n",
        "foo\n"]})
    preprocessor = Preprocessor(header_handler=handler)
    ret = preprocessor.preprocess(f_obj)
    assert "".join(ret) == "foo\ndone\n"
    assert preprocessor.include_once == {}
    assert not preprocessor.skip_file("other.h"), (
        "%s -> %s" % (preprocessor.include_once,
                      preprocessor.defines))


def test_platform_constants():
    f_obj = FakeFile("header.h", ['#ifdef ODDPLATFORM\n',
                                  'ODDPLATFORM\n', '#endif\n'])
    ret = preprocess(f_obj, extra_constants={"ODDPLATFORM": "ODDPLATFORM"})
    assert "".join(ret) == "ODDPLATFORM\n"


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


def test_handler_missing_file():
    handler = FakeHandler([])
    assert handler.parent_open("does_not_exist") is None


def test_handler_existing_file():
    handler = FakeHandler([])
    file_info = os.stat(__file__)
    with handler.parent_open(__file__) as f_obj:
        assert (os.fstat(f_obj.fileno()).st_ino ==
                file_info.st_ino)
        assert f_obj.name == __file__


def test_repeated_macro():
    f_obj = FakeFile("header.h", [
        '#define A value\n'
        'A A\n', ])
    ret = preprocess(f_obj)
    assert "".join(ret) == "value value\n"


def test_platform_undefine():
    with mock.patch(extract_platform_spec_path) as mock_spec:
        mock_spec.return_value = "Linux", "32bit"
        f_obj = FakeFile("header.h", [
            '#undef __i386__\n'
            '__i386__\n', ])
        ret = preprocess(f_obj)
        assert "".join(ret) == "__i386__\n"


def test_platform():
    with mock.patch(extract_platform_spec_path) as mock_spec:
        mock_spec.return_value = "Linux", "32bit"
        assert calculate_platform_constants() == {
            "__linux__": "__linux__",
            "__i386__": "1",
            "__i386": "1",
            "i386": "1",
            "__SIZE_TYPE__": "size_t",
        }

        mock_spec.return_value = "Linux", "64bit"
        assert calculate_platform_constants() == {
            "__linux__": "__linux__",
            "__x86_64__": "1",
            "__x86_64": "1",
            "__amd64__": "1",
            "__amd64": "1",
            "__SIZE_TYPE__": "size_t",
        }

        mock_spec.return_value = "Windows", "32bit"
        assert calculate_platform_constants() == {
            "_WIN32": "1",
            "__SIZE_TYPE__": "size_t",
            "CALLBACK": "__stdcall",
            "IN": "",
            "OUT": "",
        }

        mock_spec.return_value = "Windows", "64bit"
        assert calculate_platform_constants() == {
            "_WIN64": "1",
            "__SIZE_TYPE__": "size_t",
            "CALLBACK": "__stdcall",
            "IN": "",
            "OUT": "",
        }

        with pytest.raises(UnsupportedPlatform) as excinfo:
            mock_spec.return_value = "Linux", "128bit"
            calculate_platform_constants()
        assert "Unsupported bitness" in str(excinfo.value)

        with pytest.raises(UnsupportedPlatform) as excinfo:
            mock_spec.return_value = "Windows", "128bit"
            calculate_platform_constants()
        assert "Unsupported bitness" in str(excinfo.value)

        with pytest.raises(UnsupportedPlatform) as excinfo:
            mock_spec.return_value = "The Engine", "32it"
            calculate_platform_constants()
        assert "Unsupported platform" in str(excinfo.value)

    system = platform.system()
    bitness, _ = platform.architecture()
    assert extract_platform_spec() == (system, bitness)


def make_token(val, type_=tokens.TokenType.IDENTIFIER, ws=False):
    if ws:
        return tokens.Token.from_string(None, val, tokens.TokenType.WHITESPACE)
    return tokens.Token.from_constant(None, val, type_)


def test_process_define_assign_and_ignore():
    p = Preprocessor()
    # define when ignore True should be no-op
    p.ignore = True
    chunk = [
        make_token('NAME'),
        make_token(' ', type_=tokens.TokenType.WHITESPACE, ws=True),
    ]
    p.process_define(chunk=chunk)
    assert 'NAME' not in p.defines.defines

    # define assignment when not ignored
    p2 = Preprocessor()
    chunk2 = [
        make_token('FOO'),
        make_token(' ', type_=tokens.TokenType.WHITESPACE, ws=True),
        make_token('1'),
        make_token('\n', type_=tokens.TokenType.NEWLINE, ws=True),
    ]
    p2.process_define(chunk=chunk2)
    assert 'FOO' in p2.defines.defines
    # the stored define should be the middle token list (value '1')
    stored = p2.defines.get('FOO')
    assert any(t.value == '1' for t in stored)


def test_process_pragma_pack_and_once():
    p = Preprocessor()
    # need a header on the stack for pragma once
    p.header_stack.append(FakeFile('hdr.h', []))
    # pragma once
    list(p.process_pragma(chunk=[make_token('once')], line_no=1))
    assert p.include_once.get('hdr.h') == Tag.PRAGMA_ONCE

    # pragma pack yields values
    chunk = [
        make_token('pack'),
        make_token('('),
        make_token('4'),
        make_token(')')
    ]
    out = list(p.process_pragma(chunk=chunk, line_no=2))
    assert '#pragma' in out
    assert '(' in out and '4' in out


def test_ifdef_ifndef_branches_and_undef():
    p = Preprocessor()
    # ensure name not in defines to trigger ignore True
    chunk = [make_token('X')]
    p.process_ifdef(chunk=chunk, line_no=1)
    assert p.ignore is True
    # reset and add define to test else branch
    p2 = Preprocessor()
    p2.defines['X'] = [make_token('1')]
    p2.process_ifdef(chunk=chunk, line_no=1)
    assert any(c[0] == Tag.IFDEF for c in p2.constraints)

    # process_ifndef: when condition in defines should set ignore True
    p3 = Preprocessor()
    p3.defines['Y'] = [make_token('1')]
    p3.process_ifndef(chunk=[make_token('Y')], line_no=1)
    assert p3.ignore is True

    # process_undef removes define
    p4 = Preprocessor()
    p4.defines['Z'] = [make_token('1')]
    p4.process_undef(chunk=[make_token('Z')])
    assert 'Z' not in p4.defines.defines


def test_process_source_chunks_folding_and_expansion():
    p = Preprocessor(fold_strings_to_null=True)
    # TokenExpander will return tokens as given; test fold_strings_to_null
    s_tok = tokens.Token.from_constant(None, '"s"', tokens.TokenType.STRING)
    out = list(p.process_source_chunks([s_tok]))
    assert out == ['NULL']

    p2 = Preprocessor(fold_strings_to_null=False)
    out2 = list(
        p2.process_source_chunks([
            tokens.Token.from_constant(None, 'x', tokens.TokenType.IDENTIFIER),
        ])
    )
    assert out2 == ['x']


def test_skip_file_branches():
    p = Preprocessor()
    name = 'a.h'
    p.include_once[name] = Tag.PRAGMA_ONCE
    assert p.skip_file(name) is True
    p.include_once[name] = None
    assert p.skip_file(name) is False
    # IFDEF case
    p.include_once[name] = ('COND', Tag.IFDEF)
    # if 'COND' not in defines, skip_file should return True
    assert p.skip_file(name) is True
    # IFNDEF case
    p.include_once[name] = ('COND', Tag.IFNDEF)
    p.defines['COND'] = [make_token('1')]
    assert p.skip_file(name) is True


def test__read_header_raises_on_missing():
    fh = FakeHandler({})
    p = Preprocessor(header_handler=fh)
    # try reading header not present; should raise the given error
    gen = p._read_header('nope.h', exceptions.ParseError('missing'))
    with pytest.raises(exceptions.ParseError):
        next(gen)


def test_process_include_error_cases():
    p = Preprocessor()
    # empty include name
    with pytest.raises(exceptions.ParseError):
        p.process_include(line_no=1, chunk=[make_token(' ', ws=True)])

    # invalid string include (bad formatting)
    bad_string = tokens.Token.from_constant(None, 'notquoted', tokens.TokenType.STRING)
    with pytest.raises(exceptions.ParseError):
        p.process_include(line_no=1, chunk=[bad_string])

    # angle bracket missing '>' because newline encountered
    with pytest.raises(exceptions.ParseError):
        p.process_include(
            line_no=2,
            chunk=[
                make_token('<'),
                tokens.Token.from_string(None, '\n', tokens.TokenType.NEWLINE)
            ],
        )

    # angle bracket missing '>' because iterator exhausted
    with pytest.raises(exceptions.ParseError):
        p.process_include(line_no=3, chunk=[make_token('<'), make_token('a')])


def test_check_fullfile_guard_sets_include_once():
    p = Preprocessor()
    # set last_constraint with begin == 0
    p.last_constraint = ('GUARD', Tag.IFDEF, 0)
    p.header_stack.append(FakeFile('guard.h', []))
    p.check_fullfile_guard()
    assert p.include_once.get('guard.h') == ('GUARD', Tag.IFDEF)


def test_process_define_with_leading_whitespace_and_ifdef_whitespace():
    p = Preprocessor()
    # leading whitespace tokens before name
    chunk = [tokens.Token.from_string(None, '  ', tokens.TokenType.WHITESPACE),
             tokens.Token.from_string(None, '\t', tokens.TokenType.WHITESPACE),
             tokens.Token.from_constant(None, 'LW', tokens.TokenType.IDENTIFIER),
             tokens.Token.from_string(None, ' ', tokens.TokenType.WHITESPACE),
             tokens.Token.from_constant(None, '1', tokens.TokenType.IDENTIFIER),
             tokens.Token.from_string(None, '\n', tokens.TokenType.NEWLINE)]
    p.process_define(chunk=chunk)
    assert 'LW' in p.defines.defines

    # ifdef with leading whitespace
    p2 = Preprocessor()
    chunk2 = [tokens.Token.from_string(None, ' ', tokens.TokenType.WHITESPACE),
              tokens.Token.from_constant(None, 'COND', tokens.TokenType.IDENTIFIER)]
    p2.process_ifdef(chunk=chunk2, line_no=10)
    assert any(c[0] == Tag.IFDEF for c in p2.constraints)


def test_process_pragma_unsupported_raises():
    p = Preprocessor()
    with pytest.raises(exceptions.ParseError):
        # pragma token value that doesn't map to a handler
        for _ in p.process_pragma(
            chunk=[
                tokens.Token.from_constant(None, 'bogus', tokens.TokenType.IDENTIFIER)
            ],
            line_no=5,
        ):
            pass


def test_process_include_prefixed_string_extracts_header():
    # ensure header extraction for prefixes like u8"file"
    handler = FakeHandler({'file.h': ['x\n']})
    p = Preprocessor(header_handler=handler)
    p.header_stack.append(FakeFile('current.h', []))
    tok = tokens.Token.from_constant(None, 'u8"file.h"', tokens.TokenType.STRING)
    # process_include returns a generator (from _read_header) but header extraction runs first
    gen = p.process_include(line_no=1, chunk=[tok])
    # consuming the generator should not raise (header exists in FakeHandler)
    list(gen)


def _collect_chunk_strings(chunk):
    return "".join(t.value for t in chunk)


def test_token_from_string_and_constant():
    t1 = tokens.Token.from_string(5, "   ", tokens.TokenType.WHITESPACE)
    assert t1.line_no == 5
    assert t1.value == "   "
    assert t1.type is tokens.TokenType.WHITESPACE
    assert t1.whitespace is True

    t2 = tokens.Token.from_constant(1, "X", tokens.TokenType.IDENTIFIER)
    assert t2.whitespace is False
    assert t2.chunk_mark is False
    t2.chunk_mark = True
    assert t2.chunk_mark is True


def test_is_string_with_token_and_raw():
    s_tok = tokens.Token.from_constant(0, '"abc"', tokens.TokenType.STRING)
    assert tokens.is_string(s_tok) is True

    assert tokens.is_string('"hello"') is True
    assert tokens.is_string('L"wchar"') is True
    assert tokens.is_string('u8"hello"') is True

    assert tokens.is_string(123) is False
    assert tokens.is_string(
        tokens.Token.from_constant(0, "x", tokens.TokenType.IDENTIFIER)
    ) is False


def test_tokenexpander_simple_and_cycle():
    one = tokens.Token.from_constant(None, "1", tokens.TokenType.IDENTIFIER)
    a = tokens.Token.from_constant(None, "A", tokens.TokenType.IDENTIFIER)
    b = tokens.Token.from_constant(None, "B", tokens.TokenType.IDENTIFIER)

    defines = {"A": [one], "B": [a]}
    exp = tokens.TokenExpander(defines)
    out = list(exp.expand_tokens([b]))
    assert [t.value for t in out] == ["1"]

    x = tokens.Token.from_constant(None, "X", tokens.TokenType.IDENTIFIER)
    y = tokens.Token.from_constant(None, "Y", tokens.TokenType.IDENTIFIER)
    cyc = {"X": [y], "Y": [x]}
    exp2 = tokens.TokenExpander(cyc)
    out2 = list(exp2.expand_tokens([x]))
    assert any(t.value in ("X", "Y") for t in out2)


def test_tokenizer_read_chunks_with_and_without_trailing_newline():
    f = FakeFile("f.h", ["one\n", "two\n"])
    tok = tokens.Tokenizer(f, line_ending="\n")
    chunks = list(tok.read_chunks())
    assert len(chunks) == 2
    assert _collect_chunk_strings(chunks[0]) == "one\n"
    assert _collect_chunk_strings(chunks[1]) == "two\n"

    f2 = FakeFile("f.h", ["alpha\n", "beta"])
    tok2 = tokens.Tokenizer(f2, line_ending="\n")
    chunks2 = list(tok2.read_chunks())
    assert len(chunks2) == 2
    assert _collect_chunk_strings(chunks2[0]) == "alpha\n"
    assert _collect_chunk_strings(chunks2[1]) == "beta"


def test_scan_line_tokenizes_unterminated_string():
    f = FakeFile("f.h", ['"unterminated\n'])
    tok = tokens.Tokenizer(f, line_ending="\n")
    chunks = list(tok.read_chunks())
    assert len(chunks) >= 1
    text = "".join(t.value for t in chunks[0])
    assert '"' in text and 'unterminated' in text


def test_whitespace_before_hash_and_comment_start_is_ignored():
    f = FakeFile("f.h", ["   #\n"])
    tok = tokens.Tokenizer(f, line_ending="\n")
    chunks = list(tok.read_chunks())
    values = [t.value for t in chunks[0]]
    assert "#" in values
    assert "   " not in values

    f2 = FakeFile("f.h", ["   // comment\n"])
    tok2 = tokens.Tokenizer(f2, line_ending="\n")
    chunks2 = list(tok2.read_chunks())
    vals2 = [t.value for t in chunks2[0]]
    assert "   " not in vals2
    assert vals2 == ["\n"]


def test_scan_line_raises_syntaxerror_by_fake_scanner():
    f = FakeFile("f.h", ["x\n"])
    tok = tokens.Tokenizer(f, line_ending="\n")

    class FakeScanner:
        def scan(self, line):
            return ([], "BAD_REMAINDER")

    tok._scanner = FakeScanner()
    import pytest as _pytest
    with _pytest.raises(SyntaxError):
        tok._scan_line(0, "x\n")


def test_comment_start_and_end_single_line():
    f = FakeFile("f.h", ["/* comment */\n"])
    tok = tokens.Tokenizer(f, line_ending="\n")
    chunks = list(tok.read_chunks())
    assert len(chunks) == 1
    assert "".join(t.value for t in chunks[0]) == "\n"


def test_multiline_comment_skips_inner_tokens():
    f = FakeFile("f.h", ["/* start\n", "hello\n", "*/\n", "after\n"])
    tok = tokens.Tokenizer(f, line_ending="\n")
    chunks = list(tok.read_chunks())
    assert any("after" in "".join(t.value for t in c) for c in chunks)
    assert not any("hello" in "".join(t.value for t in c) for c in chunks)
