# tools/dawnpy/tests/descriptor/handlers/helpers.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Small object builders for handler tests."""

from dawnpy.descriptor.definitions.objects import IoObject


def to_io_obj(spec: dict, obj_id: str = "test_io") -> IoObject:
    full_spec = {
        "id": obj_id,
        "type": spec.get("type", "dummy"),
        "instance": spec.get("instance", 1),
        "dtype": spec.get("dtype", "uint32"),
        "config": spec.get("config", {}),
    }
    return IoObject.from_spec(full_spec)
