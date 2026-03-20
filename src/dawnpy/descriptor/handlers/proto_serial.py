# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_serial.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``serial`` PROTO type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    named_refs_to_objid_words,
)
from dawnpy.descriptor.handlers._allocation import bindings_allocation_rows

yaml_type: str = "serial"
cpp_class: str = "CProtoSerial"
uses_standard_bindings: bool = True
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "bindings": ("CProtoDummy", "cfgIdIOBind"),
    "serial_path": ("CProtoSerial", "cfgIdPath"),
    "serial_baudrate": ("CProtoSerial", "cfgIdBaud"),
}
dtype_names: dict[str, str] = {"string": "char", "int": "uint32"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return serial allocation summary rows."""
    path = str(proto.config.get("path", "n/a"))
    baudrate = str(proto.config.get("baudrate", "n/a"))
    return bindings_allocation_rows(
        proto.bindings, details=f"path={path}, baudrate={baudrate}"
    )


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``serial``."""
    return [
        ConfigField(
            name="path",
            cpp_helper="CProtoSerial::cfgIdPath",
            value_type="string",
        ),
        ConfigField(
            name="baudrate",
            cpp_helper="CProtoSerial::cfgIdBaud",
            value_type="uint32",
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit serial path/baudrate + standard bindings."""
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
                ctx.cfg_id("serial_path", 2),
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
                ctx.cfg_id("serial_baudrate", 3),
            ),
            [int(ctx.config["baudrate"])],
        )
    if ctx.obj.bindings:
        words = named_refs_to_objid_words(ctx.obj.bindings, ctx.obj_ids)
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(words),
                ctx.cfg_id("bindings", 1),
            ),
            words,
        )
