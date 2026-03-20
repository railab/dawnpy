# tools/dawnpy/src/dawnpy/descriptor/headers_check.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Header discovery / parsing self-check helpers.

Owns the actual logic for ``dawnpy desc-headers-check``; the CLI
command under ``commands/cmd_desc_headers_check.py`` is a click
command that calls into here.
"""

from collections.abc import Iterable, Sized
from pathlib import Path
from typing import Any, NamedTuple

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.descriptor.definitions import io_family as _io
from dawnpy.descriptor.definitions import prog_family as _prog
from dawnpy.descriptor.definitions import proto_family as _proto
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.headerdefs import HeaderDefsError, find_repo_root
from dawnpy.headerdefs.bundle import HeaderBundle
from dawnpy.sources import DawnSourcesMissing


class HeaderCheckSummary(NamedTuple):
    """Header discovery + parsing summary returned to the CLI command."""

    root: Path
    dtype_count: int
    io_class_count: int
    prog_class_count: int
    proto_class_count: int
    io_types_count: int
    prog_types_count: int
    proto_types_count: int


def collect_header_summary() -> HeaderCheckSummary:
    """Run header discovery + parsing and return a populated summary."""
    root = find_repo_root()
    if root is None:
        raise DawnSourcesMissing("Could not locate Dawn repository root.")

    defs = header_bundle.load_header_bundle()
    const_defs = defs.header_defs
    type_defs = defs.type_defs

    dtypes = const_defs.get("dtype", [])
    io_classes = const_defs.get("io_classes", {})
    prog_classes = const_defs.get("prog_classes", {})
    proto_classes = const_defs.get("proto_classes", {})
    io_types = type_defs.get("io_types", [])
    prog_types = type_defs.get("prog_types", [])
    proto_types = type_defs.get("proto_types", [])

    return HeaderCheckSummary(
        root=root,
        dtype_count=len(dtypes) if isinstance(dtypes, Sized) else 0,
        io_class_count=(
            len(io_classes) if isinstance(io_classes, Sized) else 0
        ),
        prog_class_count=(
            len(prog_classes) if isinstance(prog_classes, Sized) else 0
        ),
        proto_class_count=(
            len(proto_classes) if isinstance(proto_classes, Sized) else 0
        ),
        io_types_count=len(io_types),
        prog_types_count=len(prog_types),
        proto_types_count=len(proto_types),
    )


def _walk_fields(items: Any) -> Iterable[ConfigField]:
    """Yield every ConfigField from a (possibly nested) config-fields tree."""
    if not isinstance(items, list):
        return
    for entry in items:
        if not isinstance(entry, ConfigField):
            continue
        yield entry
        yield from _walk_fields(entry.element_fields)


def _parse_helper_token(token: str) -> tuple[str, str] | None:
    """Split ``Owner::method`` into ``(owner, method)`` or return ``None``."""
    if not token or "::" not in token:
        return None
    owner, method = token.split("::", 1)
    if not owner or not method or "{" in owner or "{" in method:
        return None
    return owner, method


def _check_field(
    label: str,
    type_name: str,
    field: ConfigField,
    defs: HeaderBundle | None = None,
) -> list[str]:
    """Verify one field's cpp_helper and enum_prefix resolve via headerdefs."""
    out: list[str] = []
    source = defs if defs is not None else header_bundle.load_header_bundle()
    parsed = _parse_helper_token(field.cpp_helper)
    if parsed is not None:
        owner, method = parsed
        try:
            source.cfg_id(owner, method)
        except HeaderDefsError as exc:
            out.append(
                f"{label}::{type_name}.{field.name}: "
                f"cpp_helper '{field.cpp_helper}' did not resolve ({exc})"
            )

    parsed_enum = _parse_helper_token(field.enum_prefix)
    if parsed_enum is not None:
        owner, prefix = parsed_enum
        try:
            source.enum_value_ids(owner, prefix)
        except HeaderDefsError as exc:
            out.append(
                f"{label}::{type_name}.{field.name}: "
                f"enum_prefix '{field.enum_prefix}' did not resolve ({exc})"
            )
    return out


def check_inline_field_schemas() -> list[str]:
    """Walk handler-owned config_fields, return resolution errors."""
    errors: list[str] = []
    defs = header_bundle.load_header_bundle()

    for field in _walk_fields(_io.get_common_fields()):
        errors.extend(_check_field("io", "<common>", field, defs))
    for io_type, fields in _io._index_fields_by_type(defs).items():
        for field in _walk_fields(fields):
            errors.extend(_check_field("io", io_type, field, defs))

    for field in _walk_fields(_prog.get_standard_fields()):
        errors.extend(_check_field("prog", "<standard>", field, defs))
    for prog_type, fields in _prog._index_fields_by_type().items():
        for field in _walk_fields(fields):
            errors.extend(_check_field("prog", prog_type, field, defs))

    for field in _walk_fields(_proto.get_standard_fields()):
        errors.extend(_check_field("proto", "<standard>", field, defs))
    for proto_type, entry in _proto._index_proto_entries(defs).items():
        for field in _walk_fields(entry.fields):
            errors.extend(_check_field("proto", proto_type, field, defs))

    return errors
