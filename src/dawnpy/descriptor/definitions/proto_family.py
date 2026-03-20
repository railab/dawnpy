# tools/dawnpy/src/dawnpy/descriptor/definitions/proto_family.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Built-in PROTO TypeRegistration.

Combines headerdefs class discovery with per-type schemas owned by
``dawnpy.descriptor.handlers.proto_*`` modules. Nested ``enum_prefix``
tokens are hydrated to ``enum_values`` maps via
:func:`dawnpy.headerdefs.load_header_enum_map` so generators see
fully-resolved data.
"""

from dataclasses import dataclass, field
from typing import Any

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.descriptor.definitions.type_info import (
    ConfigField,
    ProtoTypeInfo,
    TypeRegistration,
    _hydrate_enum_values,
)
from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import HeaderBundle

# Standard field for protocols that use the simple bindings shape.
_PROTO_STANDARD_FIELDS: list[ConfigField] = [
    ConfigField(
        name="bindings",
        cpp_helper="{cpp_class}::cfgIdIOBind",
        value_type="id_array",
    ),
]


@dataclass(frozen=True)
class _ProtoEntry:
    """Resolved protocol schema entry."""

    fields: list[ConfigField] = field(default_factory=list)
    uses_standard_bindings: bool = True


# EVERY built-in proto yaml-token is owned by a per-type handler under
# descriptor/handlers/proto_*.py. _index_proto_entries() reads the
# schema and uses_standard_bindings flag from each handler.
_PROTO_ENTRIES: dict[str, _ProtoEntry] = {}


def get_standard_fields() -> list[ConfigField]:
    """Return the PROTO standard-field block (used by ConfigLoader)."""
    return list(_PROTO_STANDARD_FIELDS)


def _index_proto_entries(
    defs: HeaderBundle,
) -> dict[str, _ProtoEntry]:
    """Return ``proto_type -> _ProtoEntry`` indexed.

    Per-type handlers own their own ``config_fields()`` and
    ``uses_standard_bindings`` flag.
    """
    by_type: dict[str, _ProtoEntry] = {}
    for proto_type, entry in _PROTO_ENTRIES.items():
        hydrated = [  # pragma: no cover
            _hydrate_enum_values(f, defs.enum_map) for f in entry.fields
        ]
        by_type[proto_type] = _ProtoEntry(  # pragma: no cover
            fields=hydrated,
            uses_standard_bindings=entry.uses_standard_bindings,
        )
    for yaml_type, handler in PROTO_HANDLER_REGISTRY.items():
        hydrated = [
            _hydrate_enum_values(f, defs.enum_map)
            for f in handler.config_fields()
        ]
        by_type[yaml_type] = _ProtoEntry(
            fields=hydrated,
            uses_standard_bindings=bool(
                getattr(handler, "uses_standard_bindings", True)
            ),
        )
    return by_type


def build_registration(
    defs: HeaderBundle | None = None,
) -> TypeRegistration:
    """Build the built-in PROTO :class:`TypeRegistration`."""
    source = defs if defs is not None else header_bundle.load_header_bundle()
    items: Any = source.type_defs.get("proto_types", [])
    if not isinstance(items, list):
        raise HeaderDefsError("Header Protocol type definitions are invalid")

    entries_by_type = _index_proto_entries(source)
    proto_types: dict[str, ProtoTypeInfo] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        yaml_type = item["yaml_type"]
        entry = entries_by_type.get(yaml_type, _ProtoEntry())
        proto_types[yaml_type] = ProtoTypeInfo(
            cpp_class=item["cpp_class"],
            header=item["header"],
            config_fields=entry.fields,
            uses_standard_bindings=entry.uses_standard_bindings,
        )
    if not proto_types:
        raise HeaderDefsError(
            "No Protocol type definitions loaded from headers"
        )
    return TypeRegistration(name="builtin-proto", proto_types=proto_types)
