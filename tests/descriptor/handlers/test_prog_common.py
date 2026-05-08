# tools/dawnpy/tests/descriptor/handlers/test_prog_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestProgramConfigGenerator:

    def test_emit_id_array_pairs(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgStatsMin::cfgIdIOBind"
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=["io1"],
            outputs=["io2"],
            reset=None,
            config={},
        )
        config = {"sources": ["io1"], "outputs": ["io2"]}
        prog_gen._emit_id_array_pairs(lines, cpp_helper, obj, config)
        assert lines == [
            "    CProgStatsMin::cfgIdIOBind(2),",
            "      IO1,",
            "      IO2,",
        ]

    def test_emit_id_array_pairs_interleaves_multiple_binds(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgStatsMin::cfgIdIOBind"
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=["io1", "io2"],
            outputs=["out1", "out2"],
            reset=None,
            config={},
        )
        config = {"sources": ["io1", "io2"], "outputs": ["out1", "out2"]}
        prog_gen._emit_id_array_pairs(lines, cpp_helper, obj, config)
        assert lines == [
            "    CProgStatsMin::cfgIdIOBind(4),",
            "      IO1,",
            "      OUT1,",
            "      IO2,",
            "      OUT2,",
        ]

    def test_emit_uint32(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgSampling::cfgIdIOInterval"
        config = {"interval": 50000}
        prog_gen._emit_uint32(lines, cpp_helper, "interval", config)
        assert lines == [
            "    CProgSampling::cfgIdIOInterval(),",
            "      50000,",
        ]

    def test_emit_uint32_uses_field_default(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        prog_gen._emit_uint32(
            lines, "CProgBuffer::cfgIdChunkSize", "chunk_size", {}, "1"
        )
        assert lines == [
            "    CProgBuffer::cfgIdChunkSize(),",
            "      1,",
        ]

    def test_emit_id_array(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgCommon::cfgIdInput"
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=["io1", "io2"],
            outputs=[],
            reset=None,
            config={},
        )
        prog_gen._emit_id_array(lines, cpp_helper, "inputs", obj)
        assert lines == [
            "    CProgCommon::cfgIdInput(),",
            "      IO1,",
            "      IO2,",
        ]

    def test_emit_id_single(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        # Case with ID
        lines = []
        cpp_helper = "CProgCommon::cfgIdReset"
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=[],
            outputs=[],
            reset="io1",
            config={},
        )
        prog_gen._emit_id_single(lines, cpp_helper, "reset", obj)
        assert lines == ["    CProgCommon::cfgIdReset(),", "      IO1,"]

        # Case without ID
        lines = []
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=[],
            outputs=[],
            reset=None,
            config={},
        )
        prog_gen._emit_id_single(lines, cpp_helper, "reset", obj)
        assert lines == ["    CProgCommon::cfgIdReset(),", "      0,"]

    def test_emit_id_array_quads(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        # Successful case
        lines = []
        cpp_helper = "CProgBuffer::cfgIdIOBind"
        config = {
            "iobind": [
                {"src": "io1", "out": "io2", "sel": "io3", "stat": "io4"}
            ]
        }
        prog_gen._emit_id_array_quads(lines, cpp_helper, "iobind", config)
        assert "    CProgBuffer::cfgIdIOBind(4)," in lines[0]

        # Negative cases for coverage
        lines = []
        config = {
            "iobind": [
                "not_a_dict",
                {"src": "io1", "out": "io2"},  # missing sel/stat
                {
                    "src": "io1",
                    "out": "io2",
                    "sel": "io3",
                    "stat": None,
                },  # invalid
            ]
        }
        prog_gen._emit_id_array_quads(lines, cpp_helper, "iobind", config)
        assert "    CProgBuffer::cfgIdIOBind(0)," in lines[0]

    def test_emit_id_list(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgSequencer::cfgIdTargets"
        config = {"targets": ["io1", {"id": "io2"}]}
        prog_gen._emit_id_list(lines, cpp_helper, "targets", config)
        assert lines == [
            "    CProgSequencer::cfgIdTargets(2),",
            "      IO1,",
            "      IO2,",
        ]

    def test_emit_type_field_coverage(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        # Test id_single coverage
        lines = []
        field_def = ConfigField(
            name="reset",
            value_type="id_single",
            cpp_helper="H",
        )
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=[],
            outputs=[],
            reset="io1",
            config={},
        )
        prog_gen._emit_type_field(lines, field_def, obj, {})
        assert "H()," in lines[0]
        assert "      IO1," in lines[1]

        # Test id_array coverage
        lines = []
        field_def = ConfigField(
            name="inputs",
            value_type="id_array",
            cpp_helper="H",
        )
        obj = ProgramObject(
            obj_id="p1",
            prog_type="stats",
            instance=0,
            inputs=["io1"],
            outputs=[],
            reset=None,
            config={},
        )
        prog_gen._emit_type_field(lines, field_def, obj, {})
        assert "H()," in lines[0]
        assert "      IO1," in lines[1]

        # Test gateway_iobind coverage
        lines = []
        field_def = ConfigField(
            name="iobind",
            value_type="gateway_iobind",
            cpp_helper="H",
        )
        config = {"iobind": [{"io1": "a", "io2": "b"}]}
        prog_gen._emit_type_field(lines, field_def, obj, config)
        assert "H(4)," in lines[0]

        # Test id_array_quads coverage
        lines = []
        field_def = ConfigField(
            name="iobind",
            value_type="id_array_quads",
            cpp_helper="H",
        )
        config = {
            "iobind": [{"src": "a", "out": "b", "sel": "c", "stat": "d"}]
        }
        prog_gen._emit_type_field(lines, field_def, {}, config)
        assert "H(4)," in lines[0]

        # Test adjust_params coverage
        lines = []
        field_def = ConfigField(
            name="params",
            value_type="adjust_params",
            cpp_helper="H",
        )
        config = {"params": {"offset": 7, "scale": 5}}
        prog_gen._emit_type_field(lines, field_def, obj, config)
        assert lines == ["    H(),", "      7,", "      5,"]

        # Test id_list coverage
        lines = []
        field_def = ConfigField(
            name="targets",
            value_type="id_list",
            cpp_helper="H",
        )
        config = {"targets": ["a", {"id": "b"}]}
        prog_gen._emit_type_field(lines, field_def, obj, config)
        assert lines == ["    H(2),", "      A,", "      B,"]

        # Test sequencer_states coverage
        lines = []
        field_def = ConfigField(
            name="states",
            value_type="sequencer_states",
            cpp_helper="H",
        )
        config = {"states": [{"value": 10, "dwell_us": 20}]}
        prog_gen._emit_type_field(lines, field_def, obj, config)
        assert lines == ["    H(2),", "      10,", "      20,"]


def test_generate_prog_config_handles_id_single(monkeypatch):
    generator = DescriptorGenerator()
    monkeypatch.setattr(
        generator.config_loader,
        "get_prog_type_fields",
        lambda prog_type: [
            ConfigField(
                name="target",
                value_type="id_single",
                cpp_helper="CProgProcess::cfgIdTarget",
            ),
        ],
    )
    from dawnpy.descriptor.definitions.objects import ProgramObject

    obj = ProgramObject.from_spec(
        {
            "id": "prog1",
            "type": "stats",
            "instance": 1,
            "config": {"target": "io1"},
        }
    )
    assert obj is not None
    lines = generator._generate_prog_config("PROG1", obj)
    assert any("IO1" in line for line in lines)

    obj_no_target = ProgramObject.from_spec(
        {
            "id": "prog1",
            "type": "stats",
            "instance": 1,
            "config": {},
        }
    )
    assert obj_no_target is not None
    lines_no_target = generator._generate_prog_config("PROG1", obj_no_target)
    assert any("0," in line for line in lines_no_target)
