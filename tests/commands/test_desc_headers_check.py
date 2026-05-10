# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_headers_check_command_success(monkeypatch):
    """Test headers-check command reports success and loaded counts."""
    runner = CliRunner()
    monkeypatch.setattr(
        headers_check_mod, "find_repo_root", lambda: Path("/tmp/repo")
    )
    groups = header_bundle_mod.HeaderDefinitionGroups(
        header_defs={
            "dtype": [1, 2],
            "io_classes": {1: "a"},
            "prog_classes": {1: "b", 2: "c"},
            "proto_classes": {},
        },
        type_defs={
            "io_types": [1],
            "prog_types": [1, 2],
            "proto_types": [1, 2, 3],
        },
        metadata_defs=[],
        component_defs={},
    )
    lookups = minimal_header_lookups(cfg_id_loader=lambda _owner, _method: 1)
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: minimal_header_bundle(groups=groups, lookups=lookups),
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

    monkeypatch.setattr(
        headers_check_mod.header_bundle,
        "load_header_bundle",
        _boom,
    )
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

    monkeypatch.setattr(
        headers_check_mod.header_bundle, "load_header_bundle", _missing
    )
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
    groups = header_bundle_mod.HeaderDefinitionGroups(
        header_defs={
            "dtype": [],
            "io_classes": {},
            "prog_classes": {},
            "proto_classes": {},
        },
        type_defs={"io_types": [], "prog_types": [], "proto_types": []},
        metadata_defs=[],
        component_defs={},
    )
    lookups = minimal_header_lookups(cfg_id_loader=lambda _owner, _method: 1)
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: minimal_header_bundle(groups=groups, lookups=lookups),
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
    groups = header_bundle_mod.HeaderDefinitionGroups(
        header_defs={
            "dtype": [],
            "io_classes": {},
            "prog_classes": {},
            "proto_classes": {},
        },
        type_defs={"io_types": [], "prog_types": [], "proto_types": []},
        metadata_defs=[],
        component_defs={},
    )
    lookups = minimal_header_lookups(cfg_id_loader=lambda _owner, _method: 1)
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: minimal_header_bundle(groups=groups, lookups=lookups),
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


def test_check_field_reports_unresolved():
    """_check_field flags helpers and enum_prefixes that fail to resolve."""
    from dawnpy.descriptor.definitions.type_info import ConfigField
    from dawnpy.descriptor.validation import headers_check as hc
    from dawnpy.headerdefs import HeaderDefsError

    def _boom_cfg(owner, method):
        raise HeaderDefsError("missing")

    def _boom_enum(owner, prefix):
        raise HeaderDefsError("missing-enum")

    field = ConfigField(
        name="foo",
        cpp_helper="Owner::method",
        enum_prefix="Owner::PREFIX_",
    )
    defs = minimal_header_bundle(
        lookups=minimal_header_lookups(
            cfg_id_loader=_boom_cfg,
            enum_value_ids_loader=_boom_enum,
        )
    )
    out = hc._check_field("io", "dummy", field, defs)
    assert any("cpp_helper 'Owner::method' did not resolve" in s for s in out)
    assert any(
        "enum_prefix 'Owner::PREFIX_' did not resolve" in s for s in out
    )
