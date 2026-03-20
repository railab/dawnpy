# tools/dawnpy/src/dawnpy/descriptor/handlers/_io_targets_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared targets+allowed encoder for control / trigger IO handlers.

Owns BOTH the binary encoder and the C++ source emitter for the
common targets-list + allowed-bitmask shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    mask_from_allowed,
    named_refs_to_objid_words,
)

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import IoObject
    from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext


def encode_targets_and_allowed(
    ctx: _IOSerializeContext,
    targets_cfg: int,
    allowed_cfg: int,
    allowed_bits: dict[str, int],
) -> None:
    """Emit the targets list + allowed bitmask cfg items."""
    targets = ctx.config.get("targets", [])
    if isinstance(targets, list) and targets:
        target_ids = named_refs_to_objid_words(targets, ctx.obj_ids)
        append_cfg_item(
            ctx.items,
            cfg_id(1, ctx.io_cls, 0, False, len(target_ids), targets_cfg),
            target_ids,
        )

    mask = mask_from_allowed(ctx.config.get("allowed", []), allowed_bits)
    if mask is not None:
        append_cfg_item(
            ctx.items,
            cfg_id(1, ctx.io_cls, 0, False, 1, allowed_cfg),
            [mask],
        )


def emit_targets_and_allowed_cpp(
    macro_name: str,
    obj: IoObject,
    cfg_alloc_helper: str,
    cfg_allowed_helper: str,
    allowed_symbols: dict[str, str],
    gctx: IoGeneratorContext,
) -> list[str]:
    """Emit per-instance C++ source lines for control/trigger IO."""
    lines: list[str] = []
    fmt = gctx.format_helper
    config = obj.config
    targets = config.get("targets", [])
    allowed_list = config.get("allowed", [])

    config_count = (1 if targets else 0) + (1 if allowed_list else 0)
    fmt.append_line(lines, 1, f"{macro_name}, {config_count},")

    if targets:
        n = len(targets)
        fmt.append_line(lines, 2, f"{cfg_alloc_helper}({n}),")
        for target_id in targets:
            fmt.append_line(lines, 3, f"{target_id.upper()},")

    if allowed_list:
        flags = [
            allowed_symbols[a] for a in allowed_list if a in allowed_symbols
        ]
        bitmask = " | ".join(flags) if flags else "0"
        fmt.append_line(lines, 2, f"{cfg_allowed_helper}(),")
        fmt.append_line(lines, 3, f"{bitmask},")

    return lines
