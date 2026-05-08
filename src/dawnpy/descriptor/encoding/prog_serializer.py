# tools/dawnpy/src/dawnpy/descriptor/encoding/prog_serializer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Program-object binary serializer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import header_object_class_name

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder


def _prog_class_name(obj: ProgramObject) -> str | None:
    """Resolve descriptor PROG class name from handlers or type info."""
    handler = PROG_HANDLER_REGISTRY.get(obj.prog_type)
    if handler is not None:
        object_class_name = getattr(handler, "object_class_name", None)
        if object_class_name is not None:
            value = object_class_name(obj)
            return str(value) if value is not None else None
        try:
            return header_object_class_name(handler.cpp_class, "objectId")
        except HeaderDefsError:  # pragma: no cover
            return None
    info = PROG_TYPES.get(obj.prog_type)
    if info is None:
        return None
    try:
        return header_object_class_name(info.cpp_class, "objectId")
    except HeaderDefsError:  # pragma: no cover
        return None


def serialize_prog_object(  # noqa: C901
    words: list[int],
    obj: ProgramObject,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append binary words for a program object into ``words``."""
    prog_cls_name = _prog_class_name(obj)
    if prog_cls_name is None:
        raise click.ClickException(
            f"Unable to resolve PROG class for '{obj.obj_id}'"
        )

    prog_cls_map = {name: cls for cls, name in decoder.prog_classes.items()}
    prog_cls = prog_cls_map.get(prog_cls_name)
    if prog_cls is None:
        raise click.ClickException(
            f"Unknown PROG class '{prog_cls_name}' for '{obj.obj_id}'"
        )

    objid = decoder.encode(3, prog_cls, 0, 0, int(obj.instance))
    obj_ids[obj.obj_id] = objid

    items: list[tuple[int, list[int]]] = []

    handler = PROG_HANDLER_REGISTRY.get(obj.prog_type)
    if handler is not None:
        handler.encode_binary(items, obj, prog_cls, obj_ids, decoder)

    words.append(objid)
    words.append(len(items))
    for cfgid, data_words in items:
        words.append(cfgid)
        words.extend(data_words)
