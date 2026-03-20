# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_nxscope_serial.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``nxscope_serial`` PROTO type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.descriptor.handlers._proto_nxscope_common import (
    encode_nxscope_iobind2,
    iobind2_field,
    nxscope_allocation_rows,
    resolve_nxscope_bindings,
)

yaml_type: str = "nxscope_serial"
cpp_class: str = "CProtoNxscopeSerial"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_LOGGING_NXSCOPE",
    "CONFIG_LOGGING_NXSCOPE_INTF_SERIAL",
    "CONFIG_LOGGING_NXSCOPE_PROTO_SER",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "nxscope_iobind": ("CProtoNxscopeDummy", "cfgIdIOBind"),
    "nxscope_iobind2": ("CProtoNxscopeDummy", "cfgIdIOBind2"),
    "nxscope_serial_path": ("CProtoNxscopeSerial", "cfgIdPath"),
    "nxscope_serial_baudrate": ("CProtoNxscopeSerial", "cfgIdBaud"),
}
dtype_names: dict[str, str] = {"string": "char", "int": "uint32"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {"nxscope_name": 12}
resolve_bindings = resolve_nxscope_bindings


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return NXScope allocation summary rows."""
    return nxscope_allocation_rows(proto.config, proto.bindings)


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema."""
    return [
        iobind2_field(cpp_class),
        ConfigField(
            name="path",
            cpp_helper="CProtoNxscopeSerial::cfgIdPath",
            value_type="string",
        ),
        ConfigField(
            name="baudrate",
            cpp_helper="CProtoNxscopeSerial::cfgIdBaud",
            value_type="uint32",
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit iobind2 + serial path/baudrate."""
    encode_nxscope_iobind2(ctx)
    if "path" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["path"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                True,
                len(packed),
                ctx.cfg_id("nxscope_serial_path", 4),
            ),
            packed,
        )
    if "baudrate" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("int"),
                True,
                1,
                ctx.cfg_id("nxscope_serial_baudrate", 5),
            ),
            [int(ctx.config["baudrate"])],
        )
