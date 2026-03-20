# tools/dawnpy/tests/test_proto_caps.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for protocol capabilities."""

from dawnpy.descriptor.encoding.proto_caps import is_multi_device


def test_is_multi_device():
    assert is_multi_device("can")
    assert is_multi_device("modbus_rtu")
    assert not is_multi_device("serial")
    assert not is_multi_device("nxscope_dummy")
    assert not is_multi_device("nxscope_serial")
    assert not is_multi_device("unknown")


def test_validate_descriptor_args():
    from dawnpy.descriptor.encoding.proto_caps import validate_descriptor_args

    validate_descriptor_args("can", ["a", "b"])
    validate_descriptor_args("serial", ["a"])

    import pytest

    with pytest.raises(ValueError, match="supports only one descriptor"):
        validate_descriptor_args("serial", ["a", "b"])

    with pytest.raises(ValueError, match="At least one descriptor"):
        validate_descriptor_args("can", [])
