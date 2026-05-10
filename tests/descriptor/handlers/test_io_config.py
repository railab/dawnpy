# tools/dawnpy/tests/descriptor/handlers/test_io_config.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.config_access import build_config_rw_grants
from dawnpy.descriptor.definitions.objects import IoObject, ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_config_io_points_to_dummy_init_value_cfg(self):
        """Test ConfigIO stores the dummy init-value config ID only."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "dtype": "float",
                    "config": {"init_value": -1.1},
                },
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "float",
                    "rw": True,
                    "config": {"objid_ref": "dummy1"},
                },
            ]
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any("CIOConfig::cfgIdCfg()" in line for line in lines)
        assert any(
            "CIODummy::cfgIdInitval(10, true, 1)" in line for line in lines
        )
        assert not any("0xbf8ccccd" in line for line in lines)

    def test_generate_config_io_ignores_dummy_dim_and_payload(self):
        """Test ConfigIO keeps only the target dummy config ID."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "dtype": "bool",
                    "config": {"dim": 2, "init_value": [True, False]},
                },
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "bool",
                    "rw": True,
                    "config": {
                        "objid_ref": "dummy1",
                        "objcfg_ref": "init_value",
                    },
                },
            ]
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any("cfgIdInitval(1, true, 2)" in line for line in lines)
        assert not any("CIODummy::cfgIdDim()" in line for line in lines)
        assert not any("      true," == line for line in lines)
        assert not any("      false," == line for line in lines)

    def test_config_io_read_only_does_not_grant_target_rw(self):
        """Config item RW follows writable ConfigIO, not target object rw."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "dtype": "uint32",
                    "config": {"init_value": 1},
                },
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": False,
                    "config": {
                        "objid_ref": "dummy1",
                        "objcfg_ref": "init_value",
                    },
                },
            ]
        }
        generator.parse_spec(spec)

        dummy_lines = generator._generate_io_config(
            "DUMMY1", generator.objects["dummy1"]
        )
        cfg_lines = generator._generate_io_config(
            "CFG1", generator.objects["cfg1"]
        )

        assert any("cfgIdInitval(7, false, 1)" in line for line in dummy_lines)
        assert any("cfgIdInitval(7, false, 1)" in line for line in cfg_lines)

    def test_config_rw_grants_skip_unresolvable_config_io_edges(self):
        """Grant resolver ignores malformed or ambiguous ConfigIO entries."""
        malformed_cfg = IoObject(
            obj_id="cfg_bad",
            io_type="config",
            instance=0,
            dtype="uint32",
            tags=[],
            config=[],
            timestamp=False,
            notify=False,
            rw=True,
            subtype=None,
            variant=None,
        )
        missing_ref_cfg = IoObject(
            obj_id="cfg_missing",
            io_type="config",
            instance=1,
            dtype="uint32",
            tags=[],
            config={},
            timestamp=False,
            notify=False,
            rw=True,
            subtype=None,
            variant=None,
        )
        ambiguous_target = IoObject(
            obj_id="dummy_ambiguous",
            io_type="dummy",
            instance=0,
            dtype="uint32",
            tags=[],
            config={"dim": 2, "init_value": [1, 2]},
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        )
        ambiguous_cfg = IoObject(
            obj_id="cfg_ambiguous",
            io_type="config",
            instance=2,
            dtype="uint32",
            tags=[],
            config={"objid_ref": "dummy_ambiguous"},
            timestamp=False,
            notify=False,
            rw=True,
            subtype=None,
            variant=None,
        )
        non_mapping_target = IoObject(
            obj_id="dummy_list_config",
            io_type="dummy",
            instance=1,
            dtype="uint32",
            tags=[],
            config=[],
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        )
        non_mapping_cfg = IoObject(
            obj_id="cfg_list_config",
            io_type="config",
            instance=3,
            dtype="uint32",
            tags=[],
            config={
                "objid_ref": "dummy_list_config",
                "objcfg_ref": "init_value",
            },
            timestamp=False,
            notify=False,
            rw=True,
            subtype=None,
            variant=None,
        )

        objects = {
            obj.obj_id: obj
            for obj in [
                malformed_cfg,
                missing_ref_cfg,
                ambiguous_target,
                ambiguous_cfg,
                non_mapping_target,
                non_mapping_cfg,
            ]
        }

        assert build_config_rw_grants(objects) == {
            ("dummy_list_config", "init_value"): True
        }

    def test_generate_config_io_program_sequencer_start_index(self):
        """Test ConfigIO can target sequencer start_index config field."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {"id": "led1", "type": "leds", "dtype": "uint32"},
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {
                        "objid_ref": "seq1",
                        "objcfg_ref": "start_index",
                    },
                },
            ],
            "programs": [
                {
                    "id": "seq1",
                    "type": "sequencer",
                    "config": {
                        "targets": ["led1"],
                        "states": [
                            {"value": 0, "dwell_us": 1000},
                            {"value": 1, "dwell_us": 1000},
                        ],
                        "start_index": 0,
                    },
                }
            ],
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any("CIOConfig::cfgIdCfg()" in line for line in lines)
        assert any(
            "CProgSequencer::cfgIdStartIndex()" in line for line in lines
        )

    def test_generate_config_io_program_sequencer_states(self):
        """Test ConfigIO can target sequencer states config field."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {"id": "led1", "type": "leds", "dtype": "uint32"},
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {"objid_ref": "seq1", "objcfg_ref": "states"},
                },
            ],
            "programs": [
                {
                    "id": "seq1",
                    "type": "sequencer",
                    "config": {
                        "targets": ["led1"],
                        "states": [
                            {"value": 0, "dwell_us": 1000},
                            {"value": 1, "dwell_us": 2000},
                        ],
                        "start_index": 0,
                    },
                }
            ],
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any("CProgSequencer::cfgIdStates(4)" in line for line in lines)

    def test_generate_config_io_program_sequencer_invalid_states(self):
        """Test ConfigIO returns empty config for invalid sequencer states."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {"id": "led1", "type": "leds", "dtype": "uint32"},
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {"objid_ref": "seq1", "objcfg_ref": "states"},
                },
            ],
            "programs": [
                {
                    "id": "seq1",
                    "type": "sequencer",
                    "config": {
                        "targets": ["led1"],
                        "states": "invalid",
                        "start_index": 0,
                    },
                }
            ],
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert lines == ["  CFG1, 0,"]

    def test_generate_config_io_program_generic_field(self):
        """Test ConfigIO generic program field fallback (non-sequencer)."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {"objid_ref": "samp1", "objcfg_ref": "interval"},
                }
            ],
            "programs": [{"id": "samp1", "type": "sampling", "config": {}}],
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any(
            "CProgSampling::cfgIdIOInterval()" in line for line in lines
        )

    def test_generate_config_io_with_objcfg_ref_for_io_target(self):
        """Test ConfigIO resolves IO target cfg fields from metadata."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "dtype": "uint32",
                    "config": {"init_value": 1},
                },
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {
                        "objid_ref": "dummy1",
                        "objcfg_ref": "init_value",
                    },
                },
            ]
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert any("CIOConfig::cfgIdCfg()" in line for line in lines)
        assert any(
            "CIODummy::cfgIdInitval(7, true, 1)" in line for line in lines
        )

    def test_generate_config_io_with_unknown_objcfg_ref_for_io_target_is_empty(
        self,
    ):
        """Test unknown IO target cfg field yields empty ConfigIO payload."""
        generator = DescriptorGenerator()
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "dtype": "uint32",
                    "config": {"init_value": 1},
                },
                {
                    "id": "cfg1",
                    "type": "config",
                    "dtype": "uint32",
                    "rw": True,
                    "config": {
                        "objid_ref": "dummy1",
                        "objcfg_ref": "start_index",
                    },
                },
            ]
        }
        generator.parse_spec(spec)
        obj = generator.objects["cfg1"]
        lines = generator._generate_io_config("CFG1", obj)
        assert lines == ["  CFG1, 0,"]

    def test_special_config_io_program_fallback_none_paths(self):
        """Test Program ConfigIO helper returns None for unsupported paths."""
        from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext
        from dawnpy.descriptor.handlers import io_config as io_config_handler

        generator = DescriptorGenerator()

        seq_obj = ProgramObject.from_spec(
            {
                "id": "seq1",
                "type": "sequencer",
                "config": {"states": []},
            }
        )
        assert seq_obj is not None
        from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY

        assert (
            PROG_HANDLER_REGISTRY["sequencer"].config_reference_cpp_line(
                seq_obj, "states", generator.config_loader
            )
            is None
        )
        assert (
            PROG_HANDLER_REGISTRY["sequencer"].config_reference_cpp_line(
                seq_obj, "nonexistent", generator.config_loader
            )
            is None
        )

        class FakeConfigLoader:
            def get_prog_type_fields(self, _prog_type):
                return [ConfigField(name="x", cpp_helper="")]

        fake_gctx = IoGeneratorContext(
            config_loader=FakeConfigLoader(),
            format_helper=generator._format_helper,
            objects={},
        )
        nonseq_obj = ProgramObject.from_spec(
            {"id": "p1", "type": "sampling", "config": {}}
        )
        assert nonseq_obj is not None
        assert (
            io_config_handler._program_objcfg_line(
                nonseq_obj, "missing", fake_gctx
            )
            is None
        )
        assert (
            io_config_handler._program_objcfg_line(nonseq_obj, "x", fake_gctx)
            is None
        )


