# tools/dawnpy/tests/test_cmd_descriptor.py
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
from dawnpy.headerdefs import HeaderDefsError, load_header_cfg_id
from dawnpy.objectid import ObjectIdDecoder
from dawnpy.sources import DawnSourcesMissing

_COMMAND_IMPORTS = (
    cmd_desc_bin_mod,
    cmd_desc_gen_mod,
    cmd_desc_valid_mod,
    cmd_desc_decode_caps_mod,
    cmd_desc_headers_check_mod,
)


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


def _print_can_kconfig_note(config: dict[str, object]) -> None:
    for note in _can_allocation_notes(_proto(config)):
        click.echo(note)


def test_headers_check_command_success(monkeypatch):
    """Test headers-check command reports success and loaded counts."""
    runner = CliRunner()
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_defs",
        lambda: {
            "dtype": [1, 2],
            "io_classes": {1: "a"},
            "prog_classes": {1: "b", 2: "c"},
            "proto_classes": {},
        },
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_type_defs",
        lambda: {
            "io_types": [1],
            "prog_types": [1, 2],
            "proto_types": [1, 2, 3],
        },
    )

    result = runner.invoke(cmd_desc_headers_check, [])
    assert result.exit_code == 0
    assert "Header root: /tmp/repo" in result.output
    assert "Loaded constants:" in result.output
    assert "Loaded type maps:" in result.output
    assert "Header check: OK" in result.output


def test_headers_check_command_missing_root(monkeypatch):
    """Test headers-check command fails when repository root is missing."""
    runner = CliRunner()
    monkeypatch.setattr(headers_check_mod, "find_repo_root", lambda: None)
    result = runner.invoke(cmd_desc_headers_check, [])
    assert result.exit_code != 0
    assert "Could not locate Dawn repository root" in result.output


def test_headers_check_command_parse_failure(monkeypatch):
    """Test headers-check command fails when header parsing fails."""
    runner = CliRunner()
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )

    def _boom():
        raise HeaderDefsError("bad header")

    monkeypatch.setattr(headers_check_mod, "load_header_defs", _boom)
    result = runner.invoke(cmd_desc_headers_check, [])
    assert result.exit_code != 0
    assert "Header parse failed: bad header" in result.output


def test_headers_check_command_propagates_dawn_sources_missing(monkeypatch):
    """DawnSourcesMissing raised during loading propagates verbatim."""
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )

    def _missing():
        raise DawnSourcesMissing("headers vanished mid-load")

    monkeypatch.setattr(headers_check_mod, "load_header_defs", _missing)
    with pytest.raises(DawnSourcesMissing, match="headers vanished"):
        cmd_desc_headers_check_mod.cmd_desc_headers_check.callback(
            strict=False
        )


def test_headers_check_strict_ok(monkeypatch):
    """--strict reports OK when every cpp_helper / enum_prefix resolves."""
    runner = CliRunner()
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_defs",
        lambda: {
            "dtype": [],
            "io_classes": {},
            "prog_classes": {},
            "proto_classes": {},
        },
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_type_defs",
        lambda: {"io_types": [], "prog_types": [], "proto_types": []},
    )
    monkeypatch.setattr(
        cmd_desc_headers_check_mod,
        "check_inline_field_schemas",
        lambda: [],
    )
    result = runner.invoke(cmd_desc_headers_check, ["--strict"])
    assert result.exit_code == 0
    assert "Strict header check: OK" in result.output


def test_headers_check_strict_fail(monkeypatch):
    """--strict surfaces unresolved cpp_helper references."""
    runner = CliRunner()
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_defs",
        lambda: {
            "dtype": [],
            "io_classes": {},
            "prog_classes": {},
            "proto_classes": {},
        },
    )
    monkeypatch.setattr(
        headers_check_mod,
        "load_header_type_defs",
        lambda: {"io_types": [], "prog_types": [], "proto_types": []},
    )
    monkeypatch.setattr(
        cmd_desc_headers_check_mod,
        "check_inline_field_schemas",
        lambda: ["io::dummy.foo: cpp_helper 'X::y' did not resolve (boom)"],
    )
    result = runner.invoke(cmd_desc_headers_check, ["--strict"])
    assert result.exit_code != 0
    assert "Strict header check: FAIL" in result.output
    assert "1 unresolved" in result.output


def test_check_inline_field_schemas_runs():
    """check_inline_field_schemas walks every registered config field."""
    from dawnpy.descriptor.validation.headers_check import (
        check_inline_field_schemas,
    )

    errors = check_inline_field_schemas()
    # Real handlers all bind to existing C++ headers; expect no errors.
    assert errors == []


def test_walk_fields_handles_non_list():
    """_walk_fields skips non-list inputs and non-ConfigField items."""
    from dawnpy.descriptor.validation.headers_check import _walk_fields

    assert list(_walk_fields(None)) == []
    assert list(_walk_fields(["not", "a", "ConfigField"])) == []


def test_parse_helper_token_rejects_templated_owner():
    """Parser rejects ``{cpp_class}`` placeholders."""
    from dawnpy.descriptor.validation.headers_check import _parse_helper_token

    assert _parse_helper_token("") is None
    assert _parse_helper_token("NoColons") is None
    assert _parse_helper_token("::missing_owner") is None
    assert _parse_helper_token("Owner::") is None
    assert _parse_helper_token("{cpp_class}::method") is None
    assert _parse_helper_token("Owner::method") == ("Owner", "method")


def test_check_field_reports_unresolved(monkeypatch):
    """_check_field flags helpers and enum_prefixes that fail to resolve."""
    from dawnpy.descriptor.definitions.type_info import ConfigField
    from dawnpy.descriptor.validation import headers_check as hc
    from dawnpy.headerdefs import HeaderDefsError

    def _boom_cfg(owner, method):
        raise HeaderDefsError("missing")

    def _boom_enum(owner, prefix):
        raise HeaderDefsError("missing-enum")

    monkeypatch.setattr(hc, "load_header_cfg_id", _boom_cfg)
    monkeypatch.setattr(hc, "load_header_enum_value_ids", _boom_enum)

    field = ConfigField(
        name="foo",
        cpp_helper="Owner::method",
        enum_prefix="Owner::PREFIX_",
    )
    out = hc._check_field("io", "dummy", field)
    assert any("cpp_helper 'Owner::method' did not resolve" in s for s in out)
    assert any(
        "enum_prefix 'Owner::PREFIX_' did not resolve" in s for s in out
    )


def test_nxscope_allocation_rows_resolves_iobind2():
    config = {
        "iobind2": [
            "io1",
            {"id": "io2"},
            {"io": "io3"},
            {"ref": "io4"},
            123,
        ],
        "path": "/dev/tty",
        "baudrate": 9600,
    }
    rows = _nxscope_allocation_rows(config, ["io1"])
    assert any("names=5" in row[-1] for row in rows)
    assert any("path=/dev/tty" in row[-1] for row in rows)


def test_nxscope_allocation_rows_uses_names_fallback():
    config = {"names": ["a", "b", "c"]}
    rows = _nxscope_allocation_rows(config, [])
    assert any("names=3" in row[-1] for row in rows)


def test_validate_command_success():
    """Test validate command with valid configuration."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        # Create defconfig
        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "[OK] Validation passed!" in result.output


def test_validate_command_missing_descriptor():
    """Test validate command with missing descriptor.cxx."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create defconfig but not descriptor.cxx
        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert "descriptor.cxx not found" in result.output


def test_validate_command_missing_defconfig():
    """Test validate command with missing defconfig."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx but not defconfig
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert "defconfig not found" in result.output


def test_validate_command_quiet():
    """Test validate command with --quiet flag."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create valid configuration
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path), "--quiet"])

        assert result.exit_code == 0
        # Should have minimal output in quiet mode
        assert (
            "Validation passed" not in result.output
            or result.output.strip() == ""
        )


def test_validate_command_invalid_config():
    """Test validate command with invalid configuration."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx with IO that needs config
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        # Create defconfig without the required config
        defconfig = config_path / "defconfig"
        defconfig.write_text("# CONFIG_DAWN_IO_DUMMY is not set\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        # Should indicate validation failed
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_fails_for_disabled_dtype_in_yaml():
    """Test validate command fails when descriptor.yaml uses disabled dtype."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "# CONFIG_DAWN_DTYPE_FLOAT is not set\n"
        )

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: float\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Validation passed" not in result.output
        assert "CONFIG_DAWN_DTYPE_FLOAT" in result.output


def test_validate_command_detects_can_overlap_in_yaml():
    """Validate should fail when descriptor.yaml has CAN ID block overlap."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "  - &io2\n"
            "    id: io2\n"
            "    type: dummy\n"
            "    instance: 2\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 0\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 256\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
            "            - *io2\n"
            "        - type: write\n"
            "          can_id_start: 257\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        fake_descriptor = SimpleNamespace(
            load_can_descriptor=lambda _: object(),
            iter_conflict_keys=lambda _: [
                (0x101, "read[0]"),
                (0x101, "write[1]"),
            ],
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: fake_descriptor,
        )
        result = runner.invoke(cmd_desc_valid, [str(config_path)])
        monkeypatch.undo()

        assert result.exit_code == 0
        assert "CAN overlap conflicts:" in result.output
        assert "0x101" in result.output
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_invalid_descriptor_yaml_reports_error():
    """Validate should report YAML parsing/runtime descriptor load errors."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text("protocols: [bad yaml")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Invalid descriptor.yaml" in result.output
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_can_mapping_failure_reports_error(monkeypatch):
    """Validate should report CAN mapping errors gracefully."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 0\n"
            "      objects: []\n"
        )

        def _raise_can_mapping(_):
            raise ValueError("broken can mapping")

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: SimpleNamespace(
                load_can_descriptor=_raise_can_mapping,
                iter_conflict_keys=lambda _: [],
            ),
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert (
            "CAN mapping validation failed: broken can mapping"
            in result.output
        )
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_prints_can_allocation_table():
    """Validate should always print CAN allocation details when CAN exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 256\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 16\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Protocol allocation summary:" in result.output
        assert "- can_main (can)" in result.output
        assert "block" in result.output
        assert "kind" in result.output
        assert "start" in result.output
        assert "end" in result.output
        assert "count" in result.output
        assert "details" in result.output
        assert "0x110" in result.output
        assert "ios=io1" in result.output


def test_validate_command_skips_can_allocation_with_kconfig():
    """Validate should skip CAN allocation when Kconfig expressions exist."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "vars:\n"
            "  can_id:\n"
            "    kconfig: CONFIG_SIM_CAN_NODEID\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: ${can_id}\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 16\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Variables:" in result.output
        assert "can_id: kconfig=CONFIG_SIM_CAN_NODEID" in result.output
        assert "can_main (can)" in result.output
        assert (
            "node=CONFIG_SIM_CAN_NODEID (assumed 0 for validation)"
            in result.output
        )
        assert "CAN runtime validation skipped" not in result.output


def test_validate_command_prints_serial_allocation_table():
    """Validate should print allocation summary for non-CAN protocols too."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/serial/simple.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_SERIAL=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: serial_main\n"
            "    type: serial\n"
            "    instance: 1\n"
            "    bindings:\n"
            "      - *io1\n"
            "    config:\n"
            "      path: /dev/ttyS1\n"
            "      baudrate: 115200\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Protocol allocation summary:" in result.output
        assert "- serial_main (serial)" in result.output
        assert "bind-index" in result.output
        assert "path=/dev/ttyS1" in result.output
        assert "baudrate=115200" in result.output
        assert "ios=io1" in result.output


def test_can_allocation_rows_indexed_and_empty_group():
    """CAN allocation helper reserves indexed IDs only for bindings."""
    rows = _can_allocation_rows(
        {
            "node_id": 256,
            "objects": [
                {
                    "type": "read_indexed",
                    "can_id_start": 5,
                    "count": 0,
                    "bindings": [],
                },
                {
                    "type": "write_indexed",
                    "can_id_start": 6,
                    "count": 2,
                    "bindings": [],
                },
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert rows[0][4] == "0"
    assert "ios=none" in rows[0][5]
    assert rows[1][2] == "n/a"
    assert rows[1][3] == "n/a"
    assert rows[1][4] == "0"
    assert "ios=none" in rows[1][5]


def test_can_allocation_rows_ignores_user_count():
    rows = _can_allocation_rows(
        {
            "node_id": 0,
            "objects": [
                {
                    "type": "read",
                    "can_id_start": 16,
                    "count": "CONFIG_COUNT",
                    "bindings": [],
                }
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert "CONFIG_COUNT" not in rows[0][5]


def test_can_allocation_rows_with_kconfig_start():
    rows = _can_allocation_rows(
        {
            "node_id": 0,
            "objects": [
                {
                    "type": "read",
                    "can_id_start": "CONFIG_START",
                    "count": 1,
                    "bindings": [],
                }
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert "note=can_id_start=CONFIG_START assumed 0" in rows[0][5]


def test_modbus_allocation_rows_with_registers():
    """Modbus allocation helper builds ranges from register blocks."""
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": 100,
                    "count": 3,
                    "bindings": [],
                },
            ]
        }
    )
    assert rows == [
        ["0", "holding", "100", "102", "3", "start=100, config=0, ios=none"]
    ]


def test_modbus_allocation_rows_with_kconfig_start():
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": "CONFIG_BASE",
                    "count": 1,
                    "bindings": [],
                },
            ]
        }
    )
    assert rows[0][2] == "0"
    assert "note=start=CONFIG_BASE assumed 0" in rows[0][5]


def test_modbus_allocation_rows_with_kconfig_count():
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": 10,
                    "count": "CONFIG_COUNT",
                    "bindings": [],
                },
            ]
        }
    )
    assert "note=count=CONFIG_COUNT assumed 0" in rows[0][5]


