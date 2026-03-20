# tools/dawnpy/src/dawnpy/descriptor/mapping.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Generic protocol mapping helpers for client tooling."""

from typing import Any

from dawnpy.descriptor.support.utils import resolve_references


def resolve_objects_with_bindings(
    config: dict[str, Any], key: str = "objects"
) -> list[dict[str, Any]]:
    """Return protocol objects with resolved bindings."""
    result: list[dict[str, Any]] = []
    for obj in config.get(key, []):
        if not isinstance(obj, dict):
            continue
        entry = dict(obj)
        entry["bindings_resolved"] = resolve_references(
            obj.get("bindings", [])
        )
        result.append(entry)
    return result
