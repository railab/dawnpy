# tools/dawnpy/src/dawnpy/descriptor/definitions.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Dawn descriptor type mappings loaded from C++ headers.

Out-of-tree projects extend the type registry by exposing a
``dawnpy.extensions`` entry-point named ``descriptor_types`` that returns a
:class:`TypeRegistration`. See ``Documentation/customization.rst`` for the
full guide.
"""

import importlib.util
import sys
from collections.abc import Iterable, Mapping
from importlib.metadata import entry_points
from pathlib import Path
from typing import (
    Any,
    TypeVar,
)

# Re-export the public TypeInfo dataclasses so consumers and OOT users
# can keep importing them from dawnpy.descriptor.definitions.registry.
from dawnpy.descriptor.definitions.type_info import (  # noqa: F401
    ConfigField as ConfigField,
)
from dawnpy.descriptor.definitions.type_info import IOTypeInfo as IOTypeInfo
from dawnpy.descriptor.definitions.type_info import (
    ProgTypeInfo as ProgTypeInfo,
)
from dawnpy.descriptor.definitions.type_info import (
    ProtoTypeInfo as ProtoTypeInfo,
)
from dawnpy.descriptor.definitions.type_info import (
    TypeRegistration as TypeRegistration,
)
from dawnpy.headerdefs import (
    HeaderDefsError,
    load_header_defs,
)
from dawnpy.logger import logger

_T = TypeVar("_T")


# Load data type mappings from headers
def _load_dtype_map() -> dict[str, str]:
    """Load data type mapping from Dawn headers."""
    defs = load_header_defs()
    dtype_entries = defs.get("dtype", [])
    if not isinstance(dtype_entries, list):
        raise HeaderDefsError("Header dtype definitions are invalid")

    dtype_map: dict[str, str] = {}
    for dtype in dtype_entries:
        if not isinstance(dtype, dict):
            continue
        yaml_type = str(dtype.get("type", "")).lower()
        name = str(dtype.get("name", ""))
        if yaml_type and name:
            dtype_map[yaml_type] = f"SObjectId::{name}"
    if not dtype_map:
        raise HeaderDefsError("No dtype definitions loaded from headers")
    return dtype_map


def _load_dtype_initval_param_map() -> dict[str, int]:
    """Load cfgIdInitval dtype parameter mapping from Dawn headers."""
    defs = load_header_defs()
    dtype_entries = defs.get("dtype", [])
    if not isinstance(dtype_entries, list):
        raise HeaderDefsError("Header dtype definitions are invalid")

    dtype_map: dict[str, int] = {}
    for dtype in dtype_entries:
        if not isinstance(dtype, dict):
            continue
        yaml_type = str(dtype.get("type", "")).lower()
        initval_param = dtype.get("initval_param")
        if yaml_type and isinstance(initval_param, int):
            dtype_map[yaml_type] = initval_param
    return dtype_map


# --- Out-of-tree extension API ---------------------------------------------
# IOTypeInfo / ProgTypeInfo / ProtoTypeInfo / TypeRegistration / ConfigField
# are re-exported from dawnpy.descriptor.definitions.type_info above.


def _merge_one(
    reg_name: str,
    kind: str,
    yaml_type: str,
    incoming: _T,
    existing: _T | None,
) -> _T:
    """Merge one TypeInfo entry. Override the spec, append config_fields.

    When ``existing`` is ``None``, the incoming TypeInfo wins unchanged.
    Otherwise the incoming spec replaces the existing one (cpp_class,
    header, helper_func, ...) and the existing ``config_fields`` are
    prepended to the incoming list so user-defined fields extend rather
    than erase built-in ones. Built-in fields stay first, followed by
    OOT user fields.
    """
    if existing is None:
        return incoming
    logger.warning(
        "TypeRegistration '%s' overrides built-in %s type '%s' "
        "(config_fields will be appended to the built-in set)",
        reg_name,
        kind,
        yaml_type,
    )
    existing_fields = list(getattr(existing, "config_fields", []))
    incoming_fields = list(getattr(incoming, "config_fields", []))
    if existing_fields and hasattr(incoming, "config_fields"):
        # Mutating the dataclass in place keeps the public TypeInfo
        # references valid for any caller that already imported them.
        incoming.config_fields = (
            existing_fields + incoming_fields
        )  # pragma: no cover
    return incoming


def _merge_into(
    reg_name: str,
    kind: str,
    src: Mapping[str, _T],
    dst: dict[str, _T],
) -> None:
    for yaml_type, info in src.items():
        dst[yaml_type] = _merge_one(
            reg_name, kind, yaml_type, info, dst.get(yaml_type)
        )


def _apply_registration(
    reg: TypeRegistration,
    io_types: dict[str, IOTypeInfo],
    prog_types: dict[str, ProgTypeInfo],
    proto_types: dict[str, ProtoTypeInfo],
) -> None:
    """Merge a single registration into the in-memory type dicts."""
    _merge_into(reg.name, "io", reg.io_types, io_types)
    _merge_into(reg.name, "prog", reg.prog_types, prog_types)
    _merge_into(reg.name, "proto", reg.proto_types, proto_types)


def _iter_registrations() -> list[TypeRegistration]:
    """Collect TypeRegistration entries from installed plugins."""
    out: list[TypeRegistration] = []
    try:
        eps = entry_points(group="dawnpy.extensions")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to enumerate dawnpy.extensions: %s", exc)
        return out

    for entry in eps:
        if entry.name != "descriptor_types":
            continue
        try:
            value = entry.load()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to load dawnpy.extensions:descriptor_types '%s': %s",
                entry.value,
                exc,
            )
            continue

        # Allow either a single TypeRegistration or an iterable of them.
        items = [value] if isinstance(value, TypeRegistration) else list(value)
        for reg in items:
            if not isinstance(reg, TypeRegistration):
                logger.warning(
                    "Ignoring non-TypeRegistration entry from %s: %r",
                    entry.value,
                    reg,
                )
                continue
            out.append(reg)
            logger.info(
                "Loaded dawnpy TypeRegistration '%s' "
                "(io=%d prog=%d proto=%d)",
                reg.name,
                len(reg.io_types),
                len(reg.prog_types),
                len(reg.proto_types),
            )
    return out


# Load all type mappings at module initialization. Built-in types are
# applied through the same _apply_registration path used by OOT plugins
# so the built-in and OOT extension shapes match (single TypeRegistration
# pattern). The deferred-import inside builtin_types.* breaks the
# circular dependency on the IOTypeInfo / ProgTypeInfo / ProtoTypeInfo
# / TypeRegistration classes defined above.
DTYPE_MAP: dict[str, str] = _load_dtype_map()
DTYPE_INITVAL_PARAM_MAP: dict[str, int] = _load_dtype_initval_param_map()
IO_TYPES: dict[str, IOTypeInfo] = {}
PROG_TYPES: dict[str, ProgTypeInfo] = {}
PROTO_TYPES: dict[str, ProtoTypeInfo] = {}


def _bootstrap_builtin_types() -> None:
    """Apply built-in TypeRegistration objects into the module dicts."""
    from dawnpy.descriptor.definitions import load_builtin_registrations

    for reg in load_builtin_registrations():
        _apply_registration(reg, IO_TYPES, PROG_TYPES, PROTO_TYPES)


_bootstrap_builtin_types()

# Apply user TypeRegistration plugins from installed Python packages.
for _reg in _iter_registrations():  # pragma: no cover
    _apply_registration(_reg, IO_TYPES, PROG_TYPES, PROTO_TYPES)


# --- Path-based loading (no install needed) --------------------------------


def load_registrations_from_path(path: Path) -> list[TypeRegistration]:
    """Load TypeRegistration objects from an arbitrary Python file or package.

    Accepts a path to either:

    - a single ``.py`` file containing a module-level ``registration``
      (single :class:`TypeRegistration`) or ``registrations`` (iterable),
    - a directory whose ``__init__.py`` exposes the same attributes.

    The module is loaded directly via ``importlib.util`` (no install, no
    site-packages mutation, no entry-point machinery). The OOT project
    points dawnpy at the file with ``--types-from PATH``.

    :param path: File or directory to load.
    :return: List of TypeRegistration objects (zero or more).
    :raises FileNotFoundError: If the path does not exist.
    :raises AttributeError: If the loaded module exposes neither
        ``registration`` nor ``registrations``.
    """
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"--types-from path does not exist: {src}")

    if src.is_dir():
        init = src / "__init__.py"
        if not init.exists():
            raise FileNotFoundError(
                f"--types-from directory has no __init__.py: {src}"
            )
        module_file = init
        # Synthesize a stable module name from the directory name.
        module_name = f"_dawnpy_types_from_{src.name}"
    else:
        module_file = src
        module_name = f"_dawnpy_types_from_{src.stem}"

    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(
            f"Could not build module spec for --types-from path: {src}"
        )
    module = importlib.util.module_from_spec(spec)
    # Register so relative imports inside multi-file packages work.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if hasattr(module, "registrations"):
        items: Iterable[Any] = module.registrations
    elif hasattr(module, "registration"):
        items = [module.registration]
    else:
        raise AttributeError(
            f"--types-from module {src} exposes neither 'registration' "
            "nor 'registrations'"
        )

    out: list[TypeRegistration] = []
    for item in items:
        if not isinstance(item, TypeRegistration):
            raise TypeError(
                f"--types-from module {src} produced a non-TypeRegistration "
                f"value: {item!r}"
            )
        out.append(item)
    return out


def apply_registration_to_module(reg: TypeRegistration) -> None:
    """Merge ``reg`` into the live module-level type dicts.

    Mutates :data:`IO_TYPES`, :data:`PROG_TYPES`, :data:`PROTO_TYPES` in
    place so any code that subsequently consults those dicts sees the
    new entries. Used by the ``--types-from`` CLI flag to apply
    registrations after the module-level import has already completed.
    """
    _apply_registration(reg, IO_TYPES, PROG_TYPES, PROTO_TYPES)


def get_io_helper_call(
    io_type: str,
    subtype: str | None,
    variant: str | None,
    dtype: str,
    instance: int,
    flags: dict[str, Any],
) -> tuple[str, str]:
    """
    Generate C++ helper function call for IO object.

    :param io_type: IO type name
    :param subtype: Optional subtype (for sensor)
    :param variant: Optional variant (for sysinfo, etc.)
    :param dtype: Data type name
    :param instance: Instance number
    :param flags: Configuration flags
    :return: Tuple of (cpp_class_name, helper_call)
    """
    if io_type not in IO_TYPES:
        raise ValueError(f"Unknown IO type: {io_type}")

    info = IO_TYPES[io_type]
    cpp_class = info.cpp_class

    # Handle special cases
    if io_type in [
        "adc_fetch",
        "adc_sync",
        "adc_stream",
        "dac",
        "leds",
        "buttons",
        "pwm",
    ]:
        # ADC/DAC/Leds/Buttons use (timestamp, instance) signature, no dtype
        timestamp = str(flags.get("timestamp", False)).lower()
        helper = info.helper_func.format(cpp_class=cpp_class)
        return cpp_class, f"{helper}({timestamp}, {instance})"

    elif io_type == "sensor" and subtype:
        # Sensor uses subtype-specific helper: CIOSensor::objectIdTemp
        subtype_cap = subtype.capitalize()
        helper = info.helper_func.format(
            cpp_class=cpp_class, subtype=subtype_cap
        )
        dtype_cpp = DTYPE_MAP.get(dtype, "SObjectId::DTYPE_ANY")
        timestamp = str(flags.get("timestamp", False)).lower()
        return cpp_class, f"{helper}({dtype_cpp}, {timestamp}, {instance})"

    elif io_type in ["sysinfo", "uname", "boardctl"] and variant:
        # System IOs use variant-specific helpers
        # Convert snake_case to CamelCase (reset_cause -> ResetCause)
        variant_cap = "".join(word.capitalize() for word in variant.split("_"))
        helper = info.helper_func.format(
            cpp_class=cpp_class, variant=variant_cap
        )
        # These often have specific signatures - handle case by case
        if io_type == "sysinfo" and variant == "uptime":
            return cpp_class, f"{helper}()"
        elif io_type == "sysinfo" and variant == "cpuload":
            dtype_cpp = DTYPE_MAP.get(dtype, "SObjectId::DTYPE_FLOAT")
            return cpp_class, f"{helper}({dtype_cpp})"
        elif io_type == "boardctl":
            return cpp_class, f"{helper}()"
        elif io_type == "uname" and variant == "hostname":
            return cpp_class, f"{helper}()"

    # Standard case
    dtype_cpp = DTYPE_MAP.get(dtype, "SObjectId::DTYPE_ANY")
    call = info.generate_helper_call(
        cpp_class, dtype_cpp, flags, instance, variant
    )
    return cpp_class, call


def get_prog_helper_call(prog_type: str, instance: int) -> tuple[str, str]:
    """
    Generate C++ helper function call for Program object.

    :param prog_type: Program type name
    :param instance: Instance number
    :return: Tuple of (cpp_class_name, helper_call)
    """
    if prog_type not in PROG_TYPES:
        raise ValueError(f"Unknown Program type: {prog_type}")

    info = PROG_TYPES[prog_type]
    return info.cpp_class, f"{info.cpp_class}::objectId({instance})"


def get_proto_helper_call(proto_type: str, instance: int) -> tuple[str, str]:
    """
    Generate C++ helper function call for Protocol object.

    :param proto_type: Protocol type name
    :param instance: Instance number
    :return: Tuple of (cpp_class_name, helper_call)
    """
    if proto_type not in PROTO_TYPES:
        raise ValueError(f"Unknown Protocol type: {proto_type}")

    info = PROTO_TYPES[proto_type]
    return info.cpp_class, f"{info.cpp_class}::objectId({instance})"
