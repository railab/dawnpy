# tools/dawnpy/tests/test_headerdefs.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for runtime C++ header definition loading."""

from pathlib import Path

import pytest

import dawnpy.descriptor.definitions.io_family as builtin_io_mod
import dawnpy.descriptor.definitions.prog_family as builtin_prog_mod
import dawnpy.descriptor.definitions.proto_family as builtin_proto_mod
import dawnpy.headerdefs as headerdefs
import dawnpy.headerdefs._components as headerdefs_components_mod
import dawnpy.headerdefs._constants as headerdefs_constants_mod
import dawnpy.headerdefs._enums as headerdefs_enums_mod
import dawnpy.headerdefs._loader as headerdefs_loader_mod
import dawnpy.headerdefs._nimble as headerdefs_nimble_mod
import dawnpy.headerdefs._parser as headerdefs_parser_mod
import dawnpy.headerdefs._paths as headerdefs_paths_mod
import dawnpy.headerdefs._typespec as headerdefs_types_mod
import dawnpy.headerdefs.bundle as header_bundle_mod
import dawnpy.objectid as objectid_mod
from dawnpy.sources import DawnSourcesMissing
from tests.headerdefs_helpers import blank_objectid_decoder, cache_clear
from tests.headerdefs_helpers import definition_set as _definition_set
from tests.headerdefs_helpers import empty_type_defs as _empty_type_defs
from tests.headerdefs_helpers import enum_type_defs as _enum_type_defs
from tests.headerdefs_helpers import patch_builtin_type_indexers
from tests.headerdefs_helpers import stub_class_header as _stub_class_header
from tests.headerdefs_helpers import stub_enum_header as _stub_enum_header
from tests.headerdefs_helpers import ts_node


@pytest.fixture(autouse=True)
def clear_header_caches():
    """Ensure header loader caches are cleared per test."""
    cache_clear(header_bundle_mod.load_header_bundle)
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()
    headerdefs.load_simple_proto_constants.cache_clear()
    yield
    cache_clear(header_bundle_mod.load_header_bundle)
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()
    headerdefs.load_simple_proto_constants.cache_clear()


@pytest.fixture(autouse=True)
def block_live_repo_lookup(monkeypatch, request):
    """Prevent unit tests from discovering the real Dawn checkout."""
    allowed = {
        "test_repo_root_from_file_search_path",
        "test_repo_root_from_cwd_search_path",
        "test_repo_root_from_nested_layout",
        "test_repo_root_returns_none_when_all_search_paths_fail",
        "test_find_repo_root_delegates",
    }
    if request.node.name not in allowed:
        monkeypatch.setattr(
            headerdefs_paths_mod, "_repo_root_from_here", lambda: None
        )


def test_eval_cpp_int_basic_expression_and_symbols():
    value = headerdefs_parser_mod._eval_cpp_int("(A << 1) | 0b1", {"A": 2})
    assert value == 5


def test_eval_cpp_int_unsupported_expression_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="Failed to evaluate"):
        headerdefs_parser_mod._eval_cpp_int("abc()", {})


def test_eval_cpp_int_invalid_character_expression_raises_unsupported():
    with pytest.raises(headerdefs.HeaderDefsError, match="Unsupported"):
        headerdefs_parser_mod._eval_cpp_int("g()", {})


def test_dtype_size_and_initval_mappings():
    assert headerdefs_constants_mod._dtype_size("FLOAT") == 32
    assert headerdefs_constants_mod._dtype_size("UNKNOWN") == 0
    # cfgIdInitval dtype param now matches SObjectId::DTYPE_*.
    assert headerdefs_constants_mod._dtype_initval_param("float") == 10
    assert headerdefs_constants_mod._dtype_initval_param("uint32") == 7
    assert headerdefs_constants_mod._dtype_initval_param("int8") == 2
    assert headerdefs_constants_mod._dtype_initval_param("char") is None


def test_class_name_normalizers():
    assert (
        headerdefs_constants_mod._normalize_prog_class_name("stats_min")
        == "stat_min"
    )
    assert (
        headerdefs_constants_mod._normalize_prog_class_name("buffer")
        == "buffer"
    )
    assert (
        headerdefs_constants_mod._normalize_proto_class_name("nimble_prph")
        == "nimble_peripheral"
    )
    assert headerdefs_constants_mod._normalize_proto_class_name("can") == "can"


def test_component_kconfig_mappings():
    assert (
        headerdefs_components_mod._component_kconfig("io", "CIOTimestamp")
        == "CONFIG_DAWN_IO_TIMESTAMPIO"
    )
    assert (
        headerdefs_components_mod._component_kconfig(
            "prog", "CProgMovingAverage"
        )
        == "CONFIG_DAWN_PROG_MOVING_AVG"
    )
    assert (
        headerdefs_components_mod._component_kconfig("prog", "CProgVecPack")
        == "CONFIG_DAWN_PROG_VECPACK"
    )
    assert (
        headerdefs_components_mod._component_kconfig("prog", "CProgBitSplit")
        == "CONFIG_DAWN_PROG_BITSPLIT"
    )
    assert (
        headerdefs_components_mod._component_kconfig("prog", "CProgBitPack")
        == "CONFIG_DAWN_PROG_BITPACK"
    )
    assert (
        headerdefs_components_mod._component_kconfig("prog", "CProgManyToOne")
        == "CONFIG_DAWN_PROG_MANYTOONE"
    )
    assert (
        headerdefs_components_mod._component_kconfig(
            "proto", "CProtoNimblePrphAios"
        )
        == "CONFIG_DAWN_PROTO_NIMBLE_AIOS"
    )
    assert (
        headerdefs_components_mod._component_kconfig("proto", "CProtoSerial")
        == "CONFIG_DAWN_PROTO_SERIAL"
    )


def test_build_component_entries_filters_and_sorts():
    specs = [
        {"cpp_class": "CIOCommon", "header": "dawn/io/common.hxx"},
        {"cpp_class": "CIODummy", "header": "dawn/io/dummy.hxx"},
        {"cpp_class": "CIOTimestamp", "header": "dawn/io/timestamp.hxx"},
        {"cpp_class": "CIODummy", "header": "dawn/io/dummy.hxx"},
    ]
    out = headerdefs_components_mod._build_component_entries("io", specs)
    assert out == [
        {
            "name": "CIODummy",
            "kval": "CONFIG_DAWN_IO_DUMMY",
            "include": "dawn/io/dummy.hxx",
        },
        {
            "name": "CIOTimestamp",
            "kval": "CONFIG_DAWN_IO_TIMESTAMPIO",
            "include": "dawn/io/timestamp.hxx",
        },
    ]


def test_build_component_entries_skips_incomplete_items():
    specs = [
        {"cpp_class": "", "header": "dawn/io/dummy.hxx"},
        {"cpp_class": "CIODummy", "header": ""},
    ]
    assert (
        headerdefs_components_mod._build_component_entries("io", specs) == []
    )


def test_load_header_component_defs_raises_when_empty(monkeypatch):
    monkeypatch.setattr(
        headerdefs_components_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_collect_class_specs",
        lambda *a, **k: [],
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="No component"):
        headerdefs.load_header_component_defs()


def test_load_header_metadata_defs(monkeypatch):
    child = ts_node("type_identifier", start_byte=0, end_byte=1)
    class_node = ts_node("class_specifier", children=[child])

    monkeypatch.setattr(
        headerdefs_components_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_parse_cpp_header",
        lambda _h: (b"class CDescriptor {}", object()),
    )
    monkeypatch.setattr(
        headerdefs_components_mod, "_iter_ts_nodes", lambda _r: [class_node]
    )
    monkeypatch.setattr(
        headerdefs_components_mod, "_ts_text", lambda *_a: "CDescriptor"
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_extract_methods_with_prefixes",
        lambda *_a: {"cfgIdVersion": [], "cfgIdString": []},
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_extract_enum_constants_from_tree",
        lambda *_a: {"DESC_CFG_VERSION": 1, "DESC_CFG_STRING": 2},
    )
    defs = headerdefs.load_header_metadata_defs()
    assert defs == [
        {
            "name": "version",
            "cpp_helper": "CDescriptor::cfgIdVersion",
            "value_type": "version",
        },
        {
            "name": "user_string",
            "cpp_helper": "CDescriptor::cfgIdString",
            "value_type": "string",
        },
    ]


