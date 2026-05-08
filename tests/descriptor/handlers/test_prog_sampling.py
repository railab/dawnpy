# tools/dawnpy/tests/descriptor/handlers/test_prog_sampling.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator
from tests.descriptor.descriptor_helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestProgramConfigGenerator:

    def test_generate_prog_config_sampling(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="prog1",
            prog_type="sampling",
            instance=0,
            inputs=["io1"],
            outputs=["io2"],
            reset=None,
            config={"interval": 1000},
        )
        lines = prog_gen.generate_prog_config("PROG1", obj)
        # sampling has iobind (pairs) and interval (uint32)
        # cfg_count = 0 (custom iobind) + 2 (type fields: iobind, interval) = 2
        assert "PROG1, 2," in lines[0]
        assert any("CProgSampling::cfgIdIOBind" in line for line in lines)
        assert any("CProgSampling::cfgIdIOInterval" in line for line in lines)


def test_sampling_program(generator):
    """Test Sampling program configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "src1",
                "type": "dummy",
                "instance": 1,
                "dtype": "float",
            },
            {
                "id": "src2",
                "type": "dummy",
                "instance": 2,
                "dtype": "float",
            },
            {
                "id": "virt1",
                "type": "virt",
                "instance": 1,
                "dtype": "float",
                "notify": False,
            },
            {
                "id": "virt2",
                "type": "virt",
                "instance": 2,
                "dtype": "float",
                "notify": False,
            },
        ],
        "programs": [
            {
                "id": "sampling1",
                "type": "sampling",
                "instance": 1,
                "config": {
                    "sources": ["src1", "src2"],
                    "outputs": ["virt1", "virt2"],
                    "interval": 10000,
                },
            }
        ],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected: 2 config items (iobind + interval)
    expected_lines = [
        "  SAMPLING1, 2,",
        "    CProgSampling::cfgIdIOBind(4),",
        "      SRC1,",
        "      SRC2,",
        "      VIRT1,",
        "      VIRT2,",
        "    CProgSampling::cfgIdIOInterval(),",
        "      10000,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"

    # Check macro definition uses CProgSampling::objectId
    assert "CProgSampling::objectId(1)" in output
