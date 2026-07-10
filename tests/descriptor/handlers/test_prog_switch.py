# tools/dawnpy/tests/descriptor/handlers/test_prog_switch.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""C++ emission tests for the ``switch`` PROG handler."""

import pytest

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_switch import emit_config_field_cpp

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_emit_switch_inputs():
    field = ConfigField(
        name="inputs",
        cpp_helper="CProgSwitch::cfgIdInputs",
        value_type="switch_inputs",
    )
    config = {"inputs": [{"io": "io1", "match": 2}, {"io": "io2"}]}
    lines: list[str] = []
    assert emit_config_field_cpp(lines, field, None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgSwitch::cfgIdInputs(4),",
        "      IO1,",
        "      2,",
        "      IO2,",
        "      1,",
    ]


def test_emit_switch_target():
    field = ConfigField(
        name="target",
        cpp_helper="CProgSwitch::cfgIdTarget",
        value_type="switch_target",
    )
    lines: list[str] = []
    emit_config_field_cpp(
        lines, field, None, {"target": ["tgt1", 5, 6]}, prog_cpp_ctx()
    )
    assert lines == [
        "    CProgSwitch::cfgIdTarget(),",
        "      TGT1,",
        "      5,",
        "      6,",
    ]


def test_emit_switch_target_defaults():
    field = ConfigField(
        name="target",
        cpp_helper="CProgSwitch::cfgIdTarget",
        value_type="switch_target",
    )
    lines: list[str] = []
    emit_config_field_cpp(lines, field, None, {"target": []}, prog_cpp_ctx())
    assert lines == [
        "    CProgSwitch::cfgIdTarget(),",
        "      0,",
        "      1,",
        "      0,",
    ]


def test_emit_declines_other_value_type():
    field = ConfigField(name="x", cpp_helper="H", value_type="uint32")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []
