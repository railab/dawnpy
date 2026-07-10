# tools/dawnpy/tests/descriptor/handlers/test_prog_buffer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""C++ emission tests for the ``buffer`` PROG handler."""

import pytest

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_buffer import emit_config_field_cpp

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _field() -> ConfigField:
    return ConfigField(
        name="iobind",
        cpp_helper="CProgBuffer::cfgIdIOBind",
        value_type="id_array_quads",
    )


def test_emit_id_array_quads():
    config = {"iobind": [{"src": "a", "out": "b", "sel": "c", "stat": "d"}]}
    lines: list[str] = []
    assert emit_config_field_cpp(lines, _field(), None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgBuffer::cfgIdIOBind(4),",
        "      A,",
        "      B,",
        "      C,",
        "      D,",
    ]


def test_emit_id_array_quads_skips_invalid_entries():
    config = {
        "iobind": [
            "not_a_dict",
            {"src": "a", "out": "b"},  # missing sel/stat
            {"src": "a", "out": "b", "sel": "c", "stat": None},  # invalid
        ]
    }
    lines: list[str] = []
    emit_config_field_cpp(lines, _field(), None, config, prog_cpp_ctx())
    assert lines == ["    CProgBuffer::cfgIdIOBind(0),"]


def test_emit_id_array_quads_non_list():
    lines: list[str] = []
    emit_config_field_cpp(
        lines, _field(), None, {"iobind": "notalist"}, prog_cpp_ctx()
    )
    assert lines == ["    CProgBuffer::cfgIdIOBind(0),"]


def test_emit_declines_other_value_type():
    field = ConfigField(name="depth", cpp_helper="H", value_type="uint32")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []
