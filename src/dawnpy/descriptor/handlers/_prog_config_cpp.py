# tools/dawnpy/src/dawnpy/descriptor/handlers/_prog_config_cpp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared C++ source emission for program config fields.

The C++ source-text config path is per-handler, symmetric with the binary
``encode_binary`` path: each program handler owns emission of its own
program-specific fields via an ``emit_config_field_cpp`` module hook. The
generic value-types shared by many programs (``id_single``, ``id_list``,
``uint32``, ...) live here as free functions and are dispatched by
:func:`emit_generic_config_field`, which every handler's default emission
loop falls back to.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.config_access import ConfigRwGrants
from dawnpy.descriptor.support.utils import resolve_reference

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.descriptor.definitions.type_info import ConfigField
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper


@dataclass
class ProgFieldCppCtx:
    """Ambient state a program config-field emitter needs.

    :ivar format_helper: Emits indented C++ source lines.
    :ivar rw_grants: Resolved ``(obj_id, field_name) -> rw`` write grants so
        rw-aware fields (``adjust``/``fusion`` params) emit the same rw flag
        the referencing config IO does.
    """

    format_helper: DescriptorFormatHelper
    rw_grants: ConfigRwGrants


def resolve_id(ref: Any) -> str | None:
    """Resolve a YAML anchor or string reference to an object ID."""
    if isinstance(ref, dict):
        return ref.get("id")
    if ref is not None:
        return str(ref)
    return None


def resolve_ids(refs: Any) -> list[str]:
    """Resolve a list of YAML references to object ID strings."""
    if not isinstance(refs, list):
        return []
    return [r for r in (resolve_id(ref) for ref in refs) if r]


def _emit_id_array_pairs(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    sources = resolve_ids(config.get("sources", obj.inputs))
    outputs = resolve_ids(config.get("outputs", obj.outputs))
    n = len(sources) + len(outputs)
    if len(sources) != len(outputs):
        raise ValueError(
            f"Program {obj.obj_id} has {len(sources)} sources and "
            f"{len(outputs)} outputs"
        )
    ctx.format_helper.append_line(lines, 2, f"{field_def.cpp_helper}({n}),")
    for src_id, output_id in zip(sources, outputs, strict=True):
        ctx.format_helper.append_line(lines, 3, f"{src_id.upper()},")
        ctx.format_helper.append_line(lines, 3, f"{output_id.upper()},")


def _emit_uint32(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    default = field_def.default
    value = config.get(field_def.name, default if default else 0)
    ctx.format_helper.append_line(lines, 2, f"{field_def.cpp_helper}(),")
    ctx.format_helper.append_line(lines, 3, f"{value},")


def _emit_uint32_list(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    values = config.get(field_def.name, [])
    n = len(values)
    ctx.format_helper.append_line(lines, 2, f"{field_def.cpp_helper}({n}),")
    for v in values:
        ctx.format_helper.append_line(lines, 3, f"{int(v)},")


def _emit_id_array(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    ctx.format_helper.append_line(lines, 2, f"{field_def.cpp_helper}(),")
    field_name = field_def.name
    # For standard inputs/outputs, they are in obj.inputs/obj.outputs
    if field_name == "inputs":
        ids = obj.inputs
    elif field_name == "outputs":
        ids = obj.outputs
    else:
        ids = obj.config.get(field_name, [])

    for obj_id in ids:
        ctx.format_helper.append_line(lines, 3, f"{obj_id.upper()},")


def _emit_id_list(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    ids = resolve_ids(config.get(field_def.name, []))
    ctx.format_helper.append_line(
        lines, 2, f"{field_def.cpp_helper}({len(ids)}),"
    )
    for obj_id in ids:
        ctx.format_helper.append_line(lines, 3, f"{obj_id.upper()},")


def _emit_id_single(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> None:
    field_name = field_def.name
    if field_name == "reset":
        obj_id = obj.reset
    else:
        obj_id = obj.config.get(field_name)
        if isinstance(obj_id, list):
            obj_id = obj_id[0] if obj_id else None
    obj_id = resolve_reference(obj_id) if obj_id else None

    ctx.format_helper.append_line(lines, 2, f"{field_def.cpp_helper}(),")
    if obj_id:
        ctx.format_helper.append_line(lines, 3, f"{obj_id.upper()},")
    else:
        ctx.format_helper.append_line(lines, 3, "0,")


#: Generic value-types shared across program handlers -> their emitter.
_GENERIC_EMITTERS = {
    "id_array_pairs": _emit_id_array_pairs,
    "uint32": _emit_uint32,
    "uint32_list": _emit_uint32_list,
    "id_array": _emit_id_array,
    "id_list": _emit_id_list,
    "id_single": _emit_id_single,
}


def emit_generic_config_field(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> bool:
    """Emit one generic config field; return whether the type was generic.

    Returns ``False`` for program-specific value-types (a handler's own
    ``emit_config_field_cpp`` hook owns those).
    """
    emitter = _GENERIC_EMITTERS.get(field_def.value_type)
    if emitter is None:
        return False
    emitter(lines, field_def, obj, config, ctx)
    return True


#: A handler's program-specific per-field hook, or ``None`` for a program type
#: with config fields but no handler module (e.g. OOT types using only the
#: generic value-types).
ConfigFieldHook = Callable[
    [
        list[str],
        "ConfigField",
        "ProgramObject",
        dict[str, Any],
        ProgFieldCppCtx,
    ],
    bool,
]


def emit_config_fields_cpp(
    hook: ConfigFieldHook | None,
    owner: str,
    lines: list[str],
    obj: ProgramObject,
    config: dict[str, Any],
    field_defs: list[ConfigField],
    ctx: ProgFieldCppCtx,
) -> None:
    """Emit every type-specific config field, hook-first then generic.

    Each field is offered to ``hook`` (a handler's ``emit_config_field_cpp``)
    when present; anything it declines falls back to the shared generic
    emitters. An unhandled value-type is a bug and raises rather than
    silently emitting nothing. ``owner`` labels the error.
    """
    for field_def in field_defs:
        if hook is not None and hook(lines, field_def, obj, config, ctx):
            continue
        if not emit_generic_config_field(lines, field_def, obj, config, ctx):
            raise ValueError(
                f"{owner}: no C++ emitter for config field "
                f"'{field_def.name}' (value_type '{field_def.value_type}')"
            )
