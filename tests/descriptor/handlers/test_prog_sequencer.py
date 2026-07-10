# tools/dawnpy/tests/descriptor/handlers/test_prog_sequencer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_sequencer import emit_config_field_cpp

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_emit_sequencer_states():
    field = ConfigField(
        name="states",
        cpp_helper="CProgSequencer::cfgIdStates",
        value_type="sequencer_states",
    )
    config = {
        "states": [
            {"value": 1, "dwell_us": 500000},
            {"value": "2", "dwell_us": "600000"},
        ]
    }
    lines: list[str] = []
    assert emit_config_field_cpp(lines, field, None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgSequencer::cfgIdStates(4),",
        "      1,",
        "      500000,",
        "      2,",
        "      600000,",
    ]


def test_emit_sequencer_states_non_list():
    field = ConfigField(
        name="states",
        cpp_helper="CProgSequencer::cfgIdStates",
        value_type="sequencer_states",
    )
    lines: list[str] = []
    emit_config_field_cpp(
        lines, field, None, {"states": "notalist"}, prog_cpp_ctx()
    )
    assert lines == ["    CProgSequencer::cfgIdStates(0),"]


def test_emit_sequencer_states_skips_non_dict_entries():
    field = ConfigField(
        name="states",
        cpp_helper="CProgSequencer::cfgIdStates",
        value_type="sequencer_states",
    )
    lines: list[str] = []
    emit_config_field_cpp(
        lines,
        field,
        None,
        {"states": ["notadict", {"value": 1, "dwell_us": 2}]},
        prog_cpp_ctx(),
    )
    assert lines == [
        "    CProgSequencer::cfgIdStates(2),",
        "      1,",
        "      2,",
    ]


def test_emit_declines_other_value_type():
    field = ConfigField(name="x", cpp_helper="H", value_type="uint32")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []
