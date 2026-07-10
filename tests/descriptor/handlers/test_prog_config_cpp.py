# tools/dawnpy/tests/descriptor/handlers/test_prog_config_cpp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the shared program config-field C++ emitters."""

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers._prog_config_cpp import (
    emit_config_fields_cpp,
    emit_generic_config_field,
)

from .helpers import prog_cpp_ctx

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _obj(**kw) -> ProgramObject:
    base = dict(
        obj_id="p1",
        prog_type="stats",
        instance=0,
        inputs=[],
        outputs=[],
        reset=None,
        config={},
    )
    base.update(kw)
    return ProgramObject(**base)


def _field(value_type: str, name: str = "f", cpp_helper: str = "H", **kw):
    return ConfigField(
        name=name, cpp_helper=cpp_helper, value_type=value_type, **kw
    )


class TestGenericEmitters:

    def test_id_array_pairs(self):
        obj = _obj(inputs=["io1"], outputs=["io2"])
        lines: list[str] = []
        handled = emit_generic_config_field(
            lines,
            _field("id_array_pairs", cpp_helper="CProgStatsMin::cfgIdIOBind"),
            obj,
            {"sources": ["io1"], "outputs": ["io2"]},
            prog_cpp_ctx(),
        )
        assert handled is True
        assert lines == [
            "    CProgStatsMin::cfgIdIOBind(2),",
            "      IO1,",
            "      IO2,",
        ]

    def test_id_array_pairs_interleaves_multiple_binds(self):
        obj = _obj(inputs=["io1", "io2"], outputs=["out1", "out2"])
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_array_pairs", cpp_helper="CProgStatsMin::cfgIdIOBind"),
            obj,
            {"sources": ["io1", "io2"], "outputs": ["out1", "out2"]},
            prog_cpp_ctx(),
        )
        assert lines == [
            "    CProgStatsMin::cfgIdIOBind(4),",
            "      IO1,",
            "      OUT1,",
            "      IO2,",
            "      OUT2,",
        ]

    def test_id_array_pairs_mismatch_raises(self):
        obj = _obj(inputs=["io1"], outputs=["io2"])
        with pytest.raises(ValueError, match="sources"):
            emit_generic_config_field(
                [],
                _field("id_array_pairs", cpp_helper="H"),
                obj,
                {"sources": ["io1", "io2"], "outputs": ["io2"]},
                prog_cpp_ctx(),
            )

    def test_uint32(self):
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field(
                "uint32",
                name="interval",
                cpp_helper="CProgSampling::cfgIdIOInterval",
            ),
            _obj(),
            {"interval": 50000},
            prog_cpp_ctx(),
        )
        assert lines == [
            "    CProgSampling::cfgIdIOInterval(),",
            "      50000,",
        ]

    def test_uint32_uses_field_default(self):
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field(
                "uint32",
                name="chunk_size",
                cpp_helper="CProgBuffer::cfgIdChunkSize",
                default="1",
            ),
            _obj(),
            {},
            prog_cpp_ctx(),
        )
        assert lines == [
            "    CProgBuffer::cfgIdChunkSize(),",
            "      1,",
        ]

    def test_uint32_list(self):
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("uint32_list", name="vals", cpp_helper="H"),
            _obj(),
            {"vals": [1, 2, 3]},
            prog_cpp_ctx(),
        )
        assert lines == ["    H(3),", "      1,", "      2,", "      3,"]

    def test_id_array(self):
        obj = _obj(inputs=["io1", "io2"])
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field(
                "id_array", name="inputs", cpp_helper="CProgCommon::cfgIdInput"
            ),
            obj,
            {},
            prog_cpp_ctx(),
        )
        assert lines == [
            "    CProgCommon::cfgIdInput(),",
            "      IO1,",
            "      IO2,",
        ]

    def test_id_single_with_and_without_id(self):
        helper = "CProgCommon::cfgIdReset"
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_single", name="reset", cpp_helper=helper),
            _obj(reset="io1"),
            {},
            prog_cpp_ctx(),
        )
        assert lines == ["    CProgCommon::cfgIdReset(),", "      IO1,"]

        lines = []
        emit_generic_config_field(
            lines,
            _field("id_single", name="reset", cpp_helper=helper),
            _obj(reset=None),
            {},
            prog_cpp_ctx(),
        )
        assert lines == ["    CProgCommon::cfgIdReset(),", "      0,"]

    def test_id_list(self):
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field(
                "id_list",
                name="targets",
                cpp_helper="CProgSequencer::cfgIdTargets",
            ),
            _obj(),
            {"targets": ["io1", {"id": "io2"}]},
            prog_cpp_ctx(),
        )
        assert lines == [
            "    CProgSequencer::cfgIdTargets(2),",
            "      IO1,",
            "      IO2,",
        ]

    def test_id_array_outputs(self):
        obj = _obj(outputs=["o1", "o2"])
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_array", name="outputs", cpp_helper="H"),
            obj,
            {},
            prog_cpp_ctx(),
        )
        assert lines == ["    H(),", "      O1,", "      O2,"]

    def test_id_array_custom_field_from_obj_config(self):
        obj = _obj(config={"extra": ["x1"]})
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_array", name="extra", cpp_helper="H"),
            obj,
            {},
            prog_cpp_ctx(),
        )
        assert lines == ["    H(),", "      X1,"]

    def test_id_single_from_config_list(self):
        obj = _obj(config={"sel": ["a", "b"]})
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_single", name="sel", cpp_helper="H"),
            obj,
            {},
            prog_cpp_ctx(),
        )
        assert lines == ["    H(),", "      A,"]

    def test_id_list_ignores_non_list_value(self):
        lines: list[str] = []
        emit_generic_config_field(
            lines,
            _field("id_list", name="targets", cpp_helper="H"),
            _obj(),
            {"targets": "notalist"},
            prog_cpp_ctx(),
        )
        assert lines == ["    H(0),"]

    def test_returns_false_for_program_specific_type(self):
        lines: list[str] = []
        handled = emit_generic_config_field(
            lines,
            _field("fusion_params", name="params"),
            _obj(),
            {"params": {}},
            prog_cpp_ctx(),
        )
        assert handled is False
        assert lines == []


