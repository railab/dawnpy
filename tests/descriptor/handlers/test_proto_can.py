# tools/dawnpy/tests/descriptor/handlers/test_proto_can.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProtocolObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.helpers import generate_from_spec

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


class TestProtoCanHandler:

    def test_generate_can_config(self, generator):
        """Test generating CAN protocol config (via handlers/proto_can)."""
        obj = ProtocolObject(
            obj_id="can1",
            proto_type="can",
            instance=1,
            bindings=[],
            config={
                "node_id": 0x100,
                "objects": [
                    {
                        "type": "push",
                        "flags": 0,
                        "can_id_start": 0x000,
                        "count": 1,
                        "bindings": ["io1"],
                    }
                ],
            },
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO, 2," in lines[0]
        assert "CProtoCan::cfgIdNodeid()" in lines[1]
        assert "0x0100," in lines[2]
        assert "CProtoCan::cfgIdIOBind(4)" in lines[4]

    def test_generate_can_config_missing_optional_field(self, generator):
        """Test CAN config with missing optional fields."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "objects": [
                        {
                            "type": "push",
                            "flags": 0,
                            "can_id_start": 0x200,
                            "count": 2,
                            "bindings": ["io1", "io2"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        # Should handle missing node_id gracefully
        assert "CAN_PROTO," in lines[0]

    def test_generate_can_object_with_non_hex_field(self, generator):
        """Test CAN object with integer field that's not hex formatted."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 100,  # Non-hex value
                    "objects": [],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        # Should handle non-hex format
        assert "CAN_PROTO," in lines[0]

    def test_generate_can_object_enum_handling(self, generator):
        """Test CAN object with enum type field."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 0x100,
                    "objects": [
                        {
                            "type": "read",  # Different enum value
                            "flags": 0,
                            "can_id_start": 0x300,
                            "count": 1,
                            "bindings": ["io1"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]
        assert "READ" in "".join(lines)

    def test_generate_can_object_computed_values(self, generator):
        """Test CAN object with computed value types."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 0x100,
                    "objects": [
                        {
                            "type": "write",
                            "flags": 5,  # Non-zero flags
                            "can_id_start": 0x400,
                            "count": 3,
                            "bindings": ["io1", "io2", "io3"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]
        assert "WRITE" in "".join(lines)
        assert "3" in "".join(lines)  # count value

    def test_can_config_with_none_schema(self, mocker):
        """Test CAN config when schema is None."""
        generator = DescriptorGenerator()
        # handler dispatched via _generate_proto_config

        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=None,
        )

        obj = to_proto_obj(
            {
                "type": "can",
                "bindings": [],
                "config": {"node_id": 0x100},
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO, 0," in lines[0]

    def test_can_config_with_non_hex_simple_field(self, mocker):
        """Test CAN config with non-hex simple field."""
        from dawnpy.descriptor.definitions.type_info import ProtoSchema

        generator = DescriptorGenerator()
        # handler dispatched via _generate_proto_config

        mock_schema = ProtoSchema(
            proto_type="can",
            uses_standard_bindings=False,
            fields=[
                ConfigField(
                    name="simple_int",
                    cpp_helper="CProtoCan::cfgIdSimple",
                    value_type="int",
                    # No format specified, not hex
                ),
            ],
        )
        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=mock_schema,
        )

        obj = to_proto_obj(
            {
                "type": "can",
                "bindings": [],
                "config": {"simple_int": 100},
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]

    def test_can_object_without_bindings_field(self, mocker):
        """CAN element_fields without a bindings entry yields no lines."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [ConfigField(name="type", value_type="enum")]
        obj_config = {"type": "push", "bindings": ["io1"]}
        assert _generate_can_object(obj_config, element_fields, gctx) == []

    def test_can_object_without_size_calculation(self, mocker):
        """CAN element_fields without size_calculation falls back to count."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
            ),
        ]
        obj_config = {"bindings": ["io1", "io2"]}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert len(lines) > 0

    def test_can_object_with_non_standard_value_type(self, mocker):
        """CAN object element with non-int, non-enum value type."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
                size_calculation="2 + count",
            ),
            ConfigField(name="custom_field", value_type="custom"),
        ]
        obj_config = {"bindings": ["io1"], "custom_field": "custom_value"}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert len(lines) > 0

    def test_can_object_with_non_hex_int_field(self, mocker):
        """CAN object element with a decimal integer value."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
                size_calculation="2 + count",
            ),
            ConfigField(name="custom_int", value_type="int"),
        ]
        obj_config = {"bindings": ["io1"], "custom_int": 17}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert any("17," in line for line in lines)


def test_can_protocol_basic(generator):
    """Test basic CAN protocol configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "io1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint64",
            }
        ],
        "programs": [],
        "protocols": [
            {
                "id": "can1",
                "type": "can",
                "instance": 1,
                "config": {
                    "node_id": 256,
                    "objects": [
                        {
                            "type": "read",
                            "flags": 0,
                            "can_id_start": 256,
                            "count": 1,
                            "bindings": ["io1"],
                        }
                    ],
                },
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Expected: CAN config with node_id and object
    expected_lines = [
        "  CAN1,",
        "    CProtoCan::cfgIdNodeid(),",
        "      0x0100,",
        "    CProtoCan::cfgIdIOBind(4),",
        "      CProtoCan::CAN_TYPE_READ,",
        "      0x0100,",
        "      1,",
        "      IO1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
