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
        lines = []
        cpp_helper = "CProgAdjust::cfgParams"
        config = {"params": {"offset": 3, "scale": 2}}
        prog_gen._emit_adjust_params(lines, cpp_helper, "params", config)
        assert lines == [
            "    CProgAdjust::cfgParams(),",
            "      3,",
            "      2,",
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
