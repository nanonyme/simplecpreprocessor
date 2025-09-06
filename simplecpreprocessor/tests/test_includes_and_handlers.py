from __future__ import absolute_import
import posixpath
import ntpath
from simplecpreprocessor import preprocess
from simplecpreprocessor.core import Preprocessor
from simplecpreprocessor.exceptions import ParseError
from simplecpreprocessor.filesystem import FakeFile, FakeHandler
import mock
import pytest


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


def test_ifdef_file_guard():
    other_header = "somedirectory/other.h"
    f_obj = FakeFile("header.h",
                     ['#include "%s"\n' % other_header])
    handler = FakeHandler({other_header: ["1\n"]})
    ret = preprocess(f_obj, header_handler=handler)
    assert "".join(ret) == "1\n"


def test_invalid_include():
    f_obj = FakeFile("header.h", ["#include bogus\n"])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "Invalid include" in str(excinfo.value)


def test_include_no_filename():
    """Fail when an include directive has no filename after it."""
    f_obj = FakeFile("header.h", ['#include \n'])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "empty include name" in str(excinfo.value)


def test_include_missing_quotes():
    """
    Fail when an include directive provides a filename without quotes or <>.
    """
    f_obj = FakeFile("header.h", ['#include other.h\n'])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "Invalid include" in str(excinfo.value)


def test_include_missing_closing_angle():
    """Fail when an angle-bracket include is missing the closing '>'."""
    f_obj = FakeFile("header.h", ['#include <other.h\n'])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "missing '>'" in str(excinfo.value)


def test_include_missing_closing_angle_at_eof_no_newline():
    """
    Fail when an angle-bracket include is missing the closing '>'
    and file ends without newline.
    """
    # No trailing newline in the include line
    f_obj = FakeFile("header.h", ['#include <other.h'])
    with pytest.raises(ParseError) as excinfo:
        "".join(preprocess(f_obj))
    assert "missing '>'" in str(excinfo.value)


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