class TestEmitConfigFieldsDispatch:

    def test_no_hook_uses_generic(self):
        """OOT program with fields but no handler uses the generic path."""
        lines: list[str] = []
        emit_config_fields_cpp(
            None,
            "oot_prog",
            lines,
            _obj(reset="io1"),
            {},
            [_field("id_single", name="reset", cpp_helper="H")],
            prog_cpp_ctx(),
        )
        assert lines == ["    H(),", "      IO1,"]

    def test_hook_takes_precedence_over_generic(self):
        calls: list[str] = []

        def hook(lines, field_def, obj, config, ctx):
            calls.append(field_def.name)
            lines.append("hooked")
            return True

        lines: list[str] = []
        emit_config_fields_cpp(
            hook,
            "owner",
            lines,
            _obj(),
            {},
            [_field("uint32", name="depth", cpp_helper="H")],
            prog_cpp_ctx(),
        )
        assert calls == ["depth"]
        assert lines == ["hooked"]

    def test_hook_declines_falls_back_to_generic(self):
        def hook(lines, field_def, obj, config, ctx):
            return False

        lines: list[str] = []
        emit_config_fields_cpp(
            hook,
            "owner",
            lines,
            _obj(),
            {"depth": 4},
            [_field("uint32", name="depth", cpp_helper="H")],
            prog_cpp_ctx(),
        )
        assert lines == ["    H(),", "      4,"]

    def test_unknown_value_type_raises(self):
        with pytest.raises(ValueError, match="no .* emitter"):
            emit_config_fields_cpp(
                None,
                "owner",
                [],
                _obj(),
                {},
                [_field("bogus_type", name="x", cpp_helper="H")],
                prog_cpp_ctx(),
            )

    def test_unclaimed_custom_type_raises(self):
        """A hook that declines a program-specific type is a bug -> raise."""

        def hook(lines, field_def, obj, config, ctx):
            return False

        with pytest.raises(ValueError, match="fusion_params"):
            emit_config_fields_cpp(
                hook,
                "fusion",
                [],
                _obj(),
                {"params": {}},
                [_field("fusion_params", name="params", cpp_helper="H")],
                prog_cpp_ctx(),
            )