def test_serial_nxscope_shell_allocation_rows():
    """Protocol-specific rows include config details for non-CAN protocols."""
    serial_rows = _serial_allocation_rows(
        {"path": "/dev/ttyS2", "baudrate": 230400},
        ["io1", "io2"],
    )
    assert (
        serial_rows[0][5] == "path=/dev/ttyS2, baudrate=230400, ios=io1, io2"
    )

    nxscope_rows = _nxscope_allocation_rows(
        {
            "iobind2": [
                {"id": "io1", "name": "a"},
                {"id": "io2", "name": "b"},
            ],
            "path": "/dev/ttyS1",
            "baudrate": 115200,
        },
        [],
    )
    assert (
        nxscope_rows[0][5]
        == "names=2, path=/dev/ttyS1, baudrate=115200, ios=io1, io2"
    )

    shell_rows = _shell_allocation_rows(
        {"prompt": "dawn>"},
        ["io1"],
    )
    assert shell_rows[0][5] == "prompt=dawn>, ios=io1"


def test_bindings_allocation_rows_with_custom_details():
    """Bindings row helper supports details text."""
    rows = _bindings_allocation_rows(["io1"], details="custom")
    assert rows == [["0", "bind-index", "1", "1", "1", "custom, ios=io1"]]


def test_nimble_allocation_rows_services():
    """Nimble summary should include service rows with bound IO details."""
    rows = _nimble_allocation_rows(
        {
            "gap_name": "thingy",
            "services": {
                "dis": {"enabled": True},
                "bas": {"battery_level": {"id": "bat1"}},
                "aios": {
                    "groups": [
                        {
                            "digital_inputs": [
                                {
                                    "data": {"id": "in1"},
                                    "metadata": {"user_description": "input"},
                                }
                            ],
                            "analog_outputs": [{"id": "out1"}],
                        }
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t1"}},
                        {"type": "humidity", "data": {"id": "h1"}},
                    ]
                },
                "imds": {"pressure": {"id": "p1"}},
            },
        }
    )
    assert rows[0] == [
        "0",
        "gap",
        "n/a",
        "n/a",
        "0",
        "gap_name=thingy, ios=none",
    ]
    assert rows[1][1] == "dis"
    assert rows[1][5] == "enabled=true, ios=none"
    assert rows[2][1] == "bas"
    assert rows[2][5] == "ios=bat1"
    assert rows[3][1] == "aios.group0"
    assert rows[3][4] == "2"
    assert rows[3][5] == "ios=in1, out1"
    assert rows[4][1] == "ess"
    assert rows[4][5] == "ios=t1, h1"
    assert rows[5][1] == "imds"
    assert rows[5][5] == "ios=p1"


def test_nimble_allocation_rows_with_invalid_services_shape():
    """Nimble summary should keep gap row when services config is invalid."""
    rows = _nimble_allocation_rows({"gap_name": "x", "services": []})
    assert rows == [["0", "gap", "n/a", "n/a", "0", "gap_name=x, ios=none"]]


def test_nimble_allocation_rows_skips_invalid_group_and_sensor_shapes():
    """Nimble summary skips malformed aios/ess/imds configs."""
    rows = _nimble_allocation_rows(
        {
            "gap_name": "x",
            "services": {
                "aios": {"groups": ["bad_group"]},
                "ess": {"characteristics": ["bad_ess"]},
                "imds": "bad_imds",
            },
        }
    )
    # malformed entries are skipped; dis defaults to disabled row
    assert rows == [
        ["0", "gap", "n/a", "n/a", "0", "gap_name=x, ios=none"],
        ["1", "dis", "n/a", "n/a", "0", "enabled=false, ios=none"],
        ["2", "bas", "n/a", "n/a", "0", "ios=none"],
        ["3", "ess", "n/a", "n/a", "0", "ios=none"],
    ]


def test_fmt_bindings_empty_and_list():
    """Binding formatter supports empty and populated lists."""
    assert _fmt_bindings([]) == "none"
    assert _fmt_bindings(["io1", "io2"]) == "io1, io2"


def test_print_table_wrap_and_empty_cell(capsys):
    """Table renderer should wrap long cells and handle empty cells."""
    headers = ["block", "kind", "start", "end", "count", "details"]
    rows = [
        [
            "0",
            "read",
            "0x1",
            "0x1",
            "1",
            "this is a very long details text that must wrap "
            "into multiple lines for readability",
        ],
        ["1", "write", "0x2", "0x2", "1", ""],
    ]
    _print_table(headers, rows)
    out = capsys.readouterr().out
    assert "block | kind" in out
    assert "this is a very long details text" in out
    # rich's MARKDOWN box with show_lines emits a separator between every row
    assert out.count("|--") >= 2


def test_print_protocol_allocation_summaries_unknown_and_empty(capsys):
    """Summary handles unknown protocol and empty descriptors."""
    empty = ClientDescriptor(ios={}, programs=[], protocols=[])
    print_protocol_allocation_summaries(empty, {})
    out = capsys.readouterr().out
    assert out == ""

    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="x1",
                proto_type="unknown_proto",
                instance=1,
                config={},
                bindings=[],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "x1 (unknown_proto)" in out
    assert "unsupported protocol" in out


def test_print_object_summary_tables(capsys):
    io = ClientIo(
        io_id="io1",
        io_type="dummy",
        instance=1,
        dtype="uint8",
        tags=["tag1"],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    prog = ClientProgram(
        prog_id="prog1",
        prog_type="statsmin",
        instance=1,
        inputs=["io1"],
        outputs=["io1"],
        config={},
    )
    proto = ClientProto(
        proto_id="can1",
        proto_type="can",
        instance=1,
        config={},
        bindings=["io1"],
    )
    desc = ClientDescriptor(
        ios={"io1": io},
        programs=[prog],
        protocols=[proto],
    )

    _print_object_summary(desc)
    out = capsys.readouterr().out
    assert "Object summary:" in out
    assert "IO objects:" in out
    assert "Program objects:" in out
    assert "Protocol objects:" in out
    assert "0x" in out


def test_print_protocol_allocation_summaries_modbus_fallback(capsys):
    """Modbus without registers falls back to binding index table."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="mb1",
                proto_type="modbus_rtu",
                instance=1,
                config={},
                bindings=["io1", "io2"],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "mb1 (modbus_rtu)" in out
    assert "bind-index" in out
    assert "registers=0" in out
    assert "ios=io1, io2" in out


def test_print_protocol_allocation_summaries_nxscope_and_shell(capsys):
    """Summary should print per-protocol details for nxscope and shell."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="nx1",
                proto_type="nxscope_serial",
                instance=1,
                config={"names": ["x", "y", "z"], "baudrate": 115200},
                bindings=["io1"],
            ),
            ClientProto(
                proto_id="sh1",
                proto_type="shell",
                instance=1,
                config={"prompt": "sh>"},
                bindings=["io2"],
            ),
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "nx1 (nxscope_serial)" in out
    assert "names=3" in out
    assert "baudrate=115200" in out
    assert "ios=io1" in out
    assert "sh1 (shell)" in out
    assert "prompt=sh>" in out
    assert "ios=io2" in out


