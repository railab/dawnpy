# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_shell.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``shell`` PROTO type (CProtoShellPretty)."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    named_refs_to_objid_words,
)
from dawnpy.descriptor.handlers._allocation import bindings_allocation_rows

yaml_type: str = "shell"
cpp_class: str = "CProtoShellPretty"
nuttx_requirements: tuple[str, ...] = ("CONFIG_SYSTEM_READLINE",)
uses_standard_bindings: bool = True
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "bindings": ("CProtoDummy", "cfgIdIOBind"),
    "shell_path": ("CProtoShellPretty", "cfgIdPath"),
    "shell_prompt": ("CProtoShellPretty", "cfgIdPrompt"),
}
dtype_names: dict[str, str] = {"string": "char"}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return shell allocation summary rows."""
    prompt = str(proto.config.get("prompt", "n/a"))
    return bindings_allocation_rows(proto.bindings, details=f"prompt={prompt}")


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``shell``."""
    return [
        ConfigField(
            name="prompt",
            cpp_helper="CProtoShellPretty::cfgIdPrompt",
            value_type="string",
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit shell path/prompt + standard bindings."""
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
                ctx.cfg_id("shell_path", 2),
            ),
            packed,
        )
    if "prompt" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["prompt"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                True,
                len(packed),
                ctx.cfg_id("shell_prompt", 3),
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
