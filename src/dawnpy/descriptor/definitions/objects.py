# tools/dawnpy/src/dawnpy/descriptor/definitions/objects.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor object decoding and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dawnpy.descriptor.definitions.registry import (
    DTYPE_INITVAL_PARAM_MAP,
    DTYPE_MAP,
    IO_TYPES,
    PROG_TYPES,
    PROTO_TYPES,
    get_io_helper_call,
    get_prog_helper_call,
    get_proto_helper_call,
)
from dawnpy.descriptor.handlers import (
    PROG_HANDLER_REGISTRY,
    PROTO_HANDLER_REGISTRY,
)
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)


class DescriptorDecodeError(ValueError):
    """Raised when a descriptor object fails validation."""


@dataclass(frozen=True)
class DescriptorObject:
    """Base descriptor object."""

    obj_id: str

    @property
    def macro_name(self) -> str:
        """Return the uppercase macro name for this object."""
        return self.obj_id.upper()

    @property
    def category(self) -> str:
        """Return object category."""
        raise NotImplementedError

    def validate(self) -> list[str]:
        """Return validation errors for this object."""
        return []

    def get_header(self) -> str:
        """Return the C++ header for this object type."""
        raise NotImplementedError

    def get_helper_call(self) -> str:
        """Return the C++ helper call for this object."""
        raise NotImplementedError


@dataclass(frozen=True)
class IoObject(DescriptorObject):
    """Decoded IO object from descriptor spec."""

    io_type: str
    instance: int
    dtype: str
    tags: list[str]
    config: dict[str, Any]
    timestamp: bool
    notify: bool
    rw: bool
    subtype: str | None
    variant: str | None

    @property
    def category(self) -> str:
        """Return object category."""
        return "IO"

    @classmethod
    def from_spec(
        cls, spec: dict[str, Any], *, strict: bool = True
    ) -> IoObject | None:
        """Construct an IoObject from its YAML definition."""
        io_id = spec.get("id")
        if not io_id:
            if strict:
                raise DescriptorDecodeError("IO entry is missing id")
            return None
        io_type = str(spec.get("type", ""))
        if not io_type:
            if strict:
                raise DescriptorDecodeError(f"IO {io_id} is missing type")
            return None
        instance = int(spec.get("instance", 0))
        dtype = str(spec.get("dtype", "uint32")).lower()
        tags = cls.normalize_tags(spec.get("tags"))
        config = spec.get("config", {}) or {}
        timestamp = bool(spec.get("timestamp", False))
        notify = bool(spec.get("notify", False))
        rw = bool(spec.get("rw", False)) if io_type == "config" else False
        subtype = cls.normalize_subtype(spec.get("subtype"))
        variant = spec.get("variant")

        obj = cls(
            obj_id=str(io_id),
            io_type=io_type,
            instance=instance,
            dtype=dtype,
            tags=tags,
            config=config,
            timestamp=timestamp,
            notify=notify,
            rw=rw,
            subtype=subtype,
            variant=variant,
        )

        errors = obj.validate()
        if errors and strict:
            raise DescriptorDecodeError(
                f"IO {io_id} invalid: {', '.join(errors)}"
            )
        if errors:
            return None
        return obj

    def validate(self) -> list[str]:
        """Return validation problems for the IO entry."""
        errors: list[str] = []
        if not self.obj_id:
            errors.append("id is required")
        if self.io_type not in IO_TYPES:
            errors.append(f"unknown IO type '{self.io_type}'")
            return errors
        if self.instance < 0:
            errors.append("instance must be >= 0")
        info = IO_TYPES[self.io_type]
        if info.subtypes:
            if not self.subtype:
                errors.append("subtype is required")
            elif self.subtype not in info.subtypes:
                errors.append(
                    f"invalid subtype '{self.subtype}' for {self.io_type}"
                )
        if info.variants:
            variant_names = [v.get("name") for v in info.variants]
            if self.variant is None:
                return errors
            if self.variant not in variant_names:
                errors.append(
                    f"invalid variant '{self.variant}' for {self.io_type}"
                )
        return errors

    @property
    def initval_param(self) -> int:
        """Return the SObjectId DTYPE_* enum value for cfgIdInitval."""
        param = DTYPE_INITVAL_PARAM_MAP.get(self.dtype)
        if param is None:
            raise ValueError(
                f"No SObjectId DTYPE mapping for IO dtype '{self.dtype}'"
            )
        return param

    @property
    def dtype_cpp(self) -> str:
        """Return the C++ enum name for this IO's data type."""
        return DTYPE_MAP.get(self.dtype, "SObjectId::DTYPE_UINT32")

    @staticmethod
    def normalize_tags(tags: Any) -> list[str]:
        """Normalize descriptor tag lists and reject non-string entries."""
        if tags is None:
            return []
        if isinstance(tags, list):
            normalized: list[str] = []
            for tag in tags:
                if tag is None:
                    continue
                if isinstance(tag, (dict, list)):
                    raise DescriptorDecodeError(
                        "tags must be a list of strings"
                    )
                normalized.append(str(tag))
            return normalized
        if isinstance(tags, dict):
            raise DescriptorDecodeError("tags must be a list of strings")
        return [str(tags)]

    @staticmethod
    def normalize_subtype(subtype: Any) -> str | None:
        """Normalize sensor subtype names to canonical identifiers."""
        if subtype is None:
            return None
        return str(subtype).lower()

    def get_header(self) -> str:
        """Return the C++ header for this IO type."""
        return IO_TYPES[self.io_type].header

    def get_helper_call(self) -> str:
        """Return the C++ helper call for this IO object."""
        _, call = get_io_helper_call(
            self.io_type,
            self.subtype,
            self.variant,
            self.dtype,
            self.instance,
            {
                "timestamp": self.timestamp,
                "rw": self.rw,
                "notify": self.notify,
            },
        )
        return call


