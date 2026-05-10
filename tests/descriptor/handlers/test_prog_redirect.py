import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_redirect_program(generator):
    """Test Redirect program configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "in1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint32",
            },
            {
                "id": "out1",
                "type": "virt",
                "instance": 1,
                "dtype": "uint32",
                "notify": False,
            },
        ],
        "programs": [
            {
                "id": "redir1",
                "type": "redirect",
                "instance": 1,
                "config": {
                    "inputs": ["in1"],
                    "outputs": ["out1"],
                },
            }
        ],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    expected_lines = [
        "  REDIR1, 1,",
        "    CProgRedirect::cfgIdIOBind(2),",
        "      IN1,",
        "      OUT1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
