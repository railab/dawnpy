# tools/dawnpy/src/dawnpy/descriptor/handlers/_io_dummy_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared init-value packing for the two CIODummy* handlers."""

from typing import Any

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.scalar import encode_scalar_words
from dawnpy.descriptor.encoding.words import cfg_id


def _pack_init_value(value: Any, dtype_name: str) -> list[int]:
    """Pack a scalar/list value into little-endian uint32 words."""
    values = value if isinstance(value, list) else [value]
    out: list[int] = []
    for item in values:
        out.extend(encode_scalar_words(item, dtype_name))
    return out


def encode_dummy_block(
    ctx: _IOSerializeContext,
    dim_cfg: int,
    init_cfg: int,
) -> None:
    """Emit the shared dim/init_value cfg items for both dummy variants."""
    config = ctx.config
    if "dim" in config:
        ctx.items.append(
            (
                cfg_id(1, ctx.io_cls, 7, False, 1, dim_cfg),
                [int(config["dim"])],
            )
        )
    if "init_value" in config:
        words = _pack_init_value(config["init_value"], ctx.dtype_name)
        rw = config_field_is_rw(
            ctx.config_rw_grants, ctx.obj.obj_id, "init_value"
        )
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    ctx.dtype,
                    rw,
                    len(words),
                    init_cfg,
                ),
                words,
            )
        )
