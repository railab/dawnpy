# tools/dawnpy/tests/test_device_registry.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for device registry."""

import pytest

from dawnpy.cli.device_registry import DeviceConflictError, DeviceRegistry
from dawnpy.descriptor.client import load_client_descriptor


def _write_descriptor(tmp_path, content: str) -> str:
    path = tmp_path / "descriptor.yaml"
    path.write_text(content)
    return str(path)


def test_device_registry_load(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios: []
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)
    registry = DeviceRegistry.load([path], loader=load_client_descriptor)
    assert registry.paths
    assert registry.devices


def test_device_registry_conflict(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios: []
protocols: []
"""
    path1 = tmp_path / "a"
    path2 = tmp_path / "b"
    path1.mkdir()
    path2.mkdir()
    desc1 = _write_descriptor(path1, descriptor)
    desc2 = _write_descriptor(path2, descriptor)

    def conflict_keys(_device):
        return [(1, "io1")]

    with pytest.raises(DeviceConflictError) as exc_info:
        DeviceRegistry.load(
            [desc1, desc2],
            loader=load_client_descriptor,
            conflict_keys=conflict_keys,
        )
    msg = exc_info.value.format_message()
    assert "Detected overlapping IDs" in msg
    assert "0x1" in msg


def test_device_conflict_error_format_limit():
    conflicts = []
    for i in range(12):
        from dawnpy.descriptor.validation.conflicts import ConflictError

        conflicts.append(
            ConflictError(can_id=i, first=f"a:{i}", second=f"b:{i}")
        )
    err = DeviceConflictError(conflicts)
    msg = err.format_message(max_items=3)
    assert "... and 9 more conflict(s)" in msg
