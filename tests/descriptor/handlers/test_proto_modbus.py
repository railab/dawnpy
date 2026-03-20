# tools/dawnpy/tests/descriptor/handlers/test_proto_modbus.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProtocolObject
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


class TestProtoModbusHandler:

    def test_generate_modbus_config_with_path_and_registers(self, generator):
        """Test Modbus RTU config generation with path/register blocks."""
        obj = to_proto_obj(
            {
                "type": "modbus_rtu",
                "bindings": ["unused_top_level_binding"],
                "config": {
                    "path": "/dev/ttyS1",
                    "registers": [
                        {
                            "type": "holding",
                            "config": 1,
                            "start": 100,
                            "bindings": ["io1", "io2"],
                        },
                        {
                            "type": "coil",
                            "config": 0,
                            "start": 200,
                            "bindings": ["io3"],
                        },
                    ],
                },
            }
        )
        assert obj.bindings == ["io1", "io2", "io3"]
        lines = generator._generate_proto_config("MODBUS_PROTO", obj)
        joined = "\n".join(lines)

        assert "MODBUS_PROTO, 2," in lines[0]
        assert "CProtoModbusRtu::cfgIdPath(" in joined
        assert "CProtoModbusRtu::cfgIdIOBind(11)" in joined
        assert "CProtoModbusRegs::MODBUS_TYPE_HOLDING, 1, 100, 2," in joined
        assert "CProtoModbusRegs::MODBUS_TYPE_COIL, 0, 200, 1," in joined
        assert "IO1," in joined
        assert "IO2," in joined
        assert "IO3," in joined

    def test_generate_modbus_tcp_config_with_port_and_registers(
        self, generator
    ):
        """Modbus TCP path uses CProtoModbusTcp and emits port + registers."""
        obj = to_proto_obj(
            {
                "type": "modbus_tcp",
                "bindings": ["unused_top_level_binding"],
                "config": {
                    "port": 502,
                    "registers": [
                        {
                            "type": "holding",
                            "config": 1,
                            "start": 100,
                            "bindings": ["io1"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("MODBUS_TCP_PROTO", obj)
        joined = "\n".join(lines)

        assert "MODBUS_TCP_PROTO, 2," in lines[0]
        assert "CProtoModbusTcp::cfgIdPort()" in joined
        assert "502," in joined
        assert "CProtoModbusTcp::cfgIdIOBind(" in joined

    def test_modbus_register_type_map_falls_back_to_rtu_for_unknown_proto(
        self, generator
    ):
        """Unknown proto type falls back to modbus_rtu lookups."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
            get_register_type_prefix,
        )

        loader = generator.config_loader
        rtu_map = get_register_type_map(loader, "modbus_rtu")
        unknown_map = get_register_type_map(loader, "__no_such_modbus__")
        assert unknown_map == rtu_map
        assert get_register_type_prefix(
            loader, "__no_such_modbus__"
        ) == get_register_type_prefix(loader, "modbus_rtu")

    def test_modbus_register_type_map_comes_from_schema(self):
        """Test modbus type mapping is derived from YAML schema."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
        )

        generator = DescriptorGenerator()
        type_map = get_register_type_map(generator.config_loader, "modbus_rtu")
        assert type_map.get("holding") == "HOLDING"
        assert type_map.get("coil") == "COIL"

    def test_modbus_register_type_map_fallback(self, monkeypatch):
        """Test modbus type map fallback when schema data is missing."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
        )

        generator = DescriptorGenerator()
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_nested_enum_map",
            lambda proto, nested, element: {},
        )
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_nested_enum_prefix",
            lambda proto, nested, element: "",
        )
        type_map = get_register_type_map(generator.config_loader, "modbus_rtu")
        assert type_map.get("holding") is None
