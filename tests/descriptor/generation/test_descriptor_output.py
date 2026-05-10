# tools/dawnpy/tests/descriptor/test_generator_descriptor_output.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor descriptor output tests for test_generator_descriptor_output."""

import pytest

from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_complete_descriptor_structure(generator):
    """Test complete descriptor structure with all sections."""
    spec = {
        "metadata": {"version": "1.0", "description": "test"},
        "ios": [
            {
                "id": "io1",
                "type": "dummy",
                "instance": 1,
                "dtype": "bool",
            }
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Check required sections are present
    required_sections = [
        "// Included Files",
        "using namespace dawn;",
        "// Object Definitions",
        "// Descriptor Array",
        "uint32_t g_dawn_desc[] =",
        "// Header",
        "CDescriptor::DAWN_DESCRIPTOR_HDR,",
        "// Metadata",
        "CDescriptor::objectId(1),",
        "// Check sum",
        "CDescriptor::DAWN_DESCRIPTOR_FOOT,",
        "0xdeadbeef",
        "size_t g_dawn_desc_size = sizeof(g_dawn_desc);",
    ]

    for section in required_sections:
        assert section in output, f"Required section not found: {section}"


def test_metadata_version_encoding(generator):
    """Test metadata version encoding."""
    spec = {
        "metadata": {"version": "2.1"},
        "ios": [],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Version 2.1 should be encoded as 0x00020001
    expected = "0x00020001"
    assert expected in output, f"Expected version encoding: {expected}"


def test_header_includes(generator):
    """Test that required headers are included."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "dummy1",
                "type": "dummy",
                "instance": 1,
                "dtype": "bool",
            }
        ],
        "programs": [
            {
                "id": "min1",
                "type": "statsmin",
                "instance": 1,
                "config": {
                    "inputs": ["dummy1"],
                    "outputs": ["dummy1"],
                },
            }
        ],
        "protocols": [
            {
                "id": "shell1",
                "type": "shell",
                "instance": 1,
                "bindings": [],
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Check all required headers
    expected_includes = [
        '#include "dawn/common/descriptor.hxx"',
        '#include "dawn/io/dummy.hxx"',
        '#include "dawn/prog/statsmin.hxx"',
        '#include "dawn/proto/shell/pretty.hxx"',
    ]

    for include in expected_includes:
        assert include in output, f"Expected include not found: {include}"


def test_object_count_in_header(generator):
    """Test that object count in header is correct."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {"id": "io1", "type": "dummy", "instance": 1, "dtype": "bool"},
            {"id": "io2", "type": "dummy", "instance": 2, "dtype": "bool"},
            {"id": "io3", "type": "dummy", "instance": 3, "dtype": "bool"},
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Should have 4 objects: metadata + 3 IOs
    # Header format: HDR, count
    lines = output.split("\n")
    header_found = False
    for i, line in enumerate(lines):
        if "CDescriptor::DAWN_DESCRIPTOR_HDR" in line:
            # Next line or same line should have count
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Count = 1 (metadata) + 3 (ios) = 4
                if next_line.startswith("4"):  # pragma: no cover
                    header_found = True
                    break
            # Or same line
            if ", 4" in line or ",4" in line:
                header_found = True
                break

    assert header_found, "Correct object count not found in header"
