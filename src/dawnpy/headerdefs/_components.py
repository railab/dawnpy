# tools/dawnpy/src/dawnpy/headerdefs/_components.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Component registration + descriptor metadata extraction from headers."""

import re
from functools import lru_cache
from typing import Any

from ._parser import (
    _extract_enum_constants_from_tree,
    _iter_ts_nodes,
    _parse_cpp_header,
    _ts_text,
)
from ._paths import HeaderDefsError, _require_repo_root
from ._typespec import _collect_class_specs, _extract_methods_with_prefixes


def _camel_to_upper_snake(name: str) -> str:
    """Convert CamelCase token to UPPER_SNAKE_CASE."""
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).upper()


def _component_kconfig(kind: str, cpp_class: str) -> str:
    """Map component C++ class name to primary Kconfig symbol."""
    prefix_map = {
        "io": "CONFIG_DAWN_IO_",
        "prog": "CONFIG_DAWN_PROG_",
        "proto": "CONFIG_DAWN_PROTO_",
    }
    class_prefix = {"io": "CIO", "prog": "CProg", "proto": "CProto"}[kind]
    stem = cpp_class[len(class_prefix) :]

    io_special = {
        "Timestamp": "TIMESTAMPIO",
        "Rand": "RANDIO",
        "File": "FILE",
        "DescSelector": "DESC_SELECTOR",
        "PulseCount": "PULSECOUNT",
    }
    prog_special = {
        "MovingAverage": "MOVING_AVG",
        "IIRFilter": "IIR_FILTER",
        "ThresholdValue": "THRESHOLD_VALUE",
        "BitSplit": "BITSPLIT",
        "BitPack": "BITPACK",
        "VecPack": "VECPACK",
        "VecSplit": "VECSPLIT",
        "ManyToOne": "MANYTOONE",
        "OneToMany": "ONETOMANY",
    }
    proto_special = {
        "NimblePrph": "NIMBLE_PERIPHERAL",
    }
    proto_stem_prefix = {
        "NimblePrphAios": "NIMBLE_AIOS",
        "NimblePrphBas": "NIMBLE_BAS",
        "NimblePrphDis": "NIMBLE_DIS",
        "NimblePrphEss": "NIMBLE_ESS",
        "NimblePrphImds": "NIMBLE_IMDS",
    }

    token: str | None = None
    if kind == "io":
        token = io_special.get(stem)
    elif kind == "prog":
        token = prog_special.get(stem)
    else:
        for prefix, mapped in proto_stem_prefix.items():
            if stem.startswith(prefix):
                token = mapped
                break
        if token is None:
            token = proto_special.get(stem)

    if token is None:
        token = _camel_to_upper_snake(stem)
    return prefix_map[kind] + token


def _is_component_class(kind: str, cpp_class: str) -> bool:
    """Return True for component classes mapped in descriptor validation."""
    skip_exact = {
        "io": {
            "CIOCommon",
            "CIOFactory",
            "CIOHandler",
        },
        "prog": {
            "CProgCommon",
            "CProgFactory",
            "CProgHandler",
            "CProgThresholdBase",
        },
        "proto": {
            "CProtoCommon",
            "CProtoFactory",
            "CProtoHandler",
            "CProtoSimpleBase",
        },
    }
    if cpp_class in skip_exact[kind]:
        return False
    return not cpp_class.endswith("Template")


def _build_component_entries(
    kind: str,
    specs: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build include->kconfig component entries from parsed class specs."""
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in specs:
        cpp_class = str(item.get("cpp_class", ""))
        header = str(item.get("header", ""))
        if not cpp_class or not header:
            continue
        if not _is_component_class(kind, cpp_class):
            continue
        key = (cpp_class, header)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "name": cpp_class,
                "kval": _component_kconfig(kind, cpp_class),
                "include": header,
            }
        )
    return sorted(entries, key=lambda x: str(x.get("name", "")))


@lru_cache(maxsize=1)
def load_header_component_defs() -> dict[str, list[dict[str, str]]]:
    """Load validator component include->kconfig definitions from headers."""
    root = _require_repo_root()
    io_specs = _collect_class_specs(
        root,
        subdir="io",
        class_prefix="CIO",
        require_methods=False,
    )
    prog_specs = _collect_class_specs(
        root,
        subdir="prog",
        class_prefix="CProg",
        require_methods=False,
    )
    proto_specs = _collect_class_specs(
        root,
        subdir="proto",
        class_prefix="CProto",
        recursive=True,
        require_methods=False,
    )
    defs = {
        "ios": _build_component_entries("io", io_specs),
        "programs": _build_component_entries("prog", prog_specs),
        "protocols": _build_component_entries("proto", proto_specs),
    }
    if not defs["ios"] and not defs["programs"] and not defs["protocols"]:
        raise HeaderDefsError("No component definitions loaded from headers")
    return defs


@lru_cache(maxsize=1)
def load_header_metadata_defs() -> list[dict[str, str]]:
    """Load descriptor metadata field definitions from C++ headers."""
    root = _require_repo_root()
    header = root / "dawn/include/dawn/common/descriptor.hxx"
    source, tree_root = _parse_cpp_header(header)
    methods: dict[str, list[str]] = {}

    for node in _iter_ts_nodes(tree_root):
        if node.type != "class_specifier":
            continue
        class_name = ""
        for child in node.children:
            if child.type == "type_identifier":
                class_name = _ts_text(child, source).strip()
                break
        if class_name != "CDescriptor":
            continue
        methods = _extract_methods_with_prefixes(
            node, source, ("cfgIdVersion", "cfgIdString")
        )
        break

    enums_desc = _extract_enum_constants_from_tree(
        source, tree_root, ("DESC_CFG_",)
    )

    defs: list[dict[str, str]] = []
    if "cfgIdVersion" in methods and "DESC_CFG_VERSION" in enums_desc:
        defs.append(
            {
                "name": "version",
                "cpp_helper": "CDescriptor::cfgIdVersion",
                "value_type": "version",
            }
        )
    if "cfgIdString" in methods and "DESC_CFG_STRING" in enums_desc:
        defs.append(
            {
                "name": "user_string",
                "cpp_helper": "CDescriptor::cfgIdString",
                "value_type": "string",
            }
        )

    if not defs:
        raise HeaderDefsError(
            "No descriptor metadata definitions loaded from headers"
        )
    return defs
