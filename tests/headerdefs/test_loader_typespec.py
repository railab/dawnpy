# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
