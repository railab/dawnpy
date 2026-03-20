# tools/dawnpy/tests/descriptor/handlers/test_proto_generic.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProtocolObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


def to_proto_obj(spec: dict, obj_id: str = "test_proto") -> ProtocolObject:
    full_spec = {
        "id": obj_id,
        "type": spec.get("type", "serial"),
        "instance": spec.get("instance", 1),
        "config": spec.get("config", {}),
        "bindings": spec.get("bindings", []),
    }
    return ProtocolObject.from_spec(full_spec)


class TestProtoGenericHandlers:

    def test_generate_proto_config_simple(self, generator):
        """Test generating simple protocol config."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1", "io2"],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 1," in lines[0]
        assert "cfgIdIOBind(2)" in lines[1]
        assert "IO1," in lines[2]
        assert "IO2," in lines[3]

    def test_generate_proto_config_bindings_from_config(self, generator):
        """Simple protocols accept bindings inside config."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "config": {"bindings": ["io1"]},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 1," in lines[0]
        assert "cfgIdIOBind(1)" in lines[1]
        assert "IO1," in lines[2]

    def test_generate_simple_proto_bindings(self, generator):
        """Test protocol builder simple binding generation."""
        proto_builder = generator._protocol_config_generator()
        lines = proto_builder.generate_simple_proto_bindings(
            "PROTO1", "serial", ["io1"]
        )
        assert lines[0] == "  PROTO1, 1,"
        assert "CProtoSerial::cfgIdIOBind(1)," in lines[1]
        assert "IO1," in lines[2]

    def test_generate_proto_config_no_bindings(self, generator):
        """Test generating protocol config with no bindings."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": [],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 0," in lines[0]

    def test_generate_proto_config_with_custom_fields(self, generator):
        """Test generating protocol config with custom fields like shell."""
        obj = to_proto_obj(
            {
                "type": "shell",
                "bindings": ["io1"],
                "config": {"prompt": "dawn> "},
            }
        )
        lines = generator._generate_proto_config("SHELL_PROTO", obj)
        # Should have custom config
        assert "SHELL_PROTO," in lines[0]
        # String now has size parameter
        assert "CProtoShellPretty::cfgIdPrompt(" in "".join(lines)
        # String is packed as uint32_t
        assert "0x" in "".join(lines)

    def test_generate_proto_config_with_nested_fields(self, generator):
        """Test protocol with nested fields like nimble."""
        obj = to_proto_obj(
            {
                "type": "nimble",
                "bindings": [],
                "config": {"services": {"dis": {}, "bas": {}}},
            }
        )
        lines = generator._generate_proto_config("NIMBLE_PROTO", obj)
        # Nested fields should be skipped in current implementation
        assert "NIMBLE_PROTO," in lines[0]

    def test_generate_proto_config_missing_optional_field(self, generator):
        """Test protocol config with optional field not provided."""
        obj = to_proto_obj(
            {
                "type": "shell",
                "bindings": ["io1"],
                "config": {},  # prompt field not provided
            }
        )
        lines = generator._generate_proto_config("SHELL_PROTO", obj)
        # Should handle missing optional fields
        assert "SHELL_PROTO," in lines[0]

    def test_generate_proto_config_unknown_type(self, generator):
        """Test generating protocol config with unknown type."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "unknown_proto",
                    "bindings": [],
                    "config": {},
                }
            )

    def test_generate_proto_config_no_custom_fields(self, generator):
        """Test protocol with standard bindings but no custom fields."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1", "io2"],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        # Should use simple bindings path
        assert "SERIAL_PROTO, 1," in lines[0]

    def test_generate_proto_config_with_iobind2(self, generator):
        """Test protocol config with nxscope iobind2."""
        obj = to_proto_obj(
            {
                "type": "nxscope_serial",
                "config": {
                    "iobind2": [
                        {"id": "io1", "name": "alpha"},
                        {"id": "io2", "name": "b"},
                    ]
                },
            }
        )
        lines = generator._generate_proto_config("NXSCOPE_PROTO", obj)
        assert "NXSCOPE_PROTO," in lines[0]
        assert "CProtoNxscopeSerial::cfgIdIOBind2(2)" in " ".join(lines)
        assert "IO1," in " ".join(lines)
        assert "IO2," in " ".join(lines)
        # Should have packed string data (3 words per name)
        word_lines = [line for line in lines if "0x" in line]
        assert len(word_lines) == 6

    def test_generate_proto_config_with_uint32(self, generator):
        """Test protocol config with uint32 value type."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1"],
                "config": {"path": "/dev/ttyS0", "baudrate": 115200},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        assert "SERIAL_PROTO," in lines[0]
        assert "CProtoSerial::cfgIdBaud()" in " ".join(lines)
        assert "115200" in " ".join(lines)

    def test_generate_proto_config_empty_fields_with_config(self, mocker):
        """Test protocol with empty fields but has config."""
        from dawnpy.descriptor.definitions.type_info import ProtoSchema

        generator = DescriptorGenerator()

        # Mock protocol with uses_standard_bindings and empty fields
        mock_schema = ProtoSchema(
            proto_type="serial",
            uses_standard_bindings=True,
            fields=[],
        )
        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=mock_schema,
        )

        # Resolve bindings
        generator.objects = {
            "io1": {
                "id": "io1",
                "category": "IO",
                "type": "dummy",
                "instance": 1,
            },
        }
        generator.object_order = ["io1"]

        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1"],
                "config": {"unknown": "value"},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        # Should use simple bindings path since fields is empty
        assert "SERIAL_PROTO, 1," in lines[0]
        assert "IO1" in " ".join(lines)

    def test_custom_proto_config_with_missing_field(self, mocker):
        """Test custom proto config when field is missing from config."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"field1": 42},
                }
            )

    def test_custom_proto_config_with_nested_field(self, mocker):
        """Test custom proto config with nested field."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"nested_config": {"key": "value"}},
                }
            )

    def test_custom_proto_config_with_int_hex(self, mocker):
        """Test custom proto config with int hex format."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"hex_value": 0x1234},
                }
            )

    def test_custom_proto_config_with_non_standard_type(self, mocker):
        """Test custom proto config with non-int, non-string value."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"other_value": 42.5},
                }
            )

    def test_to_proto_obj_helper(self):
        """Test to_proto_obj helper coverage."""
        obj = to_proto_obj({"type": "can", "bindings": ["io1"]})
        assert obj.proto_type == "can"
        assert "io1" in obj.bindings

    def test_config_loader_typed_proto_schema(self):
        """Test typed protocol schema wrapper."""
        generator = DescriptorGenerator()
        can_schema = generator.config_loader.get_proto_config_schema("can")
        missing = generator.config_loader.get_proto_config_schema(
            "missing_proto"
        )
        assert can_schema is not None
        assert isinstance(can_schema.uses_standard_bindings, bool)
        assert missing is None

    def test_generate_custom_proto_config_with_bindings(self):
        """Test generic custom protocol config with bindings."""
        generator = DescriptorGenerator()

        obj = to_proto_obj(
            {
                "type": "nxscope_serial",
                "config": {
                    "iobind2": [
                        {"id": "sensor1", "name": "a"},
                        {"id": "sensor2", "name": "b"},
                        {"id": "sensor3", "name": "c"},
                    ]
                },
            }
        )

        fields = [
            ConfigField(
                name="iobind2",
                cpp_helper="CProtoNxscopeSerial::cfgIdIOBind2",
                value_type="nxscope_iobind2",
            )
        ]

        proto_builder = generator._protocol_config_generator()
        lines = proto_builder._generic.generate(
            "NXSCOPE1", "nxscope_serial", obj, fields
        )

        # Should have 1 config item (iobind2)
        assert "NXSCOPE1, 1," in lines[0]
        assert any("cfgIdIOBind2(3)" in line for line in lines)
        assert any("SENSOR1," in line for line in lines)

    def test_registered_protocol_handlers(self):
        """Per-type proto handlers are registered in PROTO_HANDLER_REGISTRY."""
        from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

        assert "can" in PROTO_HANDLER_REGISTRY
        assert "modbus_rtu" in PROTO_HANDLER_REGISTRY
        assert "nimble" in PROTO_HANDLER_REGISTRY
        assert "nxscope_serial" in PROTO_HANDLER_REGISTRY

    def test_dispatch_uses_registered_handler(self, monkeypatch):
        """generate_proto_config routes to the registered generate_cpp."""
        from dawnpy.descriptor.handlers import (
            PROTO_HANDLER_REGISTRY,
            proto_can,
        )

        generator = DescriptorGenerator()
        obj = to_proto_obj({"type": "can", "bindings": [], "config": {}})

        def fake_generate(macro_name, obj_inst, gctx):
            assert macro_name == "CAN1"
            assert isinstance(obj_inst, ProtocolObject)
            assert obj_inst.proto_type == "can"
            return ["  CAN1, 123,"]

        monkeypatch.setattr(proto_can, "generate_cpp", fake_generate)
        # The registry stores handler instances that delegate to modules.
        assert PROTO_HANDLER_REGISTRY["can"].generate_cpp is fake_generate
        lines = generator._generate_proto_config("CAN1", obj)
        assert lines == ["  CAN1, 123,"]

    def test_proto_uses_standard_bindings_without_schema(self, monkeypatch):
        """Test protocol binding fallback when schema lookup returns none."""
        generator = DescriptorGenerator()
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_config_schema",
            lambda _: None,
        )
        assert generator._proto_uses_standard_bindings("unknown") is False

    def test_generate_generic_proto_field_without_cpp_helper(self):
        """Test generic proto field skip when helper is missing."""
        generator = DescriptorGenerator()
        field = ConfigField(name="f", value_type="int")
        proto_gen = generator._protocol_config_generator()
        assert proto_gen._generic.generate_generic_field(10, field) == []

    def test_generate_nxscope_iobind2_field_wrapper(self):
        """Test nxscope_iobind2 wrapper delegates and formats output."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()._generic
        lines = proto_gen.generate_nxscope_iobind2_field(
            value=[{"id": "io1", "name": "chan1"}, "io2"],
            field=ConfigField(name="iobind2", string_fixed_bytes=8),
            cpp_helper="CProtoNxscope::cfgIdIOBind2",
        )
        assert lines[0] == "    CProtoNxscope::cfgIdIOBind2(2),"
        assert "      IO1," in lines
        assert "      IO2," in lines

    def test_count_generic_proto_config_items(self):
        """Test counting with standard bindings and nested fields."""
        generator = DescriptorGenerator()
        fields = [
            ConfigField(name="a"),
            ConfigField(name="b", nested=True),
            ConfigField(name="c"),
        ]
        config = {"a": 1, "b": {"x": 1}}
        count = (
            generator._protocol_config_generator()._generic.count_config_items(
                fields, config, uses_standard=True, bindings=["io1"]
            )
        )
        assert count == 2

    def test_pack_string_array_field_words_mode(self):
        """Test string-array packing default size mode (words)."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()
        (
            size,
            words,
        ) = proto_gen._generic.pack_string_array_field(
            ["ab"],
            ConfigField(name="names", value_type="string_array"),
        )
        assert size == len(words)
        assert size > 0

    def test_generate_generic_proto_field_int_hex_branch(self):
        """Test generic proto int field formatting in hex mode."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()
        lines = proto_gen._generic.generate_generic_field(
            value=4660,
            field=ConfigField(
                name="hex_value",
                cpp_helper="CProtoDummy::cfgIdHex",
                value_type="int",
                value_format="hex",
            ),
        )
        assert any("CProtoDummy::cfgIdHex()" in line for line in lines)
        assert any("0x1234" in line for line in lines)


def test_generate_proto_config_handles_special_fields(monkeypatch):
    from dawnpy.descriptor.definitions.type_info import ProtoSchema

    generator = DescriptorGenerator()
    schema = ProtoSchema(
        proto_type="nxscope_dummy",
        uses_standard_bindings=False,
        fields=[
            ConfigField(
                name="iobind2",
                cpp_helper="CProtoNxscope::cfgIdIOBind2",
                value_type="nxscope_iobind2",
                string_fixed_bytes=8,
            ),
            ConfigField(
                name="names",
                cpp_helper="CProtoNxscope::cfgIdNames",
                value_type="string_array",
                string_fixed_bytes=4,
                string_array_size="count",
            ),
            ConfigField(
                name="extra_names",
                cpp_helper="CProtoNxscope::cfgIdExtra",
                value_type="string_array",
            ),
        ],
    )

    monkeypatch.setattr(
        generator.config_loader,
        "get_proto_config_schema",
        lambda proto_type: schema if proto_type == "nxscope_dummy" else None,
    )

    obj = to_proto_obj(
        {
            "type": "nxscope_dummy",
            "bindings": ["io1"],
            "config": {
                "iobind2": [
                    "io1",
                    {"id": "io2"},
                    {"io": "io3"},
                    {"ref": "io4"},
                    123,
                ],
                "names": ["alpha", "beta", "a"],
                "extra_names": ["x"],
            },
        }
    )

    lines = generator._generate_proto_config("NX1", obj)
    assert any("cfgIdIOBind2" in line for line in lines)
    assert any("cfgIdNames" in line for line in lines)
    assert any("cfgIdExtra" in line for line in lines)
