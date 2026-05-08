# tools/dawnpy/src/dawnpy/descriptor/definitions/io_family.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Built-in IO TypeRegistration.

Combines headerdefs class discovery with per-type schemas owned by
``dawnpy.descriptor.handlers.io_*`` modules. Each schema lists which
``config:`` keys are accepted under its IO yaml-token and how each maps
to a ``cpp_helper``. ``enum_prefix`` tokens are hydrated to
``enum_values`` maps via ``dawnpy.headerdefs.load_header_enum_map``.
"""

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.descriptor.definitions.type_info import (
    ConfigField,
    IOTypeInfo,
    TypeRegistration,
    _hydrate_enum_values,
)
from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import HeaderBundle

# Common fields shared by every IO type. Emitted by config_loader as the
# ``common_fields`` block.
_IO_COMMON_FIELDS: list[ConfigField] = [
    ConfigField(
        name="device",
        cpp_helper="CIOCommon::cfgIdDevno",
        value_type="int",
    ),
    ConfigField(
        name="notify",
        cpp_helper="CIOCommon::cfgIdNotify",
        value_type="notify",
    ),
    ConfigField(
        # The ``limits`` block expands into three cfg items
        # (cfgIdLimit{Min,Max,Step}); cpp_helper is left empty because the
        # generators emit the three real helpers from the value-type
        # branch.
        name="limits",
        value_type="limits",
    ),
]


# EVERY IO yaml-token's per-instance config schema lives on its handler
# under descriptor/handlers/io_*.py. _index_fields_by_type() builds the
# map by walking IO_HANDLER_REGISTRY only.
_IO_FIELDS_BY_TYPE: dict[str, list[ConfigField]] = {}


def get_common_fields() -> list[ConfigField]:
    """Return the IO common-field block (used by ConfigLoader)."""
    return list(_IO_COMMON_FIELDS)


def _index_fields_by_type(
    defs: HeaderBundle,
) -> dict[str, list[ConfigField]]:
    """Return ``yaml_type -> [hydrated fields]`` from handlers."""
    by_type: dict[str, list[ConfigField]] = {}
    for io_type, fields in _IO_FIELDS_BY_TYPE.items():
        by_type[io_type] = [  # pragma: no cover
            _hydrate_enum_values(f, defs.enum_map) for f in fields
        ]
    # Per-type handlers each own their own schema; merge them in.
    for yaml_type, handler in IO_HANDLER_REGISTRY.items():
        by_type[yaml_type] = [
            _hydrate_enum_values(f, defs.enum_map)
            for f in handler.config_fields()
        ]
    return by_type


def build_registration(
    defs: HeaderBundle | None = None,
) -> TypeRegistration:
    """Build the built-in IO :class:`TypeRegistration`."""
    source = defs if defs is not None else header_bundle.load_header_bundle()
    items = source.type_defs.get("io_types", [])
    if not isinstance(items, list):
        raise HeaderDefsError("Header IO type definitions are invalid")

    fields_by_type = _index_fields_by_type(source)
    io_types: dict[str, IOTypeInfo] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        yaml_type = item["yaml_type"]
        io_types[yaml_type] = IOTypeInfo(
            cpp_class=item["cpp_class"],
            header=item["header"],
            helper_func=item["helper_func"],
            params=item["params"],
            subtypes=item.get("subtypes"),
            variants=item.get("variants"),
            config_fields=fields_by_type.get(yaml_type, []),
        )
    if not io_types:
        raise HeaderDefsError("No IO type definitions loaded from headers")
    return TypeRegistration(name="builtin-io", io_types=io_types)