def test_print_protocol_allocation_summaries_nimble(capsys):
    """Summary should print nimble services and IO bindings."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="ble1",
                proto_type="nimble",
                instance=1,
                config={
                    "gap_name": "dev",
                    "services": {
                        "dis": {"enabled": True},
                        "bas": {"battery_level": {"id": "bat"}},
                    },
                },
                bindings=[],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "ble1 (nimble)" in out
    assert "gap_name=dev" in out
    assert "enabled=true" in out
    assert "ios=bat" in out


def test_fmt_hex_none_and_value():
    """Hex formatter handles both populated and empty IDs."""
    assert _fmt_hex(None) == "n/a"
    assert _fmt_hex(255) == "0xFF"


def test_fmt_value_and_parse_helpers(capsys):
    assert _fmt_value(None) == "n/a"
    assert _fmt_value(10) == "10"
    assert _fmt_value(10, hex_format=True) == "0xA"
    assert try_parse_int("CONFIG_X") is None
    assert try_parse_int("0x10") == 16

    _print_vars_summary(
        {
            "k1": {"kconfig": "CONFIG_X", "type": "int"},
            "v1": {"value": 5},
            "v2": {"value": "abc", "type": "string"},
            "raw": 7,
            "unknown": {"foo": "bar"},
        }
    )
    out = capsys.readouterr().out
    assert "Variables:" in out
    assert "k1: kconfig=CONFIG_X" in out
    assert "v1: value=5" in out
    assert "v2: value=abc, type=string" in out
    assert "raw: value=7" in out
    assert "unknown: value=?" in out

    _print_can_kconfig_note({"node_id": "CONFIG_NODE"})
    out = capsys.readouterr().out
    assert "node=CONFIG_NODE (assumed 0 for validation)" in out


def test_proto_unresolved_kconfig_helpers():
    assert _proto_has_unresolved_kconfig({"node_id": "CONFIG_X"}, ["node_id"])
    assert not _proto_has_unresolved_kconfig({"node_id": 1}, ["node_id"])
    assert _proto_has_unresolved_kconfig(
        {"objects": [{"can_id_start": "CONFIG_Y"}]}, ["objects"]
    )

    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="can1",
                proto_type="can",
                instance=1,
                config={"node_id": "CONFIG_X", "objects": []},
                bindings=[],
            )
        ],
    )
    assert _can_has_unresolved_kconfig(desc)

    empty = ClientDescriptor(ios={}, programs=[], protocols=[])
    assert _can_has_unresolved_kconfig(empty) is False


def test_try_parse_int_variants():
    assert try_parse_int(True) is None
    assert try_parse_int(3) == 3
    assert try_parse_int("0x2") == 2
    assert try_parse_int("CONFIG_Z") is None
    assert try_parse_int([]) is None


def test_proto_has_unresolved_kconfig_list_items():
    assert (
        _proto_has_unresolved_kconfig({"objects": ["bad"]}, ["objects"])
        is False
    )


def test_generate_command_success():
    """Test generate command with valid YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create descriptor.yaml
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - id: dummy1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "programs: []\n"
            "protocols: []\n"
        )

        # Output path
        output_path = tmpdir_path / "descriptor.cxx"

        result = runner.invoke(
            cmd_desc_gen,
            [str(yaml_path), "-o", str(output_path)],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Generated:" in result.output
        assert "CRC policy:" in result.output


def test_generate_command_default_output():
    """Test generate command with default output path."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create descriptor.yaml
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols: []\n"
        )

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])

        assert result.exit_code == 0
        # Should generate descriptor.cxx in same directory as YAML
        default_output = tmpdir_path / "descriptor.cxx"
        assert default_output.exists()
        assert "Generated:" in result.output
        assert "CRC policy:" in result.output
        assert "descriptor.cxx not found" not in result.output
        assert (
            "Descriptor generated, but validation failed." not in result.output
        )


def test_generate_command_keeps_crc_placeholder():
    """Generate keeps C++ checksum placeholder (firmware-filled policy)."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols: []\n"
        )

        output_path = tmpdir_path / "descriptor.cxx"
        result = runner.invoke(
            cmd_desc_gen,
            [str(yaml_path), "-o", str(output_path)],
        )
        assert result.exit_code == 0
        text = output_path.read_text(encoding="utf-8")
        assert "0xdeadbeef" in text.lower()


def test_generate_command_invalid_yaml():
    """Test generate command with invalid YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create invalid YAML
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("invalid: [yaml without proper structure")

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])

        # Should show error message (exit code may be 0 even on error)
        assert "Error" in result.output or "error" in result.output


def test_generate_command_debug_mode():
    """Test generate command with --debug flag raises exceptions."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create invalid YAML that will cause an error
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("invalid: [yaml")

        result = runner.invoke(cmd_desc_gen, ["--debug", str(yaml_path)])

        # In debug mode, exceptions should be raised (non-zero exit code)
        assert result.exit_code != 0


def test_generate_command_reports_validation_failure_with_defconfig(
    monkeypatch,
):
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("ios: []\nprograms: []\nprotocols: []\n")
        (tmpdir_path / "defconfig").write_text("CONFIG_TEST=y\n")

        monkeypatch.setattr(
            cmd_desc_gen_mod,
            "generate_descriptor",
            lambda yaml_path, output_path, kconfig_path=None: None,
        )
        monkeypatch.setattr(
            cmd_desc_gen_mod,
            "validate_config",
            lambda config_path, quiet, verbose: False,
        )

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])
        assert result.exit_code == 0
        assert "Descriptor generated, but validation failed." in result.output


def test_fill_crc32_footer_invalid_inputs():
    with pytest.raises(ValueError, match="too small"):
        fill_crc32_footer(b"\x00\x01\x02")

    bad_footer = struct.pack("<II", 0x0D0A0302, 1) + struct.pack(
        "<II", 0x11111111, 0x00000000
    )
    with pytest.raises(ValueError, match="footer marker mismatch"):
        fill_crc32_footer(bad_footer)


def test_fill_crc32_footer_nuttx_crc_property():
    base = struct.pack("<II", 0x0D0A0302, 1) + struct.pack(
        "<II", 0x02030A0D, 0
    )
    out = fill_crc32_footer(base)
    assert nuttx_crc32(out) == 0


def test_generate_descriptor_binary_dynamic_desc_like():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "dynamic.yaml"
        yaml_path.write_text(
            "metadata:\n"
            "  version: '0.2'\n"
            "  user_string: dynslot1\n"
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 0\n"
            "  - id: descriptor1\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 1\n"
            "  - id: descselector0\n"
            "    type: descselector\n"
            "    dtype: uint32\n"
            "  - id: dummy0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 77\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - descriptor0\n"
            "      - descriptor1\n"
            "      - descselector0\n"
            "      - dummy0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        binary = _generate_descriptor_binary(yaml_path, None)
        words = list(struct.unpack(f"<{len(binary) // 4}I", binary))

        assert words[0] == 0x0D0A0302
        assert words[1] == 6  # metadata + 4 IO + 1 protocol
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(binary) == 0
        assert 77 in words


def test_generate_descriptor_binary_pwm_freq_config():
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pwm0",
        io_type="pwm",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0, "freq": 1000},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pwm"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    freq_cfg = cfg_id(
        1, io_cls, dtype, False, 1, load_header_cfg_id("CIOPwm", "cfgIdFreq")
    )
    assert freq_cfg in words
    assert words[words.index(freq_cfg) + 1] == 1000

    freq_only = IoObject(
        obj_id="pwm_all",
        io_type="pwm",
        instance=1,
        dtype="uint32",
        tags=[],
        config={"device": 0, "freq": 500},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    freq_only_words: list[int] = []
    _serialize_io_object(freq_only_words, freq_only, {}, decoder)
    assert freq_cfg in freq_only_words


def test_generate_descriptor_binary_pwm_without_freq_has_no_type_config():
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pwm0",
        io_type="pwm",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pwm"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    freq_cfg = cfg_id(
        1, io_cls, dtype, True, 1, load_header_cfg_id("CIOPwm", "cfgIdFreq")
    )
    assert freq_cfg not in words


def test_generate_descriptor_binary_with_program_object():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "prog.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: in0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 11\n"
            "  - id: out0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "programs:\n"
            "  - id: p0\n"
            "    type: statsmin\n"
            "    config:\n"
            "      inputs:\n"
            "        - in0\n"
            "      outputs:\n"
            "        - out0\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - in0\n"
            "      - out0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        binary = _generate_descriptor_binary(yaml_path, None)
        words = list(struct.unpack(f"<{len(binary) // 4}I", binary))

        assert words[0] == 0x0D0A0302
        assert words[1] == 4  # 2 IO + 1 PROG + 1 protocol
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(binary) == 0
        assert any((word >> 30) == 3 for word in words)


