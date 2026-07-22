# tools/dawnpy/tests/descriptor/handlers/test_prog_bitmerge.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the ``bitmerge`` PROG handler."""

from types import SimpleNamespace

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers.prog_bitmerge import (
    emit_config_field_cpp,
    encode_binary,
    output_shape_owned_virt_targets,
    validate_object_refs,
)

from .helpers import prog_cpp_ctx, to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _obj(config: dict | None = None) -> ProgramObject:
    return ProgramObject(
        obj_id="bm1",
        prog_type="bitmerge",
        instance=0,
        inputs=[],
        outputs=[],
        reset=None,
        config=config if config is not None else {},
        dtype="uint32",
    )


def _inputs(*fields: tuple[str, int, int]) -> list[dict]:
    return [{"io": io, "shift": s, "mask": m} for io, s, m in fields]


def _io(dtype: str, obj_id: str, batch: int = 1):
    config = {"notify": {"batch": batch}} if batch > 1 else {}
    return to_io_obj({"dtype": dtype, "config": config}, obj_id)


def test_emit_bitmerge_inputs():
    field = ConfigField(
        name="inputs",
        cpp_helper="CProgBitMerge::cfgIdInputs",
        value_type="bitmerge_inputs",
    )
    config = {"inputs": _inputs(("adc0", 0, 0xFFF), ("tag0", 12, 0x7))}
    lines: list[str] = []
    assert emit_config_field_cpp(lines, field, None, config, prog_cpp_ctx())
    assert lines == [
        "    CProgBitMerge::cfgIdInputs(6),",
        "      ADC0,",
        "      0,",
        "      4095,",
        "      TAG0,",
        "      12,",
        "      7,",
    ]


def test_emit_declines_other_value_type():
    field = ConfigField(name="output", cpp_helper="H", value_type="id_single")
    lines: list[str] = []
    assert not emit_config_field_cpp(lines, field, None, {}, prog_cpp_ctx())
    assert lines == []


def test_emit_skips_malformed_entries():
    field = ConfigField(
        name="inputs",
        cpp_helper="CProgBitMerge::cfgIdInputs",
        value_type="bitmerge_inputs",
    )
    lines: list[str] = []
    config = {"inputs": ["junk", {"shift": 1, "mask": 1}]}
    assert emit_config_field_cpp(lines, field, None, config, prog_cpp_ctx())
    assert lines[0] == "    CProgBitMerge::cfgIdInputs(3),"
    assert lines[1] == "      0,"

    lines = []
    assert emit_config_field_cpp(
        lines, field, None, {"inputs": "junk"}, prog_cpp_ctx()
    )
    assert lines == ["    CProgBitMerge::cfgIdInputs(0),"]


def test_output_shape_owned():
    assert output_shape_owned_virt_targets(_obj({"output": "o"})) == {"o"}
    assert output_shape_owned_virt_targets(_obj()) == set()


def test_validate_field_fits_output_width():
    io_map = {
        "adc0": _io("int16", "adc0", batch=4),
        "tag0": _io("int16", "tag0"),
        "out": _io("int16", "out"),
    }
    obj = _obj(
        {
            "inputs": _inputs(("adc0", 0, 0xFFF), ("tag0", 12, 0x7)),
            "output": "out",
        }
    )
    assert validate_object_refs(obj, io_map) == []


def test_validate_field_past_output_width_rejected():
    io_map = {
        "adc0": _io("int16", "adc0", batch=4),
        "tag0": _io("int16", "tag0"),
        "out": _io("int16", "out"),
    }
    obj = _obj(
        {
            "inputs": _inputs(("adc0", 0, 0xFFF), ("tag0", 14, 0x7)),
            "output": "out",
        }
    )
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "16-bit output word" in errors[0]


def test_validate_field_past_32_bit_word():
    io_map = {"tag0": _io("uint32", "tag0")}
    obj = _obj({"inputs": _inputs(("tag0", 32, 0x1)), "output": "missing"})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "32-bit output word" in errors[0]


