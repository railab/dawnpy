# tools/dawnpy/tests/descriptor/handlers/test_prog_bitpack.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""C++ emission tests for the ``bitpack`` PROG handler."""

import pytest

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_bitpack import emit_config_field_cpp

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_emit_bitpack_inputs():
    field = ConfigField(
        name="inputs",
        cpp_helper="CProgBitPack::cfgIdInputs",
        value_type="bitpack_inputs",
    )
    config = {"inputs": [{"io": "io2", "bit": 4}, {"io": "io3", "bit": 5}]}
    lines: list[str] = []
    assert emit_config_field_cpp(lines, field, None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgBitPack::cfgIdInputs(4),",
        "      IO2,",
        "      4,",
        "      IO3,",
        "      5,",
    ]


def test_emit_declines_other_value_type():
    field = ConfigField(name="output", cpp_helper="H", value_type="id_single")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []
