from __future__ import absolute_import
import platform
import os
import mock
import pytest
from simplecpreprocessor import preprocess
from simplecpreprocessor.platform import (calculate_platform_constants,
                                          extract_platform_spec)
from simplecpreprocessor.filesystem import FakeFile, FakeHandler
from simplecpreprocessor.exceptions import UnsupportedPlatform
extract_platform_spec_path = ("simplecpreprocessor.platform."
                              "extract_platform_spec"
                              )


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


def test_platform_undefine():
    with mock.patch(extract_platform_spec_path) as mock_spec:
        mock_spec.return_value = "Linux", "32bit"
        f_obj = FakeFile("header.h", [
            '#undef __i386__\n'
            '__i386__\n', ])
        ret = preprocess(f_obj)
        assert "".join(ret) == "__i386__\n"


def test_platform_constants():
    f_obj = FakeFile("header.h", ['#ifdef ODDPLATFORM\n',
                                  'ODDPLATFORM\n', '#endif\n'])
    ret = preprocess(f_obj, extra_constants={"ODDPLATFORM": "ODDPLATFORM"})
    assert "".join(ret) == "ODDPLATFORM\n"


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
