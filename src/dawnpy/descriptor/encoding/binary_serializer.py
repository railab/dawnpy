# tools/dawnpy/src/dawnpy/descriptor/encoding/binary_serializer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""YAML descriptor -> raw little-endian binary blob with CRC footer.

The CLI command ``commands/cmd_desc_bin.py`` is a thin click
command that calls :func:`generate_descriptor_binary` here. All the
serialization logic - IO/PROG/PROTO dispatch, metadata block,
header/footer/CRC framing - lives in this module.

Per-type encoding lives in ``descriptor/handlers/<family>_<type>.py``;
this module is the family-agnostic dispatcher + framing.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click

from dawnpy.descriptor.config_access import (
    ConfigRwGrants,
    build_config_rw_grants,
)
from dawnpy.descriptor.definitions.objects import (
    DescriptorObject,
    IoObject,
    ProgramObject,
    ProtocolObject,
    decode_objects,
)
from dawnpy.descriptor.definitions.registry import IO_TYPES
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.packager import (
    fill_crc32_footer,
    pack_u32_words,
)
from dawnpy.descriptor.encoding.prog_serializer import (
    _prog_class_name,
    serialize_prog_object,
)
from dawnpy.descriptor.encoding.proto_serializer import serialize_proto_object
from dawnpy.descriptor.encoding.scalar import encode_scalar_words
from dawnpy.descriptor.encoding.words import cfg_id, dtype_id_by_name
from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper
from dawnpy.descriptor.support.vars import load_yaml_with_vars
from dawnpy.headerdefs.bundle import header_cfg_id
from dawnpy.objectid import ObjectIdDecoder

# ---------------------------------------------------------------------------
# IO class-name + dtype resolution (handler-driven)
# ---------------------------------------------------------------------------


def _io_handler_cpp_class(io_type: str) -> str | None:  # pragma: no cover
    """Return the cpp_class binding for an IO yaml-token via its handler."""
    handler = IO_HANDLER_REGISTRY.get(io_type)
    if handler is not None:
        return str(handler.cpp_class)
    # OOT types fall back to headerdefs-discovered IO_TYPES.
    info = IO_TYPES.get(io_type)  # pragma: no cover
    return info.cpp_class if info is not None else None


def _io_class_name(io: IoObject) -> str | None:
    """Resolve descriptor IO class name from the matching handler."""
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return handler.object_class_name(io)
    if _io_handler_cpp_class(io.io_type) is None:  # pragma: no cover
        return io.io_type
    return io.io_type  # pragma: no cover


def _io_dtype_name(io: IoObject) -> str:
    """Resolve the dtype name for an IoObject from the handler's policy."""
    handler = IO_HANDLER_REGISTRY.get(io.io_type)
    if handler is not None:
        return handler.dtype_name(io)
    return str(io.dtype).lower()


# ---------------------------------------------------------------------------
# Per-object serializers
# ---------------------------------------------------------------------------


def _serialize_metadata(words: list[int], spec: dict[str, Any]) -> int:
    """Serialize the optional descriptor metadata block."""
    metadata = spec.get("metadata", {})
    if not isinstance(metadata, dict):
        return 0

    fields: list[tuple[int, list[int]]] = []
    fmt = DescriptorFormatHelper()

    version_raw = metadata.get("version")
    if version_raw is not None:
        parts = str(version_raw).split(".")
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) if len(parts) > 1 else 0
        version = ((major & 0xFFFF) << 16) | (minor & 0xFFFF)
        fields.append((cfg_id(0, 0, 7, False, 1, 1), [version]))

    user_string = metadata.get("user_string")
    if user_string is not None:
        packed = fmt.pack_string(str(user_string))
        fields.append((cfg_id(0, 0, 14, False, len(packed), 2), packed))

    if metadata.get("no_idle_quit") is True:
        fields.append((cfg_id(0, 0, 3, False, 1, 3), [1]))

    if not fields:
        return 0

    # CDescriptor::objectId(1)
    words.append(1)
    words.append(len(fields))
    for cfgid, data_words in fields:
        words.append(cfgid)
        words.extend(data_words)
    return 1


