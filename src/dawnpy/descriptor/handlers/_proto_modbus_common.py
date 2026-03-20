# tools/dawnpy/src/dawnpy/descriptor/handlers/_proto_modbus_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared register-block encoder for the Modbus RTU + TCP handlers.

Owns BOTH the binary register-block encoder and the C++ register-block
emitter so the rtu / tcp handler files stay tiny.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from dawnpy.descriptor.encoding.proto_runtime import (
    _ProtoSerializeContext,
    default_enum_key,
)
from dawnpy.descriptor.encoding.words import (
    append_cfg_item,
    cfg_id,
    flex_refs_to_objid_words,
)
from dawnpy.descriptor.handlers._allocation import (
    bindings_allocation_rows,
    fmt_bindings,
    fmt_value,
    try_parse_int,
)
from dawnpy.descriptor.support.utils import resolve_references

if TYPE_CHECKING:
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext


class _RegisterConfig(TypedDict):
    """Resolved single Modbus register block."""

    reg_type: str
    config: int
    start: int
    bindings: list[str]


def encode_modbus_registers(
    ctx: _ProtoSerializeContext,
    iobind_key: str,
    iobind_default: int,
) -> None:
    """Encode the per-register-group iobind block (RTU + TCP share this)."""
    register_words: list[int] = []
    registers = ctx.config.get("registers", [])
    if isinstance(registers, list):
        default_reg_type = default_enum_key(
            ctx.enum_map("modbus_type"), "holding"
        )
        default_reg_type_val = int(
            ctx.enum_map("modbus_type").get(default_reg_type, 6)
        )
        default_config = int(ctx.default("modbus_config", 0))
        default_start = int(ctx.default("modbus_start", 0))
        for reg_cfg in registers:
            if not isinstance(reg_cfg, dict):
                continue
            reg_type_name = str(reg_cfg.get("type", default_reg_type))
            reg_type_val = int(
                ctx.enum_map("modbus_type").get(
                    reg_type_name, default_reg_type_val
                )
            )
            reg_config = int(reg_cfg.get("config", default_config))
            start = int(reg_cfg.get("start", default_start))
            reg_bindings_words = flex_refs_to_objid_words(
                reg_cfg.get("bindings", []), ctx.obj_ids
            )
            register_words.extend(
                [reg_type_val, reg_config, start, len(reg_bindings_words)]
            )
            register_words.extend(reg_bindings_words)

    if register_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(register_words),
                ctx.cfg_id(iobind_key, iobind_default),
            ),
            register_words,
        )


def modbus_allocation_rows(proto: Any) -> list[list[str]]:
    """Return Modbus register allocation rows."""
    rows: list[list[str]] = []
    for idx, reg in enumerate(proto.config.get("registers", [])):
        reg_type = str(reg.get("type", ""))
        start_raw = reg.get("start", 0)
        start = try_parse_int(start_raw)
        declared_raw = try_parse_int(reg.get("count", 0))
        declared = max(0, declared_raw) if declared_raw is not None else 0
        resolved = resolve_references(reg.get("bindings", []))
        size = (
            max(declared, len(resolved))
            if declared is not None
            else len(resolved)
        )
        note_parts: list[str] = []
        if start is None:
            start = 0
            note_parts.append(f"start={start_raw} assumed 0")
        if declared_raw is None:
            note_parts.append(f"count={reg.get('count', 0)} assumed 0")
        end = start + size - 1 if size > 0 else None
        note_suffix = ""
        if note_parts:
            note_suffix = f", note={' | '.join(note_parts)}"
        rows.append(
            [
                str(idx),
                reg_type or "n/a",
                str(start),
                str(end) if end is not None else "n/a",
                str(size if size > 0 else 0),
                (
                    f"start={fmt_value(start_raw)}, "
                    f"config={fmt_value(reg.get('config', 0))}, "
                    f"ios={fmt_bindings(resolved)}{note_suffix}"
                ),
            ]
        )
    if rows:
        return rows
    return bindings_allocation_rows(proto.bindings, details="registers=0")


def resolve_modbus_bindings(
    bindings: list[str], config: dict[str, Any]
) -> list[str]:
    """Derive protocol bindings from register blocks."""
    if "registers" not in config:
        return bindings
    resolved: list[str] = []
    registers = config.get("registers", [])
    if not isinstance(registers, list):
        return bindings
    for reg in registers:
        if isinstance(reg, dict):
            resolved.extend(resolve_references(reg.get("bindings", [])))
    return resolved


def get_register_type_map(
    config_loader: Any, proto_type: str = "modbus_rtu"
) -> dict[str, str]:
    """Return register type -> C++ constant mapping for one transport."""
    res: dict[str, str] = config_loader.get_proto_nested_enum_map(
        proto_type, "registers", "type"
    )
    if not res and proto_type != "modbus_rtu":
        res = config_loader.get_proto_nested_enum_map(
            "modbus_rtu", "registers", "type"
        )
    return res


def get_register_type_prefix(
    config_loader: Any, proto_type: str = "modbus_rtu"
) -> str:
    """Return the C++ prefix for Modbus register types."""
    prefix = config_loader.get_proto_nested_enum_prefix(
        proto_type, "registers", "type"
    )
    if not prefix and proto_type != "modbus_rtu":
        prefix = config_loader.get_proto_nested_enum_prefix(
            "modbus_rtu", "registers", "type"
        )
    return str(prefix)


def emit_modbus_registers_cpp(
    lines: list[str],
    registers: list[Any],
    cpp_class: str,
    proto_type: str,
    gctx: ProtoGeneratorContext,
) -> None:
    """Emit Modbus register blocks (shared between RTU + TCP C++ output)."""
    total_size = 0
    resolved: list[_RegisterConfig] = []
    for reg in registers:
        reg_type = str(reg.get("type", "holding")).lower()
        reg_config = int(reg.get("config", 0))
        start = int(reg.get("start", 0))
        bindings = gctx.resolve_references(reg.get("bindings", []))
        total_size += 4 + len(bindings)
        resolved.append(
            {
                "reg_type": reg_type,
                "config": reg_config,
                "start": start,
                "bindings": bindings,
            }
        )

    gctx.format_helper.append_line(
        lines, 2, f"{cpp_class}::cfgIdIOBind({total_size}),"
    )
    prefix = get_register_type_prefix(gctx.config_loader, proto_type)
    type_map = get_register_type_map(gctx.config_loader, proto_type)
    for reg in resolved:
        type_val = type_map.get(reg["reg_type"], "0")
        if type_val != "0":
            type_val = f"{prefix}{type_val}"
        gctx.format_helper.append_line(
            lines,
            3,
            f"{type_val}, {reg['config']}, "
            f"{reg['start']}, {len(reg['bindings'])},",
        )
        for binding_id in reg["bindings"]:
            gctx.format_helper.append_line(lines, 4, f"{binding_id.upper()},")