def test_load_header_metadata_defs_raises_when_missing(monkeypatch):
    child = ts_node("type_identifier", start_byte=0, end_byte=1)
    class_node = ts_node("class_specifier", children=[child])

    monkeypatch.setattr(
        headerdefs_components_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_parse_cpp_header",
        lambda _h: (b"X", object()),
    )
    monkeypatch.setattr(
        headerdefs_components_mod, "_iter_ts_nodes", lambda _r: [class_node]
    )
    monkeypatch.setattr(
        headerdefs_components_mod, "_ts_text", lambda *_a: "CNotDescriptor"
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_extract_enum_constants_from_tree",
        lambda *_a: {},
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="metadata"):
        headerdefs.load_header_metadata_defs()


def test_load_header_nimble_service_defs(monkeypatch):
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_load_nimble_prph_methods",
        lambda _r: {
            "cfgIdIOBindDis": [],
            "cfgIdIOBindBas": [],
            "cfgIdIOBindAios": [],
            "cfgIdIOBindEss": [],
            "cfgIdIOBindImds": [],
            "cfgIdIOBindOts": [],
        },
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_load_nimble_sensor_types",
        lambda _header, prefix, _cls: (
            [
                {"yaml_name": "temperature", "cpp_enum": "X::TEMP"},
                {"yaml_name": "wind_direction", "cpp_enum": "X::TWINDDIR"},
            ]
            if prefix == "PRPH_ESS_TYPE_"
            else [{"yaml_name": "temperature", "cpp_enum": "X::TEMP"}]
        ),
    )
    defs = headerdefs.load_header_nimble_service_defs()
    assert set(defs.keys()) == {"dis", "bas", "aios", "ess", "imds", "ots"}
    assert defs["dis"]["cpp_helper"] == "CProtoNimblePrph::cfgIdIOBindDis"
    assert defs["aios"]["header"] == "dawn/proto/nimble/prph_aios.hxx"
    ess_names = [item["yaml_name"] for item in defs["ess"]["sensor_types"]]
    assert "temperature" in ess_names
    assert "wind_direction" in ess_names
    imds_names = [item["yaml_name"] for item in defs["imds"]["sensor_types"]]
    assert "temperature" in imds_names
    assert "wind_direction" not in imds_names
    assert defs["ots"]["cpp_helper"] == "CProtoNimblePrph::cfgIdIOBindOts"
    assert defs["ots"]["header"] == "dawn/proto/nimble/prph_ots.hxx"
    assert defs["ots"]["object_types"]["file"] == 0
    assert defs["ots"]["object_access"]["rw"] == 2


def test_load_nimble_prph_methods_returns_empty(monkeypatch):
    child = ts_node("type_identifier", start_byte=0, end_byte=1)
    class_node = ts_node("class_specifier", children=[child])

    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_parse_cpp_header",
        lambda _h: (b"X", object()),
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_iter_ts_nodes", lambda _r: [class_node]
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_ts_text", lambda *_a: "CNotNimble"
    )
    assert headerdefs_nimble_mod._load_nimble_prph_methods(Path("/x")) == {}


def test_load_header_nimble_service_defs_raises_when_empty(monkeypatch):
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_load_nimble_prph_methods", lambda _r: {}
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Nimble"):
        headerdefs.load_header_nimble_service_defs()


def test_load_header_enum_map_unknown_owner_raises(monkeypatch):
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs_enums_mod.load_header_enum_map_from_defs(
            "CProtoNope", "X_", _empty_type_defs()
        )


def test_load_header_enum_map_missing_prefix_raises(monkeypatch):
    _stub_enum_header(monkeypatch)
    with pytest.raises(headerdefs.HeaderDefsError, match="No enum constants"):
        headerdefs_enums_mod.load_header_enum_map_from_defs(
            "CProtoCan", "CAN_TYPE_NOPE_", _enum_type_defs()
        )


def test_load_header_enum_value_ids_for_can_contains_aliases(monkeypatch):
    _stub_enum_header(
        monkeypatch,
        enum_constants={
            "CAN_TYPE_INDEXED_READ": 5,
            "CAN_TYPE_INDEXED_WRITE": 6,
        },
    )
    values = headerdefs_enums_mod.load_header_enum_value_ids_from_defs(
        "CProtoCan", "CAN_TYPE_", _enum_type_defs()
    )
    assert values
    assert values["read_indexed"] == values["indexed_read"]
    assert values["write_indexed"] == values["indexed_write"]


def test_load_header_enum_value_ids_unknown_owner_raises(monkeypatch):
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs_enums_mod.load_header_enum_value_ids_from_defs(
            "CProtoNope", "X_", _empty_type_defs()
        )


def test_load_header_enum_value_ids_missing_prefix_raises(monkeypatch):
    _stub_enum_header(monkeypatch)
    with pytest.raises(headerdefs.HeaderDefsError, match="No enum constants"):
        headerdefs_enums_mod.load_header_enum_value_ids_from_defs(
            "CProtoCan", "CAN_TYPE_NOPE_", _enum_type_defs()
        )


def test_load_header_cfg_id_success(monkeypatch):
    _stub_class_header(
        monkeypatch,
        cfg_enum="PROTO_CAN_CFG_NODEID",
        enum_constants={"PROTO_CAN_CFG_NODEID": 12},
    )
    val = headerdefs_enums_mod.load_header_cfg_id_from_defs(
        "CProtoCan", "cfgIdNodeid", _enum_type_defs()
    )
    assert val == 12


def test_load_header_cfg_id_unknown_owner_raises(monkeypatch):
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs_enums_mod.load_header_cfg_id_from_defs(
            "CProtoNope", "cfgIdNodeid", _empty_type_defs()
        )


def test_load_header_cfg_id_missing_method_raises(monkeypatch):
    _stub_class_header(monkeypatch)
    with pytest.raises(headerdefs.HeaderDefsError, match="cfg enum return"):
        headerdefs_enums_mod.load_header_cfg_id_from_defs(
            "CProtoCan", "cfgIdNope", _enum_type_defs()
        )


def test_extract_class_block_defensive_paths():
    assert (
        headerdefs_enums_mod._extract_class_block("class A {}", "Nope") is None
    )
    assert headerdefs_enums_mod._extract_class_block("class A", "A") is None
    assert headerdefs_enums_mod._extract_class_block("class A {", "A") is None


def test_extract_cfg_enum_from_method_text_direct_return():
    class_text = "class X { int cfg() { return IO_CFG_DEVNO; } };"
    assert (
        headerdefs_enums_mod._extract_cfg_enum_from_method_text(
            class_text, "cfg"
        )
        == "IO_CFG_DEVNO"
    )


def test_extract_cfg_enum_from_method_text_missing_body_returns_none(
    monkeypatch,
):
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_method_body_text",
        lambda _text, _method: None,
    )
    assert (
        headerdefs_enums_mod._extract_cfg_enum_from_method_text(
            "class X {}", "cfg"
        )
        is None
    )


def test_load_header_cfg_id_missing_class_block_raises(monkeypatch):
    _stub_class_header(monkeypatch, class_block=None)
    with pytest.raises(headerdefs.HeaderDefsError, match="class block"):
        headerdefs_enums_mod.load_header_cfg_id_from_defs(
            "CProtoCan", "cfgIdNodeid", _enum_type_defs()
        )


def test_load_header_cfg_id_missing_enum_constant_raises(monkeypatch):
    _stub_class_header(
        monkeypatch,
        cfg_enum="PROTO_CAN_CFG_NODEID",
        enum_constants={},
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="not found"):
        headerdefs_enums_mod.load_header_cfg_id_from_defs(
            "CProtoCan", "cfgIdNodeid", _enum_type_defs()
        )


def test_load_header_object_class_name_success(monkeypatch):
    _stub_class_header(
        monkeypatch,
        object_class_enum="PROTO_CLASS_CAN",
    )
    name = headerdefs_enums_mod.load_header_object_class_name_from_defs(
        "CProtoCan", "objectId", _enum_type_defs()
    )
    assert name == "can"


def test_load_header_object_class_name_missing_method_raises(monkeypatch):
    _stub_class_header(monkeypatch)
    with pytest.raises(headerdefs.HeaderDefsError, match="class enum return"):
        headerdefs_enums_mod.load_header_object_class_name_from_defs(
            "CProtoCan", "objectIdNope", _enum_type_defs()
        )


def test_load_header_object_class_name_bad_enum_token_raises(monkeypatch):
    _stub_class_header(
        monkeypatch,
        object_class_enum="BAD_CLASS_TOKEN",
    )
    with pytest.raises(
        headerdefs.HeaderDefsError, match="Unsupported class enum"
    ):
        headerdefs_enums_mod.load_header_object_class_name_from_defs(
            "CProtoCan", "objectId", _enum_type_defs()
        )


def test_extract_cfg_enum_from_method_text_direct_and_none():
    class_text_direct = "class X { int cfg() { return IO_CFG_DEVNO; } };"
    assert (
        headerdefs_enums_mod._extract_cfg_enum_from_method_text(
            class_text_direct, "cfg"
        )
        == "IO_CFG_DEVNO"
    )
    class_text_direct_non_cfg = (
        "class X { int cfg2() { return SOME_TOKEN; } };"
    )
    assert (
        headerdefs_enums_mod._extract_cfg_enum_from_method_text(
            class_text_direct_non_cfg, "cfg2"
        )
        == "SOME_TOKEN"
    )
    class_text_none = "class X { int cfg() { return something; } };"
    assert (
        headerdefs_enums_mod._extract_cfg_enum_from_method_text(
            class_text_none, "cfg"
        )
        is None
    )


def test_extract_object_class_enum_from_method_text_none_paths():
    class_text_no_helper = "class X { int objectId() { return 0; } };"
    assert (
        headerdefs_enums_mod._extract_object_class_enum_from_method_text(
            class_text_no_helper, "objectId"
        )
        is None
    )
    class_text_helper_missing_decl = (
        "class X { int objectId() { return ObjectIdHelper::create(1); } };"
    )
    assert (
        headerdefs_enums_mod._extract_object_class_enum_from_method_text(
            class_text_helper_missing_decl, "objectId"
        )
        is None
    )


def test_extract_object_class_enum_from_method_text_missing_body_returns_none(
    monkeypatch,
):
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_method_body_text",
        lambda _text, _method: None,
    )
    assert (
        headerdefs_enums_mod._extract_object_class_enum_from_method_text(
            "class X {}", "objectId"
        )
        is None
    )


def test_extract_method_body_text_defensive_paths():
    no_brace = "class X { int cfg() };"
    assert (
        headerdefs_enums_mod._extract_method_body_text(no_brace, "cfg") is None
    )
    has_semicolon_before_brace = "class X { int cfg() ; { return 1; } };"
    assert (
        headerdefs_enums_mod._extract_method_body_text(
            has_semicolon_before_brace, "cfg"
        )
        is None
    )


def test_cfg_id_fallback_headers_io_and_desc(tmp_path):
    io_headers = headerdefs_enums_mod._cfg_id_fallback_headers(
        tmp_path, "IO_CFG_DEVNO"
    )
    assert any(str(p).endswith("dawn/io/common.hxx") for p in io_headers)
    desc_headers = headerdefs_enums_mod._cfg_id_fallback_headers(
        tmp_path, "DESC_CFG_VERSION"
    )
    assert any(
        str(p).endswith("dawn/common/descriptor.hxx") for p in desc_headers
    )


def test_load_header_object_class_name_unknown_owner_raises(monkeypatch):
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs_enums_mod.load_header_object_class_name_from_defs(
            "CProtoNope", "objectId", _empty_type_defs()
        )


def test_load_header_object_class_name_no_class_block_raises(monkeypatch):
    _stub_class_header(monkeypatch, class_block=None)
    with pytest.raises(headerdefs.HeaderDefsError, match="class block"):
        headerdefs_enums_mod.load_header_object_class_name_from_defs(
            "CProtoCan", "objectId", _enum_type_defs()
        )


def test_repo_root_from_file_search_path(monkeypatch, tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo = tmp_path / "repo"
    target = repo / "dawn/include/dawn/common"
    target.mkdir(parents=True)
    (target / "objectid.hxx").write_text("// test", encoding="utf-8")
    fake_module = repo / "tools/dawnpy/src/dawnpy/headerdefs/_paths.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# test\n", encoding="utf-8")
    monkeypatch.setattr(headerdefs_paths_mod.Path, "cwd", lambda: cwd)
    monkeypatch.setattr(headerdefs_paths_mod, "__file__", str(fake_module))
    root = headerdefs_paths_mod._repo_root_from_here()
    assert root is not None
    assert (root / "dawn/include/dawn/common/objectid.hxx").exists()


