import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_dummy_protocol(generator):
    """Test Dummy protocol configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "io1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint32",
            }
        ],
        "programs": [],
        "protocols": [
            {
                "id": "proto_dummy1",
                "type": "dummy",
                "instance": 1,
                "bindings": ["io1"],
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    expected_lines = [
        "  PROTO_DUMMY1, 1,",
        "    CProtoDummy::cfgIdIOBind(1),",
        "      IO1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
