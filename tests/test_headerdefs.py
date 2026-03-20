# tools/dawnpy/tests/test_headerdefs.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for runtime C++ header definition loading."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import dawnpy.descriptor.definitions.io_family as builtin_io_mod
import dawnpy.descriptor.definitions.prog_family as builtin_prog_mod
import dawnpy.descriptor.definitions.proto_family as builtin_proto_mod
import dawnpy.descriptor.definitions.registry as types_mod
import dawnpy.headerdefs as headerdefs
import dawnpy.headerdefs._components as headerdefs_components_mod
import dawnpy.headerdefs._constants as headerdefs_constants_mod
import dawnpy.headerdefs._enums as headerdefs_enums_mod
import dawnpy.headerdefs._loader as headerdefs_loader_mod
import dawnpy.headerdefs._nimble as headerdefs_nimble_mod
import dawnpy.headerdefs._parser as headerdefs_parser_mod
import dawnpy.headerdefs._paths as headerdefs_paths_mod
import dawnpy.headerdefs._typespec as headerdefs_types_mod
import dawnpy.objectid as objectid_mod


@pytest.fixture(autouse=True)
def clear_header_caches():
    """Ensure header loader caches are cleared per test."""
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()
    yield
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()


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


def test_load_header_metadata_defs():
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
    child = SimpleNamespace(
        **{
            "type": "type_identifier",
            "start_byte": 0,
            "end_byte": 1,
            "children": [],
        }
    )
    class_node = SimpleNamespace(type="class_specifier", children=[child])

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


def test_load_header_nimble_service_defs():
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
    child = SimpleNamespace(
        **{
            "type": "type_identifier",
            "start_byte": 0,
            "end_byte": 1,
            "children": [],
        }
    )
    class_node = SimpleNamespace(type="class_specifier", children=[child])

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


def test_load_header_enum_map_unknown_owner_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs.load_header_enum_map("CProtoNope", "X_")


def test_load_header_enum_map_missing_prefix_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="No enum constants"):
        headerdefs.load_header_enum_map("CProtoCan", "CAN_TYPE_NOPE_")


def test_load_header_enum_value_ids_for_can_contains_aliases():
    values = headerdefs.load_header_enum_value_ids("CProtoCan", "CAN_TYPE_")
    assert values
    assert values["read_indexed"] == values["indexed_read"]
    assert values["write_indexed"] == values["indexed_write"]


def test_load_header_enum_value_ids_unknown_owner_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs.load_header_enum_value_ids("CProtoNope", "X_")


def test_load_header_enum_value_ids_missing_prefix_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="No enum constants"):
        headerdefs.load_header_enum_value_ids("CProtoCan", "CAN_TYPE_NOPE_")


def test_load_header_cfg_id_success():
    val = headerdefs.load_header_cfg_id("CProtoCan", "cfgIdNodeid")
    assert int(val) >= 0


def test_load_header_cfg_id_unknown_owner_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs.load_header_cfg_id("CProtoNope", "cfgIdNodeid")


def test_load_header_cfg_id_missing_method_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="cfg enum return"):
        headerdefs.load_header_cfg_id("CProtoCan", "cfgIdNope")


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


def test_load_header_cfg_id_missing_class_block_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_enums_mod, "_enum_header_for_owner", lambda _o: "x.hxx"
    )
    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _h: (b"class A{}", object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod, "_extract_class_block", lambda text, owner: None
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="class block"):
        headerdefs.load_header_cfg_id("CProtoCan", "cfgIdNodeid")


def test_load_header_cfg_id_missing_enum_constant_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_enums_mod, "_enum_header_for_owner", lambda _o: "x.hxx"
    )
    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _h: (b"class A{}", object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_class_block",
        lambda text, owner: "class A{}",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_cfg_enum_from_method_text",
        lambda class_text, method_name: "PROTO_CAN_CFG_NODEID",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_enum_constants_from_tree",
        lambda *_a: {},
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="not found"):
        headerdefs.load_header_cfg_id("CProtoCan", "cfgIdNodeid")


def test_load_header_object_class_name_success():
    name = headerdefs.load_header_object_class_name("CProtoCan", "objectId")
    assert name == "can"


def test_load_header_object_class_name_missing_method_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="class enum return"):
        headerdefs.load_header_object_class_name("CProtoCan", "objectIdNope")


def test_load_header_object_class_name_bad_enum_token_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_enums_mod, "_enum_header_for_owner", lambda _owner: "x.hxx"
    )
    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _h: (b"class A{}", object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_class_block",
        lambda _text, _owner: "class A{}",
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_object_class_enum_from_method_text",
        lambda _text, _method: "BAD_CLASS_TOKEN",
    )
    with pytest.raises(
        headerdefs.HeaderDefsError, match="Unsupported class enum"
    ):
        headerdefs.load_header_object_class_name("CProtoCan", "objectId")


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