def test_repo_root_from_cwd_search_path(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    target = root / "dawn/include/dawn/common"
    target.mkdir(parents=True)
    (target / "objectid.hxx").write_text("// test")
    monkeypatch.setattr(headerdefs_paths_mod.Path, "cwd", lambda: root)
    assert headerdefs_paths_mod._repo_root_from_here() == root


def test_repo_root_from_nested_layout(monkeypatch, tmp_path):
    wrapper = tmp_path / "wrapper"
    repo = wrapper / "dawn"
    target = repo / "dawn/include/dawn/common"
    target.mkdir(parents=True)
    (target / "objectid.hxx").write_text("// test")
    monkeypatch.setattr(headerdefs_paths_mod.Path, "cwd", lambda: wrapper)
    monkeypatch.setattr(
        headerdefs_paths_mod, "__file__", str(wrapper / "x.py")
    )
    assert headerdefs_paths_mod._repo_root_from_here() == repo


def test_repo_root_returns_none_when_all_search_paths_fail(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(headerdefs_paths_mod.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(
        headerdefs_paths_mod, "__file__", str(tmp_path / "x.py")
    )
    assert headerdefs_paths_mod._repo_root_from_here() is None


def test_find_repo_root_delegates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: tmp_path
    )
    assert headerdefs.find_repo_root() == tmp_path


def test_cpp_parser_raises_when_unavailable(monkeypatch):
    headerdefs_parser_mod._cpp_parser.cache_clear()
    monkeypatch.setattr(headerdefs_parser_mod, "tree_sitter", None)
    monkeypatch.setattr(headerdefs_parser_mod, "tree_sitter_cpp", None)
    with pytest.raises(headerdefs.HeaderDefsError, match="tree-sitter"):
        headerdefs_parser_mod._cpp_parser()


def test_iter_ts_nodes_preorder():
    class _Node:
        def __init__(self, children):
            self._children = children

        @property
        def children(self):
            return self._children

    leaf_a = _Node([])
    leaf_b = _Node([])
    root = _Node([leaf_a, leaf_b])
    out = headerdefs_parser_mod._iter_ts_nodes(root)
    assert out == [root, leaf_a, leaf_b]


def test_ts_text_extracts_source_slice():
    class _Node:
        start_byte = 1
        end_byte = 4

    assert headerdefs_parser_mod._ts_text(_Node(), b"0abc9") == "abc"


def test_parse_cpp_header_uses_parser(monkeypatch, tmp_path):
    hdr = tmp_path / "a.hxx"
    hdr.write_text("int x;")

    class _Tree:
        root_node = "ROOT"

    class _Parser:
        def parse(self, source):
            assert source == b"int x;"
            return _Tree()

    monkeypatch.setattr(
        headerdefs_parser_mod, "_cpp_parser", lambda: _Parser()
    )
    source, root = headerdefs_parser_mod._parse_cpp_header(hdr)
    assert source == b"int x;"
    assert root == "ROOT"


def test_parse_cpp_header_raises_on_error_node(monkeypatch, tmp_path):
    hdr = tmp_path / "a.hxx"
    hdr.write_text("int x;")

    class _ErrNode:
        def __init__(self):
            self.type = "ERROR"
            self.start_point = (2, 4)
            self.children = []

    class _Root:
        has_error = True
        children = [_ErrNode()]

    class _Tree:
        root_node = _Root()

    class _Parser:
        def parse(self, _source):
            return _Tree()

    monkeypatch.setattr(
        headerdefs_parser_mod, "_cpp_parser", lambda: _Parser()
    )
    with pytest.raises(headerdefs.HeaderDefsError, match=":3:5"):
        headerdefs_parser_mod._parse_cpp_header(hdr)


def test_parse_cpp_header_raises_on_error_without_error_node(
    monkeypatch, tmp_path
):
    hdr = tmp_path / "a.hxx"
    hdr.write_text("int x;")

    class _Root:
        has_error = True
        children = []

    class _Tree:
        root_node = _Root()

    class _Parser:
        def parse(self, _source):
            return _Tree()

    monkeypatch.setattr(
        headerdefs_parser_mod, "_cpp_parser", lambda: _Parser()
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Header parse error"):
        headerdefs_parser_mod._parse_cpp_header(hdr)


def test_parse_cpp_header_allows_nonfatal_error_with_extractable_nodes(
    monkeypatch, tmp_path
):
    hdr = tmp_path / "a.hxx"
    hdr.write_text("int x;")

    class _Node:
        def __init__(self, node_type):
            self.type = node_type
            self.start_point = (0, 0)
            self.children = []

    class _Root:
        has_error = True
        children = [_Node("field_declaration")]

    class _Tree:
        root_node = _Root()

    class _Parser:
        def parse(self, _source):
            return _Tree()

    monkeypatch.setattr(
        headerdefs_parser_mod, "_cpp_parser", lambda: _Parser()
    )
    source, root = headerdefs_parser_mod._parse_cpp_header(hdr)
    assert source == b"int x;"
    assert root is _Tree.root_node


def test_extract_constexpr_values_from_tree_paths():
    class _Node:
        def __init__(self, t, s, e, children=None):
            self.type = t
            self.start_byte = s
            self.end_byte = e
            self.children = children or []

    src = (
        b"constexpr static size_t A = 1;\n"
        b"constexpr static size_t BAD = MISSING;\n"
    )
    n1 = _Node(
        "field_declaration",
        0,
        30,
        [
            _Node("type_qualifier", 0, 9),
            _Node("storage_class_specifier", 10, 16),
            _Node("field_identifier", 24, 25),
            _Node("=", 26, 27),
            _Node("number_literal", 28, 29),
            _Node(";", 29, 30),
        ],
    )
    n2 = _Node(
        "field_declaration",
        31,
        len(src),
        [
            _Node("type_qualifier", 31, 40),
            _Node("storage_class_specifier", 41, 47),
            _Node("field_identifier", 55, 58),
            _Node("=", 59, 60),
            _Node("identifier", 61, 68),
            _Node(";", 68, 69),
        ],
    )
    n3 = _Node(
        "field_declaration",
        0,
        30,
        [
            _Node("type_qualifier", 0, 9),
            _Node("field_identifier", 24, 25),
            _Node("=", 26, 27),
            _Node("number_literal", 28, 29),
            _Node(";", 29, 30),
        ],
    )
    root = _Node("translation_unit", 0, len(src), [n1, n2, n3])
    out = headerdefs_parser_mod._extract_constexpr_values_from_tree(src, root)
    assert out == {"A": 1}


def test_rhs_expr_from_node_handles_multi_token_and_missing_equals():
    class _Node:
        def __init__(self, t, s, e, children=None):
            self.type = t
            self.start_byte = s
            self.end_byte = e
            self.children = children or []

    src = b"A = X + 1;"
    node = _Node(
        "field_declaration",
        0,
        len(src),
        [
            _Node("field_identifier", 0, 1),
            _Node("=", 2, 3),
            _Node("identifier", 4, 5),
            _Node("+", 6, 7),
            _Node("number_literal", 8, 9),
            _Node(";", 9, 10),
        ],
    )
    assert headerdefs_parser_mod._rhs_expr_from_node(node, src, ";") == "X + 1"

    missing_eq = _Node(
        "field_declaration",
        0,
        len(src),
        [
            _Node("field_identifier", 0, 1),
            _Node(";", 9, 10),
        ],
    )
    assert (
        headerdefs_parser_mod._rhs_expr_from_node(missing_eq, src, ";") == ""
    )

    empty_rhs = _Node(
        "field_declaration",
        0,
        len(src),
        [
            _Node("field_identifier", 0, 1),
            _Node("=", 2, 3),
            _Node(";", 3, 3),
        ],
    )
    assert headerdefs_parser_mod._rhs_expr_from_node(empty_rhs, src, ";") == ""


def test_extract_enum_constants_from_tree_paths():
    class _Node:
        def __init__(self, t, s, e, children=None):
            self.type = t
            self.start_byte = s
            self.end_byte = e
            self.children = children or []

    src = b"IO_A = 1, IO_B, OTHER = 2,"
    e1 = _Node(
        "enumerator",
        0,
        8,
        [
            _Node("identifier", 0, 4),
            _Node("=", 5, 6),
            _Node("number_literal", 7, 8),
        ],
    )
    e2 = _Node(
        "enumerator",
        10,
        14,
        [_Node("identifier", 10, 14)],
    )
    e3 = _Node(
        "enumerator",
        16,
        25,
        [
            _Node("identifier", 16, 21),
            _Node("=", 22, 23),
            _Node("number_literal", 24, 25),
        ],
    )
    e4 = _Node(
        "enumerator",
        0,
        1,
        [_Node("number_literal", 0, 1)],
    )
    e5 = _Node(
        "enumerator",
        0,
        8,
        [
            _Node("identifier", 0, 4),
            _Node("=", 5, 6),
            _Node("identifier", 7, 8),
        ],
    )
    root = _Node("translation_unit", 0, len(src), [e1, e2, e3, e4, e5])
    out = headerdefs_parser_mod._extract_enum_constants_from_tree(
        src, root, ("IO_",)
    )
    assert out["IO_A"] == 1
    assert out["IO_B"] == 2

    bad_src = b"IO_A = 1, IO_C = BAD,"
    b1 = _Node(
        "enumerator",
        0,
        8,
        [
            _Node("identifier", 0, 4),
            _Node("=", 5, 6),
            _Node("number_literal", 7, 8),
        ],
    )
    b2 = _Node(
        "enumerator",
        10,
        20,
        [
            _Node("identifier", 10, 14),
            _Node("=", 15, 16),
            _Node("identifier", 17, 20),
        ],
    )
    bad_root = _Node("translation_unit", 0, len(bad_src), [b1, b2])
    bad_out = headerdefs_parser_mod._extract_enum_constants_from_tree(
        bad_src, bad_root, ("IO_",)
    )
    assert bad_out["IO_C"] == 2


def test_build_class_map_skips_non_prefix_entries():
    out = headerdefs_constants_mod._build_class_map(
        {"OTHER_CLASS_X": 1}, prefix="IO_CLASS_"
    )
    assert out == {}


def test_require_symbol_map_keys_raises_on_missing():
    with pytest.raises(
        headerdefs.HeaderDefsError, match="Missing test symbols: B"
    ):
        headerdefs_constants_mod._require_symbol_map_keys(
            {"A": 1}, ["A", "B"], "test"
        )


def test_load_header_defs_raises_when_required_symbols_missing(monkeypatch):
    monkeypatch.setattr(
        headerdefs_loader_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_loader_mod,
        "_parse_cpp_header",
        lambda _path: (b"", object()),
    )
    monkeypatch.setattr(
        headerdefs_loader_mod,
        "_extract_constexpr_values_from_tree",
        lambda _src, _root: {},
    )
    monkeypatch.setattr(
        headerdefs_loader_mod,
        "_extract_enum_constants_from_tree",
        lambda _src, _root, _prefixes: {},
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Missing bit-field"):
        headerdefs.load_header_defs()


@pytest.mark.parametrize(
    "missing, match",
    [
        ("dtype", "Missing dtype symbols"),
        ("io", "Missing IO class symbols"),
        ("prog", "Missing Program class symbols"),
        ("proto", "Missing Protocol class symbols"),
    ],
)
def test_load_header_defs_raises_when_symbol_category_missing(
    monkeypatch, missing, match
):
    monkeypatch.setattr(
        headerdefs_loader_mod, "_require_repo_root", lambda: Path("/x")
    )
    constexprs = {
        "PRIV_SHIFT": 0,
        "PRIV_MAX": 1,
        "FLAGS_SHIFT": 0,
        "FLAGS_MAX": 1,
        "DTYPE_SHIFT": 0,
        "DTYPE_MAX": 1,
        "EXT_SHIFT": 0,
        "EXT_MAX": 1,
        "CLS_SHIFT": 0,
        "CLS_MAX": 1,
        "TYPE_SHIFT": 0,
        "TYPE_MAX": 1,
    }

    def _fake_enums(_src, _root, prefixes):
        if prefixes == ("OBJTYPE_", "DTYPE_"):
            base = {
                "OBJTYPE_ANY": 0,
                "OBJTYPE_IO": 1,
                "OBJTYPE_PROTO": 2,
                "OBJTYPE_PROG": 3,
            }
            if missing != "dtype":
                base["DTYPE_BOOL"] = 1
            return base
        if prefixes == ("IO_CLASS_",):
            return {} if missing == "io" else {"IO_CLASS_DUMMY": 1}
        if prefixes == ("PROG_CLASS_",):
            return {} if missing == "prog" else {"PROG_CLASS_DUMMY": 1}
        if prefixes == ("PROTO_CLASS_",):
            return {} if missing == "proto" else {"PROTO_CLASS_DUMMY": 1}
        return {}

    assert _fake_enums(b"", object(), ("OTHER_",)) == {}
    monkeypatch.setattr(
        headerdefs_loader_mod,
        "_load_header_symbol_sets",
        lambda _root: (
            constexprs,
            _fake_enums(b"", object(), ("OBJTYPE_", "DTYPE_")),
            _fake_enums(b"", object(), ("IO_CLASS_",)),
            _fake_enums(b"", object(), ("PROG_CLASS_",)),
            _fake_enums(b"", object(), ("PROTO_CLASS_",)),
        ),
    )
    with pytest.raises(headerdefs.HeaderDefsError, match=match):
        headerdefs.load_header_defs()


def test_normalize_preprocessed_cpp_rewrites_typedef_enum():
    text = "#line 1\nenum { A = 1 } typedef EA;\n"
    assert (
        headerdefs_parser_mod._normalize_preprocessed_cpp(text)
        == "enum { A = 1 } EA;"
    )


def test_yaml_type_from_cpp_class_aliases():
    assert (
        headerdefs_types_mod._yaml_type_from_cpp_class("io", "CIOFile")
        == "fileio"
    )
    assert (
        headerdefs_types_mod._yaml_type_from_cpp_class("io", "CIODescSelector")
        == "descselector"
    )
    assert (
        headerdefs_types_mod._yaml_type_from_cpp_class("prog", "CProgProcess")
        == "stats"
    )
    assert (
        headerdefs_types_mod._yaml_type_from_cpp_class(
            "proto", "CProtoShellPretty"
        )
        == "shell"
    )


def test_normalize_io_param_name_preserves_notify_name():
    assert (
        headerdefs_types_mod._normalize_io_param_name("ts", "gpi") == "notify"
    )
    assert (
        headerdefs_types_mod._normalize_io_param_name("ts", "gpo") == "notify"
    )
    assert (
        headerdefs_types_mod._normalize_io_param_name("ts", "virt") == "notify"
    )
    assert (
        headerdefs_types_mod._normalize_io_param_name("rw", "dummy")
        == "notify"
    )
    assert (
        headerdefs_types_mod._normalize_io_param_name("timestamp", "dummy")
        == "timestamp"
    )
    assert (
        headerdefs_types_mod._normalize_io_param_name("unknown", "dummy")
        is None
    )


def test_yaml_type_from_cpp_class_handles_nonprefixed_input():
    assert (
        headerdefs_types_mod._yaml_type_from_cpp_class("io", "CustomIoClass")
        == "custom_io_class"
    )


def test_collect_class_specs_skips_class_without_type_identifier(
    monkeypatch, tmp_path
):
    hdr = tmp_path / "dawn/include/dawn/io/test.hxx"
    hdr.parent.mkdir(parents=True)
    hdr.write_text("class X {};")

    class _Node:
        def __init__(self, node_type, children=None):
            self.type = node_type
            self.children = children or []

    root = _Node("translation_unit", [_Node("class_specifier", [])])
    monkeypatch.setattr(
        headerdefs_types_mod, "_parse_cpp_header", lambda _path: (b"", root)
    )
    out = headerdefs_types_mod._collect_class_specs(
        tmp_path, subdir="io", class_prefix="CIO"
    )
    assert out == []


def test_build_io_type_spec_handles_non_dict_methods():
    item = {
        "cpp_class": "CIOBoardctl",
        "header": "dawn/io/boardctl.hxx",
        "methods": [],
    }
    out = headerdefs_types_mod._build_io_type_spec(item)
    assert out["helper_func"] == "{cpp_class}::objectId{variant}"
    assert out["variants"] == []


def test_load_header_type_defs_raises_when_io_types_empty(monkeypatch):
    monkeypatch.setattr(
        headerdefs_types_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_types_mod,
        "_collect_class_specs",
        lambda *_args, **_kwargs: [],
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="No IO type"):
        headerdefs.load_header_type_defs()


def test_load_header_type_defs_raises_when_prog_types_empty(monkeypatch):
    monkeypatch.setattr(
        headerdefs_types_mod, "_require_repo_root", lambda: Path("/x")
    )

    def _fake_collect(_root, *, subdir, **_kwargs):
        if subdir == "io":
            return [
                {
                    "cpp_class": "CIODummy",
                    "header": "dawn/io/dummy.hxx",
                    "methods": {"objectId": ["dtype", "ts", "inst"]},
                }
            ]
        if subdir == "prog":
            return []
        return [
            {
                "cpp_class": "CProtoDummy",
                "header": "dawn/proto/dummy.hxx",
                "methods": {"objectId": ["id"]},
            }
        ]

    monkeypatch.setattr(
        headerdefs_types_mod, "_collect_class_specs", _fake_collect
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="No Program type"):
        headerdefs.load_header_type_defs()


def test_load_header_type_defs_raises_when_proto_types_empty(monkeypatch):
    monkeypatch.setattr(
        headerdefs_types_mod, "_require_repo_root", lambda: Path("/x")
    )

    def _fake_collect(_root, *, subdir, **_kwargs):
        if subdir == "io":
            return [
                {
                    "cpp_class": "CIODummy",
                    "header": "dawn/io/dummy.hxx",
                    "methods": {"objectId": ["dtype", "ts", "inst"]},
                }
            ]
        if subdir == "prog":
            return [
                {
                    "cpp_class": "CProgDummy",
                    "header": "dawn/prog/dummy.hxx",
                    "methods": {"objectId": ["inst"]},
                }
            ]
        return []

    monkeypatch.setattr(
        headerdefs_types_mod, "_collect_class_specs", _fake_collect
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="No Protocol type"):
        headerdefs.load_header_type_defs()


def test_load_header_defs_has_expected_shape(monkeypatch):
    monkeypatch.setattr(
        headerdefs_loader_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_loader_mod,
        "_load_header_symbol_sets",
        lambda _root: (
            {
                "PRIV_SHIFT": 0,
                "PRIV_MAX": 1,
                "FLAGS_SHIFT": 4,
                "FLAGS_MAX": 3,
                "DTYPE_SHIFT": 8,
                "DTYPE_MAX": 15,
                "EXT_SHIFT": 12,
                "EXT_MAX": 1,
                "CLS_SHIFT": 16,
                "CLS_MAX": 255,
                "TYPE_SHIFT": 30,
                "TYPE_MAX": 3,
            },
            {
                "OBJTYPE_ANY": 0,
                "OBJTYPE_IO": 1,
                "OBJTYPE_PROTO": 2,
                "OBJTYPE_PROG": 3,
                "DTYPE_UINT32": 8,
            },
            {"IO_CLASS_DUMMY": 1},
            {"PROG_CLASS_SAMPLING": 2},
            {"PROTO_CLASS_CAN": 3},
        ),
    )
    defs = headerdefs.load_header_defs()
    assert "bit_fields" in defs
    assert "object_types" in defs
    assert "dtype" in defs
    assert defs["bit_fields"]["type"]["shift"] == 30
    assert defs["object_types"][1] == "IO"
    assert defs["dtype"][0]["type"] == "uint32"


def test_load_header_defs_root_missing_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: None
    )
    with pytest.raises(DawnSourcesMissing):
        headerdefs.load_header_defs()


def test_load_header_type_defs_has_expected_keys(monkeypatch):
    monkeypatch.setattr(
        headerdefs_types_mod, "_require_repo_root", lambda: Path("/x")
    )

    def _fake_collect(
        _root: Path, *, subdir: str, **_kwargs: object
    ) -> list[dict[str, object]]:
        if subdir == "io":
            return [
                {
                    "cpp_class": "CIODummy",
                    "header": "dawn/io/dummy.hxx",
                    "methods": {"objectId": ["dtype", "instance"]},
                }
            ]
        if subdir == "prog":
            return [
                {
                    "cpp_class": "CProgSampling",
                    "header": "dawn/prog/sampling.hxx",
                    "methods": {},
                }
            ]
        return [
            {
                "cpp_class": "CProtoCan",
                "header": "dawn/proto/can.hxx",
                "methods": {"objectId": []},
            }
        ]

    monkeypatch.setattr(
        headerdefs_types_mod, "_collect_class_specs", _fake_collect
    )
    defs = headerdefs.load_header_type_defs()
    assert "io_types" in defs
    assert "prog_types" in defs
    assert "proto_types" in defs
    assert any(item["yaml_type"] == "dummy" for item in defs["io_types"])
    assert any(item["yaml_type"] == "sampling" for item in defs["prog_types"])
    assert any(item["yaml_type"] == "can" for item in defs["proto_types"])


def test_load_header_type_defs_root_missing_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: None
    )
    with pytest.raises(DawnSourcesMissing):
        headerdefs.load_header_type_defs()


def test_load_simple_proto_constants(monkeypatch):
    import dawnpy.headerdefs._simple_proto as headerdefs_simple_proto_mod

    monkeypatch.setattr(
        headerdefs_simple_proto_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_simple_proto_mod,
        "_parse_cpp_header",
        lambda _h: (b"constexpr", object()),
    )
    monkeypatch.setattr(
        headerdefs_simple_proto_mod,
        "_extract_enum_constants_from_tree",
        lambda *_a: {"CMD_PING": 1, "STATUS_OK": 0},
    )
    monkeypatch.setattr(
        headerdefs_simple_proto_mod,
        "_extract_constexpr_values_from_tree",
        lambda *_a: {"FRAME_SYNC": 170, "IGNORED": 9},
    )
    assert headerdefs_simple_proto_mod.load_simple_proto_constants() == {
        "FRAME_SYNC": 170,
        "CMD_PING": 1,
        "STATUS_OK": 0,
    }


def test_header_bundle_builds_dtype_map(monkeypatch):
    dtype_map = _definition_set(
        header_defs={"dtype": [{"type": "bool", "name": "DTYPE_BOOL"}]}
    ).dtype_map()
    assert dtype_map == {"bool": "SObjectId::DTYPE_BOOL"}


def test_header_bundle_builds_dtype_initval_param_map(monkeypatch):
    init_map = _definition_set(
        header_defs={
            "dtype": [
                "bad",
                {"type": "bool", "name": "DTYPE_BOOL", "initval_param": 1},
            ]
        }
    ).dtype_initval_param_map()
    assert init_map == {"bool": 1}


def test_header_bundle_keeps_compatibility_aliases():
    assert (
        header_bundle_mod.HeaderDefinitionSet is header_bundle_mod.HeaderBundle
    )
    assert (
        header_bundle_mod.load_header_definition_set
        is header_bundle_mod.load_header_bundle
    )


def test_header_bundle_enum_helpers_use_bundle_type_defs(monkeypatch):
    type_defs = {
        "io_types": [{"cpp_class": "CIODummy", "header": "dawn/io/dummy.hxx"}],
        "prog_types": [],
        "proto_types": [],
    }
    defs = header_bundle_mod.HeaderBundle(
        header_bundle_mod.HeaderDefinitionGroups(
            header_defs={"dtype": []},
            type_defs=type_defs,
            metadata_defs=[],
        )
    )
    seen: list[object] = []

    def _record_enum_map(
        owner: str, prefix: str, passed_defs: object
    ) -> dict[str, str]:
        seen.append((owner, prefix, passed_defs))
        return {"value": "VALUE"}

    monkeypatch.setattr(
        header_bundle_mod, "load_header_enum_map_from_defs", _record_enum_map
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_cfg_id_from_defs",
        lambda owner, method, passed_defs: seen.append(
            (owner, method, passed_defs)
        )
        or 7,
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_enum_value_ids_from_defs",
        lambda owner, prefix, passed_defs: seen.append(
            (owner, prefix, passed_defs)
        )
        or {"value": 9},
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_object_class_name_from_defs",
        lambda owner, method, passed_defs: seen.append(
            (owner, method, passed_defs)
        )
        or "dummy",
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_type_defs",
        lambda: (_ for _ in ()).throw(AssertionError("should not reload")),
    )

    assert defs.enum_map("CIODummy", "DUMMY_") == {"value": "VALUE"}
    assert defs.cfg_id("CIODummy", "cfgId") == 7
    assert defs.enum_value_ids("CIODummy", "DUMMY_") == {"value": 9}
    assert defs.object_class_name("CIODummy", "objectId") == "dummy"
    assert [item[2] for item in seen] == [type_defs] * 4


def test_header_enum_helpers_from_defs(monkeypatch):
    type_defs = {
        "io_types": [{"cpp_class": "CIODummy", "header": "dawn/io/dummy.hxx"}],
        "prog_types": [],
        "proto_types": [],
    }
    seen: list[object] = []

    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_load_header_enum_map",
        lambda owner, prefix, header: seen.append((owner, prefix, header))
        or {"value": "VALUE"},
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_load_header_cfg_id",
        lambda owner, method, header: seen.append((owner, method, header))
        or 7,
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_load_header_enum_value_ids",
        lambda owner, prefix, header: seen.append((owner, prefix, header))
        or {"value": 9},
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_load_header_object_class_name",
        lambda owner, method, header: seen.append((owner, method, header))
        or "dummy",
    )

    assert headerdefs_enums_mod.load_header_enum_map_from_defs(
        "CIODummy", "DUMMY_", type_defs
    ) == {"value": "VALUE"}
    assert (
        headerdefs_enums_mod.load_header_cfg_id_from_defs(
            "CIODummy", "cfgId", type_defs
        )
        == 7
    )
    assert headerdefs_enums_mod.load_header_enum_value_ids_from_defs(
        "CIODummy", "DUMMY_", type_defs
    ) == {"value": 9}
    assert (
        headerdefs_enums_mod.load_header_object_class_name_from_defs(
            "CIODummy", "objectId", type_defs
        )
        == "dummy"
    )
    assert [item[2] for item in seen] == ["dawn/io/dummy.hxx"] * 4


@pytest.mark.parametrize(
    ("loader", "args"),
    [
        (headerdefs_enums_mod.load_header_enum_map_from_defs, ("X_",)),
        (headerdefs_enums_mod.load_header_cfg_id_from_defs, ("cfgId",)),
        (
            headerdefs_enums_mod.load_header_enum_value_ids_from_defs,
            ("X_",),
        ),
        (
            headerdefs_enums_mod.load_header_object_class_name_from_defs,
            ("objectId",),
        ),
    ],
)
def test_header_enum_helpers_from_defs_unknown_owner(loader, args):
    empty_defs = {"io_types": [], "prog_types": [], "proto_types": []}
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        loader("CNope", *args, empty_defs)


def test_definition_set_loader_loads_all_header_groups(monkeypatch):
    header_bundle_mod.load_header_bundle.cache_clear()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_defs",
        lambda: {"dtype": [{"type": "bool", "name": "DTYPE_BOOL"}]},
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_type_defs",
        lambda: {"io_types": [], "prog_types": [], "proto_types": []},
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_metadata_defs",
        lambda: [{"name": "version"}],
    )
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_component_defs",
        lambda: {"ios": [{"name": "CIODummy"}]},
    )

    defs = header_bundle_mod.load_header_bundle()

    assert defs.dtype_map() == {"bool": "SObjectId::DTYPE_BOOL"}
    assert defs.metadata_defs == [{"name": "version"}]
    assert defs.component_defs == {"ios": [{"name": "CIODummy"}]}
    header_bundle_mod.load_header_bundle.cache_clear()


