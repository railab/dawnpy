# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_dummy.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``dummy`` PROTO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    named_refs_to_objid_words,
)

yaml_type: str = "dummy"
cpp_class: str = "CProtoDummy"
uses_standard_bindings: bool = True
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "bindings": ("CProtoDummy", "cfgIdIOBind"),
}
dtype_names: dict[str, str] = {}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``dummy`` (none)."""
    return []


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit the standard bindings block (no other fields)."""
    if not ctx.obj.bindings:
        return
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
