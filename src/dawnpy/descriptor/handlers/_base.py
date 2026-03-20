# tools/dawnpy/src/dawnpy/descriptor/handlers/_base.py
#
# SPDX-License-Identifier: Apache-2.0
#

from __future__ import annotations

"""Base classes for per-type handlers.

A handler owns EVERYTHING for one yaml-token: the C++ class binding,
the user-facing config field schema, the C++ source generator hook,
and the binary serializer hook. Adding a built-in type = drop one new
file under ``handlers/`` and add it to the matching registry.
"""

from types import ModuleType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from dawnpy.descriptor.definitions.type_info import ConfigField

if TYPE_CHECKING:
    from dawnpy.descriptor.client import ClientIo, ClientProgram
    from dawnpy.descriptor.definitions.objects import IoObject, ProgramObject
    from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
    from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
    from dawnpy.objectid import ObjectIdDecoder

_IO_CLASS_OVERRIDES: dict[str, str] = {
    "gpi": "gpi_single",
    "gpo": "gpo_single",
    "uuid": "system_uuid",
    "systime": "system_systemtime",
    "fileio": "file",
    "descselector": "desc_selector",
}


@runtime_checkable
class IOHandler(Protocol):
    """One IO yaml-token's handler module contract."""

    yaml_type: str
    cpp_class: str
    nuttx_requirements: tuple[str, ...]
    no_fields: bool
    pass_through: bool
    dtype: str | None
    variant_dtypes: dict[str, str]

    @staticmethod
    def config_fields() -> list[ConfigField]:
        """Return the user-facing config schema for this IO type."""
        raise NotImplementedError

    @staticmethod
    def encode_binary(ctx: _IOSerializeContext) -> None:
        """Append binary config items for this IO object into ``ctx``."""
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        """Allow optional per-handler C++ generator hooks."""
        raise NotImplementedError

    def object_class_name(self, obj: IoObject) -> str | None:
        """Return the ObjectID class name for an IO object."""
        raise NotImplementedError

    def dtype_name(self, obj: IoObject) -> str:
        """Return the ObjectID dtype name for an IO object."""
        raise NotImplementedError

    def summary_class_name(self, obj: ClientIo) -> str | None:
        """Return the ObjectID class name for client summaries."""
        raise NotImplementedError

    def summary_dtype_name(self, obj: ClientIo) -> str:
        """Return the dtype name for client summaries."""
        raise NotImplementedError

    def summary_instance(self, obj: ClientIo) -> int:
        """Return the ObjectID instance/priv field for summaries."""
        raise NotImplementedError

    def summary_flags(self, obj: ClientIo) -> int:
        """Return the ObjectID flags field for summaries."""
        raise NotImplementedError


@runtime_checkable
class ProgHandler(Protocol):
    """One PROG yaml-token's handler module contract."""

    yaml_type: str
    cpp_class: str
    nuttx_requirements: tuple[str, ...]

    @staticmethod
    def config_fields() -> list[ConfigField]:
        """Return the user-facing config schema for this prog type."""
        raise NotImplementedError

    @staticmethod
    def encode_binary(
        items: list[tuple[int, list[int]]],
        obj: ProgramObject,
        prog_cls: int,
        obj_ids: dict[str, int],
        decoder: ObjectIdDecoder,
    ) -> None:
        """Append binary config items for this PROG object into ``items``.

        The dispatcher has already resolved obj_ids[obj.obj_id] and the
        prog class enum; the handler only owns the cfg-block payload
        unique to its type.
        """
        raise NotImplementedError

    def object_class_name(self, obj: ProgramObject | ClientProgram) -> str:
        """Return the ObjectID class name for this program."""
        raise NotImplementedError

    def config_reference_cpp_line(
        self,
        obj: ProgramObject,
        field_name: str,
        config_loader: Any,
    ) -> str | None:
        """Return cfgId line when another object references a config field."""
        raise NotImplementedError

    def validate_object(self, obj: ProgramObject) -> list[str]:
        """Return program validation errors owned by this handler."""
        raise NotImplementedError

    def validate_object_refs(
        self, obj: ProgramObject, io_map: dict[str, IoObject]
    ) -> list[str]:
        """Return validation errors that require IO metadata."""
        raise NotImplementedError

    def output_shape_owned_virt_targets(self, obj: ProgramObject) -> set[str]:
        """Return virt IO refs whose output shape is owned by this program."""
        raise NotImplementedError

    def emit_iobind_cpp(
        self,
        lines: list[str],
        obj: ProgramObject,
        total_ids: int,
        format_helper: Any,
        cpp_class: str,
    ) -> bool:
        """Emit custom C++ iobind config and return whether handled."""
        raise NotImplementedError