def test_header_bundle_raises_on_invalid_dtype_container(monkeypatch):
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header dtype definitions are invalid",
    ):
        _definition_set(header_defs={"dtype": {}}).dtype_map()


def test_header_bundle_raises_on_empty_dtype_entries(monkeypatch):
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No dtype definitions loaded"
    ):
        _definition_set(header_defs={"dtype": []}).dtype_map()


def test_header_bundle_dtype_map_skips_non_dict_entries(monkeypatch):
    dtype_map = _definition_set(
        header_defs={"dtype": ["bad", {"type": "bool", "name": "DTYPE_BOOL"}]}
    ).dtype_map()
    assert dtype_map["bool"] == "SObjectId::DTYPE_BOOL"


def test_header_bundle_initval_raises_on_invalid_dtype_container(monkeypatch):
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header dtype definitions are invalid",
    ):
        _definition_set(header_defs={"dtype": {}}).dtype_initval_param_map()


def _header_type_defs(defs):
    return _definition_set(type_defs=defs)


def test_builtin_types_loader_uses_header_type_defs(monkeypatch):
    patch_builtin_type_indexers(monkeypatch)
    defs = _header_type_defs(
        {
            "io_types": [
                {
                    "yaml_type": "x",
                    "cpp_class": "CX",
                    "header": "dawn/io/x.hxx",
                    "helper_func": "{cpp_class}::objectId",
                    "params": ["instance"],
                }
            ],
            "prog_types": [
                {
                    "yaml_type": "p",
                    "cpp_class": "CP",
                    "header": "dawn/prog/p.hxx",
                }
            ],
            "proto_types": [
                {
                    "yaml_type": "r",
                    "cpp_class": "CR",
                    "header": "dawn/proto/r.hxx",
                }
            ],
        },
    )
    assert "x" in builtin_io_mod.build_registration(defs).io_types
    assert "p" in builtin_prog_mod.build_registration(defs).prog_types
    assert "r" in builtin_proto_mod.build_registration(defs).proto_types