def test_binary_command_deterministic_output_for_same_input():
    """Characterization: binary CLI output is stable for identical YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "stable.yaml"
        out1 = Path(tmpdir) / "out1.bin"
        out2 = Path(tmpdir) / "out2.bin"
        yaml_path.write_text(
            "metadata:\n"
            "  version: '1.2'\n"
            "  user_string: stable\n"
            "ios:\n"
            "  - id: io0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 5\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n"
            "    bindings:\n"
            "      - io0\n",
            encoding="utf-8",
        )

        result1 = runner.invoke(
            cmd_desc_bin, [str(yaml_path), "-o", str(out1)]
        )
        result2 = runner.invoke(
            cmd_desc_bin, [str(yaml_path), "-o", str(out2)]
        )

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert "Generated binary" in result1.output
        assert "Generated binary" in result2.output

        bin1 = out1.read_bytes()
        bin2 = out2.read_bytes()
        assert bin1 == bin2

        words = list(struct.unpack(f"<{len(bin1) // 4}I", bin1))
        assert words[0] == 0x0D0A0302
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(bin1) == 0


def test_binary_command_rejects_unsupported_io_type():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "bad.yaml"
        out_path = Path(tmpdir) / "bad.bin"
        yaml_path.write_text(
            "ios:\n"
            "  - id: io0\n"
            "    type: unknown_io\n"
            "    dtype: uint32\n"
            "protocols: []\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cmd_desc_bin,
            [str(yaml_path), "-o", str(out_path)],
        )

        assert result.exit_code != 0
        assert result.exception is not None
        assert "unknown io type" in str(result.exception).lower()


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


def test_io_class_and_dtype_mapping_branches():
    assert _io_class_name(_mk_io("sensor", subtype="temp")) == (
        "sensor_temperature"
    )
    assert _io_class_name(_mk_io("sensor")) is None
    assert _io_class_name(_mk_io("sysinfo", variant="uptime")) == (
        "system_uptime"
    )
    assert _io_class_name(_mk_io("sysinfo")) is None
    assert _io_class_name(_mk_io("uname", variant="hostname")) == (
        "system_hostname"
    )
    assert _io_class_name(_mk_io("uname", variant="other")) is None
    assert _io_class_name(_mk_io("boardctl", variant="poweroff")) == (
        "system_poweroff"
    )
    assert _io_class_name(_mk_io("boardctl", variant="x")) is None

    assert _io_dtype_name(_mk_io("sysinfo", variant="uptime")) == "uint64"
    assert _io_dtype_name(_mk_io("uname", variant="hostname")) == "char"
    assert _io_dtype_name(_mk_io("boardctl", variant="reset")) == "int32"
    assert _io_dtype_name(_mk_io("boardctl", variant="unknown")) == "uint32"


def test_coerce_u32_words_for_dtype_branches():
    assert _coerce_u32_words_for_dtype(1.5, "float")
    assert len(_coerce_u32_words_for_dtype(1.5, "double")) == 2
    assert len(_coerce_u32_words_for_dtype(-1, "int64")) == 2
    assert len(_coerce_u32_words_for_dtype(1, "uint64")) == 2
    assert _coerce_u32_words_for_dtype(-2, "int32")[0] == 0xFFFFFFFE
    assert _coerce_u32_words_for_dtype(True, "bool")[0] == 1
    with pytest.raises(
        click.ClickException,
        match="Unsupported dummy init_value dtype",
    ):
        _coerce_u32_words_for_dtype(1, "block")


def test_binary_command_success_and_default_output():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "ok.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 0\n"
            "  - id: descriptor1\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 1\n"
            "  - id: descselector0\n"
            "    type: descselector\n"
            "    dtype: uint32\n"
            "  - id: capabilities0\n"
            "    type: capabilities\n"
            "    dtype: block\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - descriptor0\n"
            "      - descriptor1\n"
            "      - descselector0\n"
            "      - capabilities0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        result = runner.invoke(cmd_desc_bin, [str(yaml_path)])
        assert result.exit_code == 0
        assert "Generated binary" in result.output
        assert (Path(tmpdir) / "descriptor.bin").exists()


def test_binary_command_proto_dummy_and_prog_stats_supported():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        proto_dummy_yaml = Path(tmpdir) / "proto_dummy.yaml"
        proto_dummy_yaml.write_text(
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "protocols:\n"
            "  - id: dummy0\n"
            "    type: dummy\n",
            encoding="utf-8",
        )
        result_proto_dummy = runner.invoke(
            cmd_desc_bin, [str(proto_dummy_yaml)]
        )
        assert result_proto_dummy.exit_code == 0
        assert "Generated binary" in result_proto_dummy.output

        proto_bad_yaml = Path(tmpdir) / "proto_bad.yaml"
        proto_bad_yaml.write_text(
            "protocols:\n" "  - id: p0\n" "    type: unknown_protocol\n",
            encoding="utf-8",
        )
        result_proto_bad = runner.invoke(cmd_desc_bin, [str(proto_bad_yaml)])
        assert result_proto_bad.exit_code != 0
        assert (
            "unknown protocol type" in str(result_proto_bad.exception).lower()
        )

        prog_ok_yaml = Path(tmpdir) / "prog_stats_ok.yaml"
        prog_ok_yaml.write_text(
            "programs:\n"
            "  - id: p0\n"
            "    type: stats\n"
            "    config: {}\n",
            encoding="utf-8",
        )
        result_prog_ok = runner.invoke(cmd_desc_bin, [str(prog_ok_yaml)])
        assert result_prog_ok.exit_code == 0
        assert "Generated binary" in result_prog_ok.output

        prog_bad_yaml = Path(tmpdir) / "prog_bad.yaml"
        prog_bad_yaml.write_text(
            "programs:\n"
            "  - id: p1\n"
            "    type: unknown_program\n"
            "    config: {}\n",
            encoding="utf-8",
        )
        result_prog_bad = runner.invoke(cmd_desc_bin, [str(prog_bad_yaml)])
        assert result_prog_bad.exit_code != 0
        assert result_prog_bad.exception is not None
        assert "unknown program type" in str(result_prog_bad.exception).lower()


def test_serialize_error_paths_for_unknown_mappings():
    decoder = ObjectIdDecoder()
    io = _mk_io("sensor")
    with pytest.raises(
        click.ClickException,
        match="Unable to resolve IO class",
    ):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], io, {}, decoder)

    decoder.io_classes = {}
    with pytest.raises(click.ClickException, match="Unknown IO class"):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], _mk_io("dummy"), {}, decoder)

    decoder = ObjectIdDecoder()
    bad_dtype_io = _mk_io("dummy", dtype="notype")
    with pytest.raises(click.ClickException, match="Unknown IO dtype"):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], bad_dtype_io, {}, decoder)

    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=["x"]
    )
    with pytest.raises(KeyError, match="x"):
        from dawnpy.descriptor.encoding.proto_serializer import (
            serialize_proto_object,
        )

        serialize_proto_object([], proto, {}, decoder)

    unknown_io = IoObject(
        obj_id="io_unknown",
        io_type="system_uptime",
        instance=0,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    with pytest.raises(click.ClickException, match="supports IO types"):
        _serialize_io_object([], unknown_io, {}, ObjectIdDecoder())


def test_serialize_metadata_non_dict_and_dummy_dim_branch():
    words: list[int] = []
    assert _serialize_metadata(words, {"metadata": []}) == 0

    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="dummy0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"dim": 3},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    out: list[int] = []
    _serialize_io_object(out, obj, {}, decoder)
    assert 3 in out


def test_serialize_metadata_no_idle_quit_only():
    words: list[int] = []

    assert (
        _serialize_metadata(words, {"metadata": {"no_idle_quit": True}}) == 1
    )

    assert words == [
        1,  # CDescriptor::objectId(1)
        1,
        (3 << 16) | (1 << 5) | 3,
        1,
    ]


def test_serialize_proto_unknown_class_raises():
    decoder = ObjectIdDecoder()
    decoder.proto_classes = {}
    proto = ProtocolObject(
        obj_id="serial0",
        proto_type="serial",
        instance=0,
        config={},
        bindings=[],
    )
    with pytest.raises(click.ClickException, match="Unknown protocol class"):
        serialize_proto_object([], proto, {}, decoder)


def _make_capabilities_blob_v2() -> bytes:
    decoder = ObjectIdDecoder()
    payload = bytearray(504)

    io_names = ("dummy", "capabilities", "encoder", "encoder_index")
    prog_names = (
        "dummy",
        "bitsplit",
        "toggle",
        "counter",
        "switch",
        "expression",
        "selector",
        "bitpack",
        "configwriter",
    )
    proto_names = ("serial", "nxscope_udp", "modbus_rtu", "modbus_tcp")

    io_bits = [
        next(k for k, v in decoder.io_classes.items() if v == name)
        for name in io_names
    ]
    prog_bits = [
        next(k for k, v in decoder.prog_classes.items() if v == name)
        for name in prog_names
    ]
    proto_bits = [
        next(k for k, v in decoder.proto_classes.items() if v == name)
        for name in proto_names
    ]

    for bit in io_bits:
        payload[bit // 8] |= 1 << (bit % 8)
    for bit in prog_bits:
        payload[64 + (bit // 8)] |= 1 << (bit % 8)
    for bit in proto_bits:
        payload[128 + (bit // 8)] |= 1 << (bit % 8)

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


def test_capabilities_decode_helpers():
    blob = _make_capabilities_blob_v2()
    decoded = _decode_capabilities_blob(blob)
    assert decoded["version"] == 2
    assert decoded["layout_id"] == 0
    assert decoded["payload_len"] == 504
    assert decoded["desc_slots"] == 2
    assert decoded["desc_slot_size"] == 4096
    assert decoded["max_io_cls"] == 0x1FF
    assert 85 in decoded["io_enabled"]
    assert 86 in decoded["io_enabled"]
    assert 20 in decoded["prog_enabled"]
    assert 27 in decoded["prog_enabled"]
    assert 13 in decoded["proto_enabled"]
    assert 19 in decoded["proto_enabled"]


def test_capabilities_decode_helper_errors():
    assert parse_hex_file_text("00000000: 01 02 03 |...|") == bytes(
        [0x01, 0x02, 0x03]
    )

    with pytest.raises(click.ClickException, match="Hex file is empty"):
        parse_hex_file_text("   \n\t")

    with pytest.raises(click.ClickException, match="even number"):
        parse_hex_file_text("A")

    with pytest.raises(click.ClickException, match="too short"):
        _decode_capabilities_blob(b"\x02")

    bad_version = bytearray(_make_capabilities_blob_v2())
    bad_version[0] = 1
    with pytest.raises(click.ClickException, match="Unsupported.*version"):
        _decode_capabilities_blob(bytes(bad_version))

    bad_layout = bytearray(_make_capabilities_blob_v2())
    bad_layout[1] = 7
    with pytest.raises(click.ClickException, match="Unsupported.*layout"):
        _decode_capabilities_blob(bytes(bad_layout))

    bad_len = bytearray(_make_capabilities_blob_v2())
    bad_len[2:4] = (503).to_bytes(2, "little")
    with pytest.raises(
        click.ClickException, match="Unsupported.*payload length"
    ):
        _decode_capabilities_blob(bytes(bad_len))

    bad_reserved = bytearray(_make_capabilities_blob_v2())
    bad_reserved[4:8] = (1).to_bytes(4, "little")
    with pytest.raises(click.ClickException, match="reserved field"):
        _decode_capabilities_blob(bytes(bad_reserved))

    bad_actual = _make_capabilities_blob_v2()[:-1]
    with pytest.raises(click.ClickException, match="payload size mismatch"):
        _decode_capabilities_blob(bad_actual)

    bad_class_limit = bytearray(_make_capabilities_blob_v2())
    struct.pack_into("<I", bad_class_limit, 8 + 192 + (8 * 4), 84)
    with pytest.raises(click.ClickException, match="above advertised max"):
        _decode_capabilities_blob(bytes(bad_class_limit))


def test_capabilities_decode_uses_inlined_layout():
    """Inlined layout constants drive _decode_capabilities_blob end-to-end."""
    blob = _make_capabilities_blob_v2()
    decoded = _decode_capabilities_blob(blob)
    assert decoded["version"] == 2
    assert decoded["layout_id"] == 0
    assert decoded["desc_slots"] == 2
    assert decoded["dtype_bits_lo"] != 0


def test_enabled_flag_names_skips_invalid_entries():
    names = enabled_flag_names(
        0b11,
        [
            {"bit": -1, "name": "bad"},
            {"bit": 0, "name": ""},
            {"bit": 1, "name": "ok"},
        ],
    )
    assert names == ["ok"]


def test_serialize_io_control_trigger_and_config_paths():
    decoder = ObjectIdDecoder()

    dummy_obj = IoObject(
        obj_id="dummy0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 5},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    control_obj = IoObject(
        obj_id="control0",
        io_type="control",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"targets": ["dummy0"], "allowed": ["stop", "start"]},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    trigger_obj = IoObject(
        obj_id="trigger0",
        io_type="trigger",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "targets": ["dummy0"],
            "allowed": ["reset", "trigger1", "trigger2", "trigger3"],
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    config_obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 5},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    obj_ids: dict[str, int] = {}
    words: list[int] = []

    _serialize_io_object(words, dummy_obj, obj_ids, decoder)
    _serialize_io_object(words, control_obj, obj_ids, decoder)
    _serialize_io_object(words, trigger_obj, obj_ids, decoder)
    _serialize_io_object(words, config_obj, obj_ids, decoder)

    assert "control0" in obj_ids
    assert "trigger0" in obj_ids
    assert "config0" in obj_ids


def test_serialize_io_config_raises_when_dummy_class_missing():
    decoder = ObjectIdDecoder()
    decoder.io_classes = {
        cls_id: name
        for cls_id, name in decoder.io_classes.items()
        if name != "dummy"
    }

    obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 5},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    with pytest.raises(click.ClickException, match="Unknown IO class 'dummy'"):
        _serialize_io_object([], obj, {"dummy0": 0x12345678}, decoder)


def test_io_config_generic_helper_edge_branches():
    """Cover generic ConfigField helper branches for config IO."""
    assert (
        io_config_mod._cpp_helper_call(
            ConfigField(name="x"), SimpleNamespace(), 0
        )
        is None
    )
    assert (
        io_config_mod._cpp_helper_call(
            ConfigField(
                name="x",
                cpp_helper="CExample::cfg",
                params=["custom"],
                default_params=[False],
            ),
            SimpleNamespace(initval_param=7, rw=True),
            0,
        )
        == "CExample::cfg(false),"
    )
    assert (
        io_config_mod._choose_config_field(
            [
                ConfigField(name="a", cpp_helper="CExample::a"),
                ConfigField(name="b", cpp_helper="CExample::b"),
            ],
            {"a": 1, "b": 2},
            "",
        )
        is None
    )


def test_io_config_binary_handles_non_dict_reference_config():
    """Cover malformed anchored-reference config without target coupling."""
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": [],
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    _serialize_io_object([], obj, {"dummy0": 0x12345678}, decoder)


def test_io_config_binary_default_param_branch():
    """Cover generic binary cfg-id params that use ConfigField defaults."""
    decoder = ObjectIdDecoder()
    io_dtype_map = {
        str(info["type"]).lower(): dtype_id
        for dtype_id, info in decoder.dtype_info.items()
    }
    io_cls_map = {
        name.lower(): cls_id for cls_id, name in decoder.io_classes.items()
    }
    ctx = io_config_mod._IOSerializeContext(
        obj=IoObject(
            obj_id="config0",
            io_type="config",
            instance=0,
            dtype="uint32",
            tags=[],
            config={},
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        ),
        io_cls=io_cls_map["config"],
        dtype=io_dtype_map["uint32"],
        dtype_name="uint32",
        config={},
        obj_ids={},
        items=[],
        decoder=decoder,
        io_dtype_map=io_dtype_map,
        io_cls_map=io_cls_map,
    )
    field = ConfigField(
        name="init_value",
        cpp_helper="CIODummy::cfgIdInitval",
        params=["custom"],
        default_params=[False],
    )
    value = io_config_mod._binary_cfg_id(
        ctx,
        field,
        {
            "id": "dummy0",
            "type": "dummy",
            "dtype": "uint32",
            "config": {"init_value": 1},
        },
    )
    assert isinstance(value, int)


def test_io_config_binary_uses_config_io_rw_grant():
    """ConfigIO target cfg-id RW comes from the resolved ConfigIO grant."""
    decoder = ObjectIdDecoder()
    io_dtype_map = {
        str(info["type"]).lower(): dtype_id
        for dtype_id, info in decoder.dtype_info.items()
    }
    io_cls_map = {
        name.lower(): cls_id for cls_id, name in decoder.io_classes.items()
    }
    ctx = io_config_mod._IOSerializeContext(
        obj=IoObject(
            obj_id="config0",
            io_type="config",
            instance=0,
            dtype="uint32",
            tags=[],
            config={},
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        ),
        io_cls=io_cls_map["config"],
        dtype=io_dtype_map["uint32"],
        dtype_name="uint32",
        config={},
        obj_ids={},
        items=[],
        decoder=decoder,
        io_dtype_map=io_dtype_map,
        io_cls_map=io_cls_map,
        config_rw_grants={("pwm0", "freq"): True},
    )
    field = ConfigField(
        name="freq",
        cpp_helper="CIOPwm::cfgIdFreq",
        value_type="int",
    )

    value = io_config_mod._binary_cfg_id(
        ctx,
        field,
        {
            "id": "pwm0",
            "type": "pwm",
            "dtype": "uint32",
            "config": {"freq": 1000},
        },
    )

    assert value == cfg_id(
        1,
        io_cls_map["pwm"],
        io_dtype_map["uint32"],
        True,
        1,
        load_header_cfg_id("CIOPwm", "cfgIdFreq"),
    )


def test_serialize_io_extended_supported_types():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []

    dummy_notify = IoObject(
        obj_id="dn0",
        io_type="dummy_notify",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "dim": 2,
            "init_value": [1, 2],
            "interval_us": 1000,
            "notify_on_write": True,
        },
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )
    timestamp = IoObject(
        obj_id="ts0",
        io_type="timestamp",
        instance=0,
        dtype="uint64",
        tags=[],
        config={"interval_us": 5000},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    fileio = IoObject(
        obj_id="f0",
        io_type="fileio",
        instance=0,
        dtype="block",
        tags=[],
        config={"path": "/tmp/test.bin", "perm": 2},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    gpi = IoObject(
        obj_id="gpi0",
        io_type="gpi",
        instance=0,
        dtype="bool",
        tags=[],
        config={"device": 1},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, dummy_notify, obj_ids, decoder)
    _serialize_io_object(words, timestamp, obj_ids, decoder)
    _serialize_io_object(words, fileio, obj_ids, decoder)
    _serialize_io_object(words, gpi, obj_ids, decoder)
    assert obj_ids["dn0"] != 0
    assert obj_ids["ts0"] != 0
    assert obj_ids["f0"] != 0
    assert obj_ids["gpi0"] != 0


def test_serialize_io_encoder_emits_posmax():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    encoder = IoObject(
        obj_id="enc0",
        io_type="encoder",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"posmax": 4096},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    encoder_index = IoObject(
        obj_id="enc_idx0",
        io_type="encoder_index",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"posmax": 8192},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, encoder, obj_ids, decoder)
    _serialize_io_object(words, encoder_index, obj_ids, decoder)

    assert obj_ids["enc0"] != 0
    assert obj_ids["enc_idx0"] != 0
    assert 4096 in words
    assert 8192 in words


def test_serialize_io_notify_unknown_dtype_raises(monkeypatch):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="dn0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"notify": {"type": "stream", "priority": 1, "batch": 2}},
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )

    monkeypatch.setattr(
        binary_serializer_mod,
        "dtype_id_by_name",
        lambda _decoder, _name: None,
    )
    with pytest.raises(click.ClickException, match="notify cfg"):
        _serialize_io_object([], obj, {}, decoder)


def test_serialize_io_notify_config_serializes_values():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    obj = IoObject(
        obj_id="dn1",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"notify": {"type": "stream", "priority": 7, "batch": 3}},
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, obj, obj_ids, decoder)
    assert obj_ids["dn1"] != 0
    assert 7 in words
    assert 3 in words


def test_encode_limit_word_dtype_paths():
    from dawnpy.descriptor.encoding.binary_serializer import (
        _encode_limit_word,
        _limit_value_words,
    )

    assert _encode_limit_word(7, "uint32") == 7
    # Negative int8 -> two's complement bit pattern.
    assert (
        _encode_limit_word(-3, "int8")
        == struct.unpack("<I", struct.pack("<i", -3))[0]
    )
    # Float -> IEEE-754 bit pattern.
    expected_float = struct.unpack("<I", struct.pack("<f", 0.25))[0]
    assert _encode_limit_word(0.25, "float") == expected_float
    # List input expands to per-element words.
    assert _limit_value_words([1, 2, 3], "uint32") == [1, 2, 3]
    # Scalar wraps in single-element list.
    assert _limit_value_words(5, "uint32") == [5]


def test_encode_limit_word_unsupported_dtype_raises():
    from dawnpy.descriptor.encoding.binary_serializer import _encode_limit_word

    with pytest.raises(click.ClickException, match="limits not supported"):
        _encode_limit_word(0, "block")


def test_serialize_io_limits_uint32_emits_three_items():
    from dawnpy.descriptor.encoding.binary_serializer import (
        _append_limits_items,
    )
    from dawnpy.headerdefs import load_header_cfg_id

    items: list[tuple[int, list[int]]] = []
    _append_limits_items(
        items,
        {"min": 0, "max": 10, "step": 1},
        "uint32",
        dtype_id=8,  # arbitrary id; cfg_id only masks low bits
    )
    assert len(items) == 3
    cfg_min = load_header_cfg_id("CIOCommon", "cfgIdLimitMin")
    cfg_max = load_header_cfg_id("CIOCommon", "cfgIdLimitMax")
    cfg_step = load_header_cfg_id("CIOCommon", "cfgIdLimitStep")
    assert (items[0][0] & 0x1F) == cfg_min
    assert (items[1][0] & 0x1F) == cfg_max
    assert (items[2][0] & 0x1F) == cfg_step
    assert items[0][1] == [0]
    assert items[1][1] == [10]
    assert items[2][1] == [1]


def test_serialize_io_limits_partial_block():
    from dawnpy.descriptor.encoding.binary_serializer import (
        _append_limits_items,
    )

    items: list[tuple[int, list[int]]] = []
    _append_limits_items(items, {"min": 0, "max": 10}, "uint32", dtype_id=8)
    # No step => only two items emitted.
    assert len(items) == 2

    items_skipped: list[tuple[int, list[int]]] = []
    _append_limits_items(items_skipped, "not-a-dict", "uint32", dtype_id=8)
    assert items_skipped == []


def test_serialize_io_limits_full_object_path():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    obj = IoObject(
        obj_id="lim1",
        io_type="dummy",
        instance=0,
        dtype="int8",
        tags=[],
        config={"limits": {"min": -5, "max": 5, "step": 1}},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, obj, obj_ids, decoder)
    assert obj_ids["lim1"] != 0
    # Negative min must be encoded as two's complement uint32.
    expected_min = struct.unpack("<I", struct.pack("<i", -5))[0]
    assert expected_min in words
    assert 5 in words


def test_descriptor_generator_limits_emits_helpers():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import (
        IoConfigGenerator,
        _limits_item_count,
    )
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    obj = IoObject(
        obj_id="lim2",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"limits": {"min": 0, "max": 10, "step": [1]}},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    assert _limits_item_count({"min": 0, "max": 10}) == 2
    assert _limits_item_count("invalid") == 0

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: {},
        config_rw_grants=lambda: {},
    )
    lines = gen.generate_io_config("DUMMY_MACRO", obj)
    body = "\n".join(lines)
    # The leading count line must include three cfg items for the limits
    # block, even though it is one YAML key.
    assert "DUMMY_MACRO, 3," in lines[0]
    assert "CIOCommon::cfgIdLimitMin" in body
    assert "CIOCommon::cfgIdLimitMax" in body
    assert "CIOCommon::cfgIdLimitStep" in body


def test_descriptor_generator_io_config_limits_uint32():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target = IoObject(
        obj_id="dummy_lim",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 4},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio = IoObject(
        obj_id="cfgio_lim",
        io_type="config",
        instance=1,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": "dummy_lim",
            "limits": {"min": 0, "max": 10, "step": 2},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {"dummy_lim": target, "cfgio_lim": cfgio}

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )
    lines = gen.generate_io_config("CFGIO_LIM", cfgio)
    body = "\n".join(lines)
    # 2 (cfgIdCfg + cfgIdAlloc) + 3 (limits) cfg items.
    assert "CFGIO_LIM, 5," in lines[0]
    assert "CIOCommon::cfgIdLimitMin" in body
    assert "CIOCommon::cfgIdLimitMax" in body
    assert "CIOCommon::cfgIdLimitStep" in body
    assert "CIOConfig::cfgIdCfg()" in body
    assert "DUMMY_LIM" in body


def test_descriptor_generator_io_config_limits_partial():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target = IoObject(
        obj_id="dummy_p",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio = IoObject(
        obj_id="cfg_p",
        io_type="config",
        instance=4,
        dtype="uint32",
        tags=[],
        # No 'step' key -> partial-limits path in generate_cpp.
        config={"objid_ref": "dummy_p", "limits": {"min": 0, "max": 10}},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {"dummy_p": target, "cfg_p": cfgio}
    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )
    body = "\n".join(gen.generate_io_config("CFG_P", cfgio))
    assert "cfgIdLimitMin" in body
    assert "cfgIdLimitMax" in body
    assert "cfgIdLimitStep" not in body


def test_descriptor_generator_io_config_limits_signed_and_float():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target_i = IoObject(
        obj_id="dummy_i",
        io_type="dummy",
        instance=0,
        dtype="int8",
        tags=[],
        config={"init_value": 0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio_i = IoObject(
        obj_id="cfg_i",
        io_type="config",
        instance=2,
        dtype="int8",
        tags=[],
        config={
            "objid_ref": "dummy_i",
            "limits": {"min": -5, "max": [5], "step": 1},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    target_f = IoObject(
        obj_id="dummy_f",
        io_type="dummy",
        instance=0,
        dtype="float",
        tags=[],
        config={"init_value": 0.0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio_f = IoObject(
        obj_id="cfg_f",
        io_type="config",
        instance=3,
        dtype="float",
        tags=[],
        config={
            "objid_ref": "dummy_f",
            "limits": {"min": 0.0, "max": 1.0, "step": 0.25},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {
        "dummy_i": target_i,
        "cfg_i": cfgio_i,
        "dummy_f": target_f,
        "cfg_f": cfgio_f,
    }
    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )

    body_i = "\n".join(gen.generate_io_config("CFG_I", cfgio_i))
    # Negative integer literal must be cast through uint32_t.
    assert "(uint32_t)-5" in body_i

    body_f = "\n".join(gen.generate_io_config("CFG_F", cfgio_f))
    # Float literals are emitted as hex bit patterns (0.25 -> 0x3e800000).
    assert "0x3e800000" in body_f


def test_descriptor_generator_limits_partial_and_non_dict():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: {},
        config_rw_grants=lambda: {},
    )

    # Non-dict limits value: emitter must short-circuit silently.
    out: list[str] = []
    gen._append_limits_lines(out, "not-a-dict", "uint32")
    assert out == []

    # Missing one of the keys: emitter skips it without erroring.
    out = []
    gen._append_limits_lines(out, {"min": 0, "max": 10}, "uint32")
    body = "\n".join(out)
    assert "cfgIdLimitMin" in body
    assert "cfgIdLimitMax" in body
    assert "cfgIdLimitStep" not in body


def test_serialize_proto_shell_path_prompt_and_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {"dummy0": 0x11111111}
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="shell0",
        proto_type="shell",
        instance=0,
        config={"path": "/dev/ttyS0", "prompt": "dawn> "},
        bindings=["dummy0"],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["shell0"] != 0


def test_serialize_proto_can_with_objects():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="can0",
        proto_type="can",
        instance=0,
        config={
            "device": 1,
            "node_id": 0x21,
            "objects": [
                1,
                {
                    "type": "read",
                    "flags": 2,
                    "can_id_start": 0x80,
                    "bindings": [{"id": "io0"}, {"ref": "io1"}],
                },
                {"bindings": ["io0"]},
            ],
        },
        bindings=[],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["can0"] != 0
    assert len(words) > 0


def test_serialize_proto_modbus_with_registers_and_fallback_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_with_regs: list[int] = []
    proto_with_regs = ProtocolObject(
        obj_id="mb0",
        proto_type="modbus_rtu",
        instance=0,
        config={
            "path": "/tmp/ttySIM0",
            "baudrate": 115200,
            "registers": [
                1,
                {
                    "type": "holding",
                    "config": 1,
                    "start": 100,
                    "bindings": [{"id": "io0"}, {"ref": "io1"}],
                },
                {"bindings": ["io0"]},
            ],
        },
        bindings=[],
    )
    serialize_proto_object(words_with_regs, proto_with_regs, obj_ids, decoder)
    assert obj_ids["mb0"] != 0
    assert len(words_with_regs) > 0

    words_fallback: list[int] = []
    proto_fallback = ProtocolObject(
        obj_id="mb1",
        proto_type="modbus_rtu",
        instance=1,
        config={"path": "/tmp/ttySIM1"},
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_fallback, proto_fallback, obj_ids, decoder)
    assert obj_ids["mb1"] != 0
    assert len(words_fallback) > 0

    words_tcp: list[int] = []
    proto_tcp = ProtocolObject(
        obj_id="mbtcp0",
        proto_type="modbus_tcp",
        instance=0,
        config={
            "port": 502,
            "registers": [
                {
                    "type": "holding",
                    "config": 1,
                    "start": 100,
                    "bindings": ["io0"],
                },
            ],
        },
        bindings=[],
    )
    serialize_proto_object(words_tcp, proto_tcp, obj_ids, decoder)
    assert obj_ids["mbtcp0"] != 0
    assert 502 in words_tcp


def test_serialize_proto_nxscope_serial_and_dummy():
    def cfg_item_ids(words: list[int]) -> list[int]:
        item_ids: list[int] = []
        idx = 2
        for _ in range(words[1]):
            cfgid = words[idx]
            item_ids.append(cfgid & 0x1F)
            idx += 1 + ((cfgid >> 5) & 0x3FF)
        return item_ids

    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_serial: list[int] = []
    proto_serial = ProtocolObject(
        obj_id="nxs0",
        proto_type="nxscope_serial",
        instance=0,
        config={
            "iobind2": [
                {"id": "io0", "name": "a"},
                "io1",
                {"name": "missing"},
                1,
            ],
            "path": "/tmp/ttySIM0",
            "baudrate": 115200,
        },
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_serial, proto_serial, obj_ids, decoder)
    assert obj_ids["nxs0"] != 0
    assert len(words_serial) > 0
    assert 1 not in cfg_item_ids(words_serial)
    assert 2 in cfg_item_ids(words_serial)

    words_serial_unnamed: list[int] = []
    proto_serial_unnamed = ProtocolObject(
        obj_id="nxs1",
        proto_type="nxscope_serial",
        instance=1,
        config={"bindings": ["io0"]},
        bindings=["io0"],
    )
    serialize_proto_object(
        words_serial_unnamed, proto_serial_unnamed, obj_ids, decoder
    )
    assert 1 in cfg_item_ids(words_serial_unnamed)
    assert 2 not in cfg_item_ids(words_serial_unnamed)

    words_serial_bad_bindings: list[int] = []
    proto_serial_bad_bindings = ProtocolObject(
        obj_id="nxs2",
        proto_type="nxscope_serial",
        instance=2,
        config={"bindings": "io0"},
        bindings=[],
    )
    serialize_proto_object(
        words_serial_bad_bindings,
        proto_serial_bad_bindings,
        obj_ids,
        decoder,
    )
    assert cfg_item_ids(words_serial_bad_bindings) == []

    words_dummy: list[int] = []
    proto_dummy = ProtocolObject(
        obj_id="nxd0",
        proto_type="nxscope_dummy",
        instance=0,
        config={"iobind2": [{"id": "io0", "name": "d"}]},
        bindings=[],
    )
    serialize_proto_object(words_dummy, proto_dummy, obj_ids, decoder)
    assert obj_ids["nxd0"] != 0
    assert len(words_dummy) > 0

    words_udp: list[int] = []
    proto_udp = ProtocolObject(
        obj_id="nxu0",
        proto_type="nxscope_udp",
        instance=0,
        config={
            "iobind2": [{"id": "io0", "name": "u"}],
            "port": 50000,
        },
        bindings=["io0"],
    )
    serialize_proto_object(words_udp, proto_udp, obj_ids, decoder)
    assert obj_ids["nxu0"] != 0
    assert len(words_udp) > 0


def test_serialize_proto_nimble_services():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "bat0": 0x10000001,
        "di0": 0x10000002,
        "do0": 0x10000003,
        "ai0": 0x10000004,
        "t0": 0x10000005,
        "h0": 0x10000006,
        "p0": 0x10000007,
        "g0": 0x10000008,
        "fio0": 0x10000009,
        "fio1": 0x1000000A,
    }
    words: list[int] = []
    proto = ProtocolObject(
        obj_id="nim0",
        proto_type="nimble",
        instance=0,
        config={
            "gap_name": "thingy53",
            "services": {
                "dis": {"enabled": True},
                "bas": {"battery_level": {"id": "bat0"}},
                "aios": {
                    "groups": [
                        {
                            "digital_inputs": ["di0"],
                            "digital_outputs": ["do0"],
                        },
                        {"analog_inputs": ["ai0"]},
                        {"digital_inputs": "bad"},
                        1,
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t0"}},
                        {"type": "humidity", "data": {"id": "h0"}},
                        {"type": "pressure", "data": {"id": "p0"}},
                        {"type": "gas_resistance", "data": {"id": "g0"}},
                    ]
                },
                "imds": {
                    "temperature": {
                        "data": {"id": "t0"},
                        "metadata": {"user_description": "imds temp"},
                    },
                    "humidity": {"id": "h0"},
                    "pressure": {"id": "p0"},
                    "gas_resistance": {"id": "g0"},
                },
                "ots": {
                    "objects": [
                        {
                            "name": "ro",
                            "type": "file",
                            "access": "read",
                            "io": "fio0",
                        },
                        {
                            "type": "file",
                            "on_complete": "delete",
                            "io": {"id": "fio1"},
                        },
                        # Skipped: not a dict.
                        "bad-entry",
                        # Skipped: io is missing.
                        {"name": "no-io"},
                        # Skipped: io does not resolve.
                        {"name": "bad-io", "io": "missing"},
                    ]
                },
            },
        },
        bindings=[],
    )
    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["nim0"] != 0
    assert len(words) > 0

    words_bad_services: list[int] = []
    proto_bad_services = ProtocolObject(
        obj_id="nim1",
        proto_type="nimble",
        instance=1,
        config={"gap_name": "x", "services": []},
        bindings=[],
    )
    serialize_proto_object(
        words_bad_services, proto_bad_services, obj_ids, decoder
    )
    assert obj_ids["nim1"] != 0

    words_malformed_ess: list[int] = []
    proto_malformed_ess = ProtocolObject(
        obj_id="nim2",
        proto_type="nimble",
        instance=2,
        config={
            "services": {
                "ess": {
                    "characteristics": [
                        "bad",
                        {
                            "type": "temperature",
                            "data": {"id": "t0"},
                            "metadata": "bad",
                        },
                    ]
                }
            }
        },
        bindings=[],
    )
    serialize_proto_object(
        words_malformed_ess, proto_malformed_ess, obj_ids, decoder
    )
    assert obj_ids["nim2"] != 0

    words_bad_ess_shape: list[int] = []
    proto_bad_ess_shape = ProtocolObject(
        obj_id="nim3",
        proto_type="nimble",
        instance=3,
        config={"services": {"ess": {"characteristics": "bad"}}},
        bindings=[],
    )
    serialize_proto_object(
        words_bad_ess_shape, proto_bad_ess_shape, obj_ids, decoder
    )
    assert obj_ids["nim3"] != 0


def test_serialize_proto_udp_and_ipc():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_udp: list[int] = []
    proto_udp = ProtocolObject(
        obj_id="udp0",
        proto_type="udp",
        instance=0,
        config={"port": 3344},
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_udp, proto_udp, obj_ids, decoder)
    assert obj_ids["udp0"] != 0
    assert len(words_udp) > 0

    words_ipc: list[int] = []
    proto_ipc = ProtocolObject(
        obj_id="ipc0",
        proto_type="ipc",
        instance=0,
        config={"rx_path": "/var/pipe/rx", "tx_path": "/var/pipe/tx"},
        bindings=["io0"],
    )
    serialize_proto_object(words_ipc, proto_ipc, obj_ids, decoder)
    assert obj_ids["ipc0"] != 0
    assert len(words_ipc) > 0


def test_serialize_proto_dummy_with_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
    }

    words_dummy: list[int] = []
    proto_dummy = ProtocolObject(
        obj_id="dummy0",
        proto_type="dummy",
        instance=0,
        config={},
        bindings=["io0"],
    )
    serialize_proto_object(words_dummy, proto_dummy, obj_ids, decoder)
    assert obj_ids["dummy0"] != 0
    assert len(words_dummy) > 0


def test_capabilities_decode_command_file():
    runner = CliRunner()
    blob = _make_capabilities_blob_v2()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "cap.bin"
        path.write_bytes(blob)
        hex_path = Path(tmpdir) / "cap.hex"
        hex_path.write_text(blob.hex(), encoding="utf-8")
        shell_hex_path = Path(tmpdir) / "cap_shell.hex"
        shell_hex_path.write_text(_to_shell_hexdump(blob), encoding="utf-8")
        bad_hex_path = Path(tmpdir) / "cap_bad.hex"
        bad_hex_path.write_text("GG", encoding="utf-8")

        result = runner.invoke(cmd_desc_decode_caps, [str(path)])
        assert result.exit_code == 0
        assert (
            "Capabilities Blob: version=2 layout=0 payload=504B"
            in result.output
        )
        assert "Descriptor: slots=2 slot_size=4096" in result.output
        assert "Build flags: os_nuttx, desc_dynamic" in result.output
        assert "IO classes enabled" in result.output
        assert "dummy" in result.output
        assert "capabilities" in result.output
        assert "encoder" in result.output
        assert "encoder_index" in result.output
        assert "bitsplit" in result.output
        assert "configwriter" in result.output
        assert "nxscope_udp" in result.output
        assert "modbus_tcp" in result.output

        result_hex_file = runner.invoke(
            cmd_desc_decode_caps,
            [str(path), "--hex-file", str(hex_path)],
        )
        assert result_hex_file.exit_code == 0
        assert "PROTO classes enabled" in result_hex_file.output

        result_shell_hex_file = runner.invoke(
            cmd_desc_decode_caps,
            [
                str(path),
                "--hex-file",
                str(shell_hex_path),
            ],
        )
        assert result_shell_hex_file.exit_code == 0
        assert "Capabilities Blob: version=2 layout=0 payload=504B" in (
            result_shell_hex_file.output
        )

        result_bad_hex = runner.invoke(
            cmd_desc_decode_caps,
            [
                str(path),
                "--hex-file",
                str(bad_hex_path),
            ],
        )
        assert result_bad_hex.exit_code != 0
        assert "Invalid hex file content" in result_bad_hex.output

    result_bad = runner.invoke(
        cmd_desc_decode_caps, ["/nonexistent/path/cap.bin"]
    )
    assert result_bad.exit_code != 0
    assert "Input file not found" in result_bad.output


def test_inlined_serializer_registries_bind_yaml_to_cpp_class():
    # Every IO yaml-token lives in its own handler under handlers/io_*.py;
    # IO_HANDLER_REGISTRY is the single source of truth.
    from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY

    assert IO_HANDLER_REGISTRY["sensor"].cpp_class == "CIOSensor"
    assert IO_HANDLER_REGISTRY["sensor"].no_fields is True
    assert IO_HANDLER_REGISTRY["descriptor"].pass_through is True
    assert IO_HANDLER_REGISTRY["descriptor"].dtype == "block"
    assert IO_HANDLER_REGISTRY["sysinfo"].variant_dtypes["uptime"] == "uint64"
    assert IO_HANDLER_REGISTRY["dummy"].cpp_class == "CIODummy"
    assert IO_HANDLER_REGISTRY["control"].cpp_class == "CIOControl"
    assert IO_HANDLER_REGISTRY["fileio"].cpp_class == "CIOFile"
    assert IO_HANDLER_REGISTRY["pwm"].cpp_class == "CIOPwm"
    assert IO_HANDLER_REGISTRY["leds"].cpp_class == "CIOLeds"

    # Every PROG yaml-token lives in its own handler under handlers/prog_*.py.
    from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
    from dawnpy.headerdefs import load_header_type_defs

    prog_yaml_types = {
        item["yaml_type"] for item in load_header_type_defs()["prog_types"]
    }
    assert prog_yaml_types == set(PROG_HANDLER_REGISTRY)

    assert PROG_HANDLER_REGISTRY["stats"].cpp_class == "CProgStatsAvg"
    assert PROG_HANDLER_REGISTRY["sampling"].cpp_class == "CProgSampling"
    assert [
        f.name for f in PROG_HANDLER_REGISTRY["movingavg"].config_fields()
    ] == [
        "iobind",
        "window",
    ]

    # Every PROTO type now lives in a per-type handler under handlers/.
    from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

    assert PROTO_HANDLER_REGISTRY["serial"].cpp_class == "CProtoSerial"
    assert PROTO_HANDLER_REGISTRY["nimble"].cpp_class == "CProtoNimblePrph"
    assert PROTO_HANDLER_REGISTRY["can"].cpp_class == "CProtoCan"
    assert PROTO_HANDLER_REGISTRY["serial"].dtype_names()["string"] == "char"
    assert (
        PROTO_HANDLER_REGISTRY["nxscope_serial"].fixed_string_bytes()[
            "nxscope_name"
        ]
        == 12
    )


def test_io_class_name_resolution_via_headerdefs():
    # Sensor without subtype cannot resolve a method.
    assert _io_class_name(_mk_io("sensor")) is None
    # Sensor temp resolves through CIOSensor::objectIdTemp.
    assert _io_class_name(_mk_io("sensor", subtype="temp")) == (
        "sensor_temperature"
    )
    # System IOs resolve via CIOSysinfo / CIOUname / CIOBoardctl variants.
    assert _io_class_name(_mk_io("sysinfo", variant="uptime")) == (
        "system_uptime"
    )
    assert _io_class_name(_mk_io("uname", variant="hostname")) == (
        "system_hostname"
    )
    assert _io_class_name(_mk_io("boardctl", variant="reset")) == (
        "system_reset"
    )
    # Standard objectId path resolves dummy via headerdefs.
    assert _io_class_name(_mk_io("dummy")) == "dummy"


def test_io_helper_branch_edges():
    from dawnpy.descriptor.encoding.words import (
        dtype_id_by_name,
        mask_from_allowed,
    )

    decoder = ObjectIdDecoder()
    assert dtype_id_by_name(decoder, "not-a-type") is None
    assert mask_from_allowed([], {"x": 1}) is None
    assert mask_from_allowed(["x"], []) == 0
    assert mask_from_allowed(["x", "y"], {"x": 0}) == 1


def test_default_enum_key_helper_branches():
    assert default_enum_key({"a": 1, "b": 2}, "x") == "a"
    assert default_enum_key({}, "x") == "x"


def test_prog_yaml_driven_branches_and_errors(monkeypatch):
    decoder = ObjectIdDecoder()
    obj_ids = {
        "src0": 0x1001,
        "src1": 0x1002,
        "virt0": 0x2001,
        "virt1": 0x2002,
        "o0": 0x3001,
        "sel0": 0x3002,
        "stat0": 0x3003,
        "t0": 0x4001,
    }
    words: list[int] = []

    # Prog policy now lives in handlers/prog_*.py; no YAML monkey-patch
    # needed.
    sampling = ProgramObject(
        obj_id="p_sampling",
        prog_type="sampling",
        instance=0,
        inputs=["src0", "src1"],
        outputs=["virt0", "virt1"],
        reset=None,
        config={"interval": 5},
    )
    serialize_prog_object(words, sampling, obj_ids, decoder)

    adjust = ProgramObject(
        obj_id="p_adjust",
        prog_type="adjust",
        instance=1,
        inputs=["src0"],
        outputs=["virt0"],
        reset=None,
        config={"params": {"offset": 2, "scale": 3}},
    )
    serialize_prog_object(words, adjust, obj_ids, decoder)

    gateway = ProgramObject(
        obj_id="p_gateway",
        prog_type="gateway",
        instance=2,
        inputs=[],
        outputs=[],
        reset=None,
        config={"iobind": [0, {"x": 1}, {"io1": "src0", "io2": "virt0"}]},
    )
    serialize_prog_object(words, gateway, obj_ids, decoder)

    buffer = ProgramObject(
        obj_id="p_buffer",
        prog_type="buffer",
        instance=3,
        inputs=[],
        outputs=[],
        reset=None,
        config={
            "iobind": [
                0,
                {"x": 1},
                {
                    "src": "src0",
                    "out": "o0",
                    "sel": "sel0",
                    "stat": "stat0",
                },
            ],
            "chunk_size": 32,
        },
    )
    serialize_prog_object(words, buffer, obj_ids, decoder)
    assert 32 in words

    default_buffer_words: list[int] = []
    default_buffer = ProgramObject(
        obj_id="p_buffer_default",
        prog_type="buffer",
        instance=5,
        inputs=[],
        outputs=[],
        reset=None,
        config={},
    )
    serialize_prog_object(
        default_buffer_words, default_buffer, dict(obj_ids), decoder
    )
    from dawnpy.descriptor.encoding.words import cfg_id

    buffer_cls = next(
        cls for cls, name in decoder.prog_classes.items() if name == "buffer"
    )
    chunk_cfg = cfg_id(3, buffer_cls, 0, False, 1, 4)
    chunk_idx = default_buffer_words.index(chunk_cfg)
    assert default_buffer_words[chunk_idx + 1] == 1

    sequencer = ProgramObject(
        obj_id="p_seq",
        prog_type="sequencer",
        instance=4,
        inputs=[],
        outputs=[],
        reset=None,
        config={
            "targets": ["x", "t0"],
            "states": [0, {"x": 1}, {"value": 7, "dwell_us": 10}],
            "start_index": 1,
        },
    )
    serialize_prog_object(words, sequencer, obj_ids, decoder)
    assert obj_ids["p_seq"] != 0
    adjust_objid = obj_ids["p_adjust"]
    adjust_idx = words.index(adjust_objid)
    assert words[adjust_idx + 1] == 2

    # When neither the handlers nor PROG_TYPES has an entry for a prog
    # type, the serializer cannot resolve the C++ class and bails out.
    monkeypatch.setattr(prog_serializer_mod, "PROG_HANDLER_REGISTRY", {})
    monkeypatch.setattr(prog_serializer_mod, "PROG_TYPES", {})
    with pytest.raises(
        click.ClickException, match="Unable to resolve PROG class"
    ):
        serialize_prog_object([], sampling, dict(obj_ids), decoder)

    # When the resolved class name is not in the decoder map, the serializer
    # raises an "Unknown PROG class" error.
    monkeypatch.setattr(
        prog_serializer_mod,
        "load_header_object_class_name",
        lambda owner, method: "missing_prog_class",
    )
    monkeypatch.setattr(
        prog_serializer_mod,
        "PROG_HANDLER_REGISTRY",
        {"sampling": SimpleNamespace(cpp_class="CProgSampling")},
    )
    with pytest.raises(click.ClickException, match="Unknown PROG class"):
        serialize_prog_object([], sampling, {}, decoder)


def test_simple_prog_handlers_encode_binary():
    """Cover simple auto-discovered PROG handler binary paths."""
    decoder = ObjectIdDecoder()
    obj_ids = {"src0": 0x1001, "virt0": 0x2001}

    cases = [
        ("dummy", {}),
        ("latest", {}),
        ("redirect", {}),
        ("statsavg", {}),
        ("statscount", {}),
        ("statsmax", {}),
        ("statsrms", {}),
        ("statssum", {}),
        ("movingavg", {"window": 4}),
        ("iirfilter", {"alpha_num": 1, "alpha_den": 8}),
        ("threshold", {"mode": 1, "low": 2, "high": 3}),
        ("thresholdvalue", {"mode": 1, "low": 2, "high": 3}),
    ]
    for index, (prog_type, config) in enumerate(cases):
        words: list[int] = []
        obj = ProgramObject(
            obj_id=f"p_{prog_type}",
            prog_type=prog_type,
            instance=index,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config=config,
        )
        serialize_prog_object(words, obj, dict(obj_ids), decoder)
        assert words[1] >= 1

    # Exercise the "field not present" branch in shared uint32 emission.
    serialize_prog_object(
        [],
        ProgramObject(
            obj_id="p_movingavg_empty",
            prog_type="movingavg",
            instance=99,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={},
        ),
        dict(obj_ids),
        decoder,
    )


def test_prog_iobind_binary_interleaves_multiple_binds():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "src0": 0x1001,
        "src1": 0x1002,
        "virt0": 0x2001,
        "virt1": 0x2002,
    }
    words: list[int] = []
    obj = ProgramObject(
        obj_id="p_bitsplit",
        prog_type="bitsplit",
        instance=0,
        inputs=["src0", "src1"],
        outputs=["virt0", "virt1"],
        reset=None,
        config={"bits": [0, 1]},
    )

    serialize_prog_object(words, obj, dict(obj_ids), decoder)

    assert words[3:7] == [0x1001, 0x2001, 0x1002, 0x2002]


def test_prog_iobind_binary_rejects_mismatched_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {"src0": 0x1001, "src1": 0x1002, "virt0": 0x2001}
    obj = ProgramObject(
        obj_id="p_mismatch",
        prog_type="statsmin",
        instance=0,
        inputs=["src0"],
        outputs=["virt0"],
        reset=None,
        config={"sources": ["src0", "src1"], "outputs": ["virt0"]},
    )

    with pytest.raises(ValueError, match="has 2 sources and 1 outputs"):
        serialize_prog_object([], obj, obj_ids, decoder)


def test_prog_serializer_falls_back_to_registered_type(monkeypatch):
    """Cover OOT-style PROG_TYPES fallback when no built-in handler exists."""
    decoder = ObjectIdDecoder()
    monkeypatch.setattr(prog_serializer_mod, "PROG_HANDLER_REGISTRY", {})
    monkeypatch.setattr(
        prog_serializer_mod,
        "PROG_TYPES",
        {"oot_sampling": SimpleNamespace(cpp_class="CProgSampling")},
    )
    words: list[int] = []
    serialize_prog_object(
        words,
        ProgramObject(
            obj_id="oot",
            prog_type="oot_sampling",
            instance=0,
            inputs=[],
            outputs=[],
            reset=None,
            config={},
        ),
        {},
        decoder,
    )
    assert words[1] == 0


def test_auto_handler_registry_error_branches(monkeypatch):
    """Cover handler auto-discovery validation errors."""
    import dawnpy.descriptor.handlers as handlers_mod

    missing = ModuleType("missing")
    monkeypatch.setattr(
        handlers_mod, "_iter_handler_modules", lambda family: [missing]
    )
    with pytest.raises(RuntimeError, match="missing required io handler"):
        handlers_mod._load_io_registry()

    invalid = ModuleType("invalid")
    for attr in handlers_mod._FAMILY_REQUIRED_ATTRS["prog"]:
        setattr(invalid, attr, object())
    invalid.yaml_type = ""
    monkeypatch.setattr(
        handlers_mod, "_iter_handler_modules", lambda family: [invalid]
    )
    with pytest.raises(RuntimeError, match="invalid prog handler yaml_type"):
        handlers_mod._load_prog_registry()

    for family, loader, label in (
        ("io", handlers_mod._load_io_registry, "IO"),
        ("prog", handlers_mod._load_prog_registry, "PROG"),
        ("proto", handlers_mod._load_proto_registry, "PROTO"),
    ):
        first = ModuleType(f"{family}_first")
        second = ModuleType(f"{family}_second")
        for module in (first, second):
            for attr in handlers_mod._FAMILY_REQUIRED_ATTRS[family]:
                setattr(module, attr, object())
            module.yaml_type = "dup"
        monkeypatch.setattr(
            handlers_mod,
            "_iter_handler_modules",
            lambda requested_family, a=first, b=second: [a, b],
        )
        with pytest.raises(RuntimeError, match=f"Duplicate {label} handler"):
            loader()


def test_serialize_io_error_branches(monkeypatch):
    """Cover the dtype-lookup error branches in binary.py + io_config."""
    from dawnpy.descriptor.encoding import io_serialization as io_runtime_mod

    decoder = ObjectIdDecoder()
    io = IoObject(
        obj_id="cfg0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "device": 1,
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 1},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    obj_ids = {"dummy0": 0x12345678}

    # Branch 1: device-cfg dtype lookup fails inside binary.py.
    monkeypatch.setattr(
        binary_serializer_mod,
        "dtype_id_by_name",
        lambda *a, **kw: None,
    )
    with pytest.raises(click.ClickException, match="device cfg"):
        _serialize_io_object([], io, dict(obj_ids), decoder)
    monkeypatch.undo()

    # Branch 2: config-reference dtype lookup fails inside io_config
    # handler (the first resolve_dtype call inside io_config.encode_binary).
    calls = {"n": 0}

    def _none_on_nth(want_n: int):
        def _wrapped(*a, **kw):
            calls["n"] += 1
            if calls["n"] == want_n:
                return None
            return 7

        return _wrapped

    calls["n"] = 0
    monkeypatch.setattr(io_runtime_mod, "dtype_id_by_name", _none_on_nth(1))
    with pytest.raises(click.ClickException, match="config reference$"):
        _serialize_io_object([], io, dict(obj_ids), decoder)

    calls["n"] = 0
    monkeypatch.setattr(io_runtime_mod, "dtype_id_by_name", _none_on_nth(2))
    with pytest.raises(click.ClickException, match="reference cfgid"):
        _serialize_io_object([], io, dict(obj_ids), decoder)


def test_serialize_proto_error_branches(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=[]
    )

    # The handler registry drives class resolution; remove "serial" from
    # both the handler registry and the PROTO_TYPES fallback to force the
    # failure path.
    monkeypatch.setattr(
        proto_serializer_mod,
        "PROTO_HANDLER_REGISTRY",
        {
            k: v
            for k, v in proto_serializer_mod.PROTO_HANDLER_REGISTRY.items()
            if k != "serial"
        },
    )
    monkeypatch.setattr(
        proto_serializer_mod,
        "PROTO_TYPES",
        {
            k: v
            for k, v in proto_serializer_mod.PROTO_TYPES.items()
            if k != "serial"
        },
    )
    with pytest.raises(click.ClickException, match="supports protocol type"):
        serialize_proto_object([], proto, {}, decoder)

    # Restore PROTO_TYPES; force handler-declared dtype lookup failures.
    monkeypatch.undo()
    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", lambda d, name: None
    )
    with pytest.raises(click.ClickException, match="protocol field 'string'"):
        serialize_proto_object([], proto, {}, decoder)

    def _dtype_missing_int(dec, name):
        if name == "char":
            return 14
        return None

    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", _dtype_missing_int
    )
    with pytest.raises(click.ClickException, match="protocol field 'int'"):
        serialize_proto_object([], proto, {}, decoder)

    # Custom (non-built-in) proto type cannot be resolved.
    custom_proto = ProtocolObject(
        obj_id="custom0",
        proto_type="custom_proto",
        instance=0,
        config={},
        bindings=[],
    )
    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", lambda d, n: 7
    )
    with pytest.raises(click.ClickException, match="supports protocol type"):
        serialize_proto_object([], custom_proto, {}, decoder)

    # UDP port dtype lookup failure names the handler-declared field.
    monkeypatch.setattr(
        proto_serializer_mod,
        "dtype_id_by_name",
        lambda dec, name: None if name == "uint16" else 7,
    )
    with pytest.raises(
        click.ClickException, match="protocol field 'udp_port'"
    ):
        serialize_proto_object(
            [],
            ProtocolObject(
                obj_id="udp0",
                proto_type="udp",
                instance=0,
                config={"port": 1},
                bindings=[],
            ),
            {},
            decoder,
        )


def test_serialize_proto_non_dict_cfg_sections(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=[]
    )
    serialize_proto_object([], proto, {}, decoder)


def test_serialize_proto_nimble_non_dict_maps():
    decoder = ObjectIdDecoder()
    obj_ids = {"io0": 0x10000001}
    proto = ProtocolObject(
        obj_id="nimx",
        proto_type="nimble",
        instance=0,
        config={
            "services": {"aios": {"groups": [{"digital_inputs": "bad"}]}},
        },
        bindings=[],
    )
    serialize_proto_object([], proto, obj_ids, decoder)


def test_serialize_proto_nimble_service_enum_paths(monkeypatch):
    decoder = ObjectIdDecoder()
    obj_ids = {"di0": 0x10000001, "ai0": 0x10000002, "t0": 0x10000003}
    proto = ProtocolObject(
        obj_id="nimsvc",
        proto_type="nimble",
        instance=0,
        config={
            "services": {
                "aios": {
                    "groups": [
                        {"digital_inputs": ["di0", "ai0"]},
                        {"digital_inputs": "bad"},
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t0"}}
                    ]
                },
                "imds": {"temperature": {"id": "t0"}},
            }
        },
        bindings=[],
    )

    def _enum_map(owner, _prefix):
        if owner == "CProtoNimblePrphAios":
            return {"digital_inputs": 1}
        return {"temperature": 2}

    monkeypatch.setattr(
        proto_serializer_mod, "load_header_enum_value_ids", _enum_map
    )
    words: list[int] = []
    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["nimsvc"] != 0
    assert len(words) > 0


def test_serialize_proto_defensive_header_enum_failure(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="s1",
        proto_type="can",
        instance=0,
        config={},
        bindings=[],
    )

    # When headerdefs raises for an enum prefix, the safe-resolver returns {}
    # and serialization proceeds without crashing.
    def _raise(*_a):
        raise proto_serializer_mod.HeaderDefsError("missing")

    monkeypatch.setattr(
        proto_serializer_mod, "load_header_enum_value_ids", _raise
    )
    serialize_proto_object([], proto, {}, decoder)


def test_serialize_io_dummy_baseline():
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="d0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []
    _serialize_io_object(words, obj, {}, decoder)
    assert words


def test_generate_descriptor_binary_unknown_object_raises(monkeypatch):
    class _Unknown:
        pass

    monkeypatch.setattr(
        binary_serializer_mod, "load_yaml_with_vars", lambda *a, **k: {}
    )
    monkeypatch.setattr(
        binary_serializer_mod,
        "decode_objects",
        lambda *a, **k: [_Unknown()],
    )
    with pytest.raises(click.ClickException, match="supports IO/PROG/PROTO"):
        _generate_descriptor_binary(Path("/tmp/x.yaml"), None)
