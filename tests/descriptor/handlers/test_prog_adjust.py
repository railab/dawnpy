# tools/dawnpy/tests/descriptor/handlers/test_prog_adjust.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestProgramConfigGenerator:

    def test_emit_adjust_params(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="adjust1",
            prog_type="adjust",
            instance=0,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={"params": {"offset": 3, "scale": 2}},
        )
        lines = []
        cpp_helper = "CProgAdjust::cfgParams"
        config = {"params": {"offset": 3, "scale": 2}}
        prog_gen._emit_adjust_params(lines, cpp_helper, "params", obj, config)
        assert lines == [
            "    CProgAdjust::cfgParams(),",
            "      3,",
            "      2,",
        ]

    def test_emit_adjust_params_float(self):
        """A float-dtype prog encodes offset/scale as IEEE-754 bit patterns."""
        import struct

        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="adjust1",
            prog_type="adjust",
            instance=0,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={"params": {"offset": -8.7, "scale": 1.0}},
            dtype="float",
        )
        lines = []
        cpp_helper = "CProgAdjust::cfgParams"
        config = {"params": {"offset": -8.7, "scale": 1.0}}
        prog_gen._emit_adjust_params(lines, cpp_helper, "params", obj, config)

        off = int.from_bytes(struct.pack("<f", -8.7), "little")
        scl = int.from_bytes(struct.pack("<f", 1.0), "little")
        assert lines == [
            "    CProgAdjust::cfgParams(),",
            f"      {off:#010x},",
            f"      {scl:#010x},",
        ]

    def test_emit_adjust_iobind(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="adjust1",
            prog_type="adjust",
            instance=0,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={"params": {"offset": 3, "scale": 2}},
        )
        lines = []

        prog_gen._emit_adjust_iobind(lines, obj)

        assert lines == [
            "    CProgAdjust::cfgIdIOBind(),",
            "      SRC0,",
            "      VIRT0,",
        ]
