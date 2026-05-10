import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_movingavg_program(generator):
    """Test MovingAverage program configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "in1",
                "type": "dummy",
                "instance": 1,
                "dtype": "float",
            },
            {
                "id": "out1",
                "type": "virt",
                "instance": 1,
                "dtype": "float",
                "notify": False,
            },
        ],
        "programs": [
            {
                "id": "mov1",
                "type": "movingavg",
                "instance": 1,
                "config": {
                    "inputs": ["in1"],
                    "outputs": ["out1"],
                    "window": 8,
                },
            }
        ],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    expected_lines = [
        "  MOV1, 2,",
        "    CProgMovingAverage::cfgIdIOBind(2),",
        "      IN1,",
        "      OUT1,",
        "    CProgMovingAverage::cfgIdWindow(),",
        "      8,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
