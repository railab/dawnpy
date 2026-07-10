# tools/dawnpy/src/dawnpy/descriptor/handlers/_proto_nxscope_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared iobind2 encoder for the three NXScope handlers.

Each NXScope variant (dummy/serial/udp) emits the same iobind2 block
plus its variant-specific fields in its own handler.
"""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    flex_refs_to_objid_words,
)
from dawnpy.descriptor.handlers._allocation import bindings_allocation_rows
from dawnpy.descriptor.support.utils import resolve_flexible_reference


def encode_nxscope_iobind2(ctx: _ProtoSerializeContext) -> None:
    """Encode channel-name bindings and explicit unnamed bindings."""
    iobind2_words: list[int] = []
    raw_iobind2 = ctx.config.get("iobind2", [])
    if isinstance(raw_iobind2, list):
        for entry in raw_iobind2:
            io_id = resolve_flexible_reference(entry)
            if not io_id or io_id not in ctx.obj_ids:
                continue
            name = (
                str(entry.get("name", "")) if isinstance(entry, dict) else ""
            )
            iobind2_words.append(ctx.obj_ids[io_id])
            iobind2_words.extend(
                ctx.fmt.pack_fixed_string(
                    name, ctx.fixed_bytes("nxscope_name", 12)
                )
            )
    if iobind2_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(iobind2_words),
                ctx.cfg_id("nxscope_iobind2", 2),
            ),
            iobind2_words,
        )

    explicit_bindings = ctx.config.get("bindings", [])
    if isinstance(explicit_bindings, list):
        bindings_words = flex_refs_to_objid_words(
            explicit_bindings, ctx.obj_ids
        )
    else:
        bindings_words = []
    if bindings_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(bindings_words),
                ctx.cfg_id("nxscope_iobind", 1),
            ),
            bindings_words,
        )


def nxscope_emit_config_field_cpp(
    lines: list[str], field: ConfigField, value: Any, ctx: Any
) -> bool:
    """Emit the ``nxscope_iobind2`` C++ config field; return whether handled.

    This is the per-handler C++ source hook counterpart to
    :func:`encode_nxscope_iobind2` (the binary path). ``ctx`` is the
    protocol generator context (provides ``format_helper``).
    """
    if field.value_type != "nxscope_iobind2":
        return False

    entries = value if isinstance(value, list) else []
    resolved_entries: list[tuple[str, str]] = []
    for entry in entries:
        if isinstance(entry, str):
            name = ""
        elif isinstance(entry, dict):
            name = entry.get("name", "")
        else:
            continue
        resolved_id = resolve_flexible_reference(entry)
        if resolved_id:
            resolved_entries.append((resolved_id, name))

    ctx.format_helper.append_line(
        lines, 2, f"{field.cpp_helper}({len(resolved_entries)}),"
    )
    fixed_bytes = int(field.string_fixed_bytes or 12)
    for obj_id, name in resolved_entries:
        ctx.format_helper.append_line(lines, 3, f"{obj_id.upper()},")
        ctx.format_helper.append_words(
            lines,
            ctx.format_helper.pack_fixed_string(str(name), fixed_bytes),
            level=3,
        )
    return True


def iobind2_field(cpp_class: str) -> ConfigField:
    """Return the iobind2 schema row, bound to the variant's cpp_class."""
    return ConfigField(
        name="iobind2",
        cpp_helper=f"{cpp_class}::cfgIdIOBind2",
        value_type="nxscope_iobind2",
        string_fixed_bytes=12,
    )


def resolve_nxscope_bindings(
    bindings: list[str], config: dict[str, object]
) -> list[str]:
    """Resolve bindings from ``iobind2`` entries when none are declared."""
    if bindings:
        return bindings
    iobind2 = config.get("iobind2")
    if not isinstance(iobind2, list):
        return bindings
    resolved: list[str] = []
    for entry in iobind2:
        obj_id = resolve_flexible_reference(entry)
        if obj_id:
            resolved.append(obj_id)
    return resolved


def nxscope_allocation_rows(
    config: dict[str, object],
    bindings: list[str],
) -> list[list[str]]:
    """Return allocation rows for NXScope channel bindings."""
    names_count = 0
    resolved_bindings = bindings
    iobind2 = config.get("iobind2", None)
    if isinstance(iobind2, list):
        names_count = len(iobind2)
        iobind2_ids: list[str] = []
        for entry in iobind2:
            resolved = resolve_flexible_reference(entry)
            if resolved:
                iobind2_ids.append(resolved)
        if iobind2_ids:
            resolved_bindings = iobind2_ids
    else:
        names = config.get("names", [])
        names_count = len(names) if isinstance(names, list) else 0
    details_parts = [f"names={names_count}"]
    if "path" in config:
        details_parts.append(f"path={config.get('path', 'n/a')}")
    if "baudrate" in config:
        details_parts.append(f"baudrate={config.get('baudrate', 'n/a')}")
    return bindings_allocation_rows(
        resolved_bindings, details=", ".join(details_parts)
    )
