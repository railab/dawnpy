# tools/dawnpy/src/dawnpy/descriptor/io_runtime.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Leaf module shared by the IO binary serializer and per-type handlers.

Mirrors :mod:`dawnpy.descriptor.encoding.proto_runtime`: holds the dispatch
context dataclass passed to every per-IO encoder, plus tiny helpers
both sides need. Lives at the descriptor package root (no internal
dawnpy deps beyond ``binary_words``) so per-type handlers under
``descriptor/handlers/io_*.py`` can import these at top-level without
creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.encoding.words import dtype_id_by_name
from dawnpy.headerdefs import HeaderDefsError, load_header_enum_value_ids

if TYPE_CHECKING:
    from dawnpy.descriptor.config_access import ConfigRwGrants
    from dawnpy.descriptor.definitions.objects import IoObject
    from dawnpy.objectid import ObjectIdDecoder


@dataclass
class _IOSerializeContext:
    """Bag of pre-resolved data passed to every per-IO encoder."""

    obj: IoObject
    io_cls: int
    dtype: int
    dtype_name: str
    config: dict[str, Any]
    obj_ids: dict[str, int]
    items: list[tuple[int, list[int]]]
    decoder: ObjectIdDecoder
    io_dtype_map: dict[str, int]
    io_cls_map: dict[str, int]
    config_rw_grants: ConfigRwGrants = field(default_factory=dict)


def resolve_dtype(
    decoder: ObjectIdDecoder, dtype_name: str, label: str
) -> int:
    """Resolve a named dtype to its enum id or raise a ClickException."""
    import click

    dtype = dtype_id_by_name(decoder, dtype_name)
    if dtype is None:
        raise click.ClickException(f"Unknown dtype '{dtype_name}' for {label}")
    return int(dtype)


def resolve_allowed_bits(owner: str, prefix: str) -> dict[str, int]:
    """Return enum values normalized to bit positions (control/trigger)."""
    try:
        raw = load_header_enum_value_ids(owner, prefix)
    except HeaderDefsError:  # pragma: no cover
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        v = int(value)
        if v > 0 and (v & (v - 1)) == 0:
            out[key] = v.bit_length() - 1
        else:
            out[key] = v  # pragma: no cover
    return out
