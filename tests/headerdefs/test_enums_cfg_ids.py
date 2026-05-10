# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
