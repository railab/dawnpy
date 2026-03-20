# tools/dawnpy/src/dawnpy/descriptor/encoding/proto_serializer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Protocol-object binary serializer.

Owns ONLY the entry-point ``serialize_proto_object`` and the helpers it
needs to build the per-type ``_ProtoSerializeContext``. Per-type
encoders + cpp_class bindings + config schemas live in
``dawnpy/descriptor/handlers/proto_*.py`` - one file per yaml-token. To
add a new built-in proto type, drop a new ``handlers/proto_*.py`` and
add it to ``handlers.PROTO_HANDLER_REGISTRY`` - nothing else here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from dawnpy.descriptor.definitions.registry import PROTO_TYPES
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import dtype_id_by_name
from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY
from dawnpy.descriptor.handlers._base import ProtoHandler
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import (
    header_cfg_id,
    header_enum_value_ids,
    header_object_class_name,
)

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.objectid import ObjectIdDecoder


def _resolve_proto_cfg_ids(handler: ProtoHandler) -> dict[str, int]:
    """Resolve cfg-id helpers declared by the selected protocol handler."""
    return {
        key: header_cfg_id(owner, method)
        for key, (owner, method) in handler.cfg_id_helpers().items()
    }


def _safe_enum_value_ids(owner: str, prefix: str) -> dict[str, int]:
    """Resolve enum value map; return empty dict if the header is unknown."""
    try:
        return header_enum_value_ids(owner, prefix)
    except HeaderDefsError:
        return {}


def _resolve_proto_cpp_class(proto_type: str) -> str | None:
    """Resolve cpp_class from a per-type handler, then PROTO_TYPES."""
    handler = PROTO_HANDLER_REGISTRY.get(proto_type)
    if handler is not None:
        return str(handler.cpp_class)
    info = PROTO_TYPES.get(proto_type)
    return info.cpp_class if info is not None else None


def _resolve_dtype_ids(
    handler: ProtoHandler, decoder: ObjectIdDecoder
) -> dict[str, int]:
    """Resolve dtype ids declared by the selected protocol handler."""
    dtype_ids: dict[str, int] = {}
    for key, dtype_name in handler.dtype_names().items():
        dtype_id = dtype_id_by_name(decoder, dtype_name)
        if dtype_id is None:
            raise click.ClickException(
                f"Unknown dtype '{dtype_name}' for protocol field '{key}'"
            )
        dtype_ids[key] = int(dtype_id)
    return dtype_ids


def _resolve_enum_value_maps(
    handler: ProtoHandler,
) -> dict[str, dict[str, int]]:
    """Resolve enum maps declared by the selected protocol handler."""
    return {
        key: _safe_enum_value_ids(owner, prefix)
        for key, (owner, prefix) in handler.enum_value_maps().items()
    }


def serialize_proto_object(  # noqa: C901
    words: list[int],
    obj: ProtocolObject,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append binary words for a protocol object into ``words``.

    Resolves the C++ class via the handler registry (or PROTO_TYPES for
    OOT types), packs the per-protocol context, and dispatches to the
    handler's ``encode_binary``.
    """
    supported_types = tuple(PROTO_HANDLER_REGISTRY.keys())
    cpp_class = _resolve_proto_cpp_class(obj.proto_type)
    cls_name: str | None = None
    handler = PROTO_HANDLER_REGISTRY.get(obj.proto_type)
    if handler is not None:
        cls_name = handler.object_class_name(obj)
    elif cpp_class is not None:  # pragma: no cover
        try:  # pragma: no cover
            cls_name = header_object_class_name(cpp_class, "objectId")
        except HeaderDefsError:  # pragma: no cover
            cls_name = None
    if not cls_name:
        supported_str = ", ".join(str(item) for item in supported_types)
        raise click.ClickException(
            "descriptor binary currently supports protocol type: "
            f"{supported_str} (got '{obj.proto_type}')"
        )

    proto_cls_map = {name: cls for cls, name in decoder.proto_classes.items()}
    cls = proto_cls_map.get(cls_name)
    if cls is None:
        raise click.ClickException(
            f"Unknown protocol class '{cls_name}' for '{obj.obj_id}'"
        )

    if handler is None:  # pragma: no cover
        supported_str = ", ".join(str(item) for item in supported_types)
        raise click.ClickException(
            "descriptor binary currently supports protocol type: "
            f"{supported_str} (got '{obj.proto_type}')"
        )

    objid = decoder.encode(2, cls, 0, 0, int(obj.instance))
    obj_ids[obj.obj_id] = objid

    config = obj.config if isinstance(obj.config, dict) else {}
    items: list[tuple[int, list[int]]] = []
    ctx = _ProtoSerializeContext(
        obj=obj,
        cls=cls,
        config=config,
        obj_ids=obj_ids,
        items=items,
        fmt=DescriptorFormatHelper(),
        dtype_ids=_resolve_dtype_ids(handler, decoder),
        cfg_ids=_resolve_proto_cfg_ids(handler),
        defaults=handler.defaults(),
        enum_values=_resolve_enum_value_maps(handler),
        fixed_string_bytes=handler.fixed_string_bytes(),
    )
    handler.encode_binary(ctx)

    words.append(objid)
    words.append(len(items))
    for cfgid, data_words in items:
        words.append(cfgid)
        words.extend(data_words)