@runtime_checkable
class ProtoHandler(Protocol):
    """One PROTO yaml-token's handler module contract."""

    yaml_type: str
    cpp_class: str
    nuttx_requirements: tuple[str, ...]
    uses_standard_bindings: bool

    @staticmethod
    def config_fields() -> list[ConfigField]:
        """Return the user-facing config schema for this protocol type."""
        raise NotImplementedError

    @staticmethod
    def encode_binary(ctx: _ProtoSerializeContext) -> None:
        """Append binary config items for this protocol object into ``ctx``."""
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        """Allow optional per-handler C++ generator hooks."""
        raise NotImplementedError

    def object_class_name(self, obj: Any) -> str:
        """Return the ObjectID class name for this protocol."""
        raise NotImplementedError

    def resolve_bindings(
        self, bindings: list[str], config: dict[str, Any]
    ) -> list[str]:
        """Return protocol bindings after handler-specific fallbacks."""
        raise NotImplementedError

    def allocation_rows(self, proto: Any) -> list[list[str]]:
        """Return protocol allocation summary rows."""
        raise NotImplementedError

    def allocation_notes(self, proto: Any) -> list[str]:
        """Return protocol-specific notes printed before allocation rows."""
        raise NotImplementedError

    def validate_object(self, obj: Any) -> list[str]:
        """Return protocol validation errors owned by this handler."""
        raise NotImplementedError

    def validate_descriptor_context(
        self,
        proto_id: str,
        config: dict[str, Any],
        objects: dict[str, Any],
    ) -> None:
        """Validate protocol rules that need access to all objects."""
        raise NotImplementedError

    def cfg_id_helpers(self) -> dict[str, tuple[str, str]]:
        """Return cfg-id helpers this protocol encoder needs."""
        raise NotImplementedError

    def dtype_names(self) -> dict[str, str]:
        """Return dtype names this protocol encoder needs."""
        raise NotImplementedError

    def enum_value_maps(self) -> dict[str, tuple[str, str]]:
        """Return enum maps this protocol encoder needs."""
        raise NotImplementedError

    def defaults(self) -> dict[str, Any]:
        """Return protocol encoder defaults."""
        raise NotImplementedError

    def fixed_string_bytes(self) -> dict[str, int]:
        """Return fixed string widths this protocol encoder needs."""
        raise NotImplementedError

    def is_multi_device(self) -> bool:
        """Return whether protocol supports multiple descriptors."""
        raise NotImplementedError


class ModuleHandlerAdapter:
    """Class-based facade around a module-level handler.

    Handler files export constants/functions. The registry stores adapter
    instances so consumers depend on one class policy surface while each
    handler file stays small and explicit.
    """

    def __init__(self, module: ModuleType) -> None:
        """Store the wrapped module."""
        self._module = module

    def __getattr__(self, name: str) -> Any:
        """Delegate optional handler hooks to the wrapped module."""
        return getattr(self._module, name)

    @property
    def yaml_type(self) -> str:
        """Return this handler's YAML token."""
        return str(vars(self._module)["yaml_type"])

    @property
    def cpp_class(self) -> str:
        """Return this handler's C++ class binding."""
        return str(vars(self._module)["cpp_class"])

    @property
    def nuttx_requirements(self) -> tuple[str, ...]:
        """Return NuttX Kconfig symbols required by this handler."""
        value = getattr(self._module, "nuttx_requirements", ())
        return tuple(str(item) for item in value)

    def config_fields(self) -> list[ConfigField]:
        """Return this handler's config field schema."""
        return list(vars(self._module)["config_fields"]())


