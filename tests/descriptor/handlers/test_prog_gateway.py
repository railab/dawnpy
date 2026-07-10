# tools/dawnpy/tests/descriptor/handlers/test_prog_gateway.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_gateway import emit_config_field_cpp

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _field():
    return ConfigField(
        name="iobind",
        cpp_helper="CProgGateway::cfgIdIOBind",
        value_type="gateway_iobind",
    )


def test_emit_gateway_iobind():
    config = {"iobind": [{"io1": "io1", "io2": "io2", "flags": 1, "dim": 2}]}
    lines: list[str] = []
    assert emit_config_field_cpp(lines, _field(), None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgGateway::cfgIdIOBind(4),",
        "      IO1,",
        "      IO2,",
        "      1,",
        "      2,",
    ]


def test_emit_gateway_iobind_skips_invalid_entries():
    config = {
        "iobind": [
            "not_a_dict",
            {"io1": "io1"},  # missing io2
            {"io1": "io1", "io2": None},  # invalid io2
        ]
    }
    lines: list[str] = []
    emit_config_field_cpp(lines, _field(), None, config, prog_cpp_ctx())
    assert "    CProgGateway::cfgIdIOBind(0)," in lines[0]


def test_emit_gateway_iobind_non_list():
    lines: list[str] = []
    emit_config_field_cpp(
        lines, _field(), None, {"iobind": "notalist"}, prog_cpp_ctx()
    )
    assert lines == ["    CProgGateway::cfgIdIOBind(0),"]


def test_emit_declines_other_value_type():
    field = ConfigField(name="x", cpp_helper="H", value_type="uint32")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []
