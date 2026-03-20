# tools/dawnpy/src/dawnpy/headerdefs/_loader.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Top-level loader: parse core headers, validate, build object-id maps."""

from functools import lru_cache
from pathlib import Path

from ._constants import (
    _build_bit_fields,
    _build_class_map,
    _build_dtypes,
    _build_object_types,
    _normalize_prog_class_name,
    _normalize_proto_class_name,
    _require_symbol_map_keys,
)
from ._parser import (
    _extract_constexpr_values_from_tree,
    _extract_enum_constants_from_tree,
    _parse_cpp_header,
)
from ._paths import HeaderDefsError, _require_repo_root


def _load_header_symbol_sets(
    root: Path,
) -> tuple[
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, int],
]:
    """Parse core headers and return extracted constexpr/enum maps."""
    objectid_header = root / "dawn/include/dawn/common/objectid.hxx"
    io_common_header = root / "dawn/include/dawn/io/common.hxx"
    prog_common_header = root / "dawn/include/dawn/prog/common.hxx"
    proto_common_header = root / "dawn/include/dawn/proto/common.hxx"

    objectid_src, objectid_root = _parse_cpp_header(objectid_header)
    io_src, io_root = _parse_cpp_header(io_common_header)
    prog_src, prog_root = _parse_cpp_header(prog_common_header)
    proto_src, proto_root = _parse_cpp_header(proto_common_header)

    constexprs = _extract_constexpr_values_from_tree(
        objectid_src, objectid_root
    )
    enums_objectid = _extract_enum_constants_from_tree(
        objectid_src, objectid_root, ("OBJTYPE_", "DTYPE_")
    )
    enums_io = _extract_enum_constants_from_tree(
        io_src, io_root, ("IO_CLASS_",)
    )
    enums_prog = _extract_enum_constants_from_tree(
        prog_src, prog_root, ("PROG_CLASS_",)
    )
    enums_proto = _extract_enum_constants_from_tree(
        proto_src, proto_root, ("PROTO_CLASS_",)
    )
    return constexprs, enums_objectid, enums_io, enums_prog, enums_proto


def _validate_loaded_symbol_sets(
    constexprs: dict[str, int],
    enums_objectid: dict[str, int],
    enums_io: dict[str, int],
    enums_prog: dict[str, int],
    enums_proto: dict[str, int],
) -> None:
    """Validate required symbols for object id and class maps."""
    _require_symbol_map_keys(
        constexprs,
        [
            "PRIV_SHIFT",
            "PRIV_MAX",
            "FLAGS_SHIFT",
            "FLAGS_MAX",
            "DTYPE_SHIFT",
            "DTYPE_MAX",
            "EXT_SHIFT",
            "EXT_MAX",
            "CLS_SHIFT",
            "CLS_MAX",
            "TYPE_SHIFT",
            "TYPE_MAX",
        ],
        "bit-field",
    )
    _require_symbol_map_keys(
        enums_objectid,
        ["OBJTYPE_ANY", "OBJTYPE_IO", "OBJTYPE_PROTO", "OBJTYPE_PROG"],
        "object type",
    )
    checks = [
        (
            any(name.startswith("DTYPE_") for name in enums_objectid),
            "Missing dtype symbols in objectid header",
        ),
        (
            any(name.startswith("IO_CLASS_") for name in enums_io),
            "Missing IO class symbols in io/common.hxx",
        ),
        (
            any(name.startswith("PROG_CLASS_") for name in enums_prog),
            "Missing Program class symbols in prog/common.hxx",
        ),
        (
            any(name.startswith("PROTO_CLASS_") for name in enums_proto),
            "Missing Protocol class symbols in proto/common.hxx",
        ),
    ]
    for valid, message in checks:
        if not valid:
            raise HeaderDefsError(message)


@lru_cache(maxsize=1)
def load_header_defs() -> dict[str, object]:
    """Load object-id constants and class maps from Dawn headers."""
    root = _require_repo_root()
    constexprs, enums_objectid, enums_io, enums_prog, enums_proto = (
        _load_header_symbol_sets(root)
    )
    _validate_loaded_symbol_sets(
        constexprs, enums_objectid, enums_io, enums_prog, enums_proto
    )

    return {
        "bit_fields": _build_bit_fields(constexprs),
        "object_types": _build_object_types(enums_objectid),
        "dtype": _build_dtypes(enums_objectid),
        "io_classes": _build_class_map(enums_io, prefix="IO_CLASS_"),
        "prog_classes": _build_class_map(
            enums_prog,
            prefix="PROG_CLASS_",
            normalizer=_normalize_prog_class_name,
        ),
        "proto_classes": _build_class_map(
            enums_proto,
            prefix="PROTO_CLASS_",
            normalizer=_normalize_proto_class_name,
        ),
    }