def test_builtin_types_loader_raises_on_invalid_type_containers(monkeypatch):
    patch_builtin_type_indexers(monkeypatch)
    defs = _header_type_defs(
        {"io_types": {}, "prog_types": {}, "proto_types": {}},
    )
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header IO type definitions are invalid",
    ):
        builtin_io_mod.build_registration(defs)
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header Program type definitions are invalid",
    ):
        builtin_prog_mod.build_registration(defs)
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header Protocol type definitions are invalid",
    ):
        builtin_proto_mod.build_registration(defs)


def test_builtin_types_loader_raises_when_header_type_defs_error(
    monkeypatch,
):
    def _boom():
        raise headerdefs.HeaderDefsError("x")

    patch_builtin_type_indexers(monkeypatch)
    monkeypatch.setattr(
        builtin_io_mod.header_bundle, "load_header_bundle", _boom
    )
    monkeypatch.setattr(
        builtin_prog_mod.header_bundle, "load_header_bundle", _boom
    )
    monkeypatch.setattr(
        builtin_proto_mod.header_bundle, "load_header_bundle", _boom
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_io_mod.build_registration()
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_prog_mod.build_registration()
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_proto_mod.build_registration()


def test_builtin_types_loader_skips_non_dict_type_entries(monkeypatch):
    patch_builtin_type_indexers(monkeypatch)
    defs = _header_type_defs(
        {
            "io_types": [
                "bad",
                {
                    "yaml_type": "x",
                    "cpp_class": "CX",
                    "header": "dawn/io/x.hxx",
                    "helper_func": "{cpp_class}::objectId",
                    "params": ["instance"],
                },
            ],
            "prog_types": [
                "bad",
                {
                    "yaml_type": "p",
                    "cpp_class": "CP",
                    "header": "dawn/prog/p.hxx",
                },
            ],
            "proto_types": [
                "bad",
                {
                    "yaml_type": "r",
                    "cpp_class": "CR",
                    "header": "dawn/proto/r.hxx",
                },
            ],
        },
    )
    assert "x" in builtin_io_mod.build_registration(defs).io_types
    assert "p" in builtin_prog_mod.build_registration(defs).prog_types
    assert "r" in builtin_proto_mod.build_registration(defs).proto_types


def test_builtin_types_loader_raises_on_empty_type_entries(monkeypatch):
    patch_builtin_type_indexers(monkeypatch)
    defs = _header_type_defs(
        {"io_types": [], "prog_types": [], "proto_types": []},
    )
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No IO type definitions loaded"
    ):
        builtin_io_mod.build_registration(defs)
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No Program type definitions loaded"
    ):
        builtin_prog_mod.build_registration(defs)
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No Protocol type definitions loaded"
    ):
        builtin_proto_mod.build_registration(defs)


