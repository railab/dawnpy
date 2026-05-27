# tools/dawnpy/src/dawnpy/headerdefs/_typespec.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""IO/PROG/PROTO type-spec extraction from C++ class declarations."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from ._constants import _camel_to_snake
from ._parser import (
    _iter_ts_nodes,
    _parse_cpp_header,
    _ts_text,
)
from ._paths import HeaderDefsError, _require_repo_root


def _parse_function_name_and_params(
    node: Any, source: bytes
) -> tuple[str, list[str]] | None:
    """Extract function declarator name and parameter identifiers."""
    declarator = next(
        (
            child
            for child in _iter_ts_nodes(node)
            if child.type == "function_declarator"
        ),
        None,
    )
    if declarator is None:
        return None
    name = next(
        (
            _ts_text(child, source).strip()
            for child in declarator.children
            if child.type in ("field_identifier", "identifier")
        ),
        "",
    )
    if not name:
        return None

    params: list[str] = []
    parameter_lists = [
        child
        for child in declarator.children
        if child.type == "parameter_list"
    ]
    for param_list in parameter_lists:
        for param_node in param_list.children:
            if param_node.type != "parameter_declaration":
                continue
            token = next(
                (
                    _ts_text(part, source).strip()
                    for part in _iter_ts_nodes(param_node)
                    if part.type in ("field_identifier", "identifier")
                ),
                "",
            )
            if token:
                params.append(token)
    return name, params


def _extract_methods_with_prefixes(
    class_node: Any,
    source: bytes,
    prefixes: tuple[str, ...],
) -> dict[str, list[str]]:
    """Collect class methods and parameters matching any name prefix."""
    methods: dict[str, list[str]] = {}
    for node in _iter_ts_nodes(class_node):
        if node.type not in (
            "function_definition",
            "field_declaration",
            "declaration",
        ):
            continue
        sig = _parse_function_name_and_params(node, source)
        if sig is None:
            continue
        name, params = sig
        if any(name.startswith(prefix) for prefix in prefixes):
            methods[name] = params
    return methods


def _extract_objectid_methods(
    class_node: Any, source: bytes
) -> dict[str, list[str]]:
    """Collect objectId* methods and their parameter names for one class."""
    return _extract_methods_with_prefixes(class_node, source, ("objectId",))


def _collect_class_specs(
    root: Path,
    *,
    subdir: str,
    class_prefix: str,
    recursive: bool = False,
    require_methods: bool = True,
) -> list[dict[str, Any]]:
    """Parse headers and collect class entries exposing objectId methods."""
    include_root = root / "dawn/include/dawn" / subdir
    raw_paths = (
        include_root.rglob("*.hxx")
        if recursive
        else include_root.glob("*.hxx")
    )
    # Skip editor lock-files / hidden files (emacs leaves dangling
    # `.#name.hxx` symlinks during edits which break header parsing).
    paths = sorted(p for p in raw_paths if not p.name.startswith("."))
    out: list[dict[str, Any]] = []
    for header in paths:
        source, tree_root = _parse_cpp_header(header)
        rel = header.relative_to(root / "dawn/include").as_posix()
        for node in _iter_ts_nodes(tree_root):
            if node.type != "class_specifier":
                continue
            class_name: str | None = None
            for child in node.children:
                if child.type == "type_identifier":
                    class_name = _ts_text(child, source).strip()
                    break
            if not isinstance(class_name, str):
                continue
            if not class_name.startswith(class_prefix):
                continue
            methods = _extract_objectid_methods(node, source)
            if require_methods and not methods:
                continue
            out.append(
                {"cpp_class": class_name, "header": rel, "methods": methods}
            )
    return out


def _yaml_type_from_cpp_class(kind: str, cpp_class: str) -> str:
    """Map C++ class name to descriptor YAML type token."""
    prefix = {"io": "CIO", "prog": "CProg", "proto": "CProto"}[kind]
    if cpp_class.startswith(prefix):
        stem = cpp_class[len(prefix) :]
    else:
        stem = cpp_class
    snake = _camel_to_snake(stem)
    compact = snake.replace("_", "")
    if kind == "io":
        alias = {
            "file": "fileio",
            "desc_selector": "descselector",
            "pulse_count": "pulsecount",
        }
        return alias.get(snake, snake)
    if kind == "prog":
        alias = {"process": "stats", "moving_average": "movingavg"}
        return alias.get(snake, compact)
    alias = {"shell_pretty": "shell", "nimble_prph": "nimble"}
    return alias.get(snake, snake)


def _normalize_io_param_name(param: str, yaml_type: str) -> str | None:
    """Normalize objectId parameter names to dawnpy helper tokens."""
    token = param.lower()
    if token in ("dtype",):
        return "dtype"
    if token in ("id", "inst", "instance"):
        return "instance"
    if token in ("rw", "notify"):
        return "notify"
    if token in ("ts", "timestamp"):
        if yaml_type in ("gpi", "gpo", "virt"):
            return "notify"
        return "timestamp"
    return None


