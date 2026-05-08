# tools/dawnpy/src/dawnpy/headerdefs/_enums.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Enum value lookup helpers (cfg-id, object-class, value maps)."""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._constants import _normalize_prog_class_name, _normalize_proto_class_name
from ._parser import _extract_enum_constants_from_tree, _parse_cpp_header
from ._paths import HeaderDefsError, _require_repo_root
from ._typespec import load_header_type_defs


def _enum_key_from_suffix(owner: str, suffix: str) -> str:
    """Convert enum suffix token to descriptor YAML key."""
    if owner == "CProtoCan":
        if suffix == "INDEXED_READ":
            return "read_indexed"
        if suffix == "INDEXED_WRITE":
            return "write_indexed"
    return suffix.lower()


TypeDefs = Mapping[str, list[dict[str, Any]]]


def _enum_header_for_owner(
    owner: str, type_defs: TypeDefs | None = None
) -> str | None:
    """Resolve include header path for an enum owner class."""
    defs = type_defs if type_defs is not None else load_header_type_defs()
    for group in ("io_types", "prog_types", "proto_types"):
        for item in defs.get(group, []):
            if item.get("cpp_class") == owner:
                return str(item.get("header", ""))
    extras = {
        "CIOCommon": "dawn/io/common.hxx",
        "CProgCommon": "dawn/prog/common.hxx",
        "CProtoModbusRegs": "dawn/proto/modbus/regs.hxx",
        "CProtoNimblePrphAios": "dawn/proto/nimble/prph_aios.hxx",
        "CProtoNimblePrphEss": "dawn/proto/nimble/prph_ess.hxx",
        "CProtoNimblePrphImds": "dawn/proto/nimble/prph_imds.hxx",
    }
    return extras.get(owner)


def _extract_class_block(source_text: str, owner: str) -> str | None:
    """Extract one class definition block by class name."""
    class_pat = re.compile(rf"\bclass\s+{re.escape(owner)}\b")
    match = class_pat.search(source_text)
    if not match:
        return None
    brace_start = source_text.find("{", match.end())
    if brace_start < 0:
        return None
    depth = 0
    idx = brace_start
    while idx < len(source_text):
        ch = source_text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source_text[match.start() : idx + 1]
        idx += 1
    return None


def _extract_cfg_enum_from_method_text(
    class_text: str, method_name: str
) -> str | None:
    """Extract enum token returned by one cfg helper method."""
    body = _extract_method_body_text(class_text, method_name)
    if body is None:
        return None
    cfg_tokens = re.findall(
        r"\b(?:IO|PROG|PROTO|DESC)_[A-Z0-9_]*CFG[A-Z0-9_]*\b",
        body,
    )
    if cfg_tokens:
        return str(cfg_tokens[-1])
    direct = re.search(r"return\s+([A-Z][A-Z0-9_]+)\s*;", body)
    if direct:
        return direct.group(1)
    return None


def _extract_object_class_enum_from_method_text(
    class_text: str, method_name: str
) -> str | None:
    """Extract IO/PROG/PROTO class enum token from objectId* helper body."""
    body = _extract_method_body_text(class_text, method_name)
    if body is None:
        return None
    class_tokens = re.findall(
        r"\b(?:IO|PROG|PROTO)_CLASS_[A-Z0-9_]+\b",
        body,
    )
    if class_tokens:
        return str(class_tokens[0])
    if "ObjectIdHelper::create" not in body:
        return None
    helper_decl = re.search(
        r"using\s+ObjectIdHelper\s*=\s*[^;<>]*<\s*"
        r"(?:[A-Za-z_][A-Za-z0-9_:]*::)?"
        r"((?:IO|PROG|PROTO)_CLASS_[A-Z0-9_]+)",
        class_text,
        flags=re.S,
    )
    if helper_decl:
        return helper_decl.group(1)  # pragma: no cover
    return None


