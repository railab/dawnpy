# tools/dawnpy/src/dawnpy/descriptor/definitions/prog_family.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Built-in PROG TypeRegistration.

Mirrors :mod:`dawnpy.descriptor.definitions.io_family` for program
types. Header discovery supplies the built-in program list and each
per-type handler supplies the C++ binding policy and config schema.
"""

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.descriptor.definitions.type_info import (
    ConfigField,
    ProgTypeInfo,
    TypeRegistration,
)
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import HeaderBundle

# Standard fields applied to every PROG type. The ``cpp_helper`` uses the
# templated ``{cpp_class}`` token because the generator emits the helper
# bound to the concrete prog class (e.g. CProgStatsAvg::cfgIdIOBind), not
# the abstract base. Templated helpers are skipped by
# ``dawnpy desc-headers-check --strict``.
_PROG_STANDARD_FIELDS: list[ConfigField] = [
    ConfigField(
        name="inputs",
        cpp_helper="{cpp_class}::cfgIdIOBind",
        value_type="id_array",
    ),
    ConfigField(
        name="outputs",
        cpp_helper="{cpp_class}::cfgIdIOBind",
        value_type="id_array",
    ),
]


def get_standard_fields() -> list[ConfigField]:
    """Return the PROG standard-field block (used by ConfigLoader)."""
    return list(_PROG_STANDARD_FIELDS)


def _index_fields_by_type() -> dict[str, list[ConfigField]]:
    """Return ``yaml_type -> [fields]`` from per-type handlers."""
    out: dict[str, list[ConfigField]] = {}
    for yaml_type, handler in PROG_HANDLER_REGISTRY.items():
        out[yaml_type] = list(handler.config_fields())
    return out


def build_registration(
    defs: HeaderBundle | None = None,
) -> TypeRegistration:
    """Build the built-in PROG :class:`TypeRegistration`."""
    source = defs if defs is not None else header_bundle.load_header_bundle()
    items = source.type_defs.get("prog_types", [])
    if not isinstance(items, list):
        raise HeaderDefsError("Header Program type definitions are invalid")

    fields_by_type = _index_fields_by_type()
    prog_types: dict[str, ProgTypeInfo] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        yaml_type = item["yaml_type"]
        prog_types[yaml_type] = ProgTypeInfo(
            cpp_class=item["cpp_class"],
            header=item["header"],
            config_fields=fields_by_type.get(yaml_type, []),
        )
    if not prog_types:
        raise HeaderDefsError(
            "No Program type definitions loaded from headers"
        )
    return TypeRegistration(name="builtin-prog", prog_types=prog_types)