@dataclass(frozen=True)
class ProgramObject(DescriptorObject):
    """Decoded Program object from descriptor spec."""

    prog_type: str
    instance: int
    inputs: list[str]
    outputs: list[str]
    reset: str | None
    config: dict[str, Any]

    @property
    def category(self) -> str:
        """Return object category."""
        return "PROG"

    @classmethod
    def from_spec(
        cls, spec: dict[str, Any], *, strict: bool = True
    ) -> ProgramObject | None:
        """Construct and validate a Program entry from YAML."""
        prog_id = spec.get("id")
        if not prog_id:
            if strict:
                raise DescriptorDecodeError("Program entry is missing id")
            return None
        prog_type = str(spec.get("type", ""))
        if not prog_type:
            if strict:
                raise DescriptorDecodeError(
                    f"Program {prog_id} is missing type"
                )
            return None
        instance = int(spec.get("instance", 0))
        config = spec.get("config", {}) or {}
        inputs = resolve_references(config.get("inputs", []))
        outputs = resolve_references(config.get("outputs", []))
        reset_ref = config.get("reset")
        reset = resolve_reference(reset_ref) if reset_ref else None

        obj = cls(
            obj_id=str(prog_id),
            prog_type=prog_type,
            instance=instance,
            inputs=inputs,
            outputs=outputs,
            reset=reset,
            config=config,
        )

        errors = obj.validate()
        if errors and strict:
            raise DescriptorDecodeError(
                f"Program {prog_id} invalid: {', '.join(errors)}"
            )
        if errors:
            return None
        return obj

    def validate(self) -> list[str]:
        """Ensure program metadata references known classes."""
        errors: list[str] = []
        if not self.obj_id:
            errors.append("id is required")
        if self.prog_type not in PROG_TYPES:
            errors.append(f"unknown program type '{self.prog_type}'")
            return errors
        if self.instance < 0:
            errors.append("instance must be >= 0")
        handler = PROG_HANDLER_REGISTRY.get(self.prog_type)
        if handler is not None:
            errors.extend(handler.validate_object(self))
        return errors

    def get_header(self) -> str:
        """Return the C++ header for this program type."""
        return PROG_TYPES[self.prog_type].header

    def get_helper_call(self) -> str:
        """Return the C++ helper call for this program object."""
        _, call = get_prog_helper_call(self.prog_type, self.instance)
        return call


@dataclass(frozen=True)
class ProtocolObject(DescriptorObject):
    """Decoded Protocol object from descriptor spec."""

    proto_type: str
    instance: int
    config: dict[str, Any]
    bindings: list[str]

    @property
    def category(self) -> str:
        """Return object category."""
        return "PROTO"

    @classmethod
    def from_spec(
        cls, spec: dict[str, Any], *, strict: bool = True
    ) -> ProtocolObject | None:
        """Instantiate and validate a protocol entry (using subclasses)."""
        proto_id = spec.get("id")
        if not proto_id:
            if strict:
                raise DescriptorDecodeError("Protocol entry is missing id")
            return None
        proto_type = str(spec.get("type", ""))
        if not proto_type:
            if strict:
                raise DescriptorDecodeError(
                    f"Protocol {proto_id} is missing type"
                )
            return None
        instance = int(spec.get("instance", 0))
        config = spec.get("config", {}) or {}
        bindings = cls._decode_bindings(spec, config)
        bindings = cls.resolve_bindings(proto_type, bindings, config)

        obj = cls(
            obj_id=str(proto_id),
            proto_type=proto_type,
            instance=instance,
            config=config,
            bindings=bindings,
        )
        errors = obj.validate()
        if errors and strict:
            raise DescriptorDecodeError(
                f"Protocol {proto_id} invalid: {', '.join(errors)}"
            )
        if errors:
            return None
        return obj

    def validate(self) -> list[str]:
        """Ensure required protocol metadata and config structure."""
        errors: list[str] = []
        if not self.obj_id:
            errors.append("id is required")
        if self.proto_type not in PROTO_TYPES:
            errors.append(f"unknown protocol type '{self.proto_type}'")
        if self.instance < 0:
            errors.append("instance must be >= 0")
        if not isinstance(self.config, dict):
            errors.append("config must be a mapping")
            return errors
        handler = PROTO_HANDLER_REGISTRY.get(self.proto_type)
        if handler is not None:
            errors.extend(handler.validate_object(self))
        return errors

    def get_header(self) -> str:
        """Return the C++ header for this protocol type."""
        return PROTO_TYPES[self.proto_type].header

    def get_helper_call(self) -> str:
        """Return the C++ helper call for this protocol object."""
        _, call = get_proto_helper_call(self.proto_type, self.instance)
        return call

    @staticmethod
    def _decode_bindings(spec: dict[str, Any], config: Any) -> list[str]:
        """Return simple protocol bindings from config.

        Top-level ``bindings`` remains a legacy fallback.
        """
        if isinstance(config, dict):
            raw_bindings = config.get("bindings", spec.get("bindings", []))
        else:
            raw_bindings = spec.get("bindings", [])
        if not isinstance(raw_bindings, list):
            return []
        return resolve_references(raw_bindings)

    @staticmethod
    def resolve_bindings(
        proto_type: str, bindings: list[str], config: Any
    ) -> list[str]:
        """Resolve protocol bindings through the protocol handler policy."""
        if not isinstance(config, dict):
            return bindings
        handler = PROTO_HANDLER_REGISTRY.get(proto_type)
        if handler is None:
            return bindings
        return handler.resolve_bindings(bindings, config)


