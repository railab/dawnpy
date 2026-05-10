# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