_LIMIT_KEY_TO_HELPER: tuple[tuple[str, str], ...] = (
    ("min", "cfgIdLimitMin"),
    ("max", "cfgIdLimitMax"),
    ("step", "cfgIdLimitStep"),
)

_SIGNED_DTYPES: frozenset[str] = frozenset({"int8", "int16", "int32"})
_UNSIGNED_DTYPES: frozenset[str] = frozenset(
    {"bool", "uint8", "uint16", "uint32", "char"}
)


def _encode_limit_word(value: Any, dtype_name: str) -> int:
    """Encode one limit value into the uint32 bit pattern matching dtype.

    Limits are single-word, so only 32-bit dtypes are supported; the actual
    word encoding is delegated to the shared scalar encoder.
    """
    if (
        dtype_name != "float"
        and dtype_name not in _SIGNED_DTYPES
        and dtype_name not in _UNSIGNED_DTYPES
    ):
        raise click.ClickException(
            f"limits not supported for IO dtype '{dtype_name}'"
        )
    return encode_scalar_words(value, dtype_name)[0]


def _limit_value_words(value: Any, dtype_name: str) -> list[int]:
    """Encode a scalar or list of limit values into uint32 words."""
    if isinstance(value, list):
        return [_encode_limit_word(v, dtype_name) for v in value]
    return [_encode_limit_word(value, dtype_name)]


def _append_limits_items(
    items: list[tuple[int, list[int]]],
    limits_cfg: Any,
    dtype_name: str,
    dtype_id: int,
) -> None:
    """Encode a YAML ``limits`` block into cfgIdLimit{Min,Max,Step} items."""
    if not isinstance(limits_cfg, dict):
        return

    for key, helper in _LIMIT_KEY_TO_HELPER:
        if key not in limits_cfg:
            continue
        cfg_enum = header_cfg_id("CIOCommon", helper)
        words_data = _limit_value_words(limits_cfg[key], dtype_name)
        size = len(words_data)
        items.append(
            (cfg_id(1, 0, int(dtype_id), False, size, cfg_enum), words_data)
        )


def _serialize_io_object(  # noqa: C901
    words: list[int],
    obj: IoObject,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
    config_rw_grants: ConfigRwGrants | None = None,
) -> None:
    """Serialize a single IO object into descriptor words."""
    common_device_cfg = header_cfg_id("CIOCommon", "cfgIdDevno")
    common_notify_cfg = header_cfg_id("CIOCommon", "cfgIdNotify")
    grants = config_rw_grants or {}

    io_cls_name = _io_class_name(obj)
    if io_cls_name is None:
        raise click.ClickException(
            f"Unable to resolve IO class for '{obj.obj_id}'"
        )

    io_cls_map = {name: cls for cls, name in decoder.io_classes.items()}
    io_cls = io_cls_map.get(io_cls_name)
    if io_cls is None:
        raise click.ClickException(
            f"Unknown IO class '{io_cls_name}' for '{obj.obj_id}'"
        )

    io_dtype_map = {
        str(info.get("type")): dtype_id
        for dtype_id, info in decoder.dtype_info.items()
    }
    dtype_name = _io_dtype_name(obj)
    dtype = io_dtype_map.get(dtype_name)
    if dtype is None:
        raise click.ClickException(
            f"Unknown IO dtype '{dtype_name}' for '{obj.obj_id}'"
        )

    flags = 1 if obj.timestamp else 0
    objid = decoder.encode(1, io_cls, dtype, flags, int(obj.instance))
    obj_ids[obj.obj_id] = objid

    items: list[tuple[int, list[int]]] = []
    config = obj.config if isinstance(obj.config, dict) else {}

    if "device" in config:
        dev_dtype = dtype_id_by_name(decoder, "uint32")
        if dev_dtype is None:
            raise click.ClickException("Unknown dtype 'uint32' for device cfg")
        items.append(
            (
                cfg_id(1, 0, int(dev_dtype), False, 1, common_device_cfg),
                [int(config["device"])],
            )
        )

    if "notify" in config:
        notify_cfg = config["notify"]
        if isinstance(notify_cfg, dict):
            notify_type_map = {"poll": 0, "stream": 1}
            ntype = notify_type_map.get(str(notify_cfg.get("type", "poll")), 0)
            nprio = int(notify_cfg.get("priority", 0))
            nbatch = int(notify_cfg.get("batch", 1))
            notify_dtype = dtype_id_by_name(decoder, "uint32")
            if notify_dtype is None:
                raise click.ClickException(
                    "Unknown dtype 'uint32' for notify cfg"
                )
            items.append(
                (
                    cfg_id(
                        1,
                        0,
                        int(notify_dtype),
                        False,
                        3,
                        common_notify_cfg,
                    ),
                    [ntype, nprio, nbatch],
                )
            )

    if "limits" in config:
        _append_limits_items(items, config["limits"], dtype_name, dtype)

    handler = IO_HANDLER_REGISTRY.get(obj.io_type)
    if handler is None:
        supported_str = ", ".join(sorted(IO_HANDLER_REGISTRY.keys()))
        raise click.ClickException(
            f"descriptor binary currently supports IO types: {supported_str} "
            f"(got '{obj.io_type}')"
        )

    ctx = _IOSerializeContext(
        obj=obj,
        io_cls=io_cls,
        dtype=dtype,
        dtype_name=dtype_name,
        config=config,
        obj_ids=obj_ids,
        items=items,
        decoder=decoder,
        io_dtype_map=io_dtype_map,
        io_cls_map=io_cls_map,
        config_rw_grants=grants,
    )
    handler.encode_binary(ctx)

    words.append(objid)
    words.append(len(items))
    for cfgid, data_words in items:
        words.append(cfgid)
        words.extend(data_words)


