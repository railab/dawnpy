# tools/dawnpy/src/dawnpy/descriptor/handlers/_allocation.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared helpers for handler-owned allocation report rows."""

from __future__ import annotations

from typing import Any


def try_parse_int(value: Any) -> int | None:
    """Parse int from int/str literal; return None if not an integer."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def fmt_hex(value: int | None) -> str:
    """Return a hex string for an optional integer value."""
    if value is None:
        return "n/a"
    return f"0x{value:X}"


def fmt_bindings(bindings: list[str]) -> str:
    """Return a compact binding list for table output."""
    if not bindings:
        return "none"
    return ", ".join(bindings)


def fmt_value(value: Any, hex_format: bool = False) -> str:
    """Return a stable display string for an allocation-table value."""
    if isinstance(value, int):
        if hex_format:
            return f"0x{value:X}"
        return str(value)
    if value is None:
        return "n/a"
    return str(value)


def bindings_allocation_rows(
    bindings: list[str],
    details: str = "",
) -> list[list[str]]:
    """Return standard bind-index rows for protocols with simple bindings."""
    size = len(bindings)
    end = size if size > 0 else None
    return [
        [
            "0",
            "bind-index",
            "1" if size else "n/a",
            str(end) if end else "n/a",
            str(size),
            (
                f"{details}, ios={fmt_bindings(bindings)}"
                if details
                else f"ios={fmt_bindings(bindings)}"
            ),
        ]
    ]
