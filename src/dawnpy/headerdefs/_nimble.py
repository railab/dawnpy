# tools/dawnpy/src/dawnpy/headerdefs/_nimble.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Nimble peripheral service schema extraction from C++ headers."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from ._parser import (
    _extract_enum_constants_from_tree,
    _iter_ts_nodes,
    _parse_cpp_header,
    _ts_text,
)
from ._paths import HeaderDefsError, _require_repo_root
from ._typespec import _extract_methods_with_prefixes


def _nimble_sensor_yaml_name(token: str) -> str:
    """Map Nimble sensor enum suffix to YAML field token."""
    alias = {
        "TEMP": "temperature",
        "HUM": "humidity",
        "PRESS": "pressure",
        "UVIDX": "uv_index",
        "TWINDSPEED": "wind_speed",
        "TWINDDIR": "wind_direction",
        "GAS": "gas_resistance",
    }
    return alias.get(token, token.lower())


def _load_nimble_sensor_types(
    header: Path,
    enum_prefix: str,
    cpp_service_class: str,
) -> list[dict[str, str]]:
    """Extract Nimble sensor type entries from enum constants."""
    source, tree_root = _parse_cpp_header(header)
    enums = _extract_enum_constants_from_tree(
        source, tree_root, (enum_prefix,)
    )
    types: list[dict[str, str]] = []
    for enum_name, _ in sorted(enums.items(), key=lambda item: item[1]):
        suffix = enum_name.replace(enum_prefix, "")
        types.append(
            {
                "yaml_name": _nimble_sensor_yaml_name(suffix),
                "cpp_enum": f"{cpp_service_class}::{enum_name}",
            }
        )
    return types


def _load_nimble_prph_methods(root: Path) -> dict[str, list[str]]:
    """Load selected CProtoNimblePrph cfg helpers."""
    prph_header = root / "dawn/include/dawn/proto/nimble/prph.hxx"
    source, tree_root = _parse_cpp_header(prph_header)
    for node in _iter_ts_nodes(tree_root):
        if node.type != "class_specifier":
            continue
        class_name = ""
        for child in node.children:
            if child.type == "type_identifier":
                class_name = _ts_text(child, source).strip()
                break
        if class_name != "CProtoNimblePrph":
            continue
        return _extract_methods_with_prefixes(
            node,
            source,
            (
                "cfgIdIOBindDis",
                "cfgIdIOBindBas",
                "cfgIdIOBindAios",
                "cfgIdIOBindEss",
                "cfgIdIOBindImds",
                "cfgIdIOBindOts",
            ),
        )
    return {}


def _nimble_aios_def() -> dict[str, Any]:
    """Return AIOS service schema from static/header-backed mapping."""
    return {
        "name": "aios",
        "cpp_helper": "CProtoNimblePrph::cfgIdIOBindAios",
        "cpp_service_class": "CProtoNimblePrphAios",
        "header": "dawn/proto/nimble/prph_aios.hxx",
        "has_groups": True,
        "group_fields": [
            {"name": "digital_inputs", "io_type": "PRPH_AIOS_TYPE_DIGITAL"},
            {"name": "digital_outputs", "io_type": "PRPH_AIOS_TYPE_DIGITAL"},
            {"name": "analog_inputs", "io_type": "PRPH_AIOS_TYPE_ANALOG"},
            {"name": "analog_outputs", "io_type": "PRPH_AIOS_TYPE_ANALOG"},
        ],
    }


def _nimble_sensor_service_def(
    *,
    root: Path,
    service_name: str,
    helper_name: str,
    service_class: str,
    header_rel: str,
    enum_prefix: str,
) -> dict[str, Any]:
    """Build ESS/IMDS service schema with header-derived sensor enum map."""
    sensor_header = root / "dawn/include" / header_rel
    return {
        "name": service_name,
        "cpp_helper": helper_name,
        "cpp_service_class": service_class,
        "header": header_rel,
        "sensor_types": _load_nimble_sensor_types(
            sensor_header,
            enum_prefix,
            service_class,
        ),
    }


@lru_cache(maxsize=1)
def load_header_nimble_service_defs() -> dict[str, dict[str, Any]]:
    """Load Nimble service schema definitions from C++ headers."""
    root = _require_repo_root()
    methods = _load_nimble_prph_methods(root)
    defs: dict[str, dict[str, Any]] = {}
    if "cfgIdIOBindDis" in methods:
        defs["dis"] = {
            "name": "dis",
            "enabled_only": True,
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindDis",
        }
    if "cfgIdIOBindBas" in methods:
        defs["bas"] = {
            "name": "bas",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindBas",
            "fields": [{"name": "battery_level", "required": True}],
        }
    if "cfgIdIOBindAios" in methods:
        defs["aios"] = _nimble_aios_def()
    if "cfgIdIOBindEss" in methods:
        defs["ess"] = _nimble_sensor_service_def(
            root=root,
            service_name="ess",
            helper_name="CProtoNimblePrph::cfgIdIOBindEss",
            service_class="CProtoNimblePrphEss",
            header_rel="dawn/proto/nimble/prph_ess.hxx",
            enum_prefix="PRPH_ESS_TYPE_",
        )
    if "cfgIdIOBindImds" in methods:
        defs["imds"] = _nimble_sensor_service_def(
            root=root,
            service_name="imds",
            helper_name="CProtoNimblePrph::cfgIdIOBindImds",
            service_class="CProtoNimblePrphImds",
            header_rel="dawn/proto/nimble/prph_imds.hxx",
            enum_prefix="PRPH_IMDS_TYPE_",
        )
    if "cfgIdIOBindOts" in methods:
        defs["ots"] = {
            "name": "ots",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindOts",
            "cpp_service_class": "CProtoNimblePrphOts",
            "header": "dawn/proto/nimble/prph_ots.hxx",
            "object_types": {
                "file": 0,
                "descriptor": 1,
                "capabilities": 2,
            },
            "object_access": {
                "read": 0,
                "write": 1,
                "rw": 2,
            },
        }

    if not defs:
        raise HeaderDefsError("No Nimble service definitions loaded")
    return defs
