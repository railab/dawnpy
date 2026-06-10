# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor CLI commands."""

import importlib
import struct
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import click
import pytest
from click.testing import CliRunner

import dawnpy.commands.cmd_desc_bin as cmd_desc_bin_mod
import dawnpy.commands.cmd_desc_decode_caps as cmd_desc_decode_caps_mod
import dawnpy.commands.cmd_desc_gen as cmd_desc_gen_mod
import dawnpy.commands.cmd_desc_valid as cmd_desc_valid_mod
import dawnpy.descriptor.encoding.binary_serializer as binary_serializer_mod
import dawnpy.descriptor.encoding.prog_serializer as prog_serializer_mod
import dawnpy.descriptor.encoding.proto_serializer as proto_serializer_mod
import dawnpy.descriptor.validation.headers_check as headers_check_mod
import dawnpy.headerdefs.bundle as header_bundle_mod
from dawnpy.commands import (
    cmd_desc_headers_check as cmd_desc_headers_check_mod,
)
from dawnpy.commands.cmd_desc_bin import cmd_desc_bin
from dawnpy.commands.cmd_desc_decode_caps import cmd_desc_decode_caps
from dawnpy.commands.cmd_desc_gen import cmd_desc_gen
from dawnpy.commands.cmd_desc_headers_check import cmd_desc_headers_check
from dawnpy.commands.cmd_desc_valid import cmd_desc_valid
from dawnpy.descriptor.client import (
    ClientDescriptor,
    ClientIo,
    ClientProgram,
    ClientProto,
)
from dawnpy.descriptor.definitions.objects import (
    IoObject,
    ProgramObject,
    ProtocolObject,
)
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.binary_serializer import (
    _io_class_name,
    _io_dtype_name,
    _serialize_io_object,
    _serialize_metadata,
)
from dawnpy.descriptor.encoding.binary_serializer import (
    generate_descriptor_binaries as _generate_descriptor_binaries,
)
from dawnpy.descriptor.encoding.binary_serializer import (
    generate_descriptor_binary as _generate_descriptor_binary,
)
from dawnpy.descriptor.encoding.packager import (
    fill_crc32_footer,
    nuttx_crc32,
    parse_hex_file_text,
)
from dawnpy.descriptor.encoding.prog_serializer import serialize_prog_object
from dawnpy.descriptor.encoding.proto_runtime import default_enum_key
from dawnpy.descriptor.encoding.proto_serializer import serialize_proto_object
from dawnpy.descriptor.encoding.words import cfg_id, enabled_flag_names
from dawnpy.descriptor.handlers import io_config as io_config_mod
from dawnpy.descriptor.handlers._allocation import (
    bindings_allocation_rows as _bindings_allocation_rows,
)
from dawnpy.descriptor.handlers._allocation import (
    fmt_bindings as _fmt_bindings,
)
from dawnpy.descriptor.handlers._allocation import fmt_hex as _fmt_hex
from dawnpy.descriptor.handlers._allocation import fmt_value as _fmt_value
from dawnpy.descriptor.handlers._allocation import (
    try_parse_int,
)
from dawnpy.descriptor.handlers._io_dummy_common import (
    _pack_init_value as _coerce_u32_words_for_dtype,
)
from dawnpy.descriptor.handlers._proto_modbus_common import (
    modbus_allocation_rows as _modbus_handler_allocation_rows,
)
from dawnpy.descriptor.handlers._proto_nxscope_common import (
    nxscope_allocation_rows as _nxscope_allocation_rows,
)
from dawnpy.descriptor.handlers.proto_can import (
    allocation_notes as _can_allocation_notes,
)
from dawnpy.descriptor.handlers.proto_can import (
    allocation_rows as _can_handler_allocation_rows,
)
from dawnpy.descriptor.handlers.proto_nimble import (
    allocation_rows as _nimble_handler_allocation_rows,
)
from dawnpy.descriptor.handlers.proto_serial import (
    allocation_rows as _serial_handler_allocation_rows,
)
from dawnpy.descriptor.handlers.proto_shell import (
    allocation_rows as _shell_handler_allocation_rows,
)
from dawnpy.descriptor.handlers.proto_wakaama import (
    allocation_rows as _wakaama_handler_allocation_rows,
)
from dawnpy.descriptor.reports.allocation import (
    _print_vars_summary,
    print_protocol_allocation_summaries,
)
from dawnpy.descriptor.reports.capabilities_blob import (
    decode_capabilities_blob as _decode_capabilities_blob,
)
from dawnpy.descriptor.validation.validate import (
    _print_object_summary,
    _print_table,
    _proto_has_unresolved_kconfig,
)
from dawnpy.descriptor.validation.validate import (
    can_has_unresolved_kconfig as _can_has_unresolved_kconfig,
)
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import header_cfg_id
from dawnpy.objectid import ObjectIdDecoder
from dawnpy.sources import DawnSourcesMissing
from tests.descriptor.conftest import (
    minimal_header_bundle,
    minimal_header_lookups,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")
_COMMAND_IMPORTS = (
    cmd_desc_bin_mod,
    cmd_desc_gen_mod,
    cmd_desc_valid_mod,
    cmd_desc_decode_caps_mod,
    cmd_desc_headers_check_mod,
)


@pytest.fixture
def mock_header_cfg_id(monkeypatch):
    """Replace Dawn header cfg-id lookups with fixed unit-test values."""
    mapping = {
        ("CIOPwm", "cfgIdFreq"): 17,
        ("CIOPulseCount", "cfgIdHighNs"): 18,
        ("CIOPulseCount", "cfgIdLowNs"): 19,
        ("CIOCommon", "cfgIdDevno"): 4,
        ("CIOCommon", "cfgIdNotify"): 5,
        ("CIOCommon", "cfgIdLimitMin"): 1,
        ("CIOCommon", "cfgIdLimitMax"): 2,
        ("CIOCommon", "cfgIdLimitStep"): 3,
    }

    def _fake(owner: str, method: str) -> int:
        return mapping[(owner, method)]

    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: minimal_header_bundle(
            lookups=minimal_header_lookups(cfg_id_loader=_fake)
        ),
    )
    return _fake