def test_config_io_binding(generator):
    """Test ConfigIO with object binding."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "dummy1",
                "type": "dummy",
                "instance": 1,
                "dtype": "uint32",
                "config": {"init_value": 100},
            },
            {
                "id": "cfg1",
                "type": "config",
                "instance": 1,
                "dtype": "uint32",
                "config": {"objid_ref": "dummy1"},
            },
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected: ConfigIO should have 2 config items
    expected_lines = [
        "  CFG1, 2,",
        "    CIOConfig::cfgIdCfg(),",
        "      CIODummy::cfgIdInitval(7, false, 1),",
        "    CIOConfig::cfgIdAlloc(SObjectId::DTYPE_UINT32, false, 1),",
        "      DUMMY1,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"


def test_config_io_with_different_dtypes(generator):
    """Test ConfigIO with various data types."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "dummy_int",
                "type": "dummy",
                "instance": 1,
                "dtype": "int32",
                "config": {"init_value": -20},
            },
            {
                "id": "dummy_float",
                "type": "dummy",
                "instance": 2,
                "dtype": "float",
                "config": {"init_value": -1.1},
            },
            {
                "id": "cfg_int",
                "type": "config",
                "instance": 1,
                "dtype": "int32",
                "config": {"objid_ref": "dummy_int"},
            },
            {
                "id": "cfg_float",
                "type": "config",
                "instance": 2,
                "dtype": "float",
                "config": {"objid_ref": "dummy_float"},
            },
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Check int32 ConfigIO
    expected_int = [
        "CIOConfig::cfgIdAlloc(SObjectId::DTYPE_INT32, false, 1)",
        "DUMMY_INT,",
    ]
    for expected in expected_int:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line for int32 ConfigIO: {expected}"

    # Check float ConfigIO
    expected_float = [
        "CIOConfig::cfgIdAlloc(SObjectId::DTYPE_FLOAT, false, 1)",
        "DUMMY_FLOAT,",
    ]
    for expected in expected_float:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line for float ConfigIO: {expected}"
