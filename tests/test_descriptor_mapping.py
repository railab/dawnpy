# tools/dawnpy/tests/test_descriptor_mapping.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor mapping helpers."""

from dawnpy.descriptor.support.mapping import resolve_objects_with_bindings


def test_resolve_objects_with_bindings():
    config = {
        "objects": [
            {"type": "read", "bindings": [{"id": "io1"}, "io2"]},
            {"type": "write", "bindings": []},
            "invalid",
        ]
    }
    result = resolve_objects_with_bindings(config)
    assert len(result) == 2
    assert result[0]["bindings_resolved"] == ["io1", "io2"]
    assert result[1]["bindings_resolved"] == []
