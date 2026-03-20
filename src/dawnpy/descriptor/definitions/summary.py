# tools/dawnpy/src/dawnpy/descriptor/object_summary.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Object ID summary helpers for descriptors."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from dawnpy.descriptor.handlers import (
    IO_HANDLER_REGISTRY,
    PROG_HANDLER_REGISTRY,
    PROTO_HANDLER_REGISTRY,
)
from dawnpy.device.decode import normalize_dtype

if TYPE_CHECKING:
    from dawnpy.descriptor.client import (
        ClientDescriptor,
        ClientIo,
        ClientProgram,
        ClientProto,
    )

from dawnpy.objectid import ObjectIdDecoder


class ObjectIdResolver:
    """Resolve ObjectIDs for descriptor objects."""

    def __init__(self) -> None:
        """Initialize resolver with YAML-backed mappings."""
        self.decoder = ObjectIdDecoder()
        self._dtype_ids = {
            info["type"]: dtype_id
            for dtype_id, info in self.decoder.dtype_info.items()
        }
        self._io_class_ids = {
            name: io_id for io_id, name in self.decoder.io_classes.items()
        }
        self._proto_class_ids = {
            name: proto_id
            for proto_id, name in self.decoder.proto_classes.items()
        }
        self._prog_class_ids = {
            name: prog_id
            for prog_id, name in self.decoder.prog_classes.items()
        }

    def io_objid(self, io: ClientIo) -> int | None:
        """Return ObjectID for an IO entry."""
        class_name = _io_class_name(io)
        if not class_name:
            return None
        class_id = self._io_class_ids.get(class_name)
        if class_id is None:
            return None
        dtype = _io_dtype(io)
        dtype_id = self._dtype_ids.get(dtype, 0)
        flags = _io_flags(io)
        inst = _io_instance(io)
        return self.decoder.encode(1, class_id, dtype_id, flags, inst)

    def program_objid(self, prog: ClientProgram) -> int | None:
        """Return ObjectID for a program entry."""
        class_name = _prog_class_name(prog)
        if not class_name:
            return None
        class_id = self._prog_class_ids.get(class_name)
        if class_id is None:
            return None
        return self.decoder.encode(3, class_id, 0, 0, prog.instance)

    def protocol_objid(self, proto: ClientProto) -> int | None:
        """Return ObjectID for a protocol entry."""
        class_name = _proto_class_name(proto)
        if not class_name:
            return None
        class_id = self._proto_class_ids.get(class_name)
        if class_id is None:
            return None
        return self.decoder.encode(2, class_id, 0, 0, proto.instance)


def build_io_table(
    desc: ClientDescriptor,
    *,
    resolver: ObjectIdResolver | None = None,
    methods_lookup: Callable[[str], str] | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Build IO object table rows."""
    resolver = resolver or ObjectIdResolver()
    headers = ["objid", "io", "type", "inst", "dtype", "tags"]
    if methods_lookup:
        headers.insert(5, "methods")
    rows: list[list[str]] = []
    for io_id in sorted(desc.ios.keys()):
        io = desc.ios[io_id]
        objid = resolver.io_objid(io)
        objid_str = _fmt_objid(objid)
        tags = ", ".join(io.tags) if io.tags else "-"
        row = [
            objid_str,
            io.io_id,
            io.io_type,
            str(io.instance),
            io.dtype,
        ]
        if methods_lookup:
            row.append(methods_lookup(io.io_id))
        row.append(tags)
        rows.append(row)
    return headers, rows


def build_program_table(
    desc: ClientDescriptor,
    *,
    resolver: ObjectIdResolver | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Build program object table rows."""
    resolver = resolver or ObjectIdResolver()
    headers = ["objid", "program", "type", "inst", "details"]
    rows: list[list[str]] = []
    for prog in desc.programs:
        objid = resolver.program_objid(prog)
        details = f"inputs={len(prog.inputs)}, outputs={len(prog.outputs)}"
        rows.append(
            [
                _fmt_objid(objid),
                prog.prog_id,
                prog.prog_type,
                str(prog.instance),
                details,
            ]
        )
    return headers, rows


def build_protocol_table(
    desc: ClientDescriptor,
    *,
    resolver: ObjectIdResolver | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Build protocol object table rows."""
    resolver = resolver or ObjectIdResolver()
    headers = ["objid", "protocol", "type", "inst", "details"]
    rows: list[list[str]] = []
    for proto in desc.protocols:
        objid = resolver.protocol_objid(proto)
        details = f"bindings={len(proto.bindings)}"
        rows.append(
            [
                _fmt_objid(objid),
                proto.proto_id,
                proto.proto_type,
                str(proto.instance),
                details,
            ]
        )
    return headers, rows


def _fmt_objid(objid: int | None) -> str:
    if objid is None:
        return "n/a"
    return f"0x{objid:08X}"


def _io_class_name(io: ClientIo) -> str | None:  # noqa: C901
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return handler.summary_class_name(io)
    return io.io_type


def _io_dtype(io: ClientIo) -> str:
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return normalize_dtype(handler.summary_dtype_name(io))
    return normalize_dtype(io.dtype)  # pragma: no cover


def _io_instance(io: ClientIo) -> int:
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return handler.summary_instance(io)
    return io.instance  # pragma: no cover


def _io_flags(io: ClientIo) -> int:
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return handler.summary_flags(io)
    return int(io.timestamp)  # pragma: no cover


def _prog_class_name(prog: ClientProgram) -> str | None:
    handler = PROG_HANDLER_REGISTRY.get(prog.prog_type)
    if handler is not None:
        return handler.object_class_name(prog)
    return prog.prog_type


def _proto_class_name(proto: ClientProto) -> str | None:
    handler = PROTO_HANDLER_REGISTRY.get(proto.proto_type)
    if handler is not None:
        return handler.object_class_name(proto)
    return proto.proto_type
