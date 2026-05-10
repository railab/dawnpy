import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_dummy_program(generator):
    """Test Dummy program configuration."""
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
                "id": "dummy_prog1",
                "type": "dummy",
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
        "  DUMMY_PROG1, 1,",
        "    CProgDummy::cfgIdIOBind(2),",
        "      INPUT1,",
        "      OUTPUT1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
