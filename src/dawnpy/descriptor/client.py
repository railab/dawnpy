# tools/dawnpy/src/dawnpy/descriptor/client.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Client descriptor parsing utilities.

Provides protocol-agnostic access to descriptor.yaml for client tools.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dawnpy.descriptor.definitions.objects import (
    DescriptorDecodeError,
    IoObject,
    ProgramObject,
    ProtocolObject,
    prepare_spec_instances,
)
from dawnpy.descriptor.support.vars import load_yaml_with_vars

TAGS_TYPE_ERROR = "tags must be a list of strings"


@dataclass(frozen=True)
class ClientIo:
    """IO definition from descriptor."""

    io_id: str
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


@dataclass(frozen=True)
class ClientProto:
    """Protocol definition from descriptor."""

    proto_id: str
    proto_type: str
    instance: int
    config: dict[str, Any]
    bindings: list[str]


@dataclass(frozen=True)
class ClientProgram:
    """Program definition from descriptor."""

    prog_id: str
    prog_type: str
    instance: int
    inputs: list[str]
    outputs: list[str]
    config: dict[str, Any]


@dataclass
class ClientDescriptor:
    """Parsed descriptor for runtime tooling."""

    ios: dict[str, ClientIo]
    programs: list[ClientProgram]
    protocols: list[ClientProto]

    def get_io(self, io_id: str) -> ClientIo | None:
        """Return IO metadata by ID."""
        return self.ios.get(io_id)

    def get_protocols(self, proto_type: str) -> list[ClientProto]:
        """Return protocols matching type."""
        return [p for p in self.protocols if p.proto_type == proto_type]

    def get_protocol(self, proto_type: str) -> ClientProto | None:
        """Return first protocol of a given type."""
        for proto in self.protocols:
            if proto.proto_type == proto_type:
                return proto
        return None

    def get_tagged_ios(self, tag: str) -> list[ClientIo]:
        """Return IOs matching a tag."""
        tag_lc = tag.lower()
        return [
            io
            for io in self.ios.values()
            if any(t.lower() == tag_lc for t in io.tags)
        ]


def find_descriptor_path(path: str) -> str:
    """Resolve a descriptor path from user input."""
    candidate = Path(path)
    if candidate.is_dir():
        descriptor = candidate / "descriptor.yaml"
        return str(descriptor)
    return str(candidate)


def _is_fatal_io_decode_error(exc: DescriptorDecodeError) -> bool:
    """Return True for IO decode errors that should be surfaced to callers."""
    return TAGS_TYPE_ERROR in str(exc)


def load_client_descriptor(  # noqa: C901
    yaml_path: str,
    kconfig_path: str | None = None,
    kconfig_overrides: dict[str, Any] | None = None,
) -> ClientDescriptor:
    """Load descriptor.yaml into a runtime-friendly structure."""
    spec = load_yaml_with_vars(
        yaml_path,
        kconfig_path=kconfig_path,
        kconfig_overrides=kconfig_overrides,
    )

    # Automate instances before decoding
    prepare_spec_instances(spec)

    ios: dict[str, ClientIo] = {}
    programs: list[ClientProgram] = []
    protocols: list[ClientProto] = []

    # Unified object decode pass while preserving per-kind error policy.
    entries: list[tuple[str, dict[str, Any]]] = []
    entries.extend(("io", io) for io in spec.get("ios", []))
    entries.extend(("program", prog) for prog in spec.get("programs", []))
    entries.extend(("protocol", proto) for proto in spec.get("protocols", []))

    for kind, item in entries:
        try:
            if kind == "io":
                io_obj = IoObject.from_spec(item, strict=True)
                if io_obj is None:
                    continue
                ios[io_obj.obj_id] = ClientIo(
                    io_id=io_obj.obj_id,
                    io_type=io_obj.io_type,
                    instance=io_obj.instance,
                    dtype=io_obj.dtype,
                    tags=io_obj.tags,
                    config=io_obj.config,
                    timestamp=io_obj.timestamp,
                    notify=io_obj.notify,
                    rw=io_obj.rw,
                    subtype=io_obj.subtype,
                    variant=io_obj.variant,
                )
                continue

            if kind == "program":
                prog_obj = ProgramObject.from_spec(item, strict=True)
                if prog_obj is None:
                    continue
                programs.append(
                    ClientProgram(
                        prog_id=prog_obj.obj_id,
                        prog_type=prog_obj.prog_type,
                        instance=prog_obj.instance,
                        inputs=prog_obj.inputs,
                        outputs=prog_obj.outputs,
                        config=prog_obj.config,
                    )
                )
                continue

            proto_obj = ProtocolObject.from_spec(item, strict=True)
            if proto_obj is None:
                continue
            protocols.append(
                ClientProto(
                    proto_id=proto_obj.obj_id,
                    proto_type=proto_obj.proto_type,
                    instance=proto_obj.instance,
                    config=proto_obj.config,
                    bindings=proto_obj.bindings,
                )
            )
        except DescriptorDecodeError as exc:
            if kind == "io" and _is_fatal_io_decode_error(exc):
                raise ValueError(str(exc)) from exc
            continue

    return ClientDescriptor(ios=ios, programs=programs, protocols=protocols)
