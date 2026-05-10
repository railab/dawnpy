# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
