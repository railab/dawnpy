# tools/dawnpy/tests/test_conflicts.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for conflict helpers."""

from dawnpy.descriptor.validation.conflicts import check_key_conflicts


def test_check_key_conflicts():
    items = [
        ("dev1", [(1, "io1"), (2, "io2")]),
        ("dev2", [(2, "io3")]),
    ]
    conflicts = check_key_conflicts(items)
    assert conflicts
    assert conflicts[0].can_id == 2


def test_check_key_conflicts_ignores_same_label_duplicates():
    items = [
        ("dev1", [(2, "io1"), (2, "io1")]),
    ]
    conflicts = check_key_conflicts(items)
    assert conflicts == []


def test_check_key_conflicts_detects_same_label_different_items():
    items = [
        ("dev1", [(2, "obj0"), (2, "obj1")]),
    ]
    conflicts = check_key_conflicts(items)
    assert conflicts
    assert conflicts[0].can_id == 2
