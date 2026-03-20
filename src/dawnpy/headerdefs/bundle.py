# tools/dawnpy/src/dawnpy/headerdefs/bundle.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Cached aggregate of generic Dawn header-derived definitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from dawnpy.headerdefs._components import (
    load_header_component_defs,
    load_header_metadata_defs,
)
from dawnpy.headerdefs._enums import (
    load_header_cfg_id_from_defs,
    load_header_enum_map_from_defs,
    load_header_enum_value_ids_from_defs,
    load_header_object_class_name_from_defs,
)
from dawnpy.headerdefs._loader import load_header_defs
from dawnpy.headerdefs._paths import HeaderDefsError
from dawnpy.headerdefs._typespec import load_header_type_defs


@dataclass(frozen=True)
class HeaderDefinitionGroups:
    """Generic definition groups parsed from public Dawn headers."""

    header_defs: dict[str, object]
    type_defs: dict[str, list[dict[str, Any]]]
    metadata_defs: list[dict[str, Any]]
    component_defs: dict[str, list[dict[str, str]]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class HeaderLookupFunctions:
    """Optional lookup overrides used by focused tests."""

    enum_map_loader: Callable[[str, str], dict[str, str]] | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    cfg_id_loader: Callable[[str, str], int] | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    enum_value_ids_loader: Callable[[str, str], dict[str, int]] | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    object_class_name_loader: Callable[[str, str], str] | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class HeaderBundle:
    """Header-backed generic metadata loaded once for runtime consumers."""

    groups: HeaderDefinitionGroups
    lookups: HeaderLookupFunctions = field(
        default_factory=HeaderLookupFunctions
    )

    @property
    def header_defs(self) -> dict[str, object]:
        """Return parsed ObjectId/constants definitions."""
        return self.groups.header_defs

    @property
    def type_defs(self) -> dict[str, list[dict[str, Any]]]:
        """Return parsed IO/Program/Protocol type definitions."""
        return self.groups.type_defs

    @property
    def metadata_defs(self) -> list[dict[str, Any]]:
        """Return parsed descriptor metadata definitions."""
        return self.groups.metadata_defs

    @property
    def component_defs(self) -> dict[str, list[dict[str, str]]]:
        """Return parsed component capability definitions."""
        return self.groups.component_defs

    def dtype_map(self) -> dict[str, str]:
        """Return yaml dtype token -> C++ enum token."""
        dtype_entries = self.header_defs.get("dtype", [])
        if not isinstance(dtype_entries, list):
            raise HeaderDefsError("Header dtype definitions are invalid")

        out: dict[str, str] = {}
        for dtype in dtype_entries:
            if not isinstance(dtype, dict):
                continue
            yaml_type = str(dtype.get("type", "")).lower()
            name = str(dtype.get("name", ""))
            if yaml_type and name:
                out[yaml_type] = f"SObjectId::{name}"
        if not out:
            raise HeaderDefsError("No dtype definitions loaded from headers")
        return out

    def dtype_initval_param_map(self) -> dict[str, int]:
        """Return yaml dtype token -> cfgIdInitval dtype parameter."""
        dtype_entries = self.header_defs.get("dtype", [])
        if not isinstance(dtype_entries, list):
            raise HeaderDefsError("Header dtype definitions are invalid")

        out: dict[str, int] = {}
        for dtype in dtype_entries:
            if not isinstance(dtype, dict):
                continue
            yaml_type = str(dtype.get("type", "")).lower()
            initval_param = dtype.get("initval_param")
            if yaml_type and isinstance(initval_param, int):
                out[yaml_type] = initval_param
        return out

    def enum_map(self, owner: str, enum_prefix: str) -> dict[str, str]:
        """Return yaml enum token -> C++ enum suffix for one owner."""
        if self.lookups.enum_map_loader is not None:
            return self.lookups.enum_map_loader(owner, enum_prefix)
        return load_header_enum_map_from_defs(
            owner, enum_prefix, self.type_defs
        )

    def cfg_id(self, owner: str, method_name: str) -> int:
        """Return the numeric cfg id exposed by a header helper method."""
        if self.lookups.cfg_id_loader is not None:
            return self.lookups.cfg_id_loader(owner, method_name)
        return load_header_cfg_id_from_defs(owner, method_name, self.type_defs)

    def enum_value_ids(self, owner: str, enum_prefix: str) -> dict[str, int]:
        """Return yaml enum token -> numeric enum value for one owner."""
        if self.lookups.enum_value_ids_loader is not None:
            return self.lookups.enum_value_ids_loader(owner, enum_prefix)
        return load_header_enum_value_ids_from_defs(
            owner, enum_prefix, self.type_defs
        )

    def object_class_name(self, owner: str, method_name: str) -> str:
        """Return the YAML object class name exposed by a helper method."""
        if self.lookups.object_class_name_loader is not None:
            return self.lookups.object_class_name_loader(owner, method_name)
        return load_header_object_class_name_from_defs(
            owner, method_name, self.type_defs
        )


@lru_cache(maxsize=1)
def load_header_bundle() -> HeaderBundle:
    """Load all generic header-derived definition groups once per process."""
    return HeaderBundle(
        HeaderDefinitionGroups(
            header_defs=load_header_defs(),
            type_defs=load_header_type_defs(),
            metadata_defs=load_header_metadata_defs(),
            component_defs=load_header_component_defs(),
        )
    )


@lru_cache(maxsize=None)
def load_header_enum_map(owner: str, enum_prefix: str) -> dict[str, str]:
    """Return yaml enum token -> C++ enum suffix for one owner."""
    return load_header_bundle().enum_map(owner, enum_prefix)


@lru_cache(maxsize=None)
def load_header_cfg_id(owner: str, method_name: str) -> int:
    """Return the numeric cfg id exposed by a header helper method."""
    return load_header_bundle().cfg_id(owner, method_name)


@lru_cache(maxsize=None)
def load_header_enum_value_ids(owner: str, enum_prefix: str) -> dict[str, int]:
    """Return yaml enum token -> numeric enum value for one owner."""
    return load_header_bundle().enum_value_ids(owner, enum_prefix)


@lru_cache(maxsize=None)
def load_header_object_class_name(owner: str, method_name: str) -> str:
    """Return the YAML object class name exposed by a helper method."""
    return load_header_bundle().object_class_name(owner, method_name)


def header_enum_map(owner: str, enum_prefix: str) -> dict[str, str]:
    """Return yaml enum token -> C++ enum suffix for one owner."""
    return load_header_enum_map(owner, enum_prefix)


def header_cfg_id(owner: str, method_name: str) -> int:
    """Return the numeric cfg id exposed by a header helper method."""
    return load_header_cfg_id(owner, method_name)


def header_enum_value_ids(owner: str, enum_prefix: str) -> dict[str, int]:
    """Return yaml enum token -> numeric enum value for one owner."""
    return load_header_enum_value_ids(owner, enum_prefix)


def header_object_class_name(owner: str, method_name: str) -> str:
    """Return the YAML object class name exposed by a helper method."""
    return load_header_object_class_name(owner, method_name)


def header_component_defs() -> dict[str, list[dict[str, Any]]]:
    """Return component definitions from the cached header bundle."""
    return load_header_bundle().component_defs


# Backward-compatible aliases for downstream users of the initial refactor API.
HeaderDefinitionSet = HeaderBundle
load_header_definition_set = load_header_bundle
