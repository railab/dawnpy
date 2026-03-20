# tools/dawnpy/src/dawnpy/descriptor/handlers/__init__.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Per-type handlers for built-in IO/PROG/PROTO yaml-tokens.

Each handler module owns the complete behavior for one yaml-token:
cpp_class binding, config_fields schema, binary encoder hook, and optional
generator hooks.

The ``HANDLER_REGISTRY`` dispatches by yaml-token. Built-in descriptor
families collect schemas and binary hooks from these registries.
"""

import importlib
import pkgutil
from types import ModuleType
from typing import cast

from dawnpy.descriptor.handlers._base import (
    IOHandler,
    IOHandlerAdapter,
    ProgHandler,
    ProgHandlerAdapter,
    ProtoHandler,
    ProtoHandlerAdapter,
)

_COMMON_REQUIRED_ATTRS = ("yaml_type", "cpp_class", "config_fields")
_FAMILY_REQUIRED_ATTRS: dict[str, tuple[str, ...]] = {
    "io": (
        *_COMMON_REQUIRED_ATTRS,
        "encode_binary",
        "no_fields",
        "pass_through",
        "dtype",
        "variant_dtypes",
    ),
    "prog": (*_COMMON_REQUIRED_ATTRS, "encode_binary"),
    "proto": (
        *_COMMON_REQUIRED_ATTRS,
        "encode_binary",
        "uses_standard_bindings",
    ),
}


def _io(handler: ModuleType) -> IOHandler:
    """Type one handler module as an IO handler contract."""
    adapter = getattr(handler, "handler", None)
    if adapter is None:
        adapter = IOHandlerAdapter(handler)
    return cast(IOHandler, adapter)


def _prog(handler: ModuleType) -> ProgHandler:
    """Type one handler module as a PROG handler contract."""
    adapter = getattr(handler, "handler", None)
    if adapter is None:
        adapter = ProgHandlerAdapter(handler)
    return cast(ProgHandler, adapter)


def _proto(handler: ModuleType) -> ProtoHandler:
    """Type one handler module as a PROTO handler contract."""
    adapter = getattr(handler, "handler", None)
    if adapter is None:
        adapter = ProtoHandlerAdapter(handler)
    return cast(ProtoHandler, adapter)


def _iter_handler_modules(family: str) -> list[ModuleType]:
    """Import and return all handler modules for one descriptor family."""
    prefix = f"{family}_"
    modules: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(__path__):
        name = module_info.name
        if module_info.ispkg or not name.startswith(prefix):
            continue
        modules.append(importlib.import_module(f".{name}", __name__))
    return modules


def _validate_handler_module(family: str, module: ModuleType) -> str:
    """Validate one module's handler contract and return its yaml token."""
    missing = [
        attr
        for attr in _FAMILY_REQUIRED_ATTRS[family]
        if not hasattr(module, attr)
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"{module.__name__} is missing required {family} handler "
            f"attribute(s): {joined}"
        )
    yaml_type = vars(module).get("yaml_type")
    if not isinstance(yaml_type, str) or not yaml_type:
        raise RuntimeError(
            f"{module.__name__} has invalid {family} handler yaml_type"
        )
    return yaml_type


def _load_io_registry() -> dict[str, IOHandler]:
    """Load all IO handlers from ``io_*.py`` modules."""
    registry: dict[str, IOHandler] = {}
    for module in _iter_handler_modules("io"):
        yaml_type = _validate_handler_module("io", module)
        if yaml_type in registry:
            raise RuntimeError(f"Duplicate IO handler for '{yaml_type}'")
        registry[yaml_type] = _io(module)
    return registry


def _load_prog_registry() -> dict[str, ProgHandler]:
    """Load all PROG handlers from ``prog_*.py`` modules."""
    registry: dict[str, ProgHandler] = {}
    for module in _iter_handler_modules("prog"):
        yaml_type = _validate_handler_module("prog", module)
        if yaml_type in registry:
            raise RuntimeError(f"Duplicate PROG handler for '{yaml_type}'")
        registry[yaml_type] = _prog(module)
    return registry


def _load_proto_registry() -> dict[str, ProtoHandler]:
    """Load all PROTO handlers from ``proto_*.py`` modules."""
    registry: dict[str, ProtoHandler] = {}
    for module in _iter_handler_modules("proto"):
        yaml_type = _validate_handler_module("proto", module)
        if yaml_type in registry:
            raise RuntimeError(f"Duplicate PROTO handler for '{yaml_type}'")
        registry[yaml_type] = _proto(module)
    return registry


# Built-in yaml-tokens are discovered from handlers/<family>_*.py.
IO_HANDLER_REGISTRY = _load_io_registry()
PROG_HANDLER_REGISTRY = _load_prog_registry()
PROTO_HANDLER_REGISTRY = _load_proto_registry()
