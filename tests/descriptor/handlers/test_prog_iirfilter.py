import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_iirfilter_program(generator):
    """Test IIRFilter program configuration."""
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
                "id": "iir1",
                "type": "iirfilter",
                "instance": 1,
                "config": {
                    "inputs": ["in1"],
                    "outputs": ["out1"],
                    "alpha_num": 1,
                    "alpha_den": 4,
                },
            }
        ],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    expected_lines = [
        "  IIR1, 3,",
        "    CProgIIRFilter::cfgIdIOBind(2),",
        "      IN1,",
        "      OUT1,",
        "    CProgIIRFilter::cfgIdAlphaNum(),",
        "      1,",
        "    CProgIIRFilter::cfgIdAlphaDen(),",
        "      4,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
