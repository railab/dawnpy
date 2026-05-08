# tools/dawnpy/tests/descriptor/handlers/test_io_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import IoObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
from tests.descriptor.handlers.helpers import to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_io_config_no_config(self, generator):
        """Test generating IO config with no configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="bool",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 0," in lines[0]

    def test_generate_io_config_with_device(self, generator):
        """Test generating IO config with device number."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_fetch",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"device": 0},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdDevno()" in lines[1]
        assert "0," in lines[2]

    def test_generate_io_config_with_notify(self, generator):
        """Test generating IO config with notify configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "stream", "priority": 255}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "1," in lines[2]  # stream = 1
        assert "255," in lines[3]  # priority
        assert "1," in lines[4]  # batch = 1 (default)

    def test_generate_io_config_with_notify_batch(self, generator):
        """Test generating IO config with notify batch configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "poll", "priority": 10, "batch": 8}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "0," in lines[2]  # poll = 0
        assert "10," in lines[3]  # priority
        assert "8," in lines[4]  # batch = 8

    def test_generate_io_config_with_notify_poll_default(self, generator):
        """Test generating IO config with poll notify (default type)."""
        obj = IoObject(
            obj_id="test_io",
            io_type="sensor",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "poll", "priority": 100}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "0," in lines[2]  # poll = 0
        assert "100," in lines[3]  # priority
        assert "1," in lines[4]  # batch = 1 (default)

    def test_generate_io_config_with_device_and_notify(self, generator):
        """Test generating IO config with both device and notify."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={
                "device": 2,
                "notify": {"type": "stream", "priority": 200},
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 2," in lines[0]  # 2 config items
        assert "CIOCommon::cfgIdDevno()" in lines[1]
        assert "2," in lines[2]
        assert "CIOCommon::cfgIdNotify()" in lines[3]
        assert "1," in lines[4]  # stream = 1
        assert "200," in lines[5]  # priority

    def test_generate_io_config_default_format(self, generator):
        """Test default formatting path for IO config."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="double",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"init_value": 1.25},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        # double dtype -> SObjectId::DTYPE_DOUBLE = 11; dim is the value
        # count, the C++ helper doubles the resulting cfgid size for 64-bit.
        assert any("cfgIdInitval(11, false, 1)" in line for line in lines)
        assert any("0x00000000" in line for line in lines)
        assert any("0x3ff40000" in line for line in lines)

    def test_generate_io_config_default_format_fallback(self, generator):
        """Test fallback scalar formatting for unhandled dtypes."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="b16",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"init_value": 1.25},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert any("1.25," in line for line in lines)

    def test_map_dtype_to_initval_param(self):
        """Test dtype to SObjectId::DTYPE_* enum-value mapping."""

        def get_param(dtype):
            return to_io_obj({"dtype": dtype}).initval_param

        assert get_param("bool") == 1
        assert get_param("int8") == 2
        assert get_param("uint8") == 3
        assert get_param("int16") == 4
        assert get_param("uint16") == 5
        assert get_param("int32") == 6
        assert get_param("uint32") == 7
        assert get_param("int64") == 8
        assert get_param("uint64") == 9
        assert get_param("float") == 10
        assert get_param("double") == 11
        # Unknown dtype now raises rather than silently defaulting.
        with pytest.raises(ValueError, match="No SObjectId DTYPE mapping"):
            get_param("unknown")

    def test_map_dtype_to_cpp(self):
        """Test dtype to C++ enum mapping."""

        def get_cpp(dtype):
            return to_io_obj({"dtype": dtype}).dtype_cpp

        assert get_cpp("bool") == "SObjectId::DTYPE_BOOL"
        assert get_cpp("unknown") == "SObjectId::DTYPE_UINT32"

    def test_config_loader_typed_io_fields(self):
        """Test typed IO field schemas are loaded."""
        generator = DescriptorGenerator()
        fields = generator.config_loader.get_io_config_fields("control")
        assert any(
            field.name == "allowed" and "start" in field.enum_values
            for field in fields
        )

    def test_config_field_fixed_bytes(self):
        """Test ConfigField fixed-byte values."""
        schema = ConfigField(
            name="names",
            cpp_helper="Cfg::X",
            value_type="string_array",
            value_format="hex",
            string_fixed_bytes=8,
        )
        assert schema.value_format == "hex"
        assert schema.string_fixed_bytes == 8

    def test_format_float_as_hex(self):
        """Test float to hex formatting."""
        generator = DescriptorGenerator()
        helper = generator._format_helper
        assert helper.format_float_as_hex(-1.1) == "0xbf8ccccd"
        assert helper.format_float_as_hex(100.0) == "0x42c80000"
        assert helper.format_float_as_hex(50.0) == "0x42480000"
        assert helper.format_float_as_hex(0.0) == "0x00000000"

    def test_io_config_generator_default_param_fallbacks(self):
        """Test default_params fallback for unhandled custom params."""
        generator = DescriptorGenerator()

        class FakeConfigLoader:
            def get_io_config_fields(self, io_type):
                if io_type != "dummy":
                    return []
                return [
                    ConfigField(
                        name="custom",
                        cpp_helper="CFake::cfg",
                        value_type="int",
                        params=["custom_bool", "custom_int"],
                        default_params=[True, 9],
                    )
                ]

        helper = IoConfigGenerator(
            config_loader=FakeConfigLoader(),
            format_helper=generator._format_helper,
            objects=lambda: generator.objects,
            config_rw_grants=lambda: {},
        )
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"custom": 5},
            }
        )
        lines = helper.generate_io_config("DUMMY1", obj)
        assert any("CFake::cfg(true, 9)" in line for line in lines)
        assert any("      5," == line for line in lines)

        other_obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {},
            }
        )
        assert helper.generate_io_config("GPI1", other_obj) == ["  GPI1, 0,"]

    def test_generate_io_config_with_device_int(self):
        """Test IO config generation with device field (int type)."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {"device": 5},
            },
            obj_id="gpi1",
        )
        lines = generator._generate_io_config("GPI1", obj)
        assert any("cfgIdDevno()" in line for line in lines)
        # Device should be formatted as int, not bool
        assert any("5," in line for line in lines)
        assert not any("true," in line for line in lines)

    def test_generate_io_config_value_type_precedence(self):
        """Test that field value_type takes precedence over object dtype."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {"device": 0},
            },
            obj_id="gpi1",
        )
        lines = generator._generate_io_config("GPI1", obj)
        # Should format device as integer 0, not boolean false
        assert any("0," in line for line in lines)
        assert not any("false," in line for line in lines)

    def test_generate_io_config_default_formatting(self, mocker):
        """Test IO config default value formatting fallback."""
        generator = DescriptorGenerator()

        # Mock config loader to return a field with unknown value_type
        mock_fields = [
            ConfigField(
                name="custom_field",
                cpp_helper="TestIO::cfgIdCustom",
                value_type="unknown_type",  # Not int, not auto
            )
        ]
        mocker.patch.object(
            generator.config_loader,
            "get_io_config_fields",
            return_value=mock_fields,
        )

        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"custom_field": "custom_value"},
            },
            obj_id="test1",
        )
        lines = generator._generate_io_config("TEST1", obj)
        # Should use default formatting
        assert any("custom_value," in line for line in lines)