def test_validate_empty_mask():
    obj = _obj({"inputs": _inputs(("tag0", 0, 0))})
    errors = validate_object_refs(obj, {})
    assert errors == [
        "Program bm1 invalid: bitmerge input 'tag0' has an empty mask"
    ]


def test_validate_overlap():
    obj = _obj({"inputs": _inputs(("a", 0, 0xF), ("b", 2, 0x3))})
    errors = validate_object_refs(obj, {})
    assert len(errors) == 1
    assert "overlaps" in errors[0]


def test_validate_unsupported_input_dtype():
    io_map = {"f": _io("float", "f")}
    obj = _obj({"inputs": _inputs(("f", 0, 0x1))})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "unsupported dtype 'float'" in errors[0]


def test_validate_at_most_one_batched_input():
    io_map = {
        "a": _io("uint32", "a", batch=4),
        "b": _io("uint32", "b", batch=8),
    }
    obj = _obj({"inputs": _inputs(("a", 0, 0x1), ("b", 1, 0x1))})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "at most one batched input" in errors[0]


def test_validate_batched_input_needs_dict_notify():
    io_map = {
        "a": to_io_obj({"dtype": "uint32", "config": {"notify": True}}, "a"),
        "b": SimpleNamespace(dtype="uint32", config="junk"),
    }
    obj = _obj({"inputs": _inputs(("a", 0, 0x1), ("b", 1, 0x1))})
    assert validate_object_refs(obj, io_map) == []


def test_validate_output_dtype():
    io_map = {
        "a": _io("uint16", "a", batch=4),
        "out_f": _io("float", "out_f"),
        "out_u32": _io("uint32", "out_u32"),
    }
    obj = _obj({"inputs": _inputs(("a", 0, 0x1)), "output": "out_f"})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "output 'out_f' uses unsupported dtype" in errors[0]

    obj = _obj({"inputs": _inputs(("a", 0, 0x1)), "output": "out_u32"})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 1
    assert "does not match batched input 'a'" in errors[0]


def test_validate_output_matches_batched_element_size():
    # int16 -> uint16 is accepted: the runtime compares element size only.
    io_map = {
        "a": _io("int16", "a", batch=4),
        "out": _io("uint16", "out"),
    }
    obj = _obj({"inputs": _inputs(("a", 0, 0x1)), "output": "out"})
    assert validate_object_refs(obj, io_map) == []


def test_validate_batched_input_unsupported_dtype_sizes_mismatch():
    # An unsupported batched dtype is reported once as input, and again as
    # an element-size mismatch since it has no known width.
    io_map = {
        "f": _io("float", "f", batch=4),
        "out": _io("uint32", "out"),
    }
    obj = _obj({"inputs": _inputs(("f", 0, 0x1)), "output": "out"})
    errors = validate_object_refs(obj, io_map)
    assert len(errors) == 2
    assert "unsupported dtype 'float'" in errors[0]
    assert "element size" in errors[1]


def test_validate_tolerates_missing_refs():
    obj = _obj({"inputs": [1, {"shift": 0, "mask": 1}, {"io": "nope"}]})
    errors = validate_object_refs(obj, {})
    # The second entry has no io ref, the third has a ref no IO resolves.
    assert errors == [
        "Program bm1 invalid: bitmerge input 'nope' has an empty mask"
    ]
    assert validate_object_refs(_obj({"inputs": "junk"}), {}) == []


def test_encode_binary_words():
    items: list = []
    obj = _obj(
        {
            "inputs": _inputs(("adc0", 0, 0xFFF), ("tag0", 12, 0x7)),
            "output": "out",
        }
    )
    encode_binary(
        items, obj, 40, {"adc0": 0x11, "tag0": 0x12, "out": 0x13}, None
    )
    assert len(items) == 2
    assert items[0][1] == [0x11, 0, 0xFFF, 0x12, 12, 0x7]
    assert items[1][1] == [0x13]

    items = []
    encode_binary(items, _obj(), 40, {}, None)
    assert items == []
