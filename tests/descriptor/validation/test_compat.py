#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor vs firmware capabilities compatibility checks."""

from __future__ import annotations

import struct

import pytest

from dawnpy.descriptor.validation.compat import (
    check_compatibility,
    format_report,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")

# gpi_single / gpo_single IO objects, uint32 payload.
GPI_OBJID = 0x47870000
GPO_OBJID = 0x47A70001
GPI_CLS = 60
GPO_CLS = 61
UINT32_DTYPE = 7


def make_blob(
    io_ids: list[int],
    dtypes: list[int],
    *,
    slots: int = 2,
    slot_size: int = 4096,
) -> bytes:
    """Build a minimal capabilities blob enabling the given IO classes."""
    bitmap = bytearray(64)
    for cls_id in io_ids:
        bitmap[cls_id // 8] |= 1 << (cls_id % 8)

    payload = bytearray(504)
    payload[0:64] = bytes(bitmap)

    dtype_bits = 0
    for dtype in dtypes:
        dtype_bits |= 1 << dtype
    meta = [
        dtype_bits & 0xFFFFFFFF,
        (dtype_bits >> 32) & 0xFFFFFFFF,
        0,
        0,
        0,
        0,
        slots,
        slot_size,
        max(io_ids or [0]),
        0,
        0,
    ]
    for index, word in enumerate(meta):
        struct.pack_into("<I", payload, 192 + index * 4, word)

    header = bytes([2, 0]) + (504).to_bytes(2, "little")
    return header + (0).to_bytes(4, "little") + bytes(payload)


def test_descriptor_fits_target() -> None:
    """A target providing every class and dtype accepts the descriptor."""
    blob = make_blob([GPI_CLS, GPO_CLS], [UINT32_DTYPE])

    result = check_compatibility(
        {"gpi1": GPI_OBJID, "gpo1": GPO_OBJID}, blob, slot=0
    )

    assert result.compatible
    assert result.issues == []
    assert result.checked_objects == 2


def test_missing_io_class_is_reported() -> None:
    """A class absent from the firmware bitmap blocks the upload."""
    blob = make_blob([GPO_CLS], [UINT32_DTYPE])

    result = check_compatibility({"gpi1": GPI_OBJID}, blob)

    assert not result.compatible
    assert [i.kind for i in result.issues] == ["class"]
    assert result.issues[0].object_id == "gpi1"


def test_missing_dtype_is_reported() -> None:
    """A dtype the firmware was not built with blocks the upload."""
    blob = make_blob([GPI_CLS], [])

    result = check_compatibility({"gpi1": GPI_OBJID}, blob)

    assert not result.compatible
    assert "dtype" in {issue.kind for issue in result.issues}


def test_slot_index_out_of_range() -> None:
    """Uploading beyond the advertised slot count is rejected."""
    blob = make_blob([GPI_CLS], [UINT32_DTYPE], slots=2)

    result = check_compatibility({"gpi1": GPI_OBJID}, blob, slot=7)

    assert not result.compatible
    assert [i.kind for i in result.issues] == ["slot"]


def test_descriptor_larger_than_slot() -> None:
    """A descriptor exceeding the slot size is rejected."""
    blob = make_blob([GPI_CLS], [UINT32_DTYPE], slot_size=256)

    result = check_compatibility(
        {"gpi1": GPI_OBJID}, blob, descriptor_bytes=4096
    )

    assert not result.compatible
    assert [i.kind for i in result.issues] == ["slot_size"]


def test_report_lists_every_issue() -> None:
    """The report names each blocking issue."""
    blob = make_blob([], [], slots=1, slot_size=64)

    result = check_compatibility(
        {"gpi1": GPI_OBJID}, blob, descriptor_bytes=4096, slot=3
    )
    lines = "\n".join(format_report(result))

    # Class and dtype *names* come from header defs, which these tests
    # stub out; assert on the header-independent ids instead.
    assert "INCOMPATIBLE" in lines
    assert f"(id {GPI_CLS})" in lines
    assert "slot 3 is out of range" in lines
    assert "target slot holds 64" in lines


def test_non_object_ids_are_skipped() -> None:
    """An ObjectID outside IO/PROG/PROTO carries no capability bit."""
    blob = make_blob([], [])

    result = check_compatibility({"any0": 0}, blob)

    assert result.compatible
    assert result.checked_objects == 1
