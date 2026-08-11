# tools/dawnpy/tests/descriptor/handlers/test_prog_saturate.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the ``saturate`` PROG handler."""

import dataclasses

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_saturate import (
    config_fields,
    emit_config_field_cpp,
    encode_binary,
    output_shape_owned_virt_targets,
    validate_object_refs,
)

from .helpers import prog_cpp_ctx, to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _obj(config: dict | None = None, dtype: str = "int16") -> ProgramObject:
    return ProgramObject(
        obj_id="sat1",
        prog_type="saturate",
        instance=0,
        inputs=[],
        outputs=[],
        reset=None,
        config=(
            config
            if config is not None
            else {"input": "in", "output": "out", "min": 0, "max": 4095}
        ),
        dtype=dtype,
    )


def _io_map(in_dtype: str, out_dtype: str) -> dict:
    return {
        "in": to_io_obj({"dtype": in_dtype}, "in"),
        "out": to_io_obj({"dtype": out_dtype}, "out"),
    }


def _bound(name: str) -> ConfigField:
    return ConfigField(
        name=name,
        cpp_helper=f"CProgSaturate::cfgId{name.title()}",
        value_type="saturate_bound",
        params=["rw"],
    )


def test_config_fields():
    names = [f.name for f in config_fields()]
    assert names == ["input", "output", "min", "max"]


def test_output_shape_owned():
    assert output_shape_owned_virt_targets(_obj()) == {"out"}
    assert output_shape_owned_virt_targets(_obj({})) == set()


def test_emit_bound_present():
    lines: list[str] = []
    assert emit_config_field_cpp(
        lines, _bound("min"), _obj(), {"min": -5}, prog_cpp_ctx()
    )
    assert lines == ["    CProgSaturate::cfgIdMin(),", "      (uint32_t)-5,"]


def test_emit_bound_rw():
    lines: list[str] = []
    grants = {("sat1", "max"): True}
    assert emit_config_field_cpp(
        lines, _bound("max"), _obj(), {"max": 7}, prog_cpp_ctx(grants)
    )
    assert lines[0] == "    CProgSaturate::cfgIdMax(true),"


def test_emit_real_bound_is_float_word():
    for dtype in ("float", "double"):
        lines: list[str] = []
        assert emit_config_field_cpp(
            lines,
            _bound("max"),
            _obj(dtype=dtype),
            {"max": 0.5},
            prog_cpp_ctx(),
        )
        assert lines[1] == "      0x3f000000,"


def test_emit_b16_bound_is_fixed_point_word():
    lines: list[str] = []
    assert emit_config_field_cpp(
        lines, _bound("min"), _obj(dtype="b16"), {"min": -1.5}, prog_cpp_ctx()
    )
    assert lines[1] == "      0xfffe8000,"


def test_emit_bound_absent_emits_nothing():
    lines: list[str] = []
    assert emit_config_field_cpp(
        lines, _bound("max"), _obj(), {"min": 0}, prog_cpp_ctx()
    )
    assert lines == []


def test_emit_declines_other_value_type():
    field = ConfigField(name="input", cpp_helper="H", value_type="id_single")
    lines: list[str] = []
    assert not emit_config_field_cpp(lines, field, _obj(), {}, prog_cpp_ctx())


def test_validate_ok():
    assert validate_object_refs(_obj(), _io_map("int16", "uint16")) == []


def test_validate_real_ok():
    obj = _obj({"input": "in", "output": "out", "min": -1.5}, dtype="float")
    assert validate_object_refs(obj, _io_map("float", "int8")) == []


def test_validate_unsupported_io_dtypes():
    errors = validate_object_refs(_obj(), _io_map("int64", "char"))
    assert len(errors) == 2
    assert "input 'in' uses unsupported dtype 'int64'" in errors[0]
    assert "output 'out' uses unsupported dtype 'char'" in errors[1]


def test_validate_prog_dtype_must_match_input():
    errors = validate_object_refs(_obj(), _io_map("int32", "int16"))
    assert errors == [
        "Program sat1 invalid: saturate dtype 'int16' must match input 'in' "
        "dtype 'int32'"
    ]


def test_validate_b16_not_mixed():
    obj = _obj({"input": "in", "output": "out", "min": 0}, dtype="b16")
    errors = validate_object_refs(obj, _io_map("b16", "int32"))
    assert errors == [
        "Program sat1 invalid: saturate cannot mix b16 with 'int32'"
    ]

    obj = _obj({"input": "in", "output": "out", "min": 0}, dtype="int32")
    errors = validate_object_refs(obj, _io_map("int32", "b16"))
    assert errors == [
        "Program sat1 invalid: saturate cannot mix b16 with 'int32'"
    ]

    obj = _obj({"input": "in", "output": "out", "min": -1.5}, dtype="b16")
    assert validate_object_refs(obj, _io_map("b16", "b16")) == []


def test_validate_bound_outside_output_range():
    errors = validate_object_refs(_obj(), _io_map("int16", "uint8"))
    assert errors == [
        "Program sat1 invalid: saturate 'max' 4095 outside the range of "
        "'out' dtype 'uint8'"
    ]


def test_validate_requires_a_bound():
    errors = validate_object_refs(_obj({"input": "in", "output": "out"}), {})
    assert errors == [
        "Program sat1 invalid: saturate needs at least one of 'min'/'max'"
    ]


def test_validate_unsupported_prog_dtype():
    errors = validate_object_refs(_obj(dtype="int64"), {})
    assert errors == [
        "Program sat1 invalid: saturate dtype 'int64' is not supported"
    ]


def test_validate_bound_outside_prog_dtype():
    errors = validate_object_refs(_obj({"min": -1}, dtype="uint8"), {})
    assert errors == [
        "Program sat1 invalid: saturate 'min' -1 outside the range of program "
        "dtype 'uint8'"
    ]

    errors = validate_object_refs(_obj({"max": 2}, dtype="bool"), {})
    assert len(errors) == 1
    assert "'max' 2 outside" in errors[0]

    errors = validate_object_refs(_obj({"max": 32768.0}, dtype="b16"), {})
    assert len(errors) == 1
    assert "'max' 32768.0 outside" in errors[0]


def test_validate_min_above_max():
    errors = validate_object_refs(_obj({"min": 10, "max": 5}), {})
    assert errors == ["Program sat1 invalid: saturate 'min' above 'max'"]


def test_validate_config_not_dict():
    obj = dataclasses.replace(_obj(), config="junk")
    errors = validate_object_refs(obj, {})
    assert len(errors) == 1
    assert "needs at least one" in errors[0]


def test_encode_binary_words():
    items: list = []
    encode_binary(
        items,
        _obj({"input": "in", "output": "out", "min": -1}),
        41,
        {"in": 0x21, "out": 0x22},
        None,
    )
    assert len(items) == 3
    assert items[0][1] == [0x21]
    assert items[1][1] == [0x22]
    assert items[2][1] == [0xFFFFFFFF]

    items = []
    obj = dataclasses.replace(_obj(), config="junk")
    encode_binary(items, obj, 41, {}, None)
    assert items == []


def test_encode_binary_real_and_b16_words():
    items: list = []
    encode_binary(items, _obj({"max": 0.5}, dtype="double"), 41, {}, None)
    assert items[0][1] == [0x3F000000]

    items = []
    encode_binary(items, _obj({"max": 1.5}, dtype="b16"), 41, {}, None)
    assert items[0][1] == [0x00018000]
