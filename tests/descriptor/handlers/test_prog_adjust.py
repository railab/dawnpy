# tools/dawnpy/tests/descriptor/handlers/test_prog_adjust.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import struct

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_adjust import (
    emit_config_field_cpp,
    emit_iobind_cpp,
)
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _obj(**kw) -> ProgramObject:
    base = dict(
        obj_id="adjust1",
        prog_type="adjust",
        instance=0,
        inputs=["src0"],
        outputs=["virt0"],
        reset=None,
        config={"params": {"offset": 3, "scale": 2}},
    )
    base.update(kw)
    return ProgramObject(**base)


def _params_field() -> ConfigField:
    return ConfigField(
        name="params",
        cpp_helper="CProgAdjust::cfgParams",
        value_type="adjust_params",
    )


def test_emit_adjust_params():
    obj = _obj(config={"params": {"offset": 3, "scale": 2}})
    lines: list[str] = []
    handled = emit_config_field_cpp(
        lines, _params_field(), obj, obj.config, prog_cpp_ctx()
    )
    assert handled is True
    assert lines == [
        "    CProgAdjust::cfgParams(),",
        "      3,",
        "      2,",
    ]


def test_emit_adjust_params_float():
    """A float-dtype prog encodes offset/scale as IEEE-754 bit patterns."""
    obj = _obj(
        config={"params": {"offset": -8.7, "scale": 1.0}}, dtype="float"
    )
    lines: list[str] = []
    emit_config_field_cpp(
        lines, _params_field(), obj, obj.config, prog_cpp_ctx()
    )

    off = int.from_bytes(struct.pack("<f", -8.7), "little")
    scl = int.from_bytes(struct.pack("<f", 1.0), "little")
    assert lines == [
        "    CProgAdjust::cfgParams(),",
        f"      {off:#010x},",
        f"      {scl:#010x},",
    ]


def test_emit_adjust_params_rw_when_granted():
    obj = _obj()
    lines: list[str] = []
    ctx = prog_cpp_ctx({("adjust1", "params"): True})
    emit_config_field_cpp(lines, _params_field(), obj, obj.config, ctx)
    assert lines[0] == "    CProgAdjust::cfgParams(true),"


def test_emit_adjust_params_non_dict_uses_defaults():
    obj = _obj(config={"params": "nonsense"})
    lines: list[str] = []
    emit_config_field_cpp(
        lines, _params_field(), obj, obj.config, prog_cpp_ctx()
    )
    assert lines == ["    CProgAdjust::cfgParams(),", "      0,", "      1,"]


def test_emit_declines_other_value_type():
    field = ConfigField(name="x", cpp_helper="H", value_type="uint32")
    lines: list[str] = []
    handled = emit_config_field_cpp(lines, field, _obj(), {}, prog_cpp_ctx())
    assert handled is False
    assert lines == []


def test_emit_iobind():
    lines: list[str] = []
    handled = emit_iobind_cpp(
        lines, _obj(), 2, DescriptorFormatHelper(), "CProgAdjust"
    )
    assert handled is True
    assert lines == [
        "    CProgAdjust::cfgIdIOBind(),",
        "      SRC0,",
        "      VIRT0,",
    ]