class IOHandlerAdapter(ModuleHandlerAdapter):
    """Default IO policy plus module-handler delegation."""

    @property
    def no_fields(self) -> bool:
        """Return whether the IO has no per-instance fields."""
        return bool(vars(self._module)["no_fields"])

    @property
    def pass_through(self) -> bool:
        """Return whether the IO stores an opaque block."""
        return bool(vars(self._module)["pass_through"])

    @property
    def dtype(self) -> str | None:
        """Return the forced dtype, if this IO owns one."""
        value = vars(self._module)["dtype"]
        return str(value) if value is not None else None

    @property
    def variant_dtypes(self) -> dict[str, str]:
        """Return variant-specific forced dtypes."""
        return dict(vars(self._module)["variant_dtypes"])

    def encode_binary(self, ctx: _IOSerializeContext) -> None:
        """Delegate binary encoding to the wrapped module."""
        vars(self._module)["encode_binary"](ctx)

    def object_class_name(self, obj: IoObject) -> str | None:
        """Return the ObjectID class name for an IO object."""
        custom = getattr(self._module, "object_class_name", None)
        if custom is not None:
            value = custom(obj)
            if value is None:
                return None
            return str(value)
        return _default_io_class_name(obj.io_type, obj.subtype, obj.variant)

    def dtype_name(self, obj: IoObject) -> str:
        """Return the ObjectID dtype name for an IO object."""
        forced = self._dtype_for_variant(obj.variant)
        return forced if forced is not None else str(obj.dtype).lower()

    def summary_class_name(self, obj: ClientIo) -> str | None:
        """Return the ObjectID class name for client summaries."""
        custom = getattr(self._module, "summary_class_name", None)
        if custom is not None:
            value = custom(obj)
            if value is None:
                return None
            return str(value)
        return _default_io_class_name(obj.io_type, obj.subtype, obj.variant)

    def summary_dtype_name(self, obj: ClientIo) -> str:
        """Return the ObjectID dtype name for client summaries."""
        custom = getattr(self._module, "summary_dtype_name", None)
        if custom is not None:
            return str(custom(obj))
        forced = self._dtype_for_variant(obj.variant)
        if forced is not None:
            return forced
        if self.dtype is not None:
            return self.dtype
        return str(obj.dtype).lower()

    def summary_instance(self, obj: ClientIo) -> int:
        """Return the ObjectID instance/priv field for client summaries."""
        custom = getattr(self._module, "summary_instance", None)
        if custom is not None:
            return int(custom(obj))
        if obj.io_type in ("sysinfo", "systime"):
            return 1
        if obj.io_type == "boardctl":
            return 0
        return int(obj.instance)

    def summary_flags(self, obj: ClientIo) -> int:
        """Return the ObjectID flags field for client summaries."""
        custom = getattr(self._module, "summary_flags", None)
        if custom is not None:
            return int(custom(obj))
        if obj.io_type == "systime":
            return int(obj.instance) & 0x3
        return 1 if obj.timestamp else 0

    def _dtype_for_variant(self, variant: object) -> str | None:
        """Return forced dtype for ``variant``, if any."""
        if variant is None:
            return None
        return self.variant_dtypes.get(str(variant))


