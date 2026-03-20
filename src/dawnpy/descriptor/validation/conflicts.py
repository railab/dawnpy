# tools/dawnpy/src/dawnpy/descriptor/conflicts.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Conflict check helpers for protocol mappings."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ConflictError:
    """Represents a key overlap between two mappings."""

    can_id: int
    first: str
    second: str


def check_key_conflicts(
    labeled_items: Iterable[tuple[str, Iterable[tuple[int, str]]]],
) -> list[ConflictError]:
    """Check for duplicate integer keys across different item labels.

    Duplicates are allowed only when both label and item label are identical.
    """
    seen: dict[int, tuple[str, str]] = {}
    conflicts: list[ConflictError] = []
    for label, items in labeled_items:
        for key, item_label in items:
            full_label = f"{label}:{item_label}"
            if key in seen and seen[key][1] != full_label:
                conflicts.append(
                    ConflictError(
                        can_id=key,
                        first=seen[key][1],
                        second=full_label,
                    )
                )
                continue
            if key not in seen:
                seen[key] = (label, full_label)
    return conflicts
