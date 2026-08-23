# tools/dawnpy/tests/commands/test_desc_compat.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the desc-compat CLI command."""

import copy
import struct
from pathlib import Path

import pytest
from click.testing import CliRunner

from dawnpy.commands.cmd_desc_compat import cmd_desc_compat
from dawnpy.descriptor.reports.graph import build_descriptor_graph
from dawnpy.descriptor.support.vars import load_yaml_with_vars
from dawnpy.objectid import ObjectIdDecoder

pytestmark = pytest.mark.usefixtures("source_free_headers")

_YAML = """
ios:
- id: btn0
  type: dummy
  dtype: bool
protocols:
- id: proto0
  type: dummy
  config:
    bindings: [btn0]
"""

_MULTI_YAML = """
descriptor0:
  ios:
  - id: btn0
    type: dummy
    dtype: bool
descriptor1:
  ios:
  - id: btn1
    type: dummy
    dtype: bool
"""

_EMPTY_YAML = """
ios: []
protocols: []
"""


def _write(tmp_path: Path, text: str, name: str = "descriptor.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def _objids(yaml_file: Path, key: str = "descriptor0") -> dict:
    spec = load_yaml_with_vars(str(yaml_file))
    if key in spec:
        spec = spec[key]
    graph = build_descriptor_graph(copy.deepcopy(spec), key)
    return {n.id: n.objid for n in graph.nodes if n.objid is not None}


def _blob_for(objids: dict, *, drop_io: bool = False) -> bytes:
    """Build a capabilities blob covering the given descriptor objects."""
    decoder = ObjectIdDecoder()
    sections: dict[str, set[int]] = {
        "IO": set(),
        "PROG": set(),
        "PROTO": set(),
    }
    dtypes: set[int] = set()
    for objid in objids.values():
        decoded = decoder.decode(objid)
        if decoded.type_name in sections:
            sections[decoded.type_name].add(decoded.cls)
        if decoded.dtype:
            dtypes.add(decoded.dtype)
    if drop_io:
        sections["IO"] = set()

    def bitmap(ids: set[int]) -> bytes:
        raw = bytearray(64)
        for cls_id in ids:
            raw[cls_id // 8] |= 1 << (cls_id % 8)
        return bytes(raw)

    payload = bytearray(504)
    payload[0:64] = bitmap(sections["IO"])
    payload[64:128] = bitmap(sections["PROG"])
    payload[128:192] = bitmap(sections["PROTO"])

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
        2,
        4096,
        0x1FF,
        0x1FF,
        0x1FF,
    ]
    for index, word in enumerate(meta):
        struct.pack_into("<I", payload, 192 + index * 4, word)

    header = bytes([2, 0]) + (504).to_bytes(2, "little")
    return header + (0).to_bytes(4, "little") + bytes(payload)


def test_desc_compat_accepts_supported_target(tmp_path: Path):
    """A target providing every class exits zero."""
    yaml_file = _write(tmp_path, _YAML)
    caps = tmp_path / "caps.bin"
    caps.write_bytes(_blob_for(_objids(yaml_file)))

    result = CliRunner().invoke(
        cmd_desc_compat, [str(yaml_file), str(caps), "--slot", "0"]
    )

    assert result.exit_code == 0
    assert "Descriptor compatibility: OK" in result.output


def test_desc_compat_rejects_unsupported_target(tmp_path: Path):
    """A missing class fails the command."""
    yaml_file = _write(tmp_path, _YAML)
    caps = tmp_path / "caps.bin"
    caps.write_bytes(_blob_for(_objids(yaml_file), drop_io=True))

    result = CliRunner().invoke(cmd_desc_compat, [str(yaml_file), str(caps)])

    assert result.exit_code != 0
    assert "INCOMPATIBLE" in result.output
    assert "btn0" in result.output


def test_desc_compat_reads_hex_file(tmp_path: Path):
    """--hex-file supplies the blob as hex text."""
    yaml_file = _write(tmp_path, _YAML)
    blob = _blob_for(_objids(yaml_file))
    hex_file = tmp_path / "caps.hex"
    hex_file.write_text(" ".join(f"{byte:02x}" for byte in blob))

    result = CliRunner().invoke(
        cmd_desc_compat, [str(yaml_file), "--hex-file", str(hex_file)]
    )

    assert result.exit_code == 0
    assert "Descriptor compatibility: OK" in result.output


def test_desc_compat_selects_descriptor_slot_key(tmp_path: Path):
    """--descriptor picks a slot out of a multi-descriptor YAML."""
    yaml_file = _write(tmp_path, _MULTI_YAML)
    caps = tmp_path / "caps.bin"
    caps.write_bytes(_blob_for(_objids(yaml_file, "descriptor1")))

    result = CliRunner().invoke(
        cmd_desc_compat,
        [str(yaml_file), str(caps), "--descriptor", "descriptor1"],
    )

    assert result.exit_code == 0
    assert "Objects checked: 1" in result.output


def test_desc_compat_requires_a_blob_source(tmp_path: Path):
    """Omitting both CAPS and --hex-file is an error."""
    yaml_file = _write(tmp_path, _YAML)

    result = CliRunner().invoke(cmd_desc_compat, [str(yaml_file)])

    assert result.exit_code != 0
    assert "Provide CAPS or --hex-file" in result.output


def test_desc_compat_missing_caps_file(tmp_path: Path):
    """A missing capabilities file is reported."""
    yaml_file = _write(tmp_path, _YAML)

    result = CliRunner().invoke(
        cmd_desc_compat, [str(yaml_file), str(tmp_path / "absent.bin")]
    )

    assert result.exit_code != 0
    assert "Capabilities file not found" in result.output


def test_desc_compat_descriptor_without_objects(tmp_path: Path):
    """A descriptor with no decodable objects is an error."""
    yaml_file = _write(tmp_path, _EMPTY_YAML)
    caps = tmp_path / "caps.bin"
    caps.write_bytes(_blob_for({}))

    result = CliRunner().invoke(cmd_desc_compat, [str(yaml_file), str(caps)])

    assert result.exit_code != 0
    assert "No decodable objects" in result.output
