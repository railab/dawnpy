# tools/dawnpy/src/dawnpy/descriptor/handlers/io_control.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``control`` IO type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import (
    _IOSerializeContext,
    resolve_allowed_bits,
)
from dawnpy.descriptor.handlers._io_targets_common import (
    emit_targets_and_allowed_cpp,
    encode_targets_and_allowed,
)
from dawnpy.headerdefs.bundle import header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import IoObject
    from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext


yaml_type: str = "control"
cpp_class: str = "CIOControl"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}
allowed_symbols: dict[str, str] = {
    "start": "CIOControl::CTRL_ALLOW_START",
    "stop": "CIOControl::CTRL_ALLOW_STOP",
}


def summary_dtype_name(obj: object) -> str:
    """Return the fixed ObjectID dtype name for ``control`` IOs."""
    del obj
    return "uint8"


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``control``."""
    return [
        ConfigField(
            name="targets",
            cpp_helper="CIOControl::cfgIdAllocObj",
            value_type="id_list",
        ),
        ConfigField(
            name="allowed",
            cpp_helper="CIOControl::cfgIdAllowed",
            value_type="allow_flags",
            enum_prefix="CIOControl::CTRL_ALLOW_",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit targets list + allowed bitmask cfg items."""
    encode_targets_and_allowed(
        ctx,
        targets_cfg=header_cfg_id(cpp_class, "cfgIdAllocObj"),
        allowed_cfg=header_cfg_id(cpp_class, "cfgIdAllowed"),
        allowed_bits=resolve_allowed_bits(cpp_class, "CTRL_ALLOW_"),
    )


def generate_cpp(
    macro_name: str, obj: IoObject, gctx: IoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a control IO object."""
    return emit_targets_and_allowed_cpp(
        macro_name,
        obj,
        cfg_alloc_helper="CIOControl::cfgIdAllocObj",
        cfg_allowed_helper="CIOControl::cfgIdAllowed",
        allowed_symbols=allowed_symbols,
        gctx=gctx,
    )