def _extract_method_body_text(class_text: str, method_name: str) -> str | None:
    """Extract full method body text with brace balancing."""
    sig_pat = re.compile(rf"\b{re.escape(method_name)}\s*\(")
    for match in sig_pat.finditer(class_text):
        line_start = class_text.rfind("\n", 0, match.start()) + 1
        line_prefix = class_text[line_start : match.start()].strip()
        if line_prefix.startswith("//") or line_prefix.startswith("*"):
            continue
        brace_start = class_text.find("{", match.end())
        if brace_start < 0:
            continue
        semi_pos = class_text.find(";", match.end(), brace_start)
        if semi_pos >= 0:
            continue
        depth = 0
        idx = brace_start
        while idx < len(class_text):
            ch = class_text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return class_text[brace_start + 1 : idx]
            idx += 1
    return None


def _cfg_id_fallback_headers(root: Path, enum_name: str) -> list[Path]:
    """Return fallback headers for cfg enum token lookup."""
    headers: list[Path] = []
    if enum_name.startswith("IO_"):
        headers.append(root / "dawn/include/dawn/io/common.hxx")
    if enum_name.startswith("PROG_"):
        headers.append(root / "dawn/include/dawn/prog/common.hxx")
        headers.append(root / "dawn/include/dawn/prog/process.hxx")
    if enum_name.startswith("PROTO_"):
        headers.append(root / "dawn/include/dawn/proto/common.hxx")
    if enum_name.startswith("DESC_"):
        headers.append(root / "dawn/include/dawn/common/descriptor.hxx")
    return headers


def _lookup_enum_value_in_headers(
    enum_name: str, headers: list[Path]
) -> int | None:
    """Find enum constant value across a list of headers."""
    for header in headers:
        source, tree_root = _parse_cpp_header(header)
        enums = _extract_enum_constants_from_tree(
            source, tree_root, (enum_name,)
        )
        if enum_name in enums:
            return int(enums[enum_name])
    return None


def load_header_enum_map_from_defs(
    owner: str, enum_prefix: str, type_defs: TypeDefs
) -> dict[str, str]:
    """Load enum value map using preloaded header type definitions."""
    header_rel = _enum_header_for_owner(owner, type_defs)
    if not header_rel:
        raise HeaderDefsError(f"No header found for enum owner {owner}")
    return _load_header_enum_map(owner, enum_prefix, header_rel)


def _load_header_enum_map(
    owner: str, enum_prefix: str, header_rel: str
) -> dict[str, str]:
    """Load enum value map from one resolved owner header."""
    root = _require_repo_root()
    header = root / "dawn/include" / header_rel
    source, tree_root = _parse_cpp_header(header)
    enums = _extract_enum_constants_from_tree(
        source, tree_root, (enum_prefix,)
    )
    if not enums:
        raise HeaderDefsError(
            f"No enum constants found for {owner}::{enum_prefix}"
        )

    out: dict[str, str] = {}
    for enum_name, _ in sorted(enums.items(), key=lambda item: item[1]):
        suffix = enum_name.replace(enum_prefix, "")
        key = _enum_key_from_suffix(owner, suffix)
        out[key] = suffix
        if owner == "CProtoCan" and suffix in (
            "INDEXED_READ",
            "INDEXED_WRITE",
        ):
            if key.endswith("_indexed"):
                alias = "indexed_" + key.removesuffix("_indexed")
                out[alias] = suffix
    return out


def load_header_cfg_id_from_defs(
    owner: str, method_name: str, type_defs: TypeDefs
) -> int:
    """Resolve cfg-id enum value using preloaded header type definitions."""
    header_rel = _enum_header_for_owner(owner, type_defs)
    if not header_rel:
        raise HeaderDefsError(f"No header found for enum owner {owner}")
    return _load_header_cfg_id(owner, method_name, header_rel)


