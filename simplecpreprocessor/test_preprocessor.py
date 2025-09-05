from __future__ import absolute_import
import pytest
import ntpath
from simplecpreprocessor import preprocess
from simplecpreprocessor.core import Preprocessor
from simplecpreprocessor.exceptions import ParseError, UnsupportedPlatform
from simplecpreprocessor.platform import (calculate_platform_constants,
                                          extract_platform_spec)
from simplecpreprocessor.filesystem import FakeFile, FakeHandler
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
