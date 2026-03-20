# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_can.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``can`` PROTO type.

Owns every per-type concern in one place:

* the cpp_class binding (yaml-token ``can`` -> ``CProtoCan``)
* the user-facing YAML config schema (incl. nested ``objects`` element
  fields with the ``CProtoCan::CAN_TYPE_*`` enum hydrated at registry
  build time)
* the binary serializer (per-can-object iobind packing with
  type/can_id_start headers)
* the C++ source generator (per-can-object iobind block + cfgIdNodeid)

``uses_standard_bindings`` is False because CAN does its own encoding
under ``cfgIdIOBind``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
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
    fmt_bindings,
    fmt_hex,
    fmt_value,
    try_parse_int,
)
from dawnpy.descriptor.support.mapping import resolve_objects_with_bindings
from dawnpy.descriptor.support.utils import resolve_references

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext


yaml_type: str = "can"
cpp_class: str = "CProtoCan"
nuttx_requirements: tuple[str, ...] = ("CONFIG_CAN",)
uses_standard_bindings: bool = False
multi_device: bool = True
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "can_iobind": ("CProtoCan", "cfgIdIOBind"),
    "can_devno": ("CProtoCan", "cfgIdDevno"),
    "can_node_id": ("CProtoCan", "cfgIdNodeid"),
}
dtype_names: dict[str, str] = {"int": "uint32"}
enum_value_maps: dict[str, tuple[str, str]] = {
    "can_type": ("CProtoCan", "CAN_TYPE_"),
}
defaults: dict[str, int] = {"can_id_start": 0}
fixed_string_bytes: dict[str, int] = {}