def _load_header_cfg_id(owner: str, method_name: str, header_rel: str) -> int:
    """Resolve cfg-id enum value from one resolved owner header."""
    root = _require_repo_root()
    header = root / "dawn/include" / header_rel
    source, tree_root = _parse_cpp_header(header)
    source_text = source.decode("utf-8", errors="ignore")
    class_text = _extract_class_block(source_text, owner)
    if not class_text:
        raise HeaderDefsError(f"No class block found for owner {owner}")

    enum_name = _extract_cfg_enum_from_method_text(class_text, method_name)
    if not enum_name:
        raise HeaderDefsError(
            f"No cfg enum return found for {owner}::{method_name}"
        )

    enums = _extract_enum_constants_from_tree(source, tree_root, (enum_name,))
    if enum_name in enums:
        return int(enums[enum_name])

    fallback_headers = _cfg_id_fallback_headers(root, enum_name)
    fallback_value = _lookup_enum_value_in_headers(enum_name, fallback_headers)
    if fallback_value is not None:
        return fallback_value

    raise HeaderDefsError(
        f"Enum constant {enum_name} not found for {owner}::{method_name}"
    )


def load_header_object_class_name_from_defs(
    owner: str, method_name: str, type_defs: TypeDefs
) -> str:
    """Resolve class name using preloaded header type definitions."""
    header_rel = _enum_header_for_owner(owner, type_defs)
    if not header_rel:
        raise HeaderDefsError(f"No header found for enum owner {owner}")
    return _load_header_object_class_name(owner, method_name, header_rel)


def _load_header_object_class_name(
    owner: str, method_name: str, header_rel: str
) -> str:
    """Resolve descriptor class name from one resolved owner header."""
    root = _require_repo_root()
    header = root / "dawn/include" / header_rel
    source, _tree_root = _parse_cpp_header(header)
    source_text = source.decode("utf-8", errors="ignore")
    class_text = _extract_class_block(source_text, owner)
    if not class_text:
        raise HeaderDefsError(f"No class block found for owner {owner}")

    enum_name = _extract_object_class_enum_from_method_text(
        class_text, method_name
    )
    if not enum_name:
        raise HeaderDefsError(
            f"No class enum return found for {owner}::{method_name}"
        )

    if enum_name.startswith("IO_CLASS_"):
        return enum_name.replace("IO_CLASS_", "").lower()  # pragma: no cover
    if enum_name.startswith("PROG_CLASS_"):
        raw = enum_name.replace("PROG_CLASS_", "").lower()
        return _normalize_prog_class_name(raw)
    if enum_name.startswith("PROTO_CLASS_"):
        raw = enum_name.replace("PROTO_CLASS_", "").lower()
        return _normalize_proto_class_name(raw)
    raise HeaderDefsError(
        f"Unsupported class enum token {enum_name} for {owner}::{method_name}"
    )


def load_header_enum_value_ids_from_defs(
    owner: str, enum_prefix: str, type_defs: TypeDefs
) -> dict[str, int]:
    """Load enum integer map using preloaded header type definitions."""
    header_rel = _enum_header_for_owner(owner, type_defs)
    if not header_rel:
        raise HeaderDefsError(f"No header found for enum owner {owner}")
    return _load_header_enum_value_ids(owner, enum_prefix, header_rel)


def _load_header_enum_value_ids(
    owner: str, enum_prefix: str, header_rel: str
) -> dict[str, int]:
    """Load enum integer map from one resolved owner header."""
    root = _require_repo_root()
    header = root / "dawn/include" / header_rel
    source, tree_root = _parse_cpp_header(header)
    enums = _extract_enum_constants_from_tree(
        source, tree_root, (enum_prefix,)
    )
    if not enums:
        raise HeaderDefsError(
            f"No enum constants found for {owner}::{enum_prefix}"
        )

    out: dict[str, int] = {}
    for enum_name, value in sorted(enums.items(), key=lambda item: item[1]):
        suffix = enum_name.replace(enum_prefix, "")
        key = _enum_key_from_suffix(owner, suffix)
        out[key] = int(value)
        if owner == "CProtoCan" and suffix in (
            "INDEXED_READ",
            "INDEXED_WRITE",
        ):
            if key.endswith("_indexed"):
                alias = "indexed_" + key.removesuffix("_indexed")
                out[alias] = int(value)
    return out
