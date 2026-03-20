# tools/dawnpy/tests/descriptor/handlers/test_prog_stats.py
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

    def test_generate_prog_config_stats(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="prog1",
            prog_type="stats",
            instance=0,
            inputs=["io1"],
            outputs=["io2"],
            reset=None,
            config={},
        )
        lines = prog_gen.generate_prog_config("PROG1", obj)
        # stats has no type-specific fields, should use standard iobind
        assert "PROG1, 1," in lines[0]
        assert "    CProgProcess::cfgIdIOBind(2)," in lines[1]
        assert "      IO1," in lines[2]
        assert "      IO2," in lines[3]
