import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_serial_with_uint32_baudrate(generator):
    """Test serial protocol with uint32 baudrate config."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [],
        "programs": [],
        "protocols": [
            {
                "id": "serial1",
                "type": "serial",
                "instance": 1,
                "config": {
                    "device": "/dev/ttyUSB0",
                    "baudrate": 115200,  # uint32 config
                },
                "bindings": [],
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Check that serial protocol is generated with baudrate
    expected_lines = [
        "CProtoSerial::objectId",
        "CProtoSerial::cfgIdBaud",
        "115200,",  # uint32 value without hex format
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line: {expected}"
