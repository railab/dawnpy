# tools/dawnpy/src/dawnpy/descriptor/proto_runtime.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Leaf module shared by the proto serializer and per-type handlers.

Holds the dispatch context dataclass and the small pure helpers used by
both. Lives at the descriptor package root (no internal dawnpy deps
beyond ``binary_words`` and ``formatting``) so per-type handlers under
``descriptor/handlers/`` can import these at top-level without creating
an import cycle through ``serializers/__init__``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject


@dataclass
class _ProtoSerializeContext:
    """Bag of pre-resolved data passed to every per-proto encoder."""

    obj: ProtocolObject
    cls: int
    config: dict[str, Any]
    obj_ids: dict[str, int]
    items: list[tuple[int, list[int]]]
    fmt: DescriptorFormatHelper
    dtype_ids: dict[str, int]
    cfg_ids: dict[str, int]
    defaults: dict[str, Any]
    enum_values: dict[str, dict[str, int]]
    fixed_string_bytes: dict[str, int]

    def dtype_id(self, key: str) -> int:
        """Return a resolved dtype id declared by the handler."""
        return self.dtype_ids[key]

    def cfg_id(self, key: str, default: int) -> int:
        """Return a resolved cfg-id declared by the handler."""
        value = self.cfg_ids.get(key)
        if isinstance(value, int):
            return value
        return default  # pragma: no cover

    def enum_map(self, key: str) -> dict[str, int]:
        """Return a resolved enum map declared by the handler."""
        return self.enum_values.get(key, {})

    def default(self, key: str, fallback: Any) -> Any:
        """Return a handler-declared default value."""
        return self.defaults.get(key, fallback)

    def fixed_bytes(self, key: str, fallback: int) -> int:
        """Return a handler-declared fixed string width."""
        return self.fixed_string_bytes.get(key, fallback)


def default_enum_key(values: dict[str, int], fallback: str) -> str:
    """Pick a stable default enum key from a map, or the fallback if empty."""
    if values:
        return str(next(iter(values.keys())))
    return fallback