def test_load_header_object_class_name_unknown_owner_raises():
    with pytest.raises(headerdefs.HeaderDefsError, match="enum owner"):
        headerdefs.load_header_object_class_name("CProtoNope", "objectId")


def test_load_header_object_class_name_no_class_block_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_enums_mod, "_enum_header_for_owner", lambda _owner: "x.hxx"
    )
    monkeypatch.setattr(
        headerdefs_enums_mod, "_require_repo_root", lambda: Path("/x")
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_parse_cpp_header",
        lambda _h: (b"class A{}", object()),
    )
    monkeypatch.setattr(
        headerdefs_enums_mod,
        "_extract_class_block",
        lambda _text, _owner: None,
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="class block"):
        headerdefs.load_header_object_class_name("CProtoCan", "objectId")


def test_repo_root_from_file_search_path(monkeypatch, tmp_path):
    monkeypatch.setattr(headerdefs_paths_mod.Path, "cwd", lambda: tmp_path)
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


def test_load_header_defs_has_expected_shape():
    defs = headerdefs.load_header_defs()
    assert "bit_fields" in defs
    assert "object_types" in defs
    assert "dtype" in defs
    assert defs["bit_fields"]["type"]["shift"] == 30
    assert defs["object_types"][1] == "IO"


def test_load_header_defs_root_missing_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: None
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Could not locate"):
        headerdefs.load_header_defs()


def test_load_header_type_defs_has_expected_keys():
    defs = headerdefs.load_header_type_defs()
    assert "io_types" in defs
    assert "prog_types" in defs
    assert "proto_types" in defs
    assert any(item["yaml_type"] == "dummy" for item in defs["io_types"])


def test_load_header_type_defs_root_missing_raises(monkeypatch):
    monkeypatch.setattr(
        headerdefs_paths_mod, "_repo_root_from_here", lambda: None
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Could not locate"):
        headerdefs.load_header_type_defs()


def test_types_loader_prefers_header_defs(monkeypatch):
    monkeypatch.setattr(
        types_mod,
        "load_header_defs",
        lambda: {"dtype": [{"type": "bool", "name": "DTYPE_BOOL"}]},
    )
    dtype_map = types_mod._load_dtype_map()
    assert dtype_map == {"bool": "SObjectId::DTYPE_BOOL"}


def test_types_loader_raises_on_invalid_dtype_container(monkeypatch):
    monkeypatch.setattr(types_mod, "load_header_defs", lambda: {"dtype": {}})
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header dtype definitions are invalid",
    ):
        types_mod._load_dtype_map()


def test_types_loader_raises_on_empty_dtype_entries(monkeypatch):
    monkeypatch.setattr(types_mod, "load_header_defs", lambda: {"dtype": []})
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No dtype definitions loaded"
    ):
        types_mod._load_dtype_map()


def test_types_loader_raises_when_header_defs_error(monkeypatch):
    def _boom():
        raise headerdefs.HeaderDefsError("x")

    monkeypatch.setattr(types_mod, "load_header_defs", _boom)
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        types_mod._load_dtype_map()


def test_types_loader_dtype_map_skips_non_dict_entries(monkeypatch):
    monkeypatch.setattr(
        types_mod,
        "load_header_defs",
        lambda: {"dtype": ["bad", {"type": "bool", "name": "DTYPE_BOOL"}]},
    )
    dtype_map = types_mod._load_dtype_map()
    assert dtype_map["bool"] == "SObjectId::DTYPE_BOOL"


def test_types_loader_initval_raises_when_header_defs_error(monkeypatch):
    def _boom():
        raise headerdefs.HeaderDefsError("x")

    monkeypatch.setattr(types_mod, "load_header_defs", _boom)
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        types_mod._load_dtype_initval_param_map()


def test_types_loader_initval_skips_non_dict_entries(monkeypatch):
    monkeypatch.setattr(
        types_mod,
        "load_header_defs",
        lambda: {
            "dtype": [
                "bad",
                {"type": "bool", "name": "DTYPE_BOOL", "initval_param": 1},
            ]
        },
    )
    init_map = types_mod._load_dtype_initval_param_map()
    assert init_map["bool"] == 1


def test_types_loader_initval_raises_on_invalid_dtype_container(monkeypatch):
    monkeypatch.setattr(types_mod, "load_header_defs", lambda: {"dtype": {}})
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header dtype definitions are invalid",
    ):
        types_mod._load_dtype_initval_param_map()


