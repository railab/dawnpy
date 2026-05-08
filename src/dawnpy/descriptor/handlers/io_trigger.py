# tools/dawnpy/src/dawnpy/descriptor/handlers/io_trigger.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``trigger`` IO type."""

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


yaml_type: str = "trigger"
cpp_class: str = "CIOTrigger"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}
allowed_symbols: dict[str, str] = {
    "reset": "CIOTrigger::TRIG_ALLOW_RESET",
    "trigger1": "CIOTrigger::TRIG_ALLOW_TRIGGER1",
    "trigger2": "CIOTrigger::TRIG_ALLOW_TRIGGER2",
    "trigger3": "CIOTrigger::TRIG_ALLOW_TRIGGER3",
}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``trigger``."""
    return [
        ConfigField(
            name="targets",
            cpp_helper="CIOTrigger::cfgIdAllocObj",
            value_type="id_list",
        ),
        ConfigField(
            name="allowed",
            cpp_helper="CIOTrigger::cfgIdAllowed",
            value_type="allow_flags",
            enum_prefix="CIOTrigger::TRIG_ALLOW_",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit targets list + allowed bitmask cfg items."""
    encode_targets_and_allowed(
        ctx,
        targets_cfg=header_cfg_id(cpp_class, "cfgIdAllocObj"),
        allowed_cfg=header_cfg_id(cpp_class, "cfgIdAllowed"),
        allowed_bits=resolve_allowed_bits(cpp_class, "TRIG_ALLOW_"),
    )


def generate_cpp(
    macro_name: str, obj: IoObject, gctx: IoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a trigger IO object."""
    return emit_targets_and_allowed_cpp(
        macro_name,
        obj,
        cfg_alloc_helper="CIOTrigger::cfgIdAllocObj",
        cfg_allowed_helper="CIOTrigger::cfgIdAllowed",
        allowed_symbols=allowed_symbols,
        gctx=gctx,
    )
