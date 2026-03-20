# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_udp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``udp`` PROTO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    named_refs_to_objid_words,
)

yaml_type: str = "udp"
cpp_class: str = "CProtoUdp"
nuttx_requirements: tuple[str, ...] = ("CONFIG_NET_UDP",)
uses_standard_bindings: bool = True
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "bindings": ("CProtoDummy", "cfgIdIOBind"),
    "udp_port": ("CProtoUdp", "cfgIdPort"),
}
dtype_names: dict[str, str] = {"udp_port": "uint16"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``udp``."""
    return [
        ConfigField(
            name="port", cpp_helper="CProtoUdp::cfgIdPort", value_type="uint16"
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit UDP port + standard bindings."""
    if "port" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("udp_port"),
                True,
                1,
                ctx.cfg_id("udp_port", 2),
            ),
            [int(ctx.config["port"])],
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
