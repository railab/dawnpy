# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


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