def _normalize_io_params(params: list[str], yaml_type: str) -> list[str]:
    """Normalize and deduplicate IO helper parameter names."""
    out: list[str] = []
    for param in params:
        name = _normalize_io_param_name(param, yaml_type)
        if isinstance(name, str) and name not in out:
            out.append(name)
    if yaml_type == "dac" and "dtype" not in out:
        out.insert(0, "dtype")
    return out


def _build_io_type_spec(item: dict[str, Any]) -> dict[str, Any]:
    """Build one IO type entry from parsed class methods."""
    cpp_class = str(item["cpp_class"])
    yaml_type = _yaml_type_from_cpp_class("io", cpp_class)
    methods = item.get("methods", {})
    if not isinstance(methods, dict):
        methods = {}
    method_names = sorted(
        name
        for name in methods.keys()
        if isinstance(name, str) and name.startswith("objectId")
    )
    suffixes = [
        name.replace("objectId", "")
        for name in method_names
        if name != "objectId"
    ]

    entry: dict[str, Any] = {
        "yaml_type": yaml_type,
        "cpp_class": cpp_class,
        "header": str(item["header"]),
    }
    if yaml_type in ("sensor", "sensor_producer") and suffixes:
        first = methods.get(f"objectId{suffixes[0]}", [])
        entry["helper_func"] = "{cpp_class}::objectId{subtype}"
        entry["params"] = _normalize_io_params(list(first), yaml_type)
        entry["subtypes"] = sorted(_camel_to_snake(s) for s in suffixes)
        return entry
    if "objectId" in methods:
        entry["helper_func"] = "{cpp_class}::objectId"
        entry["params"] = _normalize_io_params(
            list(methods.get("objectId", [])), yaml_type
        )
        return entry
    entry["helper_func"] = "{cpp_class}::objectId{variant}"
    entry["params"] = []
    variants: list[dict[str, Any]] = []
    for suffix in suffixes:
        params = methods.get(f"objectId{suffix}", [])
        variants.append(
            {
                "name": _camel_to_snake(suffix),
                "params": _normalize_io_params(list(params), yaml_type),
            }
        )
    entry["variants"] = sorted(variants, key=lambda x: str(x.get("name", "")))
    return entry


def _build_prog_type_spec(item: dict[str, Any]) -> dict[str, Any]:
    """Build one Program type entry from parsed class methods."""
    cpp_class = str(item["cpp_class"])
    if cpp_class in (
        "CProgCommon",
        "CProgFactory",
        "CProgHandler",
        "CProgProcessTemplate",
        "CProgThresholdBase",
    ):
        return {}
    return {
        "yaml_type": _yaml_type_from_cpp_class("prog", cpp_class),
        "cpp_class": cpp_class,
        "header": str(item["header"]),
    }


def _build_proto_type_spec(item: dict[str, Any]) -> dict[str, Any]:
    """Build one Protocol type entry from parsed class methods."""
    cpp_class = str(item["cpp_class"])
    return {
        "yaml_type": _yaml_type_from_cpp_class("proto", cpp_class),
        "cpp_class": cpp_class,
        "header": str(item["header"]),
    }


@lru_cache(maxsize=1)
def load_header_type_defs() -> dict[str, list[dict[str, Any]]]:
    """Load IO/PROG/PROTO type definitions from C++ headers."""
    root = _require_repo_root()
    io_specs = _collect_class_specs(root, subdir="io", class_prefix="CIO")
    prog_specs = _collect_class_specs(
        root,
        subdir="prog",
        class_prefix="CProg",
        require_methods=False,
    )
    proto_specs = _collect_class_specs(
        root, subdir="proto", class_prefix="CProto", recursive=True
    )

    io_types = sorted(
        (_build_io_type_spec(item) for item in io_specs),
        key=lambda x: str(x.get("yaml_type", "")),
    )
    prog_types = sorted(
        (
            spec
            for spec in (_build_prog_type_spec(item) for item in prog_specs)
            if spec
        ),
        key=lambda x: str(x.get("yaml_type", "")),
    )
    proto_types = sorted(
        (_build_proto_type_spec(item) for item in proto_specs),
        key=lambda x: str(x.get("yaml_type", "")),
    )
    if not io_types:
        raise HeaderDefsError("No IO type definitions loaded from headers")
    if not prog_types:
        raise HeaderDefsError(
            "No Program type definitions loaded from headers"
        )
    if not proto_types:
        raise HeaderDefsError(
            "No Protocol type definitions loaded from headers"
        )

    return {
        "io_types": io_types,
        "prog_types": prog_types,
        "proto_types": proto_types,
    }
