# tools/dawnpy/src/dawnpy/descriptor/definitions/system_family.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Built-in System (OBJTYPE_ANY) TypeRegistration.

Mirrors :mod:`dawnpy.descriptor.definitions.io_family`. Header discovery
supplies the built-in System type list (``CSystem*`` classes); config-item
schemas are declared here per yaml_type.
"""

from collections.abc import Callable

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.descriptor.definitions.type_info import (
    ConfigField,
    SystemTypeInfo,
    TypeRegistration,
)
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import HeaderBundle


def _lte_fields(cpp_class: str) -> list[ConfigField]:
    """Config items for the LTE System object (cls = SYS_CLASS_LTE)."""
    return [
        ConfigField(
            name="apn",
            cpp_helper=f"{cpp_class}::cfgIdApn",
            value_type="string",
        ),
        ConfigField(
            name="username",
            cpp_helper=f"{cpp_class}::cfgIdUsername",
            value_type="string",
        ),
        ConfigField(
            name="password",
            cpp_helper=f"{cpp_class}::cfgIdPassword",
            value_type="string",
        ),
        ConfigField(
            name="auth_type",
            cpp_helper=f"{cpp_class}::cfgIdAuthType",
            value_type="int",
        ),
        ConfigField(
            name="ip_type",
            cpp_helper=f"{cpp_class}::cfgIdIpType",
            value_type="int",
        ),
        ConfigField(
            name="reg_timeout",
            cpp_helper=f"{cpp_class}::cfgIdRegTimeout",
            value_type="int",
        ),
    ]


# yaml_type -> builder(cpp_class) -> config field list
_SYSTEM_FIELDS: dict[str, Callable[[str], list[ConfigField]]] = {
    "lte": _lte_fields,
}


def build_registration(
    defs: HeaderBundle | None = None,
) -> TypeRegistration:
    """Build the built-in System :class:`TypeRegistration`."""
    source = defs if defs is not None else header_bundle.load_header_bundle()
    items = source.type_defs.get("system_types", [])
    if not isinstance(items, list):
        raise HeaderDefsError("Header System type definitions are invalid")

    system_types: dict[str, SystemTypeInfo] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        yaml_type = item["yaml_type"]
        cpp_class = item["cpp_class"]
        builder = _SYSTEM_FIELDS.get(yaml_type)
        fields = builder(cpp_class) if builder is not None else []
        system_types[yaml_type] = SystemTypeInfo(
            cpp_class=cpp_class,
            header=item["header"],
            config_fields=fields,
        )
    return TypeRegistration(name="builtin-system", system_types=system_types)
