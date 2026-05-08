# tools/dawnpy/tests/descriptor/handlers/test_io_dummy.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.descriptor_helpers import generate_from_spec
from tests.descriptor.handlers.helpers import to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_io_config_with_init_value_float(self):
        """Test IO config generation with init_value for float."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "float",
                "config": {"init_value": -1.1},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # float -> SObjectId::DTYPE_FLOAT = 10
        assert any("cfgIdInitval(10, false, 1)" in line for line in lines)
        assert any("0xbf8ccccd" in line for line in lines)

    def test_generate_io_config_with_init_value_int32(self):
        """Test IO config generation with init_value for int32."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int32",
                "config": {"init_value": 100},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int32 -> SObjectId::DTYPE_INT32 = 6
        assert any("cfgIdInitval(6, false, 1)" in line for line in lines)
        assert any("100," in line for line in lines)

    def test_generate_io_config_with_init_value_negative_int(self):
        """Test IO config generation with negative int init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int32",
                "config": {"init_value": -20},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int32 -> SObjectId::DTYPE_INT32 = 6
        assert any("cfgIdInitval(6, false, 1)" in line for line in lines)
        assert any("(uint32_t)-20," in line for line in lines)

    def test_generate_io_config_with_init_value_bool(self):
        """Test IO config generation with bool init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "bool",
                "config": {"init_value": True},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # bool -> SObjectId::DTYPE_BOOL = 1
        assert any("cfgIdInitval(1, false, 1)" in line for line in lines)
        assert any("true," in line for line in lines)

    def test_generate_io_config_with_dummy_dim(self):
        """Test IO config generation with explicit dummy dimension."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"dim": 4},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        assert any("CIODummy::cfgIdDim()" in line for line in lines)
        assert any("4," in line for line in lines)

    def test_generate_io_config_with_init_value_list(self):
        """Test IO config generation with list-valued init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"dim": 4, "init_value": [1, 2, 3, 4]},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint32 -> SObjectId::DTYPE_UINT32 = 7; dim is the value count.
        assert any("cfgIdInitval(7, false, 4)" in line for line in lines)
        assert lines.count("      1,") >= 1
        assert lines.count("      4,") >= 1

    def test_generate_io_config_with_init_value_uint64(self):
        """Test IO config generation with uint64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint64",
                "config": {"init_value": 0x0123456789ABCDEF},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint64 -> SObjectId::DTYPE_UINT64 = 9; the C++ helper doubles
        # the resulting cfgid size for 64-bit dtypes, so dim is the
        # value count (1) here even though the data takes two words.
        assert any("cfgIdInitval(9, false, 1)" in line for line in lines)
        assert any("0x89abcdef" in line for line in lines)
        assert any("0x01234567" in line for line in lines)

    def test_generate_io_config_with_init_value_uint64_list(self):
        """Test IO config generation with list-valued uint64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint64",
                "config": {
                    "dim": 2,
                    "init_value": [
                        0x0123456789ABCDEF,
                        0xFEDCBA9876543210,
                    ],
                },
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint64 list of 2 values -> dim = 2 (value count).
        assert any("cfgIdInitval(9, false, 2)" in line for line in lines)
        assert any("0x89abcdef" in line for line in lines)
        assert any("0x01234567" in line for line in lines)
        assert any("0x76543210" in line for line in lines)
        assert any("0xfedcba98" in line for line in lines)

    def test_generate_io_config_with_init_value_int64(self):
        """Test IO config generation with int64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int64",
                "config": {"init_value": -2},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int64 -> SObjectId::DTYPE_INT64 = 8.
        assert any("cfgIdInitval(8, false, 1)" in line for line in lines)
        assert any("0xfffffffe" in line for line in lines)
        assert any("0xffffffff" in line for line in lines)


def test_simple_dummy_io(generator):
    """Test simple dummy IO descriptor generation."""
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
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected output
    expected_lines = [
        "  // dummy1",
        "  DUMMY1, 0,",
    ]

    # Check critical lines are present
    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"

    # Check macro definition
    assert "CIODummy::objectId(SObjectId::DTYPE_BOOL, false, 1)" in output


def test_dummy_io_with_init_value(generator):
    """Test dummy IO with initial value configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "dummy1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint32",
                "config": {"init_value": 42},
            }
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected: should have config item with init value
    expected_lines = [
        "  DUMMY1, 1,",
        "    CIODummy::cfgIdInitval(7, false, 1),",
        "      42,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
