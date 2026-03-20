# tools/dawnpy/tests/test_client_descriptor.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for client descriptor parsing utilities."""

import pytest

from dawnpy.descriptor.client import (
    TAGS_TYPE_ERROR,
    ClientDescriptor,
    _is_fatal_io_decode_error,
    find_descriptor_path,
    load_client_descriptor,
)
from dawnpy.descriptor.definitions.objects import (
    DescriptorDecodeError,
    IoObject,
    ProgramObject,
    ProtocolObject,
)


def _write_descriptor(tmp_path, content: str) -> str:
    path = tmp_path / "descriptor.yaml"
    path.write_text(content)
    return str(path)


def test_find_descriptor_path(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios: []
protocols: []
"""
    _write_descriptor(tmp_path, descriptor)
    resolved = find_descriptor_path(str(tmp_path))
    assert resolved.endswith("descriptor.yaml")
    direct = find_descriptor_path(resolved)
    assert direct == resolved


def test_client_descriptor_protocols(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
    timestamp: true
  - type: dummy
    instance: 2
    dtype: uint8
  - id: io2
    type: sysinfo
    instance: 1
    dtype: uint32
    variant: uptime
programs:
  - id: prog1
    type: statsmin
    instance: 1
    config:
      inputs: [io1]
      outputs: [io2]
protocols:
  - &proto1
    id: proto1
    type: can
    instance: 1
    bindings: [io1, 123]
    config:
      node_id: 0
  - id: proto2
    type: modbus_rtu
    instance: 1
    bindings: [*proto1]
    config:
      baudrate: 9600
"""
    path = _write_descriptor(tmp_path, descriptor)
    desc = load_client_descriptor(path)

    assert isinstance(desc, ClientDescriptor)
    assert desc.get_protocol("can") is not None
    assert desc.get_protocol("modbus_rtu") is not None
    assert desc.get_protocols("can")[0].proto_id == "proto1"
    assert desc.get_protocols("can")[0].bindings == ["io1"]
    assert desc.get_protocols("modbus_rtu")[0].bindings == ["proto1"]
    assert desc.get_io("io1") is not None
    assert desc.get_io("missing") is None
    assert desc.get_io("io1").timestamp is True
    assert desc.get_io("io1").rw is False
    assert desc.programs[0].prog_id == "prog1"
    assert desc.programs[0].inputs == ["io1"]
    assert desc.programs[0].outputs == ["io2"]


def test_client_descriptor_tags(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
    tags: [heartbeat, fast]
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)
    desc = load_client_descriptor(path)

    tagged = desc.get_tagged_ios("heartbeat")
    assert tagged[0].io_id == "io1"
    assert desc.get_tagged_ios("missing") == []


def test_client_descriptor_invalid_tags(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
    tags:
      key: value
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)
    with pytest.raises(ValueError, match="tags must be a list of strings"):
        load_client_descriptor(path)


def test_load_client_descriptor_skips_failed_entries(monkeypatch, tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
programs:
  - id: prog1
    type: statsmin
    instance: 1
    config: {}
protocols:
  - id: proto1
    type: shell
    instance: 1
    config: {}
    bindings: []
"""
    path = _write_descriptor(tmp_path, descriptor)

    monkeypatch.setattr(IoObject, "from_spec", lambda spec, strict: None)
    monkeypatch.setattr(
        ProtocolObject,
        "from_spec",
        lambda spec, strict: (_ for _ in ()).throw(
            DescriptorDecodeError("bad proto")
        ),
    )
    monkeypatch.setattr(
        ProgramObject,
        "from_spec",
        lambda spec, strict: (_ for _ in ()).throw(
            DescriptorDecodeError("bad prog")
        ),
    )

    desc = load_client_descriptor(path)
    assert desc.ios == {}
    assert desc.programs == []
    assert desc.protocols == []


def test_load_client_descriptor_raises_for_tag_error(monkeypatch, tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
programs: []
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)

    monkeypatch.setattr(
        IoObject,
        "from_spec",
        lambda spec, strict: (_ for _ in ()).throw(
            DescriptorDecodeError(TAGS_TYPE_ERROR)
        ),
    )

    with pytest.raises(ValueError, match=TAGS_TYPE_ERROR):
        load_client_descriptor(path)


def test_load_client_descriptor_skips_non_tag_io_errors(monkeypatch, tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
programs: []
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)

    monkeypatch.setattr(
        IoObject,
        "from_spec",
        lambda spec, strict: (_ for _ in ()).throw(
            DescriptorDecodeError("bad io decode")
        ),
    )

    desc = load_client_descriptor(path)
    assert desc.ios == {}


def test_is_fatal_io_decode_error():
    assert _is_fatal_io_decode_error(DescriptorDecodeError(TAGS_TYPE_ERROR))
    assert not _is_fatal_io_decode_error(DescriptorDecodeError("bad io"))


def test_load_client_descriptor_handles_none_returns(monkeypatch, tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
programs:
  - id: prog1
    type: statsmin
    instance: 1
    config: {}
protocols:
  - id: proto1
    type: shell
    instance: 1
    config: {}
    bindings: []
"""
    path = _write_descriptor(tmp_path, descriptor)

    monkeypatch.setattr(IoObject, "from_spec", lambda spec, strict: None)
    monkeypatch.setattr(ProtocolObject, "from_spec", lambda spec, strict: None)
    monkeypatch.setattr(ProgramObject, "from_spec", lambda spec, strict: None)

    desc = load_client_descriptor(path)
    assert desc.ios == {}
    assert desc.programs == []
    assert desc.protocols == []


def test_client_descriptor_tags_list_validation(tmp_path):
    descriptor = """
metadata:
  version: '1.0'
ios:
  - id: io1
    type: dummy
    instance: 1
    dtype: uint8
    tags: [null, ok]
  - id: io2
    type: dummy
    instance: 2
    dtype: uint8
    tags:
      - key: value
protocols: []
"""
    path = _write_descriptor(tmp_path, descriptor)
    with pytest.raises(ValueError, match="tags must be a list of strings"):
        load_client_descriptor(path)
