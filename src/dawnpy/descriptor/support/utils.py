# tools/dawnpy/src/dawnpy/descriptor/utils.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor helper utilities shared by client tooling."""

from collections.abc import Iterable
from typing import Any


def resolve_reference(ref: Any) -> str | None:
    """Resolve a reference to an object ID."""
    if isinstance(ref, dict):
        return ref.get("id")
    if isinstance(ref, str):
        return ref
    return None


def resolve_flexible_reference(ref: Any) -> str | None:
    """Resolve object references from id/io/ref dict forms or plain strings."""
    if isinstance(ref, str):
        return ref
    if not isinstance(ref, dict):
        return None

    value = ref.get("id")
    if value is None:
        value = ref.get("io")
    if value is None:
        value = ref.get("ref")
    return resolve_reference(value)


def resolve_references(refs: Iterable[Any]) -> list[str]:
    """Resolve a list of references to object IDs."""
    result: list[str] = []
    for ref in refs:
        resolved = resolve_reference(ref)
        if resolved:
            result.append(resolved)
    return result
