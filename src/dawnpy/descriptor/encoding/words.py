# tools/dawnpy/src/dawnpy/descriptor/encoding/words.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Binary-descriptor word-format helpers (cfg-id packing, ref resolution).

Lives at the descriptor-package root so both ``serializers/`` and
``handlers/`` can import it without creating an import cycle through
``serializers/__init__``. Was ``serializers/_common.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.support.utils import resolve_flexible_reference

if TYPE_CHECKING:
    from dawnpy.objectid import ObjectIdDecoder


def cfg_id(
    obj_type: int,
    cls: int,
    dtype: int,
    rw: bool,
    size: int,
    cfg_item_id: int,
) -> int:
    """Pack a 32-bit cfg id (type/class/dtype/rw/size/id bit layout)."""
    return (
        ((obj_type & 0x3) << 30)
        | ((cls & 0x1FF) << 21)
        | ((dtype & 0xF) << 16)
        | ((1 if rw else 0) << 15)
        | ((size & 0x3FF) << 5)
        | (cfg_item_id & 0x1F)
    )


def append_cfg_item(
    items: list[tuple[int, list[int]]],
    cfgid: int,
    data_words: list[int],
) -> None:
    """Append one serialized cfg entry."""
    items.append((cfgid, data_words))


def named_refs_to_objid_words(
    refs: list[str], obj_ids: dict[str, int]
) -> list[int]:
    """Resolve strict named references to object-id words."""
    return [obj_ids[ref] for ref in refs]


def flex_refs_to_objid_words(refs: Any, obj_ids: dict[str, int]) -> list[int]:
    """Resolve flexible references to object-id words."""
    words: list[int] = []
    for raw_ref in refs if isinstance(refs, list) else []:
        ref = resolve_flexible_reference(raw_ref)
        if ref and ref in obj_ids:
            words.append(obj_ids[ref])
    return words


def dtype_id_by_name(
    decoder: ObjectIdDecoder,
    dtype_name: str,
) -> int | None:
    """Return decoder dtype id matching ``dtype_name`` (None if unknown)."""
    for dtype_id, info in decoder.dtype_info.items():
        if str(info.get("type", "")) == dtype_name:
            return int(dtype_id)
    return None


def mask_from_allowed(
    allowed_list: Any,
    bits_cfg: Any,
) -> int | None:
    """Build a bit-mask from allowed-values list using ``bits_cfg`` map."""
    if not isinstance(allowed_list, list) or not allowed_list:
        return None
    if not isinstance(bits_cfg, dict):
        return 0
    mask = 0
    for key in allowed_list:
        bit_pos = bits_cfg.get(str(key))
        if bit_pos is None:
            continue
        mask |= 1 << int(bit_pos)
    return mask


def enabled_flag_names(value: int, flags: list[dict[str, Any]]) -> list[str]:
    """Return names of enabled flags from YAML-provided bit definitions."""
    enabled: list[str] = []
    for item in flags:
        bit = int(item.get("bit", -1))
        name = str(item.get("name", ""))
        if bit < 0 or not name:
            continue
        if value & (1 << bit):
            enabled.append(name)
    return enabled
