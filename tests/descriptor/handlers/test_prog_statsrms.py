import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_stats_rms_program(generator):
    """Test StatsRms program configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "input1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint32",
            },
            {
                "id": "output1",
                "type": "virt",
                "instance": 1,
                "dtype": "uint32",
                "notify": False,
            },
        ],
        "programs": [
            {
                "id": "rms1",
                "type": "statsrms",
                "instance": 1,
                "config": {
                    "inputs": ["input1"],
                    "outputs": ["output1"],
                },
            }
        ],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    expected_lines = [
        "  RMS1, 1,",
        "    CProgStatsRms::cfgIdIOBind(2),",
        "      INPUT1,",
        "      OUTPUT1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
