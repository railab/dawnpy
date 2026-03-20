# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_modbus_tcp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``modbus_tcp`` PROTO type.

Owns cpp_class binding, user-facing config schema (incl. nested
``registers`` element fields), and the binary serializer. Shares the
register-group encoder with :mod:`proto_modbus_rtu` via
:mod:`_proto_modbus_common`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.descriptor.handlers._proto_modbus_common import (
    emit_modbus_registers_cpp,
    encode_modbus_registers,
    modbus_allocation_rows,
    resolve_modbus_bindings,
)

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext


yaml_type: str = "modbus_tcp"
cpp_class: str = "CProtoModbusTcp"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_INDUSTRY_NXMODBUS",
    "CONFIG_NET_TCP",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "modbus_tcp_iobind": ("CProtoModbusTcp", "cfgIdIOBind"),
    "modbus_tcp_port": ("CProtoModbusTcp", "cfgIdPort"),
}
dtype_names: dict[str, str] = {"udp_port": "uint16"}
enum_value_maps: dict[str, tuple[str, str]] = {
    "modbus_type": ("CProtoModbusRegs", "MODBUS_TYPE_"),
}
defaults: dict[str, int] = {"modbus_config": 0, "modbus_start": 0}
fixed_string_bytes: dict[str, int] = {}


def allocation_rows(proto: Any) -> list[list[str]]:  # pragma: no cover
    """Return Modbus TCP allocation summary rows."""
    return modbus_allocation_rows(proto)


resolve_bindings = resolve_modbus_bindings


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``modbus_tcp``."""
    return [
        ConfigField(
            name="port",
            cpp_helper="CProtoModbusTcp::cfgIdPort",
            value_type="uint16",
        ),
        ConfigField(
            name="registers",
            nested=True,
            array=True,
            element_fields=[
                ConfigField(
                    name="type",
                    value_type="enum",
                    enum_prefix="CProtoModbusRegs::MODBUS_TYPE_",
                ),
                ConfigField(name="config", value_type="int"),
                ConfigField(name="start", value_type="int"),
                ConfigField(name="count", value_type="computed"),
                ConfigField(
                    name="bindings",
                    cpp_helper="CProtoModbusTcp::cfgIdIOBind",
                    value_type="id_array",
                    size_calculation="4 + count",
                ),
            ],
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Encode Modbus TCP binary block into ``ctx.items``."""
    if "port" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("udp_port"),
                True,
                1,
                ctx.cfg_id("modbus_tcp_port", 2),
            ),
            [int(ctx.config["port"])],
        )
    encode_modbus_registers(ctx, "modbus_tcp_iobind", 1)


def generate_cpp(
    macro_name: str, obj: ProtocolObject, gctx: ProtoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a Modbus TCP object."""
    lines: list[str] = []
    config = obj.config
    registers = config.get("registers", [])

    config_count = 0
    if "path" in config:
        config_count += 1  # pragma: no cover
    if "port" in config:
        config_count += 1
    if registers:
        config_count += 1
    gctx.format_helper.append_line(lines, 1, f"{macro_name}, {config_count},")

    if "path" in config:
        packed_words = gctx.format_helper.pack_string(
            str(config["path"])
        )  # pragma: no cover
        # The original modbus.py emitter hard-codes CProtoModbusRtu::cfgIdPath
        # for both transports - preserve that behavior to keep .cxx output
        # byte-identical against the baseline.
        gctx.format_helper.append_line(
            lines, 2, f"CProtoModbusRtu::cfgIdPath({len(packed_words)}),"
        )  # pragma: no cover
        gctx.format_helper.append_words(
            lines, packed_words, level=3
        )  # pragma: no cover
    if "port" in config:
        gctx.format_helper.append_line(lines, 2, f"{cpp_class}::cfgIdPort(),")
        gctx.format_helper.append_line(lines, 3, f"{config['port']},")
    if registers:
        emit_modbus_registers_cpp(
            lines, registers, cpp_class, "modbus_tcp", gctx
        )
    return lines
