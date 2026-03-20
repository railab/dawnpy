# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_nxscope_udp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``nxscope_udp`` PROTO type."""

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

yaml_type: str = "nxscope_udp"
cpp_class: str = "CProtoNxscopeUdp"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_LOGGING_NXSCOPE",
    "CONFIG_LOGGING_NXSCOPE_INTF_UDP",
    "CONFIG_LOGGING_NXSCOPE_PROTO_SER",
    "CONFIG_NET_UDP",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "nxscope_iobind": ("CProtoNxscopeDummy", "cfgIdIOBind"),
    "nxscope_iobind2": ("CProtoNxscopeDummy", "cfgIdIOBind2"),
    "nxscope_udp_port": ("CProtoNxscopeUdp", "cfgIdPort"),
}
dtype_names: dict[str, str] = {"udp_port": "uint16"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {"nxscope_name": 12}
resolve_bindings = resolve_nxscope_bindings


def allocation_rows(proto: Any) -> list[list[str]]:  # pragma: no cover
    """Return NXScope allocation summary rows."""
    return nxscope_allocation_rows(proto.config, proto.bindings)


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema."""
    return [
        iobind2_field(cpp_class),
        ConfigField(
            name="port",
            cpp_helper="CProtoNxscopeUdp::cfgIdPort",
            value_type="uint16",
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit iobind2 + UDP local port."""
    encode_nxscope_iobind2(ctx)
    if "port" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("udp_port"),
                True,
                1,
                ctx.cfg_id("nxscope_udp_port", 6),
            ),
            [int(ctx.config["port"])],
        )
