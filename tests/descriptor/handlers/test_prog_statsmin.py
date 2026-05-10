import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_statsmin_program(generator):
    """Test StatsMin program configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "input1",
                "type": "dummy",
                "instance": 1,
                "dtype": "float",
            },
            {
                "id": "output1",
                "type": "virt",
                "instance": 1,
                "dtype": "float",
                "notify": False,
            },
        ],
        "programs": [
            {
                "id": "min1",
                "type": "statsmin",
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

    # Expected: StatsMin has exactly 2 IDs (input, output)
    expected_lines = [
        "  MIN1, 1,",
        "    CProgStatsMin::cfgIdIOBind(2),",
        "      INPUT1,",
        "      OUTPUT1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
