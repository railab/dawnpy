# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_adjust.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``adjust`` PROG type.

Owns every per-type concern in one place:

* ``cpp_class`` binding (yaml-token ``adjust`` -> ``CProgAdjust``)
* user-facing YAML config schema (``params`` field)
* C++ source emission for the ``adjust_params`` value-type
* binary serializer block (cfgParams -> [offset, scale])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.scalar import (
    encode_scalar_words,
    format_scalar_cpp,
)
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_config_cpp import ProgFieldCppCtx
from dawnpy.headerdefs.bundle import header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder


yaml_type: str = "adjust"
cpp_class: str = "CProgAdjust"
binding_rule: tuple[int, int] = (1, 1)


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``adjust``."""
    return [
        ConfigField(
            name="params",
            cpp_helper="CProgAdjust::cfgParams",
            value_type="adjust_params",
            # cfgParams(bool rw): a writable config IO targeting these params
            # makes them runtime-writable (CProgAdjust::onSetObjConfig).
            params=["rw"],
        ),
    ]


def emit_iobind_cpp(
    lines: list[str],
    obj: ProgramObject,
    total_ids: int,
    format_helper: Any,
    cpp_class_name: str,
) -> bool:
    """Emit the single source/output binding used by ``adjust``."""
    del total_ids, cpp_class_name
    if not obj.inputs or not obj.outputs:
        return False

    format_helper.append_line(lines, 2, "CProgAdjust::cfgIdIOBind(),")
    format_helper.append_line(lines, 3, f"{obj.inputs[0].upper()},")
    format_helper.append_line(lines, 3, f"{obj.outputs[0].upper()},")
    return True


def emit_config_field_cpp(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> bool:
    """Emit the ``adjust`` params block; return whether handled."""
    if field_def.value_type != "adjust_params":
        return False

    params = config.get(field_def.name, {})
    if not isinstance(params, dict):
        params = {}

    # rw is true only when a writable config IO targets these params; the
    # config IO's reference emits the same cfgParams(rw) so the runtime
    # cfg-id lookup matches.
    rw = config_field_is_rw(ctx.rw_grants, obj.obj_id, field_def.name)
    rw_arg = "true" if rw else ""
    ctx.format_helper.append_line(
        lines, 2, f"{field_def.cpp_helper}({rw_arg}),"
    )
    for raw in (params.get("offset", 0), params.get("scale", 1)):
        for literal in format_scalar_cpp(raw, obj.dtype):
            ctx.format_helper.append_line(lines, 3, f"{literal},")
    return True


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: ProgramObject,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append the ``adjust`` cfg block to ``items``.

    The dispatcher passes the resolved prog class enum (``prog_cls``)
    and the descriptor decoder; everything else specific to ``adjust``
    lives in this function.
    """
    del decoder

    if obj.inputs and obj.outputs:
        src_id = obj_ids.get(obj.inputs[0])
        dst_id = obj_ids.get(obj.outputs[0])
        if src_id is not None and dst_id is not None:
            cfg_iobind = header_cfg_id(cpp_class, "cfgIdIOBind")
            items.append(
                (
                    cfg_id(3, prog_cls, 0, False, 2, cfg_iobind),
                    [src_id, dst_id],
                )
            )

    config = obj.config if isinstance(obj.config, dict) else {}
    params = config.get("params", {})
    if not isinstance(params, dict):
        return  # pragma: no cover
    words = encode_scalar_words(params.get("offset", 0), obj.dtype)
    words += encode_scalar_words(params.get("scale", 1), obj.dtype)
    cfg = header_cfg_id(cpp_class, "cfgParams")
    items.append((cfg_id(3, prog_cls, 0, False, len(words), cfg), words))
