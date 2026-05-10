# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
