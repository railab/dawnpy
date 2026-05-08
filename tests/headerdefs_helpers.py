#
# SPDX-License-Identifier: Apache-2.0
#

"""Small source-free helpers for headerdefs tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dawnpy.descriptor.definitions.io_family as builtin_io_mod
import dawnpy.descriptor.definitions.prog_family as builtin_prog_mod
import dawnpy.descriptor.definitions.proto_family as builtin_proto_mod
import dawnpy.headerdefs._enums as headerdefs_enums_mod
import dawnpy.headerdefs.bundle as header_bundle_mod
import dawnpy.objectid as objectid_mod
from tests.conftest import minimal_header_bundle


def definition_set(
    *,
    header_defs: dict[str, object] | None = None,
    type_defs: dict[str, list[dict[str, object]]] | None = None,
    component_defs: dict[str, list[dict[str, str]]] | None = None,
    enum_map_loader: Callable[[str, str], dict[str, str]] | None = None,
    cfg_id_loader: Callable[[str, str], int] | None = None,
    enum_value_ids_loader: Callable[[str, str], dict[str, int]] | None = None,
    object_class_name_loader: Callable[[str, str], str] | None = None,
) -> header_bundle_mod.HeaderBundle:
    groups = header_bundle_mod.HeaderDefinitionGroups(
        header_defs=header_defs if header_defs is not None else {"dtype": []},
        type_defs=(
            type_defs
            if type_defs is not None
            else {"io_types": [], "prog_types": [], "proto_types": []}
        ),
        metadata_defs=[],
        component_defs=component_defs if component_defs is not None else {},
    )
    lookups = header_bundle_mod.HeaderLookupFunctions(
        enum_map_loader=enum_map_loader or (lambda *_args: {}),
        cfg_id_loader=cfg_id_loader,
        enum_value_ids_loader=enum_value_ids_loader,
        object_class_name_loader=object_class_name_loader,
    )
    return minimal_header_bundle(
        groups=groups,
        lookups=lookups,
    )


def enum_type_defs() -> dict[str, list[dict[str, object]]]:
    return {
        "io_types": [],
        "prog_types": [],
        "proto_types": [
            {"cpp_class": "CProtoCan", "header": "x.hxx"},
        ],
    }


def empty_type_defs() -> dict[str, list[dict[str, object]]]:
    return {"io_types": [], "prog_types": [], "proto_types": []}


def stub_enum_header(
    monkeypatch: Any,
    *,
    enum_constants: dict[str, int] | None = None,
    source: bytes = b"enum {}",
) -> None:
    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _h: (source, object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_enum_constants_from_tree",
        lambda *_a: enum_constants or {},
    )


def stub_class_header(
    monkeypatch: Any,
    *,
    class_block: str | None = "class A{}",
    cfg_enum: str | None = None,
    object_class_enum: str | None = None,
    enum_constants: dict[str, int] | None = None,
) -> None:
    stub_enum_header(
        monkeypatch,
        enum_constants=enum_constants,
        source=b"class A{}",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_class_block",
        lambda _text, _owner: class_block,
    )
    if cfg_enum is not None:
        monkeypatch.setattr(
            headerdefs_enums_mod,
            "_extract_cfg_enum_from_method_text",
            lambda _text, _method: cfg_enum,
        )
    if object_class_enum is not None:
        monkeypatch.setattr(
            headerdefs_enums_mod,
            "_extract_object_class_enum_from_method_text",
            lambda _text, _method: object_class_enum,
        )


def ts_node(type_name: str, **attrs: object) -> SimpleNamespace:
    data = {"type": type_name, "children": []}
    data.update(attrs)
    return SimpleNamespace(**data)


def cache_clear(func: object) -> None:
    clear = getattr(func, "cache_clear", None)
    if clear is not None:
        clear()


def patch_builtin_type_indexers(monkeypatch: Any) -> None:
    """Stub fields-YAML indexers so builders only see headerdefs data."""
    monkeypatch.setattr(builtin_io_mod, "_index_fields_by_type", lambda _d: {})
    monkeypatch.setattr(builtin_prog_mod, "_index_fields_by_type", lambda: {})
    monkeypatch.setattr(
        builtin_proto_mod, "_index_proto_entries", lambda _d: {}
    )


def blank_objectid_decoder() -> objectid_mod.ObjectIdDecoder:
    """Create a decoder instance without bootstrapping live header data."""
    decoder = objectid_mod.ObjectIdDecoder.__new__(
        objectid_mod.ObjectIdDecoder
    )
    decoder.bit_fields = {}
    decoder.object_types = {}
    decoder.dtype_info = {}
    decoder.io_classes = {}
    decoder.proto_classes = {}
    decoder.prog_classes = {}
    return decoder
