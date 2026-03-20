# tools/dawnpy/src/dawnpy/descriptor/capabilities_blob.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Dawn capabilities IO blob: layout constants + decoder + report builder.

The CLI command ``commands/cmd_desc_decode_caps.py`` is a thin click
command that calls :func:`build_capabilities_report` here. All blob
parsing, layout constants and report formatting live in this module.
"""

import struct
from typing import Any

import click

from dawnpy.descriptor.encoding.packager import bitmap_enabled_ids
from dawnpy.descriptor.encoding.words import enabled_flag_names
from dawnpy.objectid import ObjectIdDecoder

# Capabilities IO blob layout. Mirrors dawn/include/dawn/io/capabilities.hxx
# and dawn/src/io/capabilities.cxx - keep in sync if either side changes.
_CAPS_VERSION: int = 2
_CAPS_LAYOUT_ID: int = 0
_CAPS_TOTAL_SIZE: int = 512
_CAPS_HEADER_SIZE: int = 8
_CAPS_PAYLOAD_SIZE: int = 504
_CAPS_SECTIONS: tuple[tuple[str, int, int], ...] = (
    ("io_bitmap", 0, 64),
    ("prog_bitmap", 64, 64),
    ("proto_bitmap", 128, 64),
    ("meta", 192, 312),
)
_CAPS_META_WORDS: tuple[tuple[str, int], ...] = (
    ("dtype_bits_lo", 0),
    ("dtype_bits_hi", 1),
    ("io_flags_lo", 2),
    ("io_flags_hi", 3),
    ("build_flags_lo", 4),
    ("build_flags_hi", 5),
    ("desc_slots", 6),
    ("desc_slot_size", 7),
    ("max_io_cls", 8),
    ("max_prog_cls", 9),
    ("max_proto_cls", 10),
)
_CAPS_IO_FLAGS: tuple[dict[str, Any], ...] = ({"bit": 0, "name": "timestamp"},)
_CAPS_BUILD_FLAGS: tuple[dict[str, Any], ...] = (
    {"bit": 0, "name": "os_nuttx"},
    {"bit": 1, "name": "filesystem"},
    {"bit": 2, "name": "io_notify"},
    {"bit": 3, "name": "io_has_stats"},
    {"bit": 4, "name": "object_has_name"},
    {"bit": 5, "name": "desc_dynamic"},
)


def _validate_enabled_ids(
    section_name: str, enabled_ids: list[int], max_cls: int
) -> None:
    """Validate enabled class IDs against the advertised class limit."""
    invalid_ids = [cls_id for cls_id in enabled_ids if cls_id > max_cls]
    if invalid_ids:
        ids = ", ".join(str(cls_id) for cls_id in invalid_ids)
        raise click.ClickException(
            f"Capabilities {section_name} bitmap contains class IDs "
            f"above advertised max {max_cls}: {ids}"
        )


def decode_capabilities_blob(  # noqa: C901
    blob: bytes,
) -> dict[str, Any]:
    """Decode a Dawn capabilities IO blob into a flat dict of fields."""
    header_size = _CAPS_HEADER_SIZE
    payload_size = _CAPS_PAYLOAD_SIZE
    expected_version = _CAPS_VERSION
    expected_layout_id = _CAPS_LAYOUT_ID

    if len(blob) < header_size:
        raise click.ClickException("Capabilities blob too short (<8 bytes)")

    version = blob[0]
    layout_id = blob[1]
    payload_len = int.from_bytes(blob[2:4], "little")
    reserved = int.from_bytes(blob[4:8], "little")
    payload = blob[header_size:]

    if version != expected_version:
        raise click.ClickException(
            f"Unsupported capabilities blob version: {version}"
        )
    if layout_id != expected_layout_id:
        raise click.ClickException(
            f"Unsupported capabilities layout: {layout_id}"
        )
    if payload_len != payload_size:
        raise click.ClickException(
            f"Unsupported capabilities payload length: {payload_len}"
        )
    if reserved != 0:
        raise click.ClickException(
            f"Capabilities header reserved field must be 0, got {reserved}"
        )
    if len(payload) != payload_len:
        raise click.ClickException(
            f"Capabilities payload size mismatch: hdr={payload_len}, "
            f"actual={len(payload)}"
        )

    section_map: dict[str, bytes] = {}
    for name, offset, size in _CAPS_SECTIONS:
        section_map[name] = payload[offset : offset + size]

    meta_section = section_map.get("meta", b"")
    meta_map: dict[str, int] = {}
    for name, index in _CAPS_META_WORDS:
        meta_map[name] = struct.unpack_from("<I", meta_section, index * 4)[0]

    io_enabled = bitmap_enabled_ids(section_map.get("io_bitmap", b""))
    prog_enabled = bitmap_enabled_ids(section_map.get("prog_bitmap", b""))
    proto_enabled = bitmap_enabled_ids(section_map.get("proto_bitmap", b""))
    max_io_cls = meta_map.get("max_io_cls", 0)
    max_prog_cls = meta_map.get("max_prog_cls", 0)
    max_proto_cls = meta_map.get("max_proto_cls", 0)

    _validate_enabled_ids("IO", io_enabled, max_io_cls)
    _validate_enabled_ids("PROG", prog_enabled, max_prog_cls)
    _validate_enabled_ids("PROTO", proto_enabled, max_proto_cls)

    return {
        "version": version,
        "layout_id": layout_id,
        "payload_len": payload_len,
        "io_enabled": io_enabled,
        "prog_enabled": prog_enabled,
        "proto_enabled": proto_enabled,
        "dtype_bits_lo": meta_map.get("dtype_bits_lo", 0),
        "dtype_bits_hi": meta_map.get("dtype_bits_hi", 0),
        "io_flags_lo": meta_map.get("io_flags_lo", 0),
        "io_flags_hi": meta_map.get("io_flags_hi", 0),
        "build_flags_lo": meta_map.get("build_flags_lo", 0),
        "build_flags_hi": meta_map.get("build_flags_hi", 0),
        "desc_slots": meta_map.get("desc_slots", 0),
        "desc_slot_size": meta_map.get("desc_slot_size", 0),
        "max_io_cls": max_io_cls,
        "max_prog_cls": max_prog_cls,
        "max_proto_cls": max_proto_cls,
    }


def _format_capabilities_list(
    enabled_ids: list[int], class_map: dict[int, str]
) -> list[str]:
    """Format enabled class IDs with class names."""
    return [
        f"{cls_id}: {class_map.get(cls_id, 'unknown')}"
        for cls_id in enabled_ids
    ]


def build_capabilities_report(blob: bytes) -> list[str]:
    """Decode ``blob`` and return human-readable report lines."""
    decoded = decode_capabilities_blob(blob)
    obj_decoder = ObjectIdDecoder()

    dtype_names: list[str] = []
    dtype_bits = decoded["dtype_bits_lo"] | (decoded["dtype_bits_hi"] << 32)
    for dtype_id, info in sorted(obj_decoder.dtype_info.items()):
        if dtype_bits & (1 << int(dtype_id)):
            dtype_names.append(str(info.get("type", f"dtype{dtype_id}")))

    io_lines = _format_capabilities_list(
        decoded["io_enabled"], obj_decoder.io_classes
    )
    prog_lines = _format_capabilities_list(
        decoded["prog_enabled"], obj_decoder.prog_classes
    )
    proto_lines = _format_capabilities_list(
        decoded["proto_enabled"], obj_decoder.proto_classes
    )

    io_flag_names = enabled_flag_names(
        decoded["io_flags_lo"], list(_CAPS_IO_FLAGS)
    )
    build_flag_names = enabled_flag_names(
        decoded["build_flags_lo"], list(_CAPS_BUILD_FLAGS)
    )

    lines: list[str] = []
    lines.append(
        "Capabilities Blob: "
        f"version={decoded['version']} layout={decoded['layout_id']} "
        f"payload={decoded['payload_len']}B"
    )
    lines.append(
        f"Descriptor: slots={decoded['desc_slots']} "
        f"slot_size={decoded['desc_slot_size']}"
    )
    lines.append(
        f"Class limits: io={decoded['max_io_cls']} "
        f"prog={decoded['max_prog_cls']} proto={decoded['max_proto_cls']}"
    )
    lines.append(
        "DTypes: " + (", ".join(dtype_names) if dtype_names else "none")
    )
    lines.append(
        "IO flags: " + (", ".join(io_flag_names) if io_flag_names else "none")
    )
    lines.append(
        "Build flags: "
        + (", ".join(build_flag_names) if build_flag_names else "none")
    )

    lines.append(f"IO classes enabled ({len(io_lines)}):")
    for line in io_lines:
        lines.append(f"  - {line}")
    lines.append(f"PROG classes enabled ({len(prog_lines)}):")
    for line in prog_lines:
        lines.append(f"  - {line}")
    lines.append(f"PROTO classes enabled ({len(proto_lines)}):")
    for line in proto_lines:
        lines.append(f"  - {line}")

    return lines
