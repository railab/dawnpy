# tools/dawnpy/src/dawnpy/headerdefs/_constants.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Dtype/name normalizers and symbol-set builders.

These helpers turn raw constexpr/enum dictionaries (extracted by ``_parser``)
into the structured maps consumed by ``load_header_defs``.
"""

import re
from collections.abc import Callable

from ._paths import HeaderDefsError


def _dtype_size(dtype_name: str) -> int:
    """Map DTYPE token suffix to bit size used by dawnpy."""
    sizes = {
        "ANY": 0,
        "BOOL": 32,
        "INT8": 8,
        "UINT8": 8,
        "INT16": 16,
        "UINT16": 16,
        "INT32": 32,
        "UINT32": 32,
        "INT64": 64,
        "UINT64": 64,
        "FLOAT": 32,
        "DOUBLE": 64,
        "B16": 32,
        "UB16": 32,
        "CHAR": 0,
        "BLOCK": 8,
    }
    return sizes.get(dtype_name, 0)


def _dtype_initval_param(dtype_type: str) -> int | None:
    """Return cfgIdInitval dtype discriminator when applicable.

    The value is the SObjectId::EObjectDataType enum integer that gets
    bit-packed into the resulting ObjectCfgId. CIOConfig's limits-aware
    configure path validates this dtype field against the cfgio's own
    dtype, so the encoding must match the C++ enum.
    """
    mapping = {
        "bool": 1,  # DTYPE_BOOL
        "int8": 2,  # DTYPE_INT8
        "uint8": 3,  # DTYPE_UINT8
        "int16": 4,  # DTYPE_INT16
        "uint16": 5,  # DTYPE_UINT16
        "int32": 6,  # DTYPE_INT32
        "uint32": 7,  # DTYPE_UINT32
        "int64": 8,  # DTYPE_INT64
        "uint64": 9,  # DTYPE_UINT64
        "float": 10,  # DTYPE_FLOAT
        "double": 11,  # DTYPE_DOUBLE
        "b16": 12,  # DTYPE_B16
        "ub16": 13,  # DTYPE_UB16
    }
    return mapping.get(dtype_type)


def _normalize_prog_class_name(raw: str) -> str:
    """Normalize PROG class names to existing dawnpy naming."""
    alias = {
        "stats_min": "stat_min",
        "stats_max": "stat_max",
        "stats_avg": "stat_avg",
        "stats_sum": "stat_sum",
    }
    return alias.get(raw, raw)


def _normalize_proto_class_name(raw: str) -> str:
    """Normalize PROTO class names to existing dawnpy naming."""
    alias = {
        "nimble_prph": "nimble_peripheral",
    }
    return alias.get(raw, raw)


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase token to snake_case."""
    token = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return token.lower()


def _build_bit_fields(constexprs: dict[str, int]) -> dict[str, dict[str, int]]:
    """Build bit field descriptor mapping from constexpr symbols."""
    return {
        "priv": {
            "shift": constexprs["PRIV_SHIFT"],
            "width": 14,
            "max": constexprs["PRIV_MAX"],
        },
        "flags": {
            "shift": constexprs["FLAGS_SHIFT"],
            "width": 2,
            "max": constexprs["FLAGS_MAX"],
        },
        "dtype": {
            "shift": constexprs["DTYPE_SHIFT"],
            "width": 4,
            "max": constexprs["DTYPE_MAX"],
        },
        "ext": {
            "shift": constexprs["EXT_SHIFT"],
            "width": 1,
            "max": constexprs["EXT_MAX"],
        },
        "cls": {
            "shift": constexprs["CLS_SHIFT"],
            "width": 9,
            "max": constexprs["CLS_MAX"],
        },
        "type": {
            "shift": constexprs["TYPE_SHIFT"],
            "width": 2,
            "max": constexprs["TYPE_MAX"],
        },
    }


def _require_symbol_map_keys(
    values: dict[str, int],
    required: list[str],
    context: str,
) -> None:
    """Raise HeaderDefsError when required symbols are missing."""
    missing = [key for key in required if key not in values]
    if missing:
        joined = ", ".join(sorted(missing))
        raise HeaderDefsError(f"Missing {context} symbols: {joined}")


def _build_object_types(enums_objectid: dict[str, int]) -> dict[int, str]:
    """Build object type map from OBJTYPE enum symbols."""
    out: dict[int, str] = {}
    for name, value in enums_objectid.items():
        if not name.startswith("OBJTYPE_") or name.endswith("_LAST"):
            continue
        out[value] = name.replace("OBJTYPE_", "")
    return out


def _build_dtypes(enums_objectid: dict[str, int]) -> list[dict[str, object]]:
    """Build dtype metadata list from DTYPE enum symbols."""
    out: list[dict[str, object]] = []
    for name, value in sorted(
        enums_objectid.items(), key=lambda item: item[1]
    ):
        if not name.startswith("DTYPE_") or name.endswith("_LAST"):
            continue

        suffix = name.replace("DTYPE_", "")
        dtype_type = suffix.lower()
        entry: dict[str, object] = {
            "value": value,
            "type": dtype_type,
            "name": name,
            "size": _dtype_size(suffix),
        }
        initval_param = _dtype_initval_param(dtype_type)
        if initval_param is not None:
            entry["initval_param"] = initval_param
        out.append(entry)
    return out


def _build_class_map(
    enums: dict[str, int],
    *,
    prefix: str,
    normalizer: Callable[[str], str] | None = None,
) -> dict[int, str]:
    """Build IO/PROG/PROTO class map from enum symbols."""
    out: dict[int, str] = {}
    for name, value in sorted(enums.items(), key=lambda item: item[1]):
        if not name.startswith(prefix):
            continue
        if name.endswith("_ANY") or name.endswith("_LAST"):
            continue
        if "_USER" in name:
            continue
        raw = name.replace(prefix, "").lower()
        out[value] = normalizer(raw) if normalizer else raw
    return out