class ProgHandlerAdapter(ModuleHandlerAdapter):
    """Default PROG policy plus module-handler delegation."""

    def encode_binary(
        self,
        items: list[tuple[int, list[int]]],
        obj: ProgramObject,
        prog_cls: int,
        obj_ids: dict[str, int],
        decoder: ObjectIdDecoder,
    ) -> None:
        """Delegate binary encoding to the wrapped module."""
        vars(self._module)["encode_binary"](
            items, obj, prog_cls, obj_ids, decoder
        )

    def object_class_name(self, obj: ProgramObject | ClientProgram) -> str:
        """Return the ObjectID class name for this program."""
        custom = getattr(self._module, "object_class_name", None)
        if custom is not None:
            return str(custom(obj))
        try:
            from dawnpy.headerdefs import load_header_object_class_name

            return load_header_object_class_name(self.cpp_class, "objectId")
        except Exception:
            return str(obj.prog_type)

    def config_reference_cpp_line(
        self,
        obj: ProgramObject,
        field_name: str,
        config_loader: Any,
    ) -> str | None:
        """Return cfgId line when ConfigIO references a program field."""
        custom = getattr(self._module, "config_reference_cpp_line", None)
        if custom is not None:
            value = custom(obj, field_name, config_loader)
            return str(value) if value is not None else None
        field_defs = config_loader.get_prog_type_fields(obj.prog_type)
        field = next((f for f in field_defs if f.name == field_name), None)
        if field is None or not field.cpp_helper:
            return None
        return f"{field.cpp_helper}(),"

    def validate_object(self, obj: ProgramObject) -> list[str]:
        """Return program validation errors owned by this handler."""
        custom = getattr(self._module, "validate_object", None)
        if custom is not None:
            return list(custom(obj))
        rule = getattr(self._module, "binding_rule", None)
        if rule is None:
            return []
        expected_inputs, expected_outputs = tuple(rule)
        errors: list[str] = []
        if len(obj.inputs) != expected_inputs:
            errors.append(
                f"{obj.prog_type} requires exactly {expected_inputs} input"
                f"{'' if expected_inputs == 1 else 's'}"
            )
        if len(obj.outputs) != expected_outputs:
            errors.append(
                f"{obj.prog_type} requires exactly {expected_outputs} output"
                f"{'' if expected_outputs == 1 else 's'}"
            )
        return errors

    def validate_object_refs(
        self, obj: ProgramObject, io_map: dict[str, IoObject]
    ) -> list[str]:
        """Return validation errors that require IO metadata."""
        custom = getattr(self._module, "validate_object_refs", None)
        if custom is None:
            return []
        return list(custom(obj, io_map))

    def output_shape_owned_virt_targets(self, obj: ProgramObject) -> set[str]:
        """Return virt IO refs whose output shape is owned by this program."""
        owns_shape = bool(getattr(self._module, "owns_output_shape", True))
        if not owns_shape:
            return set()
        custom = getattr(self._module, "output_shape_owned_virt_targets", None)
        if custom is not None:
            return set(custom(obj))

        from dawnpy.descriptor.support.utils import resolve_references

        config = obj.config if isinstance(obj.config, dict) else {}
        outputs = config.get("outputs", obj.outputs)
        if not isinstance(outputs, list):
            return set()
        return set(resolve_references(outputs))

    def emit_iobind_cpp(
        self,
        lines: list[str],
        obj: ProgramObject,
        total_ids: int,
        format_helper: Any,
        cpp_class: str,
    ) -> bool:
        """Emit custom C++ iobind config and return whether handled."""
        custom = getattr(self._module, "emit_iobind_cpp", None)
        if custom is None:
            return False
        return bool(custom(lines, obj, total_ids, format_helper, cpp_class))