def _is_list_of_dicts(value: object) -> bool:
    """Return True when value is a list of mappings."""
    if not isinstance(value, list):
        return False
    return all(isinstance(item, dict) for item in value)


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return CAN allocation summary rows."""
    rows: list[list[str]] = []
    node_id = try_parse_int(proto.config.get("node_id", 0)) or 0
    for idx, obj in enumerate(resolve_objects_with_bindings(proto.config)):
        method = str(obj.get("type", "")).lower()
        can_id_start_raw = obj.get("can_id_start", 0)
        can_id_start = try_parse_int(can_id_start_raw)
        resolved = obj.get("bindings_resolved", [])
        resolved_count = len(resolved)
        item_notes: list[str] = []
        if can_id_start is None:
            can_id_start = 0
            item_notes.append(f"can_id_start={can_id_start_raw} assumed 0")

        if method in ("read_indexed", "write_indexed"):
            has_group = resolved_count > 0
            reserved = 1 if has_group else 0
        else:
            reserved = resolved_count

        start: int | None = None
        end: int | None = None
        if reserved > 0:
            start = node_id + can_id_start
            end = (
                start
                if method in ("read_indexed", "write_indexed")
                else (start + reserved - 1)
            )

        note_suffix = ""
        if item_notes:
            note_suffix = f", note={' | '.join(item_notes)}"

        details = (
            f"can_id_start={fmt_value(can_id_start_raw, hex_format=True)}, "
            f"bound={resolved_count}, "
            f"ios={fmt_bindings(resolved)}{note_suffix}"
        )
        rows.append(
            [
                str(idx),
                method or "n/a",
                fmt_hex(start),
                fmt_hex(end),
                str(reserved),
                details,
            ]
        )
    return rows


def allocation_notes(proto: Any) -> list[str]:
    """Return CAN allocation report notes."""
    node_id_raw = proto.config.get("node_id")
    if isinstance(node_id_raw, str) and try_parse_int(node_id_raw) is None:
        return [f"  node={node_id_raw} (assumed 0 for validation)"]
    return []


def validate_object(obj: Any) -> list[str]:
    """Ensure CAN-specific configuration fragments use mappings."""
    objects = obj.config.get("objects")
    if objects is not None and not _is_list_of_dicts(objects):
        return ["config.objects must be a list of mappings"]
    return []


def resolve_bindings(bindings: list[str], config: dict[str, Any]) -> list[str]:
    """Derive CAN protocol bindings from mapped objects when omitted."""
    if "objects" not in config:
        return bindings
    objects = config.get("objects", [])
    if not isinstance(objects, list):
        return bindings
    resolved: list[str] = []
    for obj in objects:
        if isinstance(obj, dict):
            resolved.extend(resolve_references(obj.get("bindings", [])))
    return resolved


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``can``."""
    return [
        ConfigField(
            name="node_id",
            cpp_helper="CProtoCan::cfgIdNodeid",
            value_type="int",
            value_format="hex",
        ),
        ConfigField(
            name="objects",
            nested=True,
            array=True,
            element_fields=[
                ConfigField(
                    name="type",
                    value_type="enum",
                    enum_prefix="CProtoCan::CAN_TYPE_",
                    default="PUSH",
                ),
                ConfigField(
                    name="can_id_start", value_type="int", value_format="hex"
                ),
                ConfigField(name="count", value_type="computed"),
                ConfigField(
                    name="bindings",
                    cpp_helper="CProtoCan::cfgIdIOBind",
                    value_type="id_array",
                    size_calculation="3 + count",
                ),
            ],
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Encode CAN binary block into ``ctx.items``."""
    if "device" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("int"),
                True,
                1,
                ctx.cfg_id("can_devno", 2),
            ),
            [int(ctx.config["device"])],
        )
    if "node_id" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("int"),
                True,
                1,
                ctx.cfg_id("can_node_id", 3),
            ),
            [int(ctx.config["node_id"])],
        )

    iobind_words: list[int] = []
    can_objects = ctx.config.get("objects", [])
    if isinstance(can_objects, list):
        default_type_key = default_enum_key(ctx.enum_map("can_type"), "push")
        default_type_val = int(
            ctx.enum_map("can_type").get(default_type_key, 0)
        )
        default_id_start = int(ctx.default("can_id_start", 0))
        for obj_cfg in can_objects:
            if not isinstance(obj_cfg, dict):
                continue
            type_name = str(obj_cfg.get("type", default_type_key))
            type_val = int(
                ctx.enum_map("can_type").get(type_name, default_type_val)
            )
            id_start = int(obj_cfg.get("can_id_start", default_id_start))
            bindings_words = flex_refs_to_objid_words(
                obj_cfg.get("bindings", []), ctx.obj_ids
            )
            iobind_words.extend([type_val, id_start, len(bindings_words)])
            iobind_words.extend(bindings_words)
    if iobind_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(iobind_words),
                ctx.cfg_id("can_iobind", 1),
            ),
            iobind_words,
        )


def generate_cpp(  # noqa: C901
    macro_name: str, obj: ProtocolObject, gctx: ProtoGeneratorContext
) -> list[str]:
    """Emit the per-instance C++ source lines for a CAN protocol object."""
    lines: list[str] = []
    config = obj.config
    fmt = gctx.format_helper

    # Pull the schema for `can` (handlers own their own schema, so the
    # config_loader returns the merged result already).
    can_schema = gctx.config_loader.get_proto_config_schema("can")
    if can_schema is None:  # pragma: no cover
        fmt.append_line(lines, 1, f"{macro_name}, 0,")
        return lines
    can_fields = can_schema.fields

    config_count = 0
    for field in can_fields:
        if field.name in config:
            if field.array:
                config_count += len(config[field.name])
            else:
                config_count += 1

    fmt.append_line(lines, 1, f"{macro_name}, {config_count},")

    for field in can_fields:
        if field.name not in config:
            continue
        if field.nested and field.array:
            for item in config[field.name]:
                lines.extend(
                    _generate_can_object(item, field.element_fields, gctx)
                )
                lines.append("")
        else:
            if not field.cpp_helper:
                continue  # pragma: no cover
            value = config[field.name]
            fmt.append_line(lines, 2, f"{field.cpp_helper}(),")
            if field.value_format == "hex":
                rendered = fmt.format_numeric(value, hex_format=True)
            else:
                rendered = fmt.format_numeric(value)
            fmt.append_line(lines, 3, f"{rendered},")
            lines.append("")

    return lines


def _generate_can_object(  # noqa: C901
    obj_config: dict[str, Any],
    element_fields: list[ConfigField],
    gctx: ProtoGeneratorContext,
) -> list[str]:
    """Emit a single CAN object configuration block."""
    lines: list[str] = []
    fmt = gctx.format_helper
    raw_bindings = obj_config.get("bindings", [])
    bindings = gctx.resolve_references(raw_bindings)
    count = len(bindings)

    bindings_field = next(
        (f for f in element_fields if f.name == "bindings"), None
    )
    if bindings_field is None:
        return lines
    cpp_helper = bindings_field.cpp_helper
    size_calc = bindings_field.size_calculation
    data_size = eval(size_calc, {"count": count}) if size_calc else count

    fmt.append_line(lines, 2, f"{cpp_helper}({data_size}),")
    for field in element_fields:
        if field.name == "count":
            fmt.append_line(lines, 3, f"{count},")
        elif field.name == "bindings":
            for b in bindings:
                fmt.append_line(lines, 3, f"{b.upper()},")
        elif field.name in obj_config:
            value = obj_config[field.name]
            if field.value_type == "enum":
                enum_const = field.enum_values.get(value, field.default)
                fmt.append_line(lines, 3, f"{field.enum_prefix}{enum_const},")
            elif field.value_type == "int":
                if field.value_format == "hex":
                    rendered = fmt.format_numeric(value, hex_format=True)
                else:
                    rendered = fmt.format_numeric(value)
                fmt.append_line(lines, 3, f"{rendered},")
            else:
                rendered = fmt.format_numeric(value)
                fmt.append_line(lines, 3, f"{rendered},")
    return lines
