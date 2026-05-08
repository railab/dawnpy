# tools/dawnpy/tests/descriptor/handlers/test_prog_sequencer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestProgramConfigGenerator:

    def test_emit_sequencer_states(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgSequencer::cfgIdStates"
        config = {
            "states": [
                {"value": 1, "dwell_us": 500000},
                {"value": "2", "dwell_us": "600000"},
            ]
        }
        prog_gen._emit_sequencer_states(lines, cpp_helper, "states", config)
        assert lines == [
            "    CProgSequencer::cfgIdStates(4),",
            "      1,",
            "      500000,",
            "      2,",
            "      600000,",
        ]