def _pre_register_program_ids(
    objects: Sequence[DescriptorObject],
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Make program IDs available to earlier IO control/trigger objects."""
    prog_cls_map = {name: cls for cls, name in decoder.prog_classes.items()}
    for obj in objects:
        if not isinstance(obj, ProgramObject):
            continue

        prog_cls_name = _prog_class_name(obj)
        if prog_cls_name is None:  # pragma: no cover
            raise click.ClickException(
                f"Unable to resolve PROG class for '{obj.obj_id}'"
            )

        prog_cls = prog_cls_map.get(prog_cls_name)
        if prog_cls is None:  # pragma: no cover
            raise click.ClickException(
                f"Unknown PROG class '{prog_cls_name}' for '{obj.obj_id}'"
            )

        obj_ids[obj.obj_id] = decoder.encode(
            3, prog_cls, 0, 0, int(obj.instance)
        )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def generate_descriptor_binary(
    yaml_path: Path,
    kconfig: str | None,
) -> bytes:
    """Render YAML descriptor spec to a binary blob with CRC footer."""
    spec = load_yaml_with_vars(
        str(yaml_path),
        kconfig_path=kconfig,
        resolve_kconfig_values=False,
    )
    objects = decode_objects(spec, strict=True)
    object_map = {
        obj.obj_id: obj for obj in objects if isinstance(obj, DescriptorObject)
    }
    config_rw_grants = build_config_rw_grants(object_map)
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []

    words.append(0x0D0A0302)
    words.append(0)  # header object count placeholder

    object_count = 0
    object_count += _serialize_metadata(words, spec)
    _pre_register_program_ids(objects, obj_ids, decoder)

    # Object IDs are resolved in descriptor order, matching generator behavior.
    for obj in objects:
        if isinstance(obj, IoObject):
            _serialize_io_object(
                words, obj, obj_ids, decoder, config_rw_grants
            )
        elif isinstance(obj, ProgramObject):
            serialize_prog_object(words, obj, obj_ids, decoder)
        elif isinstance(obj, ProtocolObject):
            serialize_proto_object(words, obj, obj_ids, decoder)
        else:
            raise click.ClickException(
                "descriptor binary currently supports IO/PROG/PROTO objects"
            )
        object_count += 1

    words[1] = object_count
    words.append(0x02030A0D)
    words.append(0)
    binary = pack_u32_words(words)
    return fill_crc32_footer(binary)
