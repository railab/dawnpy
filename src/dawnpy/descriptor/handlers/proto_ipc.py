# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_ipc.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``ipc`` PROTO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    named_refs_to_objid_words,
)

yaml_type: str = "ipc"
cpp_class: str = "CProtoIpc"
nuttx_requirements: tuple[str, ...] = ("CONFIG_PIPES",)
uses_standard_bindings: bool = True
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "bindings": ("CProtoDummy", "cfgIdIOBind"),
    "ipc_rx_path": ("CProtoIpc", "cfgIdRxPath"),
    "ipc_tx_path": ("CProtoIpc", "cfgIdTxPath"),
}
dtype_names: dict[str, str] = {"string": "char"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``ipc``."""
    return [
        ConfigField(
            name="rx_path",
            cpp_helper="CProtoIpc::cfgIdRxPath",
            value_type="string",
        ),
        ConfigField(
            name="tx_path",
            cpp_helper="CProtoIpc::cfgIdTxPath",
            value_type="string",
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit IPC rx/tx FIFO paths + standard bindings."""
    if "rx_path" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["rx_path"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                True,
                len(packed),
                ctx.cfg_id("ipc_rx_path", 2),
            ),
            packed,
        )
    if "tx_path" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["tx_path"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                True,
                len(packed),
                ctx.cfg_id("ipc_tx_path", 3),
            ),
            packed,
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
