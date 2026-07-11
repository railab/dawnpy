# tools/dawnpy/tests/descriptor/handlers/test_prog_ahrs.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the ``ahrs`` PROG handler."""

import struct

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.descriptor.handlers.prog_ahrs import (
    PARAM_DEFAULTS,
    PARAM_ORDER,
    emit_config_field_cpp,
    encode_binary,
    output_shape_owned_virt_targets,
    validate_object,
    validate_object_refs,
)

from .helpers import prog_cpp_ctx, to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _f32(value: float) -> int:
    return int.from_bytes(struct.pack("<f", float(value)), "little")


def _obj(config: dict | None = None) -> ProgramObject:
    return ProgramObject(
        obj_id="ahrs1",
        prog_type="ahrs",
        instance=0,
        inputs=[],
        outputs=[],
        reset=None,
        config=(
            config
            if config is not None
            else {
                "accel": "accel0",
                "gyro": "gyro0",
                "output": "fused_src",
                "params": {
                    "gain": 0.5,
                    "accel_rejection": 10.0,
                    "recovery_period": 5.0,
                    "rate": 50.0,
                },
            }
        ),
        dtype="float",
    )


class TestAhrsHandler:

    def test_registered(self):
        assert "ahrs" in PROG_HANDLER_REGISTRY

    def test_encode_binary_words(self):
        items = []
        obj_ids = {"accel0": 0x11, "gyro0": 0x12, "fused_src": 0x13}

        encode_binary(items, _obj(), 34, obj_ids, None)

        # Three single-id items followed by the params item.
        assert len(items) == 4
        assert items[0][1] == [0x11]
        assert items[1][1] == [0x12]
        assert items[2][1] == [0x13]
        params_cfg, params_words = items[3]
        assert params_words == [_f32(0.5), _f32(10.0), _f32(5.0), _f32(50.0)]
        # The RW bit (bit 15) is granted by a config IO, not set at encode.
        assert params_cfg & (1 << 15) == 0

    def test_encode_binary_defaults(self):
        items = []
        obj = _obj(
            config={"accel": "accel0", "gyro": "gyro0", "output": "fused_src"}
        )

        encode_binary(
            items, obj, 34, {"accel0": 1, "gyro0": 2, "fused_src": 3}, None
        )

        assert items[3][1] == [_f32(PARAM_DEFAULTS[n]) for n in PARAM_ORDER]

    def test_encode_binary_params_not_dict(self):
        items = []
        obj = _obj(
            config={
                "accel": "accel0",
                "gyro": "gyro0",
                "output": "fused_src",
                "params": "nonsense",
            }
        )

        encode_binary(
            items, obj, 34, {"accel0": 1, "gyro0": 2, "fused_src": 3}, None
        )

        assert items[3][1] == [_f32(PARAM_DEFAULTS[n]) for n in PARAM_ORDER]

    def test_validate_object_requires_refs(self):
        errors = validate_object(_obj(config={"accel": "accel0"}))
        assert len(errors) == 2
        assert any("gyro" in e for e in errors)
        assert any("output" in e for e in errors)
        assert validate_object(_obj()) == []

    def test_validate_refs_dtype(self):
        io_map = {
            "accel0": to_io_obj({"dtype": "float"}, "accel0"),
            "gyro0": to_io_obj({"dtype": "uint32"}, "gyro0"),
            "fused_src": to_io_obj({"dtype": "float"}, "fused_src"),
        }

        errors = validate_object_refs(_obj(), io_map)

        assert len(errors) == 1
        assert "gyro0" in errors[0]

    def test_validate_refs_missing_io_ignored(self):
        assert validate_object_refs(_obj(), {}) == []

    def test_output_shape_ownership(self):
        assert output_shape_owned_virt_targets(_obj()) == {"fused_src"}
        obj = _obj(config={"accel": "accel0", "gyro": "gyro0"})
        assert output_shape_owned_virt_targets(obj) == set()

    def test_encode_binary_with_mag(self):
        items = []
        obj = _obj(
            config={
                "accel": "accel0",
                "gyro": "gyro0",
                "mag": "mag0",
                "output": "fused_src",
            }
        )

        encode_binary(
            items,
            obj,
            34,
            {"accel0": 1, "gyro0": 2, "mag0": 4, "fused_src": 3},
            None,
        )

        # accel, gyro, output, mag ids + params.
        assert len(items) == 5
        assert items[3][1] == [4]

    def test_validate_mag_dtype(self):
        io_map = {
            "accel0": to_io_obj({"dtype": "float"}, "accel0"),
            "gyro0": to_io_obj({"dtype": "float"}, "gyro0"),
            "mag0": to_io_obj({"dtype": "int16"}, "mag0"),
            "fused_src": to_io_obj({"dtype": "float"}, "fused_src"),
        }
        obj = _obj(
            config={
                "accel": "accel0",
                "gyro": "gyro0",
                "mag": "mag0",
                "output": "fused_src",
            }
        )

        errors = validate_object_refs(obj, io_map)

        assert len(errors) == 1
        assert "mag0" in errors[0]

    def test_mag_is_optional(self):
        assert validate_object(_obj()) == []

    def test_emit_ahrs_params(self):
        field = ConfigField(
            name="params",
            cpp_helper="CProgAhrs::cfgParams",
            value_type="ahrs_params",
        )
        lines: list[str] = []

        handled = emit_config_field_cpp(
            lines, field, _obj(), _obj().config, prog_cpp_ctx()
        )

        assert handled is True
        assert lines == [
            "    CProgAhrs::cfgParams(),",
            f"      {_f32(0.5):#010x},",
            f"      {_f32(10.0):#010x},",
            f"      {_f32(5.0):#010x},",
            f"      {_f32(50.0):#010x},",
        ]

    def test_emit_ahrs_params_rw_when_granted(self):
        field = ConfigField(
            name="params",
            cpp_helper="CProgAhrs::cfgParams",
            value_type="ahrs_params",
        )
        lines: list[str] = []
        ctx = prog_cpp_ctx({("ahrs1", "params"): True})

        emit_config_field_cpp(lines, field, _obj(), _obj().config, ctx)

        assert lines[0] == "    CProgAhrs::cfgParams(true),"

    def test_emit_ahrs_params_non_dict_uses_defaults(self):
        field = ConfigField(
            name="params",
            cpp_helper="CProgAhrs::cfgParams",
            value_type="ahrs_params",
        )
        lines: list[str] = []
        emit_config_field_cpp(
            lines, field, _obj(), {"params": "nonsense"}, prog_cpp_ctx()
        )
        assert lines == [
            "    CProgAhrs::cfgParams(),",
            *[f"      {_f32(PARAM_DEFAULTS[n]):#010x}," for n in PARAM_ORDER],
        ]

    def test_emit_declines_other_value_type(self):
        field = ConfigField(name="x", cpp_helper="H", value_type="uint32")
        lines: list[str] = []
        handled = emit_config_field_cpp(
            lines, field, _obj(), {}, prog_cpp_ctx()
        )
        assert handled is False
        assert lines == []
