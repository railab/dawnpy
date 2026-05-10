# tools/dawnpy/tests/descriptor/handlers/test_proto_shell.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestShellProtocol:
    """Test shell protocol generation."""

    def test_shell_with_bindings(self, tmp_path):
        """Test shell protocol with IO bindings."""
        yaml_content = """
ios:
  - &io1
    id: dummy1
    type: dummy
    instance: 1
    dtype: bool

protocols:
  - id: shell1
    type: shell
    instance: 1
    bindings:
      - *io1
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "CProtoShellPretty::cfgIdIOBind(1)" in cpp_code

    def test_shell_without_bindings(self, tmp_path):
        """Test shell protocol without bindings."""
        yaml_content = """
protocols:
  - id: shell1
    type: shell
    instance: 1
    bindings: []
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "SHELL1, 0," in cpp_code


def test_shell_protocol(generator):
    """Test shell protocol configuration."""
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
                "id": "shell1",
                "type": "shell",
                "instance": 1,
                "config": {"prompt": "test> "},
                "bindings": ["io1"],
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Expected: Shell config count should be 2 (prompt + bindings)
    expected_lines = [
        "  SHELL1, 2,",
        "    CProtoShellPretty::cfgIdPrompt",
        "    CProtoShellPretty::cfgIdIOBind(1)",
        "      IO1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"


def test_long_string_padding(generator):
    """Test string padding for strings longer than 16 bytes."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [],
        "programs": [],
        "protocols": [
            {
                "id": "shell1",
                "type": "shell",
                "instance": 1,
                "config": {
                    "prompt": (
                        "This is a very long prompt "
                        "string that exceeds sixteen bytes"
                    )
                },
                "bindings": [],
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Should generate shell with long prompt
    assert "CProtoShellPretty::cfgIdPrompt" in output