class ProtoHandlerAdapter(ModuleHandlerAdapter):
    """Default PROTO policy plus module-handler delegation."""

    @property
    def uses_standard_bindings(self) -> bool:
        """Return whether this protocol uses the generic bindings field."""
        return bool(vars(self._module)["uses_standard_bindings"])

    def encode_binary(self, ctx: _ProtoSerializeContext) -> None:
        """Delegate binary encoding to the wrapped module."""
        vars(self._module)["encode_binary"](ctx)

    def object_class_name(self, obj: Any) -> str:
        """Return the ObjectID class name for this protocol."""
        custom = getattr(self._module, "object_class_name", None)
        if custom is not None:
            return str(custom(obj))
        proto_type = str(getattr(obj, "proto_type", self.yaml_type))
        try:
            from dawnpy.headerdefs import load_header_object_class_name

            return load_header_object_class_name(self.cpp_class, "objectId")
        except Exception:
            return proto_type

    def resolve_bindings(
        self, bindings: list[str], config: dict[str, Any]
    ) -> list[str]:
        """Return protocol bindings after handler-specific fallbacks."""
        custom = getattr(self._module, "resolve_bindings", None)
        if custom is not None:
            return list(custom(bindings, config))
        return bindings

    def allocation_rows(self, proto: Any) -> list[list[str]]:
        """Return protocol allocation summary rows."""
        custom = getattr(self._module, "allocation_rows", None)
        if custom is not None:
            return list(custom(proto))
        return [["0", "n/a", "n/a", "n/a", "0", "unsupported protocol"]]

    def allocation_notes(self, proto: Any) -> list[str]:
        """Return protocol-specific notes printed before allocation rows."""
        custom = getattr(self._module, "allocation_notes", None)
        if custom is None:
            return []
        return list(custom(proto))

    def validate_object(self, obj: Any) -> list[str]:
        """Return protocol validation errors owned by this handler."""
        custom = getattr(self._module, "validate_object", None)
        if custom is None:
            return []
        return list(custom(obj))

    def validate_descriptor_context(
        self,
        proto_id: str,
        config: dict[str, Any],
        objects: dict[str, Any],
    ) -> None:
        """Validate protocol rules that need access to all objects."""
        custom = getattr(self._module, "validate_descriptor_context", None)
        if custom is not None:
            custom(proto_id, config, objects)

    def cfg_id_helpers(self) -> dict[str, tuple[str, str]]:
        """Return cfg-id helpers declared by the handler."""
        return dict(getattr(self._module, "cfg_id_helpers", {}))

    def dtype_names(self) -> dict[str, str]:
        """Return dtype names declared by the handler."""
        return dict(getattr(self._module, "dtype_names", {}))

    def enum_value_maps(self) -> dict[str, tuple[str, str]]:
        """Return enum maps declared by the handler."""
        return dict(getattr(self._module, "enum_value_maps", {}))

    def defaults(self) -> dict[str, Any]:
        """Return encoder defaults declared by the handler."""
        return dict(getattr(self._module, "defaults", {}))

    def fixed_string_bytes(self) -> dict[str, int]:
        """Return fixed string widths declared by the handler."""
        return dict(getattr(self._module, "fixed_string_bytes", {}))

    def is_multi_device(self) -> bool:
        """Return whether protocol supports multiple descriptors."""
        return bool(getattr(self._module, "multi_device", False))


def _sensor_summary_suffix(subtype: str) -> str:
    """Return ObjectID class suffix for a sensor subtype."""
    subtype_map = {
        "temp": "temperature",
        "accel": "accelerometer",
        "gyro": "gyroscope",
        "mag": "magneticfield",
        "baro": "barometer",
        "hum": "humidity",
        "light": "light",
        "prox": "proximity",
        "gas": "gas",
    }
    return subtype_map.get(subtype, subtype)


def _default_io_class_name(
    io_type: str, subtype: str | None, variant: object | None
) -> str | None:
    """Return default ObjectID class name for an IO token."""
    if io_type == "sensor":
        if not subtype:
            return None
        return f"sensor_{_sensor_summary_suffix(subtype)}"
    if io_type in ("sysinfo", "uname", "boardctl"):
        return _variant_io_class_name(io_type, variant)
    return _IO_CLASS_OVERRIDES.get(io_type, io_type)


def _variant_io_class_name(io_type: str, variant: object | None) -> str | None:
    """Return ObjectID class name for variant-driven IO tokens."""
    if variant is None:
        return None
    variant_str = str(variant)
    if io_type == "sysinfo":
        return f"system_{variant_str}"
    if io_type == "uname":
        return "system_hostname" if variant_str == "hostname" else None
    if io_type == "boardctl":
        if variant_str == "reset":
            return "system_reset"
        if variant_str == "reset_cause":
            return "system_resetcause"
        if variant_str == "poweroff":
            return "system_poweroff"
    return None
