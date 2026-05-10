# tools/dawnpy/tests/test_descriptor_utils.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor utilities."""

from dawnpy.descriptor.support.utils import (
    resolve_flexible_reference,
    resolve_reference,
    resolve_references,
)


def test_resolve_reference():
    assert resolve_reference({"id": "io1"}) == "io1"
    assert resolve_reference("io2") == "io2"
    assert resolve_reference(123) is None


def test_resolve_references():
    refs = [{"id": "io1"}, "io2", 123, {"nope": "x"}]
    assert resolve_references(refs) == ["io1", "io2"]


def test_resolve_flexible_reference():
    assert resolve_flexible_reference({"id": "io1"}) == "io1"
    assert resolve_flexible_reference({"io": "io2"}) == "io2"
    assert resolve_flexible_reference({"ref": "io3"}) == "io3"
    assert resolve_flexible_reference("io4") == "io4"
    assert resolve_flexible_reference({"id": None, "io": None}) is None
    assert resolve_flexible_reference(123) is None
