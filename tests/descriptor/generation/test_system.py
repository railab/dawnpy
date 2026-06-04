# tools/dawnpy/tests/descriptor/generation/test_system.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for System (OBJTYPE_ANY) descriptor generation."""

import pytest

from dawnpy.descriptor.definitions.objects import (
    DescriptorDecodeError,
    SystemObject,
    decode_objects,
)
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_decode_system_object():
    """A ``system:`` entry decodes to a SystemObject."""
    spec = {
        "system": [
            {"id": "lte_main", "type": "lte", "config": {"apn": "internet"}}
        ]
    }
    objs = decode_objects(spec)
    sys_objs = [o for o in objs if isinstance(o, SystemObject)]
    assert len(sys_objs) == 1
    assert sys_objs[0].category == "SYSTEM"
    assert sys_objs[0].system_type == "lte"
    assert sys_objs[0].get_helper_call() == "CSystemLte::objectId(0)"


def test_unknown_system_type_rejected():
    """An unknown System type fails strict decoding."""
    spec = {"system": [{"id": "x", "type": "nope"}]}
    with pytest.raises(DescriptorDecodeError):
        decode_objects(spec, strict=True)


def test_generate_lte_system_object():
    """LTE system object emits objectId + cfgId config items."""
    spec = {
        "metadata": {"version": "1.0"},
        "system": [
            {
                "id": "lte_main",
                "type": "lte",
                "config": {
                    "apn": "internet",
                    "auth_type": 1,
                    "ip_type": 2,
                    "reg_timeout": 90,
                },
            }
        ],
    }
    out = generate_from_spec(DescriptorGenerator(), spec)

    assert '#include "dawn/system/lte.hxx"' in out
    assert "CSystemLte::objectId(0)" in out
    assert "CSystemLte::cfgIdApn(" in out
    assert "CSystemLte::cfgIdAuthType()" in out
    assert "CSystemLte::cfgIdIpType()" in out
    assert "CSystemLte::cfgIdRegTimeout()" in out
    # auth_type / ip_type / reg_timeout scalar values present
    assert "1," in out and "2," in out and "90," in out


def test_absent_fields_not_emitted():
    """Only config items present in YAML are emitted (rest use Kconfig)."""
    spec = {
        "system": [
            {"id": "lte_main", "type": "lte", "config": {"ip_type": 0}}
        ],
    }
    out = generate_from_spec(DescriptorGenerator(), spec)
    assert "CSystemLte::cfgIdIpType()" in out
    assert "CSystemLte::cfgIdApn(" not in out
    assert "CSystemLte::cfgIdRegTimeout()" not in out