def _is_list_of_dicts(value: Any) -> bool:
    """Return True when value is a list of mappings."""
    if not isinstance(value, list):
        return False
    return all(isinstance(item, dict) for item in value)


def _automate_instances(
    items: list[dict[str, Any]], instances: dict[str, int]
) -> None:
    """Fill in missing instances while reserving explicit user values."""
    for item in items:
        item_type = item.get("type")
        if not item_type:  # pragma: no cover
            continue

        if "instance" not in item:
            item["instance"] = instances.get(item_type, 0)
            instances[item_type] = item["instance"] + 1
        else:
            try:
                provided_instance = int(item.get("instance", 0))
                instances[item_type] = max(
                    instances.get(item_type, 0), provided_instance + 1
                )
            except (ValueError, TypeError):  # pragma: no cover
                pass


def prepare_spec_instances(spec: dict[str, Any]) -> None:
    """Automate 'instance' field for IO, Programs, and Protocols in spec."""
    _automate_instances(spec.get("ios", []), {})
    _automate_instances(spec.get("programs", []), {})
    _automate_instances(spec.get("protocols", []), {})


def decode_objects(
    spec: dict[str, Any], *, strict: bool = True
) -> list[DescriptorObject]:
    """Decode descriptor spec into typed objects."""
    objects: list[DescriptorObject] = []

    # Automate instances before decoding
    prepare_spec_instances(spec)

    for io in spec.get("ios", []):
        io_obj = IoObject.from_spec(io, strict=strict)
        if io_obj:
            objects.append(io_obj)

    for prog in spec.get("programs", []):
        prog_obj = ProgramObject.from_spec(prog, strict=strict)
        if prog_obj:
            objects.append(prog_obj)

    for proto in spec.get("protocols", []):
        proto_obj = ProtocolObject.from_spec(proto, strict=strict)
        if proto_obj:
            objects.append(proto_obj)

    prog_errors = _validate_program_object_refs(objects)
    if prog_errors and strict:
        raise DescriptorDecodeError(prog_errors[0])

    return objects


def _validate_program_object_refs(  # pragma: no cover
    objects: list[DescriptorObject],
) -> list[str]:
    """Validate cross-object program constraints that need IO metadata."""
    io_map = {obj.obj_id: obj for obj in objects if isinstance(obj, IoObject)}
    errors: list[str] = []

    for obj in objects:
        if not isinstance(obj, ProgramObject):
            continue

        handler = PROG_HANDLER_REGISTRY.get(obj.prog_type)
        if handler is not None:
            errors.extend(handler.validate_object_refs(obj, io_map))
        errors.extend(_validate_virt_output_shape_ownership(obj, io_map))

    return errors


def _validate_virt_output_shape_ownership(  # pragma: no cover
    obj: ProgramObject, io_map: dict[str, IoObject]
) -> list[str]:
    """Ensure only fixed-shape programs own output-side deferred virt shape."""
    errors: list[str] = []

    for target_ref in _program_output_shape_owned_virt_targets(obj):
        io = io_map.get(target_ref)
        if io is None or io.io_type != "virt":
            continue
        handler = PROG_HANDLER_REGISTRY.get(obj.prog_type)
        if handler is None:
            errors.append(
                f"Program {obj.obj_id} invalid: {obj.prog_type} may not "
                f"own output-side virt shape '{target_ref}'"
            )

    return errors


def _program_output_shape_owned_virt_targets(  # pragma: no cover
    obj: ProgramObject,
) -> set[str]:
    """Return the IO refs whose virt shape may be owned by this program."""
    handler = PROG_HANDLER_REGISTRY.get(obj.prog_type)
    if handler is None:
        config = obj.config if isinstance(obj.config, dict) else {}
        outputs = config.get("outputs", obj.outputs)
        if not isinstance(outputs, list):
            return set()
        return set(resolve_references(outputs))
    return handler.output_shape_owned_virt_targets(obj)