def _patch_header_type_defs(monkeypatch, defs):
    """Stub load_header_type_defs across all builtin_types modules."""
    monkeypatch.setattr(builtin_io_mod, "load_header_type_defs", lambda: defs)
    monkeypatch.setattr(
        builtin_prog_mod, "load_header_type_defs", lambda: defs
    )
    monkeypatch.setattr(
        builtin_proto_mod, "load_header_type_defs", lambda: defs
    )


def _patch_indexers(monkeypatch):
    """Stub fields-YAML indexers so builders only see headerdefs data."""
    monkeypatch.setattr(builtin_io_mod, "_index_fields_by_type", dict)
    monkeypatch.setattr(builtin_prog_mod, "_index_fields_by_type", dict)
    monkeypatch.setattr(builtin_proto_mod, "_index_proto_entries", dict)


def test_builtin_types_loader_uses_header_type_defs(monkeypatch):
    _patch_indexers(monkeypatch)
    _patch_header_type_defs(
        monkeypatch,
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
    assert "x" in builtin_io_mod.build_registration().io_types
    assert "p" in builtin_prog_mod.build_registration().prog_types
    assert "r" in builtin_proto_mod.build_registration().proto_types


def test_builtin_types_loader_raises_on_invalid_type_containers(monkeypatch):
    _patch_indexers(monkeypatch)
    _patch_header_type_defs(
        monkeypatch,
        {"io_types": {}, "prog_types": {}, "proto_types": {}},
    )
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header IO type definitions are invalid",
    ):
        builtin_io_mod.build_registration()
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header Program type definitions are invalid",
    ):
        builtin_prog_mod.build_registration()
    with pytest.raises(
        headerdefs.HeaderDefsError,
        match="Header Protocol type definitions are invalid",
    ):
        builtin_proto_mod.build_registration()


def test_builtin_types_loader_raises_when_header_type_defs_error(
    monkeypatch,
):
    def _boom():
        raise headerdefs.HeaderDefsError("x")

    _patch_indexers(monkeypatch)
    monkeypatch.setattr(builtin_io_mod, "load_header_type_defs", _boom)
    monkeypatch.setattr(builtin_prog_mod, "load_header_type_defs", _boom)
    monkeypatch.setattr(builtin_proto_mod, "load_header_type_defs", _boom)
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_io_mod.build_registration()
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_prog_mod.build_registration()
    with pytest.raises(headerdefs.HeaderDefsError, match="x"):
        builtin_proto_mod.build_registration()


def test_builtin_types_loader_skips_non_dict_type_entries(monkeypatch):
    _patch_indexers(monkeypatch)
    _patch_header_type_defs(
        monkeypatch,
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
    assert "x" in builtin_io_mod.build_registration().io_types
    assert "p" in builtin_prog_mod.build_registration().prog_types
    assert "r" in builtin_proto_mod.build_registration().proto_types


def test_builtin_types_loader_raises_on_empty_type_entries(monkeypatch):
    _patch_indexers(monkeypatch)
    _patch_header_type_defs(
        monkeypatch,
        {"io_types": [], "prog_types": [], "proto_types": []},
    )
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No IO type definitions loaded"
    ):
        builtin_io_mod.build_registration()
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No Program type definitions loaded"
    ):
        builtin_prog_mod.build_registration()
    with pytest.raises(
        headerdefs.HeaderDefsError, match="No Protocol type definitions loaded"
    ):
        builtin_proto_mod.build_registration()


def test_objectid_init_raises_when_headers_not_available(monkeypatch):
    monkeypatch.setattr(
        objectid_mod.ObjectIdDecoder, "_load_from_headers", lambda self: False
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Failed to load"):
        objectid_mod.ObjectIdDecoder()


def test_objectid_load_from_headers_bad_shapes_return_false(monkeypatch):
    decoder = objectid_mod.ObjectIdDecoder()
    monkeypatch.setattr(
        objectid_mod,
        "load_header_defs",
        lambda: {"bit_fields": {}, "object_types": {}, "dtype": {}},
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
    decoder = objectid_mod.ObjectIdDecoder()
    monkeypatch.setattr(objectid_mod, "load_header_defs", lambda: payload)
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_handles_exception(monkeypatch):
    decoder = objectid_mod.ObjectIdDecoder()

    def _boom():
        raise headerdefs.HeaderDefsError("x")

    monkeypatch.setattr(objectid_mod, "load_header_defs", _boom)
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_success(monkeypatch):
    decoder = objectid_mod.ObjectIdDecoder()
    monkeypatch.setattr(
        objectid_mod,
        "load_header_defs",
        lambda: {
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
    )

    assert decoder._load_from_headers() is True
    assert decoder.TYPE_SHIFT == 30
    assert decoder.object_types[1] == "IO"
    assert decoder.dtype_info[1]["type"] == "bool"
