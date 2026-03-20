# tools/dawnpy/src/dawnpy/cli/device_registry.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Device registry for loading and validating multiple descriptors."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from dawnpy.descriptor.client import find_descriptor_path
from dawnpy.descriptor.validation.conflicts import (
    ConflictError,
    check_key_conflicts,
)

T = TypeVar("T")


ConflictKeyFn = Callable[[T], Iterable[tuple[int, str]]]


class DeviceConflictError(ValueError):
    """Raised when descriptor conflict checking finds overlaps."""

    def __init__(self, conflicts: list[ConflictError]) -> None:
        """Create a conflict error with detailed conflicts."""
        self.conflicts = conflicts
        super().__init__(self.format_message())

    def format_message(self, max_items: int = 10) -> str:
        """Format conflicts as a readable message."""
        lines = ["Detected overlapping IDs between device mappings:"]
        for conflict in self.conflicts[:max_items]:
            lines.append(
                f"- 0x{conflict.can_id:X}: {conflict.first} "
                f"<-> {conflict.second}"
            )
        remaining = len(self.conflicts) - max_items
        if remaining > 0:
            lines.append(f"- ... and {remaining} more conflict(s)")
        return "\n".join(lines)


@dataclass
class DeviceRegistry(Generic[T]):
    """Loaded descriptor registry."""

    paths: list[str]
    devices: list[T]

    @classmethod
    def load(
        cls,
        descriptor_paths: Iterable[str],
        *,
        loader: Callable[[str], T],
        conflict_keys: ConflictKeyFn[T] | None = None,
    ) -> DeviceRegistry[T]:
        """Load descriptor files into a registry."""
        paths = [find_descriptor_path(path) for path in descriptor_paths]
        devices = [loader(path) for path in paths]

        if conflict_keys:
            labeled_items = []
            for path, device in zip(paths, devices, strict=False):
                items = list(conflict_keys(device))
                labeled_items.append((path, items))
            conflicts = check_key_conflicts(labeled_items)
            if conflicts:
                raise DeviceConflictError(conflicts)

        return cls(paths=paths, devices=devices)
