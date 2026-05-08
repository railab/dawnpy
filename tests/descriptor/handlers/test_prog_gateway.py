# tools/dawnpy/tests/descriptor/handlers/test_prog_gateway.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestProgramConfigGenerator:

    def test_emit_gateway_iobind(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        # Successful case
        lines = []
        cpp_helper = "CProgGateway::cfgIdIOBind"
        config = {
            "iobind": [{"io1": "io1", "io2": "io2", "flags": 1, "dim": 2}]
        }
        prog_gen._emit_gateway_iobind(lines, cpp_helper, "iobind", config)
        assert "    CProgGateway::cfgIdIOBind(4)," in lines[0]

        # Negative cases for coverage
        lines = []
        config = {
            "iobind": [
                "not_a_dict",
                {"io1": "io1"},  # missing io2
                {"io1": "io1", "io2": None},  # invalid io2
            ]
        }
        prog_gen._emit_gateway_iobind(lines, cpp_helper, "iobind", config)
        assert "    CProgGateway::cfgIdIOBind(0)," in lines[0]
