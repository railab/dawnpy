# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_buffer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``buffer`` PROG type.

Owns the cpp_class binding, the user-facing YAML config schema, and the
binary serializer block (one cfg item built from src/out/sel/stat entries,
plus scalar fields).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import (
    resolve_flexible_reference,
    resolve_reference,
)
from dawnpy.headerdefs import load_header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder


yaml_type: str = "buffer"
cpp_class: str = "CProgBuffer"

# Per-type scalar config slots. Field name -> (cfg_item_id, rw flag, default).
_SCALAR_FIELDS: dict[str, tuple[int, bool, int | None]] = {
    "depth": (2, False, None),
    "flags": (3, False, None),
    "chunk_size": (4, False, 1),
}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``buffer``."""
    return [
        ConfigField(
            name="iobind",
            cpp_helper="CProgBuffer::cfgIdIOBind",
            value_type="id_array_quads",
        ),
        ConfigField(
            name="depth",
            cpp_helper="CProgBuffer::cfgIdDepth",
            value_type="uint32",
        ),
        ConfigField(
            name="flags",
            cpp_helper="CProgBuffer::cfgIdFlags",
            value_type="uint32",
        ),
        ConfigField(
            name="chunk_size",
            cpp_helper="CProgBuffer::cfgIdChunkSize",
            value_type="uint32",
            default="1",
        ),
    ]


def output_shape_owned_virt_targets(obj: ProgramObject) -> set[str]:
    """Return buffer roles whose output shape is defined by the program."""
    refs: set[str] = set()
    binds = obj.config.get("iobind", [])
    if not isinstance(binds, list):
        return refs

    for entry in binds:
        if not isinstance(entry, dict):
            continue
        for key in ("out", "sel", "stat"):
            ref = resolve_reference(entry.get(key))
            if ref:
                refs.add(ref)
    return refs


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: ProgramObject,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append the ``buffer`` cfg blocks to ``items``."""
    del decoder
    config = obj.config if isinstance(obj.config, dict) else {}

    raw_binds = config.get("iobind", [])
    if isinstance(raw_binds, list):
        words: list[int] = []
        for entry in raw_binds:
            if not isinstance(entry, dict):
                continue
            src = resolve_flexible_reference(entry.get("src"))
            out = resolve_flexible_reference(entry.get("out"))
            sel = resolve_flexible_reference(entry.get("sel"))
            stat = resolve_flexible_reference(entry.get("stat"))
            if (
                src not in obj_ids
                or out not in obj_ids
                or sel not in obj_ids
                or stat not in obj_ids
            ):
                continue
            words.extend(
                [obj_ids[src], obj_ids[out], obj_ids[sel], obj_ids[stat]]
            )
        if words:
            cfg = load_header_cfg_id(cpp_class, "cfgIdIOBind")
            items.append(
                (cfg_id(3, prog_cls, 0, False, len(words), cfg), words)
            )

    for name, (cfgid_item, rw, default) in _SCALAR_FIELDS.items():
        if name in config or default is not None:
            value = config[name] if name in config else default
            if value is None:
                continue  # pragma: no cover
            items.append(  # pragma: no cover
                (
                    cfg_id(3, prog_cls, 0, rw, 1, cfgid_item),
                    [int(value)],
                )
            )