def test_objectid_init_raises_when_headers_not_available(monkeypatch):
    monkeypatch.setattr(
        objectid_mod.ObjectIdDecoder, "_load_from_headers", lambda self: False
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Failed to load"):
        objectid_mod.ObjectIdDecoder()


def test_objectid_load_from_headers_bad_shapes_return_false(monkeypatch):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(
            header_defs={"bit_fields": {}, "object_types": {}, "dtype": {}}
        ),
    )
    assert decoder._load_from_headers() is False


@pytest.mark.parametrize(
    "payload",
    [
        {
            "bit_fields": [],
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": [],
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": [],
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": [],
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": [],
        },
    ],
)
def test_objectid_load_from_headers_shape_guards(monkeypatch, payload):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(header_defs=payload),
    )
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_handles_exception(monkeypatch):
    decoder = blank_objectid_decoder()

    def _boom():
        raise headerdefs.HeaderDefsError("x")

    monkeypatch.setattr(
        objectid_mod.header_bundle, "load_header_bundle", _boom
    )
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_success(monkeypatch):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(
            header_defs={
                "bit_fields": {
                    "type": {"shift": 30, "width": 2, "max": 3},
                    "cls": {"shift": 21, "width": 9, "max": 511},
                    "dtype": {"shift": 16, "width": 4, "max": 15},
                    "flags": {"shift": 14, "width": 2, "max": 3},
                    "priv": {"shift": 0, "width": 14, "max": 16383},
                    "ext": {"shift": 20, "width": 1, "max": 1},
                },
                "object_types": {1: "IO"},
                "dtype": [
                    "bad",
                    {"type": "ignored", "size": 0},
                    {"value": None, "type": "ignored2", "size": 0},
                    {"value": 1, "type": "bool", "size": 32},
                ],
                "io_classes": {5: "dummy"},
                "proto_classes": {17: "serial"},
                "prog_classes": {6: "sampling"},
            },
        ),
    )

    assert decoder._load_from_headers() is True
    assert decoder.TYPE_SHIFT == 30
    assert decoder.object_types[1] == "IO"
    assert decoder.dtype_info[1]["type"] == "bool"


def test_source_free_fixture_helpers_cover_error_paths():
    from tests import conftest as test_fixtures

    assert test_fixtures.minimal_object_class_name("CIODummy", "cfgId") == ""
    with pytest.raises(headerdefs.HeaderDefsError):
        test_fixtures.minimal_object_class_name("Nope", "objectId")
    with pytest.raises(pytest.fail.Exception):
        test_fixtures.blocked_repo_root_lookup()


def test_public_header_lookups_use_bundle(monkeypatch):
    defs = _definition_set(
        cfg_id_loader=lambda _owner, _method: 17,
        enum_map_loader=lambda _owner, _prefix: {"read": "READ"},
        enum_value_ids_loader=lambda _owner, _prefix: {"read": 3},
        object_class_name_loader=lambda _owner, _method: "can",
    )

    monkeypatch.setattr(header_bundle_mod, "load_header_bundle", lambda: defs)

    assert headerdefs.load_header_cfg_id("CProtoCan", "cfgIdNodeid") == 17
    assert headerdefs.load_header_enum_map("CProtoCan", "CAN_TYPE_") == {
        "read": "READ"
    }
    assert headerdefs.header_enum_map("CProtoCan", "CAN_TYPE_") == {
        "read": "READ"
    }
    assert headerdefs.load_header_enum_value_ids("CProtoCan", "CAN_TYPE_") == {
        "read": 3
    }
    assert (
        headerdefs.load_header_object_class_name("CProtoCan", "objectId")
        == "can"
    )