def _proto(
    config: dict[str, object], bindings: list[str] | None = None
) -> Any:
    return SimpleNamespace(config=config, bindings=bindings or [])


def _can_allocation_rows(config: dict[str, object]) -> list[list[str]]:
    return _can_handler_allocation_rows(_proto(config))


def _modbus_allocation_rows(config: dict[str, object]) -> list[list[str]]:
    return _modbus_handler_allocation_rows(_proto(config))


def _serial_allocation_rows(
    config: dict[str, object], bindings: list[str]
) -> list[list[str]]:
    return _serial_handler_allocation_rows(_proto(config, bindings))


def _shell_allocation_rows(
    config: dict[str, object], bindings: list[str]
) -> list[list[str]]:
    return _shell_handler_allocation_rows(_proto(config, bindings))


def _nimble_allocation_rows(config: dict[str, object]) -> list[list[str]]:
    return _nimble_handler_allocation_rows(_proto(config))


def _wakaama_allocation_rows(config: dict[str, object]) -> list[list[str]]:
    return _wakaama_handler_allocation_rows(_proto(config))


def _print_can_kconfig_note(config: dict[str, object]) -> None:
    for note in _can_allocation_notes(_proto(config)):
        click.echo(note)


def _mk_io(
    io_type: str,
    dtype: str = "uint32",
    *,
    subtype: str | None = None,
    variant: str | None = None,
) -> IoObject:
    return IoObject(
        obj_id=f"{io_type}0",
        io_type=io_type,
        instance=0,
        dtype=dtype,
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=subtype,
        variant=variant,
    )


_CAPS_IO_BITS = (1, 2, 3, 4)
_CAPS_PROG_BITS = (1, 2, 3, 4)
_CAPS_PROTO_BITS = (1, 2, 3, 4)


def _set_capability_bits(
    payload: bytearray, offset: int, bits: tuple[int, ...]
) -> None:
    for bit in bits:
        payload[offset + (bit // 8)] |= 1 << (bit % 8)


def _make_capabilities_blob_v2() -> bytes:
    payload = bytearray(504)

    _set_capability_bits(payload, 0, _CAPS_IO_BITS)
    _set_capability_bits(payload, 64, _CAPS_PROG_BITS)
    _set_capability_bits(payload, 128, _CAPS_PROTO_BITS)

    # metadata starts at payload offset 192
    struct.pack_into(
        "<IIIIIIIIIII",
        payload,
        192,
        0x00008089,  # dtype bits incl bool/int32/uint32/block
        0,  # dtype_hi
        1,  # io_flags_lo (timestamp)
        0,  # io_flags_hi
        0x21,  # build flags (os_nuttx + desc_dynamic)
        0,  # build_flags_hi
        2,  # desc slots
        4096,  # slot size
        0x1FF,  # max io cls
        0x1FF,  # max prog cls
        0x1FF,  # max proto cls
    )

    header = struct.pack("<BBHI", 2, 0, 504, 0)
    return header + bytes(payload)


def _to_shell_hexdump(blob: bytes) -> str:
    lines: list[str] = []
    for offset in range(0, len(blob), 16):
        chunk = blob[offset : offset + 16]
        left = " ".join(f"{b:02x}" for b in chunk[:8])
        right = " ".join(f"{b:02x}" for b in chunk[8:])
        hex_part = f"{left}  {right}" if right else left
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset:08x}: {hex_part:<47}  {ascii_part}")
    return "\n".join(lines) + "\n"


__all__ = [name for name in globals() if not name.startswith("__")]
