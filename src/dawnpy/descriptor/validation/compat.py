# tools/dawnpy/src/dawnpy/descriptor/validation/compat.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor vs firmware capabilities compatibility check.

A descriptor is data: it can be authored long after the firmware that
will run it was built. The firmware advertises the object classes and
dtypes it was compiled with through the capabilities IO blob
(``dawn/io/capabilities.hxx``). This module answers the question the
descriptor-switch workflow needs before an upload: can this target run
this descriptor?
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from dawnpy.descriptor.reports.capabilities_blob import (
    decode_capabilities_blob,
)
from dawnpy.objectid import ObjectIdDecoder

# Capabilities bitmap section per decoded ObjectID type name.
_BITMAP_BY_TYPE: dict[str, str] = {
    "IO": "io_enabled",
    "PROG": "prog_enabled",
    "PROTO": "proto_enabled",
}


class CompatIssue(BaseModel):
    """One reason a descriptor cannot run on the target."""

    model_config = ConfigDict(frozen=True)

    kind: str
    object_id: str | None
    detail: str


class CompatResult(BaseModel):
    """Outcome of a descriptor/capabilities comparison."""

    model_config = ConfigDict(frozen=True)

    compatible: bool
    issues: list[CompatIssue]
    checked_objects: int
    slot_size: int
    slots: int
    descriptor_bytes: int | None = None


def _slot_issues(
    caps: dict[str, Any], descriptor_bytes: int | None, slot: int | None
) -> list[CompatIssue]:
    """Return slot-count and slot-size issues."""
    issues: list[CompatIssue] = []
    slots = int(caps.get("desc_slots", 0))
    slot_size = int(caps.get("desc_slot_size", 0))

    if slot is not None and slot >= slots:
        issues.append(
            CompatIssue(
                kind="slot",
                object_id=None,
                detail=(
                    f"target has {slots} descriptor slot(s); "
                    f"slot {slot} is out of range"
                ),
            )
        )
    if (
        descriptor_bytes is not None
        and slot_size
        and (descriptor_bytes > slot_size)
    ):
        issues.append(
            CompatIssue(
                kind="slot_size",
                object_id=None,
                detail=(
                    f"descriptor is {descriptor_bytes} bytes; "
                    f"target slot holds {slot_size}"
                ),
            )
        )
    return issues


def check_compatibility(
    objids: dict[str, int],
    blob: bytes,
    *,
    descriptor_bytes: int | None = None,
    slot: int | None = None,
) -> CompatResult:
    """Check descriptor object IDs against a capabilities blob.

    :param objids: Mapping of descriptor object id -> encoded ObjectID.
    :param blob: Raw capabilities IO blob read from the target.
    :param descriptor_bytes: Encoded descriptor size, when known.
    :param slot: Target descriptor slot index, when known.
    """
    caps = decode_capabilities_blob(blob)
    decoder = ObjectIdDecoder()

    dtype_bits = caps["dtype_bits_lo"] | (caps["dtype_bits_hi"] << 32)
    issues: list[CompatIssue] = []

    for name, objid in sorted(objids.items()):
        decoded = decoder.decode(objid)
        section = _BITMAP_BY_TYPE.get(str(decoded.type_name))
        if section is None:
            continue
        if decoded.cls not in caps[section]:
            issues.append(
                CompatIssue(
                    kind="class",
                    object_id=name,
                    detail=(
                        f"{decoded.type_name} class "
                        f"'{decoded.cls_name}' (id {decoded.cls}) "
                        "is not enabled in the target firmware"
                    ),
                )
            )
        if decoded.dtype and not dtype_bits & (1 << int(decoded.dtype)):
            issues.append(
                CompatIssue(
                    kind="dtype",
                    object_id=name,
                    detail=(
                        f"dtype '{decoded.dtype_name}' "
                        "is not enabled in the target firmware"
                    ),
                )
            )

    issues.extend(_slot_issues(caps, descriptor_bytes, slot))

    return CompatResult(
        compatible=not issues,
        issues=issues,
        checked_objects=len(objids),
        slot_size=int(caps.get("desc_slot_size", 0)),
        slots=int(caps.get("desc_slots", 0)),
        descriptor_bytes=descriptor_bytes,
    )


def format_report(result: CompatResult) -> list[str]:
    """Return human-readable lines for a compatibility result."""
    lines = [
        "Descriptor compatibility: "
        + ("OK" if result.compatible else "INCOMPATIBLE"),
        f"Objects checked: {result.checked_objects}",
        f"Target slots: {result.slots} x {result.slot_size} bytes",
    ]
    if result.descriptor_bytes is not None:
        lines.append(f"Descriptor size: {result.descriptor_bytes} bytes")
    if result.issues:
        lines.append("")
        lines.append(f"Issues ({len(result.issues)}):")
        for issue in result.issues:
            where = f" [{issue.object_id}]" if issue.object_id else ""
            lines.append(f"  [{issue.kind}]{where} {issue.detail}")
    return lines