def test_headerdefs_remaining_branch_coverage(monkeypatch, tmp_path):
    skipped = ts_node("namespace_definition")
    type_child = ts_node("type_identifier")
    class_node = ts_node("class_specifier", children=[type_child])

    monkeypatch.setattr(headerdefs_components_mod, "_require_repo_root", Path)
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_parse_cpp_header",
        lambda _path: (b"CDescriptor", object()),
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_iter_ts_nodes",
        lambda _root: [skipped, class_node],
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_ts_text",
        lambda *_args: "CDescriptor",
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_extract_methods_with_prefixes",
        lambda *_args: {"cfgIdVersion": []},
    )
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_extract_enum_constants_from_tree",
        lambda *_args: {"DESC_CFG_VERSION": 1},
    )
    assert headerdefs.load_header_metadata_defs()[0]["name"] == "version"

    specs = [
        {
            "cpp_class": "CIODummy",
            "header": "dawn/io/dummy.hxx",
            "yaml_type": "dummy",
        }
    ]
    monkeypatch.setattr(
        headerdefs_components_mod,
        "_collect_class_specs",
        lambda *args, **kwargs: specs if kwargs["subdir"] == "io" else [],
    )
    assert (
        headerdefs.load_header_component_defs()["ios"][0]["name"] == "CIODummy"
    )
    assert headerdefs_constants_mod._build_class_map(
        {
            "IO_CLASS_ANY": 0,
            "IO_CLASS_USER_THING": 1,
            "IO_CLASS_LAST": 2,
            "IO_CLASS_DUMMY": 3,
        },
        prefix="IO_CLASS_",
    ) == {3: "dummy"}

    assert (
        headerdefs_enums_mod._enum_key_from_suffix("Other", "VALUE") == "value"
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "load_header_type_defs",
        lambda: {
            "io_types": [
                {"cpp_class": "CIODummy", "header": "dawn/io/dummy.hxx"}
            ],
            "prog_types": [],
            "proto_types": [
                {"cpp_class": "CProtoCan", "header": "dawn/proto/can/can.hxx"}
            ],
        },
    )
    assert (
        headerdefs_enums_mod._enum_header_for_owner("CProtoCan")
        == "dawn/proto/can/can.hxx"
    )
    assert (
        headerdefs_enums_mod._enum_header_for_owner("CIOCommon")
        == "dawn/io/common.hxx"
    )
    assert headerdefs_enums_mod._enum_header_for_owner("Nope") is None
    assert (
        headerdefs_enums_mod._extract_class_block(
            "class CProtoCan { int nested() { return 1; } };", "CProtoCan"
        )
        is not None
    )
    assert (
        headerdefs_enums_mod._extract_object_class_enum_from_method_text(
            "class C { int objectId() { return IO_CLASS_DUMMY; } };",
            "objectId",
        )
        == "IO_CLASS_DUMMY"
    )
    assert (
        headerdefs_enums_mod._extract_method_body_text(
            "// objectId() {}\nobjectId() { return X; }", "objectId"
        ).strip()
        == "return X;"
    )
    assert tmp_path / "dawn/include/dawn/prog/process.hxx" in (
        headerdefs_enums_mod._cfg_id_fallback_headers(tmp_path, "PROG_CFG_X")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _path: (b"", object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_enum_constants_from_tree",
        lambda *_args: {"DIRECT_ENUM": 9},
    )
    assert (
        headerdefs_enums_mod._lookup_enum_value_in_headers(
            "DIRECT_ENUM", [tmp_path / "x.hxx"]
        )
        == 9
    )

    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _path: (
            b"class CProtoCan { int cfg() { return PROTO_CFG_X; } };",
            object(),
        ),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_enum_constants_from_tree",
        lambda *_args: {
            "CAN_TYPE_INDEXED_READ": 4,
            "CAN_TYPE_INDEXED_WRITE": 5,
        },
    )
    values = headerdefs_enums_mod._load_header_enum_map(
        "CProtoCan", "CAN_TYPE_", "dawn/proto/can/can.hxx"
    )
    assert values["indexed_read"] == "INDEXED_READ"

    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_class_block",
        lambda *_args: "class CProtoCan {}",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_cfg_enum_from_method_text",
        lambda *_args: "PROG_CFG_X",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_enum_constants_from_tree",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_lookup_enum_value_in_headers",
        lambda enum_name, _headers: 7 if enum_name == "PROG_CFG_X" else None,
    )
    assert (
        headerdefs_enums_mod._load_header_cfg_id(
            "CProtoCan", "cfg", "dawn/proto/can/can.hxx"
        )
        == 7
    )

    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_object_class_enum_from_method_text",
        lambda *_args: "PROG_CLASS_STATS_MIN",
    )
    assert (
        headerdefs_enums_mod._load_header_object_class_name(
            "CProtoCan", "objectId", "dawn/proto/can/can.hxx"
        )
        == "stat_min"
    )

    assert (
        headerdefs_nimble_mod._nimble_sensor_yaml_name("TEMP") == "temperature"
    )
    assert headerdefs_nimble_mod._nimble_sensor_yaml_name("CUSTOM") == "custom"
    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_parse_cpp_header",
        lambda _path: (b"", object()),
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_extract_enum_constants_from_tree",
        lambda *_args: {
            "PRPH_ESS_TYPE_TEMP": 1,
            "PRPH_ESS_TYPE_HUM": 2,
        },
    )
    assert (
        headerdefs_nimble_mod._load_nimble_sensor_types(
            tmp_path / "x.hxx", "PRPH_ESS_TYPE_", "CProtoNimblePrphEss"
        )[0]["yaml_name"]
        == "temperature"
    )

    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_iter_ts_nodes",
        lambda _root: [skipped, class_node],
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod, "_ts_text", lambda *_args: "CProtoNimblePrph"
    )
    monkeypatch.setattr(
        headerdefs_nimble_mod,
        "_extract_methods_with_prefixes",
        lambda *_args: {"cfgIdIOBindBas": []},
    )
    assert headerdefs_nimble_mod._load_nimble_prph_methods(tmp_path) == {
        "cfgIdIOBindBas": []
    }

    bad_field = ts_node("field_declaration")
    monkeypatch.setattr(
        headerdefs_parser_mod,
        "_iter_ts_nodes",
        lambda _root: [bad_field],
    )
    monkeypatch.setattr(
        headerdefs_parser_mod,
        "_is_constexpr_static_field",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        headerdefs_parser_mod,
        "_field_name_and_expr",
        lambda *_args: ("bad-name", "1"),
    )
    assert (
        headerdefs_parser_mod._extract_constexpr_values_from_tree(
            b"", object()
        )
        == {}
    )

    bad_enum = ts_node("enumerator")
    monkeypatch.setattr(
        headerdefs_parser_mod,
        "_iter_ts_nodes",
        lambda _root: [bad_enum],
    )
    monkeypatch.setattr(
        headerdefs_parser_mod,
        "_enumerator_name_and_expr",
        lambda *_args: ("TEST_A", ""),
    )
    assert headerdefs_parser_mod._extract_enum_constants_from_tree(
        b"", object(), ("TEST_",)
    ) == {"TEST_A": 0}


def test_header_type_defs_parse_fake_headers(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    include = root / "dawn/include/dawn"
    (include / "io").mkdir(parents=True)
    (include / "prog").mkdir()
    (include / "proto/can").mkdir(parents=True)
    (include / "io/.#ignored.hxx").write_text("bad", encoding="utf-8")
    (include / "io/dummy.hxx").write_text(
        "class CIODummy { public: static int objectId(int dtype, int id)"
        " { return 0; } };",
        encoding="utf-8",
    )
    (include / "io/dac.hxx").write_text(
        "class CIODac { public: static int objectId(int ts, int id)"
        " { return 0; } };",
        encoding="utf-8",
    )
    (include / "io/sensor.hxx").write_text(
        "class CIOSensor { public:"
        " static int objectIdTemp(int dtype, int ts, int id) { return 0; }"
        " static int objectIdHum(int dtype, int ts, int id) { return 0; }"
        " };",
        encoding="utf-8",
    )
    (include / "io/sysinfo.hxx").write_text(
        "class CIOSysinfo { public: static int objectIdUptime()"
        " { return 0; } };",
        encoding="utf-8",
    )
    (include / "io/unused.hxx").write_text(
        "class Other { public: static int objectId() { return 0; } };"
        " class CIOEmpty {};",
        encoding="utf-8",
    )
    (include / "prog/sampling.hxx").write_text(
        "class CProgCommon {}; class CProgSampling {};",
        encoding="utf-8",
    )
    (include / "proto/can/can.hxx").write_text(
        "class CProtoCan { public: static int objectId() { return 0; } };",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        headerdefs_types_mod, "_require_repo_root", lambda: root
    )
    defs = headerdefs.load_header_type_defs()

    io_by_type = {item["yaml_type"]: item for item in defs["io_types"]}
    assert io_by_type["dummy"]["params"] == ["dtype", "instance"]
    assert io_by_type["dac"]["params"] == ["dtype", "timestamp", "instance"]
    assert io_by_type["sensor"]["subtypes"] == ["hum", "temp"]
    assert io_by_type["sysinfo"]["variants"][0]["name"] == "uptime"
    assert any(item["yaml_type"] == "sampling" for item in defs["prog_types"])
    assert any(item["yaml_type"] == "can" for item in defs["proto_types"])
    assert (
        headerdefs_types_mod._build_prog_type_spec(
            {"cpp_class": "CProgCommon", "header": "dawn/prog/common.hxx"}
        )
        == {}
    )


def test_remaining_standalone_coverage_branches(monkeypatch):
    node = ts_node("field_declaration")
    assert (
        headerdefs_types_mod._parse_function_name_and_params(node, b"") is None
    )
    nameless_declarator = ts_node("function_declarator")
    nameless_field = ts_node(
        "field_declaration", children=[nameless_declarator]
    )
    assert (
        headerdefs_types_mod._parse_function_name_and_params(
            nameless_field, b""
        )
        is None
    )
    assert (
        headerdefs_types_mod._extract_methods_with_prefixes(
            nameless_field, b"", ("objectId",)
        )
        == {}
    )
    assert headerdefs_parser_mod._is_constexpr_static_field(node, b"") is False
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: None
    )
    with pytest.raises(DawnSourcesMissing):
        headerdefs_paths_mod._require_repo_root()
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: Path("/x")
    )
    assert headerdefs_paths_mod._require_repo_root() == Path("/x")
