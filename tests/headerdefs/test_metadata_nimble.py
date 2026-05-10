# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
