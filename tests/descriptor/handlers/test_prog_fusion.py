# tools/dawnpy/tests/descriptor/handlers/test_prog_fusion.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the ``fusion`` PROG handler."""

import struct

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.descriptor.handlers.prog_fusion import (
    PARAM_DEFAULTS,
    PARAM_ORDER,
    encode_binary,
    output_shape_owned_virt_targets,
    validate_object,
    validate_object_refs,
)

from .helpers import to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _f32(value: float) -> int:
    return int.from_bytes(struct.pack("<f", float(value)), "little")


def _obj(config: dict | None = None) -> ProgramObject:
    return ProgramObject(
        obj_id="fusion1",
        prog_type="fusion",
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


class TestFusionHandler:

    def test_registered(self):
        assert "fusion" in PROG_HANDLER_REGISTRY

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

    def test_emit_fusion_params(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []

        prog_gen._emit_fusion_params(
            lines, "CProgFusion::cfgParams", "params", _obj(), _obj().config
        )

        assert lines == [
            "    CProgFusion::cfgParams(),",
            f"      {_f32(0.5):#010x},",
            f"      {_f32(10.0):#010x},",
            f"      {_f32(5.0):#010x},",
            f"      {_f32(50.0):#010x},",
        ]
