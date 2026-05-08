# tools/dawnpy/tests/test_descriptor_generator.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor generator."""

import pytest

from dawnpy.descriptor.config_access import build_config_rw_grants
from dawnpy.descriptor.definitions.objects import (
    IoObject,
    ProgramObject,
    ProtocolObject,
)
from dawnpy.descriptor.definitions.registry import PROG_TYPES
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import (
    DescriptorGenerator,
    generate_descriptor,
)
from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

pytestmark = pytest.mark.usefixtures("source_free_headers")


def to_io_obj(spec: dict, obj_id: str = "test_io") -> IoObject:
    """Helper to create IoObject from partial spec."""
    full_spec = {
        "id": obj_id,
        "type": spec.get("type", "dummy"),
        "instance": spec.get("instance", 1),
        "dtype": spec.get("dtype", "uint32"),
        "config": spec.get("config", {}),
    }
    return IoObject.from_spec(full_spec)


def to_proto_obj(spec: dict, obj_id: str = "test_proto") -> ProtocolObject:
    """Helper to create ProtocolObject from partial spec."""
    full_spec = {
        "id": obj_id,
        "type": spec.get("type", "serial"),
        "instance": spec.get("instance", 1),
        "config": spec.get("config", {}),
        "bindings": spec.get("bindings", []),
    }
    return ProtocolObject.from_spec(full_spec)


class TestDescriptorGenerator:
    """Test DescriptorGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a DescriptorGenerator instance."""
        return DescriptorGenerator()

    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator.objects == {}
        assert generator.object_order == []
        assert generator.includes == set()
        assert generator.metadata == {}

    def test_format_helper_alignment_lines(self):
        """Format helper centralizes generated C++ line alignment."""
        helper = DescriptorFormatHelper()
        lines: list[str] = []

        helper.append_line(lines, 2, "CExample::cfgId(),")
        helper.append_words(lines, [0x12345678, 0], level=3)

        assert helper.indent(2) == "    "
        assert helper.line(1, "ITEM, 1,") == "  ITEM, 1,"
        assert helper.define_line("FOO", "BAR") == "#define FOO  BAR"
        assert lines == [
            "    CExample::cfgId(),",
            "      0x12345678,",
            "      0x00000000,",
        ]

    def test_load_yaml_empty(self, generator, tmp_path):
        """Test loading empty YAML."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("---\n{}\n")
        spec = generator.load_yaml(str(yaml_file))
        assert spec == {} or spec is None

    def test_load_yaml_with_ios(self, generator, tmp_path):
        """Test loading YAML with IOs."""
        yaml_content = """
ios:
  - id: test_io
    type: dummy
    instance: 1
    dtype: bool
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)
        spec = generator.load_yaml(str(yaml_file))
        assert "ios" in spec
        assert len(spec["ios"]) == 1
        assert spec["ios"][0]["id"] == "test_io"

    def test_parse_spec_empty(self, generator):
        """Test parsing empty spec."""
        spec = {"ios": [], "programs": [], "protocols": []}
        generator.parse_spec(spec)
        assert len(generator.objects) == 0
        assert "dawn/common/descriptor.hxx" in generator.includes

    def test_parse_spec_with_io(self, generator):
        """Test parsing spec with single IO."""
        spec = {
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "bool",
                }
            ]
        }
        generator.parse_spec(spec)
        assert "dummy1" in generator.objects
        assert generator.objects["dummy1"].category == "IO"
        assert isinstance(generator.objects["dummy1"], IoObject)
        assert generator.objects["dummy1"].io_type == "dummy"
        assert "dawn/io/dummy.hxx" in generator.includes

    def test_parse_spec_with_program(self, generator):
        """Test parsing spec with program."""
        spec = {
            "ios": [
                {"id": "io1", "type": "dummy", "instance": 1, "dtype": "bool"}
            ],
            "programs": [
                {
                    "id": "prog1",
                    "type": "stats",
                    "instance": 1,
                    "inputs": ["io1"],
                    "outputs": [],
                }
            ],
        }
        generator.parse_spec(spec)
        assert "prog1" in generator.objects
        assert generator.objects["prog1"].category == "PROG"
        assert isinstance(generator.objects["prog1"], ProgramObject)
        assert generator.objects["prog1"].prog_type == "stats"
        assert "dawn/prog/process.hxx" in generator.includes

    def test_parse_spec_with_protocol(self, generator):
        """Test parsing spec with protocol."""
        spec = {
            "ios": [
                {"id": "io1", "type": "dummy", "instance": 1, "dtype": "bool"}
            ],
            "protocols": [
                {
                    "id": "proto1",
                    "type": "serial",
                    "instance": 1,
                    "bindings": ["io1"],
                }
            ],
        }
        generator.parse_spec(spec)
        assert "proto1" in generator.objects
        assert generator.objects["proto1"].category == "PROTO"
        assert generator.objects["proto1"].proto_type == "serial"
        assert "dawn/proto/serial/simple.hxx" in generator.includes

    def test_parse_spec_modbus_overlap_rejected(self, generator):
        """Modbus blocks in same address space must not overlap."""
        spec = {
            "ios": [
                {
                    "id": "io1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "bool",
                },
                {
                    "id": "io2",
                    "type": "dummy",
                    "instance": 2,
                    "dtype": "bool",
                },
            ],
            "protocols": [
                {
                    "id": "modbus1",
                    "type": "modbus_rtu",
                    "instance": 1,
                    "config": {
                        "registers": [
                            {
                                "type": "coil",
                                "start": 1000,
                                "bindings": ["io1"],
                            },
                            {
                                "type": "coil_packed",
                                "start": 1000,
                                "bindings": ["io2"],
                            },
                        ]
                    },
                }
            ],
        }
        with pytest.raises(ValueError, match="modbus register overlap"):
            generator.parse_spec(spec)

    def test_parse_spec_nimble_headers_from_service_config(self, generator):
        """Test nimble service headers are loaded from YAML service config."""
        spec = {
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {"services": {"aios": {}, "ess": {}}},
                }
            ]
        }
        generator.parse_spec(spec)
        assert "dawn/proto/nimble/prph_aios.hxx" in generator.includes
        assert "dawn/proto/nimble/prph_ess.hxx" in generator.includes

    def test_generate_nimble_aios_group_shape(self, generator):
        """AIOS generator must support digital_inputs/analog_inputs YAML."""
        spec = {
            "ios": [
                {
                    "id": "gpi1",
                    "type": "gpi",
                    "instance": 1,
                    "dtype": "bool",
                },
                {
                    "id": "gpo1",
                    "type": "gpo",
                    "instance": 1,
                    "dtype": "bool",
                },
                {
                    "id": "ai1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "aios": {
                                "aggregate": True,
                                "groups": [
                                    {
                                        "digital_inputs": ["gpi1"],
                                        "digital_outputs": ["gpo1"],
                                    },
                                    {"analog_inputs": ["ai1"]},
                                ],
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindAios(12)" in output
        assert "CProtoNimblePrphAios::cfgIdIOBindAiosCfg0(3)" in output
        assert (
            "CProtoNimblePrphAios::cfgIdIOBindAiosCfgObj("
            "CProtoNimblePrphAios::PRPH_AIOS_TYPE_DIGITAL)"
        ) in output
        assert (
            "CProtoNimblePrphAios::cfgIdIOBindAiosCfgObj("
            "CProtoNimblePrphAios::PRPH_AIOS_TYPE_ANALOG)"
        ) in output
        assert "GPI1," in output
        assert "GPO1," in output
        assert "AI1," in output

    def test_generate_nimble_aios_ignores_malformed_groups(self, generator):
        """AIOS generator should skip malformed group entries safely."""
        spec = {
            "ios": [
                {
                    "id": "gpi1",
                    "type": "gpi",
                    "instance": 1,
                    "dtype": "bool",
                }
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "aios": {
                                "aggregate": True,
                                "groups": [
                                    "bad-group",
                                    {"digital_inputs": "not-a-list"},
                                    {"type": "DIGITAL", "bindings": "bad"},
                                    {"digital_inputs": ["gpi1"]},
                                ],
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindAios(6)" in output
        assert "CProtoNimblePrphAios::cfgIdIOBindAiosCfg0(1)" in output
        assert "GPI1," in output

    def test_generate_nimble_aios_characteristics_with_metadata(
        self, generator
    ):
        """AIOS bindings can carry per-characteristic metadata."""
        spec = {
            "ios": [
                {
                    "id": "gpi1",
                    "type": "gpi",
                    "instance": 1,
                    "dtype": "bool",
                },
                {
                    "id": "din1_trigger_cfg",
                    "type": "dummy",
                    "instance": 2,
                    "dtype": "uint8",
                },
                {
                    "id": "din1_time_trigger_cfg",
                    "type": "dummy",
                    "instance": 3,
                    "dtype": "uint8",
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "aios": {
                                "aggregate": True,
                                "groups": [
                                    {
                                        "digital_inputs": [
                                            {
                                                "data": "gpi1",
                                                "metadata": "bad",
                                            },
                                            {
                                                "data": "gpi1",
                                                "metadata": {
                                                    "user_description": (
                                                        "button"
                                                    ),
                                                    "number_of_digitals": 1,
                                                    "value_trigger_setting": (
                                                        "din1_trigger_cfg"
                                                    ),
                                                    "time_trigger_setting": (
                                                        "din1_time_trigger_cfg"
                                                    ),
                                                    "presentation_format": {
                                                        "format": 1,
                                                        "exponent": 0,
                                                        "unit": 9984,
                                                        "namespace": 1,
                                                        "description": 0,
                                                    },
                                                    "extended_properties": 0,
                                                },
                                            },
                                        ]
                                    }
                                ],
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindAios(25)" in output
        assert "CProtoNimblePrphAios::cfgIdIOBindAiosCfg1(1)" in output
        assert "GPI1," in output
        assert "CProtoNimblePrphAios::AIOS_EXT_USER_DESCRIPTION, 4" in output
        assert "CProtoNimblePrphAios::AIOS_EXT_NUMBER_OF_DIGITALS, 1" in output
        assert (
            "CProtoNimblePrphAios::AIOS_EXT_VALUE_TRIGGER_SETTING, 1" in output
        )
        assert (
            "CProtoNimblePrphAios::AIOS_EXT_TIME_TRIGGER_SETTING, 1" in output
        )
        assert (
            "CProtoNimblePrphAios::AIOS_EXT_PRESENTATION_FORMAT, 2" in output
        )
        assert (
            "CProtoNimblePrphAios::AIOS_EXT_EXTENDED_PROPERTIES, 1" in output
        )
        assert "DIN1_TRIGGER_CFG," in output
        assert "DIN1_TIME_TRIGGER_CFG," in output
        assert "0x27000001," in output
        assert "0x00000001," in output
        assert "0x00000000," in output
        assert "0x74747562," in output

    def test_generate_nimble_ess_characteristics_with_metadata(
        self, generator
    ):
        """ESS uses normalized entries with optional metadata."""
        spec = {
            "ios": [
                {
                    "id": "temp1",
                    "type": "sensor",
                    "subtype": "temp",
                    "instance": 1,
                    "dtype": "float",
                    "config": {
                        "device": 0,
                        "measurement_period": 60,
                        "update_interval": 10,
                    },
                },
                {
                    "id": "cfg_measurement_period",
                    "type": "config",
                    "instance": 2,
                    "dtype": "uint32",
                    "rw": True,
                    "config": {
                        "objid_ref": "temp1",
                        "objcfg_ref": "measurement_period",
                    },
                },
                {
                    "id": "cfg_update_interval",
                    "type": "config",
                    "instance": 3,
                    "dtype": "uint32",
                    "rw": True,
                    "config": {
                        "objid_ref": "temp1",
                        "objcfg_ref": "update_interval",
                    },
                },
                {
                    "id": "cfg_es_configuration",
                    "type": "dummy",
                    "instance": 4,
                    "dtype": "uint8",
                },
                {
                    "id": "cfg_trigger_setting",
                    "type": "dummy",
                    "instance": 5,
                    "dtype": "uint8",
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "ess": {
                                "characteristics": [
                                    {
                                        "type": "temperature",
                                        "data": "temp1",
                                        "metadata": {
                                            "user_description": "ambient",
                                            "valid_range": {
                                                "min": 0xFFFFF060,
                                                "max": 8500,
                                            },
                                            "measurement": {
                                                "measurement_period": (
                                                    "cfg_measurement_period"
                                                ),
                                                "update_interval": (
                                                    "cfg_update_interval"
                                                ),
                                            },
                                            "configuration": (
                                                "cfg_es_configuration"
                                            ),
                                            "trigger_setting": (
                                                "cfg_trigger_setting"
                                            ),
                                        },
                                    }
                                ]
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindEss(25)" in output
        assert "CProtoNimblePrphEss::cfgIdIOBindEssCfg0(1)" in output
        assert (
            "CProtoNimblePrphEss::cfgIdIOBindEssCfgObj("
            "CProtoNimblePrphEss::PRPH_ESS_TYPE_TEMP)"
        ) in output
        assert "TEMP1," in output
        assert "5," in output
        assert "ESS_EXT_USER_DESCRIPTION, 4" in output
        assert "ESS_EXT_VALID_RANGE, 2" in output
        assert "ESS_EXT_MEASUREMENT, 6" in output
        assert "ESS_EXT_CONFIGURATION, 1" in output
        assert "ESS_EXT_TRIGGER_SETTING, 1" in output
        assert "0xfffff060," in output
        assert "0x00002134," in output
        assert "CFG_MEASUREMENT_PERIOD," in output
        assert "CFG_UPDATE_INTERVAL," in output
        assert "CFG_ES_CONFIGURATION," in output
        assert "CFG_TRIGGER_SETTING," in output

    def test_generate_nimble_ess_characteristic_with_invalid_metadata(
        self, generator
    ):
        """ESS metadata is optional and ignores malformed metadata blocks."""
        spec = {
            "ios": [
                {
                    "id": "temp1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
                {
                    "id": "hum1",
                    "type": "dummy",
                    "instance": 2,
                    "dtype": "float",
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "ess": {
                                "characteristics": [
                                    {
                                        "type": "temperature",
                                        "data": "temp1",
                                        "metadata": "bad",
                                    }
                                ]
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindEss(6)" in output
        assert "TEMP1," in output
        assert "0," in output

    def test_nimble_ess_extension_cfg_word(self):
        """ESS compact extension helper packs kind and payload size."""
        from dawnpy.descriptor.handlers import proto_nimble

        assert proto_nimble._ess_ext_cfg(3, 6) == 0x603

    def test_generate_nimble_imds_characteristic_with_metadata(
        self, generator
    ):
        """IMDS measurements can carry per-characteristic metadata."""
        spec = {
            "ios": [
                {
                    "id": "temp1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                }
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "imds": {
                                "temperature": {
                                    "data": "temp1",
                                    "metadata": {"user_description": "probe"},
                                },
                                "humidity": {
                                    "data": "hum1",
                                    "metadata": "bad",
                                },
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindImds(14)" in output
        assert "CProtoNimblePrphImds::cfgIdIOBindImdsCfg0(2)" in output
        assert (
            "CProtoNimblePrphImds::cfgIdIOBindImdsCfgObj("
            "CProtoNimblePrphImds::PRPH_IMDS_TYPE_TEMP)"
        ) in output
        assert "TEMP1," in output
        assert "HUM1," in output
        assert "IMDS_EXT_USER_DESCRIPTION, 4" in output
        assert "0x626f7270," in output

    def test_nimble_imds_extension_cfg_word(self):
        """IMDS compact extension helper packs kind and payload size."""
        from dawnpy.descriptor.handlers import proto_nimble

        assert proto_nimble._imds_ext_cfg(1, 4) == 0x401

    def test_generate_nimble_imds_scalar_binding(self, generator):
        """IMDS accepts direct IO IDs when no metadata is needed."""
        spec = {
            "ios": [
                {
                    "id": "temp1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                }
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "imds": {
                                "temperature": "temp1",
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        assert "CProtoNimblePrph::cfgIdIOBindImds(6)" in output
        assert "TEMP1," in output

    def test_nimble_aios_extension_cfg_word(self):
        """AIOS compact extension helper packs kind and payload size."""
        from dawnpy.descriptor.handlers import proto_nimble

        assert proto_nimble._aios_ext_cfg(1, 4) == 0x401

    def test_generate_nimble_ots_basic(self, generator):
        """OTS generator should emit one cfgIdIOBindOts block per service."""
        spec = {
            "ios": [
                {
                    "id": "fileio_ro",
                    "type": "fileio",
                    "instance": 1,
                    "dtype": "block",
                    "config": {"path": "/tmp/some_file_ro.txt", "perm": 0},
                },
                {
                    "id": "fileio_rw",
                    "type": "fileio",
                    "instance": 2,
                    "dtype": "block",
                    "config": {"path": "/tmp/some_file_rw.txt", "perm": 2},
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "ots": {
                                "objects": [
                                    {
                                        "name": "ro",
                                        "type": "file",
                                        "access": "read",
                                        "io": "fileio_ro",
                                    },
                                    {
                                        "type": "file",
                                        "io": "fileio_rw",
                                    },
                                ]
                            }
                        }
                    },
                }
            ],
        }

        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())

        # 3 header words + 6 per object * 2 = 15 words
        assert "CProtoNimblePrph::cfgIdIOBindOts(15)" in output
        assert "FILEIO_RO," in output
        assert "FILEIO_RW," in output
        # The OTS service header must be pulled into includes.
        assert "dawn/proto/nimble/prph_ots.hxx" in generator.includes

    def test_generate_nimble_ots_access_modes_packed(self, generator):
        """OTS cfg word packs type|access|on_complete in low 8 bits."""
        spec = {
            "ios": [
                {
                    "id": "fileio_rw",
                    "type": "fileio",
                    "instance": 1,
                    "dtype": "block",
                    "config": {"path": "/tmp/some_file_rw.txt", "perm": 2},
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "ots": {
                                "objects": [
                                    {
                                        "type": "file",
                                        "io": "fileio_rw",
                                    }
                                ]
                            }
                        }
                    },
                }
            ],
        }
        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())
        # access=rw -> 2 << 4 = 0x20; type=file (0); on_complete=none (0).
        assert "0x00000020,  // OTS cfg" in output

    def test_generate_nimble_ots_skips_invalid_entries(self, generator):
        """OTS generator skips non-dict entries and entries without io."""
        spec = {
            "ios": [
                {
                    "id": "fileio_rw",
                    "type": "fileio",
                    "instance": 1,
                    "dtype": "block",
                    "config": {"path": "/tmp/some_file_rw.txt", "perm": 2},
                },
            ],
            "protocols": [
                {
                    "id": "nimble1",
                    "type": "nimble",
                    "instance": 1,
                    "config": {
                        "services": {
                            "ots": {
                                "objects": [
                                    "not-a-dict",
                                    {"name": "no-io"},
                                    {
                                        "type": "file",
                                        "io": "fileio_rw",
                                    },
                                ]
                            }
                        }
                    },
                }
            ],
        }
        generator.parse_spec(spec)
        output = "\n".join(generator.generate_descriptor_array())
        # Only the single valid entry survives -> 3 header + 6 = 9 words.
        assert "CProtoNimblePrph::cfgIdIOBindOts(9)" in output
        assert "FILEIO_RW," in output

    def test_resolve_reference_dict(self, generator):
        """Test resolving dictionary reference."""
        ref = {"id": "test_io"}
        resolved = generator._resolve_reference(ref)
        assert resolved == "test_io"

    def test_resolve_reference_string(self, generator):
        """Test resolving string reference."""
        ref = "test_io"
        resolved = generator._resolve_reference(ref)
        assert resolved == "test_io"

    def test_resolve_reference_none(self, generator):
        """Test resolving None reference."""
        resolved = generator._resolve_reference(None)
        assert resolved is None

    def test_resolve_references_list(self, generator):
        """Test resolving list of references."""
        refs = [{"id": "io1"}, "io2", {"id": "io3"}]
        resolved = generator._resolve_references(refs)
        assert resolved == ["io1", "io2", "io3"]

    def test_generate_defines_io(self, generator):
        """Test generating defines for IO."""
        generator.objects = {
            "test_io": IoObject(
                obj_id="test_io",
                io_type="dummy",
                dtype="bool",
                instance=1,
                timestamp=False,
                rw=False,
                notify=False,
                tags=[],
                config={},
                subtype=None,
                variant=None,
            )
        }
        generator.object_order = ["test_io"]
        lines = generator.generate_defines()
        assert len(lines) == 1
        assert "#define TEST_IO" in lines[0]
        assert "CIODummy::objectId" in lines[0]

    def test_generate_defines_prog(self, generator):
        """Test generating defines for program."""
        generator.objects = {
            "test_prog": ProgramObject(
                obj_id="test_prog",
                prog_type="stats",
                instance=1,
                inputs=[],
                outputs=[],
                reset=None,
                config={},
            )
        }
        generator.object_order = ["test_prog"]
        lines = generator.generate_defines()
        assert len(lines) == 1
        assert "#define TEST_PROG" in lines[0]
        assert "CProgProcess::objectId" in lines[0]

    def test_generate_defines_proto(self, generator):
        """Test generating defines for protocol."""
        generator.objects = {
            "test_proto": ProtocolObject(
                obj_id="test_proto",
                proto_type="serial",
                instance=1,
                config={},
                bindings=[],
            )
        }
        generator.object_order = ["test_proto"]
        lines = generator.generate_defines()
        assert len(lines) == 1
        assert "#define TEST_PROTO" in lines[0]
        assert "CProtoSerial::objectId" in lines[0]

    def test_encode_version(self, generator):
        """Test version encoding."""
        assert generator._encode_version("1.0") == "0x00010000"
        assert generator._encode_version("2.5") == "0x00020005"
        assert generator._encode_version("10.255") == "0x000a00ff"

    def test_generate_io_config_no_config(self, generator):
        """Test generating IO config with no configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="bool",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 0," in lines[0]

    def test_generate_io_config_with_device(self, generator):
        """Test generating IO config with device number."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_fetch",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"device": 0},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdDevno()" in lines[1]
        assert "0," in lines[2]

    def test_generate_io_config_with_notify(self, generator):
        """Test generating IO config with notify configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "stream", "priority": 255}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "1," in lines[2]  # stream = 1
        assert "255," in lines[3]  # priority
        assert "1," in lines[4]  # batch = 1 (default)

    def test_generate_io_config_with_notify_batch(self, generator):
        """Test generating IO config with notify batch configuration."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "poll", "priority": 10, "batch": 8}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "0," in lines[2]  # poll = 0
        assert "10," in lines[3]  # priority
        assert "8," in lines[4]  # batch = 8

    def test_generate_io_config_with_notify_poll_default(self, generator):
        """Test generating IO config with poll notify (default type)."""
        obj = IoObject(
            obj_id="test_io",
            io_type="sensor",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={"notify": {"type": "poll", "priority": 100}},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOCommon::cfgIdNotify()" in lines[1]
        assert "0," in lines[2]  # poll = 0
        assert "100," in lines[3]  # priority
        assert "1," in lines[4]  # batch = 1 (default)

    def test_generate_io_config_with_device_and_notify(self, generator):
        """Test generating IO config with both device and notify."""
        obj = IoObject(
            obj_id="test_io",
            io_type="adc_stream",
            dtype="uint32",
            instance=0,
            timestamp=False,
            rw=False,
            notify=True,
            tags=[],
            config={
                "device": 2,
                "notify": {"type": "stream", "priority": 200},
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 2," in lines[0]  # 2 config items
        assert "CIOCommon::cfgIdDevno()" in lines[1]
        assert "2," in lines[2]
        assert "CIOCommon::cfgIdNotify()" in lines[3]
        assert "1," in lines[4]  # stream = 1
        assert "200," in lines[5]  # priority

    def test_generate_io_config_with_interval(self, generator):
        """Test generating IO config with interval."""
        obj = IoObject(
            obj_id="test_io",
            io_type="timestamp",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"interval_us": 1000000},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOTimestamp::cfgInterval" in lines[1]
        assert "1000000," in lines[2]

    def test_generate_io_config_default_format(self, generator):
        """Test default formatting path for IO config."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="double",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"init_value": 1.25},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        # double dtype -> SObjectId::DTYPE_DOUBLE = 11; dim is the value
        # count, the C++ helper doubles the resulting cfgid size for 64-bit.
        assert any("cfgIdInitval(11, false, 1)" in line for line in lines)
        assert any("0x00000000" in line for line in lines)
        assert any("0x3ff40000" in line for line in lines)

    def test_generate_io_config_default_format_fallback(self, generator):
        """Test fallback scalar formatting for unhandled dtypes."""
        obj = IoObject(
            obj_id="test_io",
            io_type="dummy",
            dtype="b16",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"init_value": 1.25},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert any("1.25," in line for line in lines)

    def test_generate_control_io_full(self, generator):
        """Test special IO generator for control target/allowed payload."""
        obj = IoObject(
            obj_id="ctrl1",
            io_type="control",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={
                "targets": ["sampling1", "sampling2"],
                "allowed": ["start", "stop"],
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(2)," in lines[1]
        assert "SAMPLING1," in lines[2]
        assert "SAMPLING2," in lines[3]
        assert "CIOControl::cfgIdAllowed()," in lines[4]
        assert "CTRL_ALLOW_START" in lines[5]
        assert "CTRL_ALLOW_STOP" in lines[5]

    def test_generate_control_io_start_only(self, generator):
        """Test control payload with only start allowed."""
        obj = IoObject(
            obj_id="ctrl1",
            io_type="control",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={
                "targets": ["io1"],
                "allowed": ["start"],
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(1)," in lines[1]
        assert "IO1," in lines[2]
        assert "CIOControl::cfgIdAllowed()," in lines[3]
        assert "CTRL_ALLOW_START" in lines[4]
        assert "CTRL_ALLOW_STOP" not in lines[4]

    def test_generate_control_io_no_targets(self, generator):
        """Test control payload with no targets (only allowed)."""
        obj = to_io_obj(
            {
                "type": "control",
                "config": {
                    "allowed": ["stop"],
                },
            },
            obj_id="ctrl1",
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 1," in lines[0]
        assert "CIOControl::cfgIdAllowed()," in lines[1]
        assert "CTRL_ALLOW_STOP" in lines[2]

    def test_generate_control_io_via_generate_io_config(self, generator):
        """Test that _generate_io_config dispatches to control handler."""
        obj = to_io_obj(
            {
                "type": "control",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["start"],
                },
            },
            obj_id="ctrl1",
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(1)," in lines[1]

    def test_generate_trigger_io_full(self, generator):
        """Test special IO generator for trigger target/allowed payload."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["prog1"],
                    "allowed": ["trigger1", "trigger2"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]
        assert "PROG1," in lines[2]
        assert "CIOTrigger::cfgIdAllowed()," in lines[3]
        assert "TRIG_ALLOW_TRIGGER1" in lines[4]
        assert "TRIG_ALLOW_TRIGGER2" in lines[4]

    def test_generate_trigger_io_reset_only(self, generator):
        """Test trigger payload with only reset allowed."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["reset"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]
        assert "IO1," in lines[2]
        assert "CIOTrigger::cfgIdAllowed()," in lines[3]
        assert "TRIG_ALLOW_RESET" in lines[4]
        assert "TRIG_ALLOW_TRIGGER1" not in lines[4]

    def test_generate_trigger_io_via_generate_io_config(self, generator):
        """Test that _generate_io_config dispatches to trigger handler."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["trigger1"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]

    def test_generate_trigger_io_multi_target(self, generator):
        """Test trigger payload with multiple targets."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1", "io2", "io3"],
                    "allowed": ["trigger1"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(3)," in lines[1]
        assert "IO1," in lines[2]
        assert "IO2," in lines[3]
        assert "IO3," in lines[4]
        assert "CIOTrigger::cfgIdAllowed()," in lines[5]

    def test_generate_proto_config_simple(self, generator):
        """Test generating simple protocol config."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1", "io2"],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 1," in lines[0]
        assert "cfgIdIOBind(2)" in lines[1]
        assert "IO1," in lines[2]
        assert "IO2," in lines[3]

    def test_generate_proto_config_bindings_from_config(self, generator):
        """Simple protocols accept bindings inside config."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "config": {"bindings": ["io1"]},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 1," in lines[0]
        assert "cfgIdIOBind(1)" in lines[1]
        assert "IO1," in lines[2]

    def test_generate_simple_proto_bindings(self, generator):
        """Test protocol builder simple binding generation."""
        proto_builder = generator._protocol_config_generator()
        lines = proto_builder.generate_simple_proto_bindings(
            "PROTO1", "serial", ["io1"]
        )
        assert lines[0] == "  PROTO1, 1,"
        assert "CProtoSerial::cfgIdIOBind(1)," in lines[1]
        assert "IO1," in lines[2]

    def test_generate_proto_config_no_bindings(self, generator):
        """Test generating protocol config with no bindings."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": [],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("TEST_PROTO", obj)
        assert "TEST_PROTO, 0," in lines[0]

    def test_generate_can_config(self, generator):
        """Test generating CAN protocol config (via handlers/proto_can)."""
        obj = ProtocolObject(
            obj_id="can1",
            proto_type="can",
            instance=1,
            bindings=[],
            config={
                "node_id": 0x100,
                "objects": [
                    {
                        "type": "push",
                        "flags": 0,
                        "can_id_start": 0x000,
                        "count": 1,
                        "bindings": ["io1"],
                    }
                ],
            },
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO, 2," in lines[0]
        assert "CProtoCan::cfgIdNodeid()" in lines[1]
        assert "0x0100," in lines[2]
        assert "CProtoCan::cfgIdIOBind(4)" in lines[4]

    def test_generate_proto_config_with_custom_fields(self, generator):
        """Test generating protocol config with custom fields like shell."""
        obj = to_proto_obj(
            {
                "type": "shell",
                "bindings": ["io1"],
                "config": {"prompt": "dawn> "},
            }
        )
        lines = generator._generate_proto_config("SHELL_PROTO", obj)
        # Should have custom config
        assert "SHELL_PROTO," in lines[0]
        # String now has size parameter
        assert "CProtoShellPretty::cfgIdPrompt(" in "".join(lines)
        # String is packed as uint32_t
        assert "0x" in "".join(lines)

    def test_generate_proto_config_with_nested_fields(self, generator):
        """Test protocol with nested fields like nimble."""
        obj = to_proto_obj(
            {
                "type": "nimble",
                "bindings": [],
                "config": {"services": {"dis": {}, "bas": {}}},
            }
        )
        lines = generator._generate_proto_config("NIMBLE_PROTO", obj)
        # Nested fields should be skipped in current implementation
        assert "NIMBLE_PROTO," in lines[0]

    def test_generate_proto_config_missing_optional_field(self, generator):
        """Test protocol config with optional field not provided."""
        obj = to_proto_obj(
            {
                "type": "shell",
                "bindings": ["io1"],
                "config": {},  # prompt field not provided
            }
        )
        lines = generator._generate_proto_config("SHELL_PROTO", obj)
        # Should handle missing optional fields
        assert "SHELL_PROTO," in lines[0]

    def test_generate_can_config_missing_optional_field(self, generator):
        """Test CAN config with missing optional fields."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "objects": [
                        {
                            "type": "push",
                            "flags": 0,
                            "can_id_start": 0x200,
                            "count": 2,
                            "bindings": ["io1", "io2"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        # Should handle missing node_id gracefully
        assert "CAN_PROTO," in lines[0]

    def test_generate_can_object_with_non_hex_field(self, generator):
        """Test CAN object with integer field that's not hex formatted."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 100,  # Non-hex value
                    "objects": [],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        # Should handle non-hex format
        assert "CAN_PROTO," in lines[0]

    def test_generate_can_object_enum_handling(self, generator):
        """Test CAN object with enum type field."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 0x100,
                    "objects": [
                        {
                            "type": "read",  # Different enum value
                            "flags": 0,
                            "can_id_start": 0x300,
                            "count": 1,
                            "bindings": ["io1"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]
        assert "READ" in "".join(lines)

    def test_generate_can_object_computed_values(self, generator):
        """Test CAN object with computed value types."""
        # handler dispatched via _generate_proto_config
        obj = to_proto_obj(
            {
                "type": "can",
                "config": {
                    "node_id": 0x100,
                    "objects": [
                        {
                            "type": "write",
                            "flags": 5,  # Non-zero flags
                            "can_id_start": 0x400,
                            "count": 3,
                            "bindings": ["io1", "io2", "io3"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]
        assert "WRITE" in "".join(lines)
        assert "3" in "".join(lines)  # count value

    def test_generate_proto_config_unknown_type(self, generator):
        """Test generating protocol config with unknown type."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "unknown_proto",
                    "bindings": [],
                    "config": {},
                }
            )

    def test_generate_proto_config_no_custom_fields(self, generator):
        """Test protocol with standard bindings but no custom fields."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1", "io2"],
                "config": {},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        # Should use simple bindings path
        assert "SERIAL_PROTO, 1," in lines[0]

    def test_generate_modbus_config_with_path_and_registers(self, generator):
        """Test Modbus RTU config generation with path/register blocks."""
        obj = to_proto_obj(
            {
                "type": "modbus_rtu",
                "bindings": ["unused_top_level_binding"],
                "config": {
                    "path": "/dev/ttyS1",
                    "registers": [
                        {
                            "type": "holding",
                            "config": 1,
                            "start": 100,
                            "bindings": ["io1", "io2"],
                        },
                        {
                            "type": "coil",
                            "config": 0,
                            "start": 200,
                            "bindings": ["io3"],
                        },
                    ],
                },
            }
        )
        assert obj.bindings == ["io1", "io2", "io3"]
        lines = generator._generate_proto_config("MODBUS_PROTO", obj)
        joined = "\n".join(lines)

        assert "MODBUS_PROTO, 2," in lines[0]
        assert "CProtoModbusRtu::cfgIdPath(" in joined
        assert "CProtoModbusRtu::cfgIdIOBind(11)" in joined
        assert "CProtoModbusRegs::MODBUS_TYPE_HOLDING, 1, 100, 2," in joined
        assert "CProtoModbusRegs::MODBUS_TYPE_COIL, 0, 200, 1," in joined
        assert "IO1," in joined
        assert "IO2," in joined
        assert "IO3," in joined

    def test_generate_modbus_tcp_config_with_port_and_registers(
        self, generator
    ):
        """Modbus TCP path uses CProtoModbusTcp and emits port + registers."""
        obj = to_proto_obj(
            {
                "type": "modbus_tcp",
                "bindings": ["unused_top_level_binding"],
                "config": {
                    "port": 502,
                    "registers": [
                        {
                            "type": "holding",
                            "config": 1,
                            "start": 100,
                            "bindings": ["io1"],
                        }
                    ],
                },
            }
        )
        lines = generator._generate_proto_config("MODBUS_TCP_PROTO", obj)
        joined = "\n".join(lines)

        assert "MODBUS_TCP_PROTO, 2," in lines[0]
        assert "CProtoModbusTcp::cfgIdPort()" in joined
        assert "502," in joined
        assert "CProtoModbusTcp::cfgIdIOBind(" in joined

    def test_modbus_register_type_map_falls_back_to_rtu_for_unknown_proto(
        self, generator
    ):
        """Unknown proto type falls back to modbus_rtu lookups."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
            get_register_type_prefix,
        )

        loader = generator.config_loader
        rtu_map = get_register_type_map(loader, "modbus_rtu")
        unknown_map = get_register_type_map(loader, "__no_such_modbus__")
        assert unknown_map == rtu_map
        assert get_register_type_prefix(
            loader, "__no_such_modbus__"
        ) == get_register_type_prefix(loader, "modbus_rtu")

    def test_generate_descriptor_array_empty(self, generator):
        """Test generating empty descriptor array."""
        generator.objects = {}
        generator.object_order = []
        lines = generator.generate_descriptor_array()
        assert "uint32_t g_dawn_desc[] =" in lines[0]
        assert "CDescriptor::DAWN_DESCRIPTOR_HDR, 0," in " ".join(lines)
        assert "CDescriptor::DAWN_DESCRIPTOR_FOOT," in " ".join(lines)

    def test_generate_descriptor_array_with_metadata(self, generator):
        """Test generating descriptor array with metadata."""
        generator.metadata = {"version": "1.0"}
        generator.objects = {}
        generator.object_order = []
        lines = generator.generate_descriptor_array()
        assert "Metadata" in " ".join(lines)
        assert "cfgIdVersion()" in " ".join(lines)
        assert "0x00010000" in " ".join(lines)

    def test_generate_metadata_config_version_only(self, generator):
        """Test metadata generation with version only."""
        generator.metadata = {"version": "2.5"}
        lines = generator._generate_metadata_config()
        assert len(lines) > 0
        assert "CDescriptor::objectId(1), 1," in lines[0]
        assert "CDescriptor::cfgIdVersion()" in " ".join(lines)
        assert "0x00020005" in " ".join(lines)

    def test_generate_metadata_config_multiple_fields(self, generator):
        """Test metadata generation with multiple fields."""
        generator.metadata = {
            "version": "1.2",
            "user_string": "custom_id",
        }
        lines = generator._generate_metadata_config()
        assert len(lines) > 0
        # Should have 2 config items (version and user_string)
        assert "CDescriptor::objectId(1), 2," in lines[0]
        assert "CDescriptor::cfgIdVersion()" in " ".join(lines)
        # Strings now have size parameter
        assert "CDescriptor::cfgIdString(" in " ".join(lines)
        # Strings are packed as uint32_t, not quoted
        joined = " ".join(lines)
        assert "0x" in joined  # Has hex values

    def test_generate_metadata_config_with_user_string(self, generator):
        """Test metadata generation with version and user string."""
        generator.metadata = {
            "version": "1.0",
            "user_string": "test_id",
        }
        lines = generator._generate_metadata_config()
        assert "CDescriptor::cfgIdVersion()" in " ".join(lines)
        assert "CDescriptor::cfgIdString(" in " ".join(lines)
        assert "0x" in " ".join(lines)  # Has hex values for packed string

    def test_generate_metadata_config_empty(self, generator):
        """Test metadata generation with empty metadata."""
        generator.metadata = {}
        lines = generator._generate_metadata_config()
        assert len(lines) == 0

    def test_generate_metadata_config_no_valid_fields(self, mocker):
        """Test metadata with fields but none are valid."""
        generator = DescriptorGenerator()

        # Mock metadata fields where all have empty cpp_helper
        mock_fields = [
            {
                "name": "broken1",
                "cpp_helper": "",
                "value_type": "string",
            },
            {
                "name": "broken2",
                "cpp_helper": "",
                "value_type": "string",
            },
        ]
        mocker.patch.object(
            generator.config_loader,
            "get_metadata_fields",
            return_value=mock_fields,
        )

        generator.metadata = {
            "broken1": "value1",
            "broken2": "value2",
        }
        lines = generator._generate_metadata_config()
        # Should return empty lines since no valid fields
        assert len(lines) == 0

    def test_generate_metadata_config_unknown_fields(self, generator):
        """Test metadata generation with unknown fields (ignored)."""
        generator.metadata = {
            "version": "1.0",
            "unknown_field": "ignored",
        }
        lines = generator._generate_metadata_config()
        # Should only generate version, unknown field ignored
        assert "CDescriptor::objectId(1), 1," in lines[0]
        assert "unknown_field" not in " ".join(lines)

    def test_generate_metadata_config_with_string_only(self, generator):
        """Test metadata generation with string only."""
        generator.metadata = {
            "user_string": "my_custom_id",
        }
        lines = generator._generate_metadata_config()
        assert "CDescriptor::objectId(1), 1," in lines[0]
        assert "CDescriptor::cfgIdString(" in " ".join(lines)
        # String should be packed as hex values
        assert "0x" in " ".join(lines)

    def test_generate_metadata_config_field_without_helper(self, mocker):
        """Test metadata field without cpp_helper (defensive code)."""
        generator = DescriptorGenerator()

        # Mock metadata fields with one missing cpp_helper
        mock_fields = [
            {
                "name": "version",
                "cpp_helper": "CDescriptor::cfgIdVersion",
                "value_type": "version",
            },
            {
                "name": "broken_field",
                "cpp_helper": "",  # Empty helper
                "value_type": "string",
            },
        ]
        mocker.patch.object(
            generator.config_loader,
            "get_metadata_fields",
            return_value=mock_fields,
        )

        generator.metadata = {
            "version": "1.0",
            "broken_field": "ignored",
        }
        lines = generator._generate_metadata_config()
        # Should only generate version, broken field skipped
        assert "CDescriptor::objectId(1), 1," in lines[0]
        assert "broken_field" not in " ".join(lines)

    def test_generate_metadata_config_unknown_value_type(self, mocker):
        """Test metadata with unknown value type (uses default)."""
        generator = DescriptorGenerator()

        # Mock metadata field with unknown value type
        mock_fields = [
            {
                "name": "custom_field",
                "cpp_helper": "CDescriptor::cfgIdCustom",
                "value_type": "unknown_type",
            },
        ]
        mocker.patch.object(
            generator.config_loader,
            "get_metadata_fields",
            return_value=mock_fields,
        )

        generator.metadata = {
            "custom_field": "raw_value",
        }
        lines = generator._generate_metadata_config()
        assert "CDescriptor::cfgIdCustom()" in " ".join(lines)
        assert "raw_value" in " ".join(lines)

    def test_generate_proto_config_with_iobind2(self, generator):
        """Test protocol config with nxscope iobind2."""
        obj = to_proto_obj(
            {
                "type": "nxscope_serial",
                "config": {
                    "iobind2": [
                        {"id": "io1", "name": "alpha"},
                        {"id": "io2", "name": "b"},
                    ]
                },
            }
        )
        lines = generator._generate_proto_config("NXSCOPE_PROTO", obj)
        assert "NXSCOPE_PROTO," in lines[0]
        assert "CProtoNxscopeSerial::cfgIdIOBind2(2)" in " ".join(lines)
        assert "IO1," in " ".join(lines)
        assert "IO2," in " ".join(lines)
        # Should have packed string data (3 words per name)
        word_lines = [line for line in lines if "0x" in line]
        assert len(word_lines) == 6

    def test_generate_proto_config_with_uint32(self, generator):
        """Test protocol config with uint32 value type."""
        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1"],
                "config": {"path": "/dev/ttyS0", "baudrate": 115200},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        assert "SERIAL_PROTO," in lines[0]
        assert "CProtoSerial::cfgIdBaud()" in " ".join(lines)
        assert "115200" in " ".join(lines)

    def test_generate_proto_config_empty_fields_with_config(self, mocker):
        """Test protocol with empty fields but has config."""
        from dawnpy.descriptor.definitions.type_info import ProtoSchema

        generator = DescriptorGenerator()

        # Mock protocol with uses_standard_bindings and empty fields
        mock_schema = ProtoSchema(
            proto_type="serial",
            uses_standard_bindings=True,
            fields=[],
        )
        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=mock_schema,
        )

        # Resolve bindings
        generator.objects = {
            "io1": {
                "id": "io1",
                "category": "IO",
                "type": "dummy",
                "instance": 1,
            },
        }
        generator.object_order = ["io1"]

        obj = to_proto_obj(
            {
                "type": "serial",
                "bindings": ["io1"],
                "config": {"unknown": "value"},
            }
        )
        lines = generator._generate_proto_config("SERIAL_PROTO", obj)
        # Should use simple bindings path since fields is empty
        assert "SERIAL_PROTO, 1," in lines[0]
        assert "IO1" in " ".join(lines)

    def test_generate_full_empty_descriptor(self, generator, tmp_path):
        """Test generating complete empty descriptor."""
        yaml_content = "---\nios: []\nprograms: []\nprotocols: []\n"
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text(yaml_content)

        cpp_code = generator.generate(str(yaml_file))
        assert "//*******************" in cpp_code
        assert "Auto-generated from empty.yaml" in cpp_code
        assert '#include "dawn/common/descriptor.hxx"' in cpp_code
        assert "using namespace dawn;" in cpp_code
        assert "uint32_t g_dawn_desc[]" in cpp_code
        assert "CDescriptor::DAWN_DESCRIPTOR_HDR" in cpp_code
        assert "size_t g_dawn_desc_size" in cpp_code

    def test_generate_full_with_io(self, generator, tmp_path):
        """Test generating complete descriptor with IO."""
        yaml_content = """
ios:
  - id: test_io
    type: dummy
    instance: 1
    dtype: bool
programs: []
protocols: []
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        cpp_code = generator.generate(str(yaml_file))
        assert "#define TEST_IO" in cpp_code
        assert "CIODummy::objectId" in cpp_code
        assert '#include "dawn/io/dummy.hxx"' in cpp_code


class TestGenerateDescriptor:
    """Test generate_descriptor function."""

    def test_generate_to_stdout(self, tmp_path, capsys):
        """Test generating descriptor to stdout."""
        yaml_content = "---\nios: []\nprograms: []\nprotocols: []\n"
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generate_descriptor(str(yaml_file), None)
        captured = capsys.readouterr()
        assert "Auto-generated from test.yaml" in captured.out
        assert "uint32_t g_dawn_desc[]" in captured.out

    def test_generate_to_file(self, tmp_path):
        """Test generating descriptor to file."""
        yaml_content = "---\nios: []\nprograms: []\nprotocols: []\n"
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        output_file = tmp_path / "output.cxx"
        generate_descriptor(str(yaml_file), str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "Auto-generated from test.yaml" in content
        assert "uint32_t g_dawn_desc[]" in content


class TestRealDescriptors:
    """Test with real descriptor YAML files."""

    def test_empty_tests_descriptor(self, tmp_path):
        """Test generating empty tests descriptor."""
        yaml_content = """
# Dawn Descriptor - Minimal/Empty Test Configuration
metadata:
  version: "1.0"

ios: []
programs: []
protocols: []
"""
        yaml_file = tmp_path / "descriptor.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        # Verify structure
        assert "CDescriptor::DAWN_DESCRIPTOR_HDR, 1," in cpp_code
        assert "Metadata" in cpp_code
        assert "cfgIdVersion()" in cpp_code
        assert "0x00010000" in cpp_code

    def test_simple_can_descriptor(self, tmp_path):
        """Test generating simple CAN descriptor."""
        yaml_content = """
metadata:
  version: "1.0"

ios:
  - &dummy1
    id: can_dummy1
    type: dummy
    instance: 1
    dtype: bool

protocols:
  - id: can_main
    type: can
    instance: 1
    config:
      node_id: 0x100
      objects:
        - type: push
          can_id_start: 0x000
          count: 1
          bindings:
            - *dummy1
"""
        yaml_file = tmp_path / "descriptor.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        # Verify IOs
        assert "#define CAN_DUMMY1" in cpp_code
        assert "CIODummy::objectId" in cpp_code

        # Verify CAN protocol
        assert "#define CAN_MAIN" in cpp_code
        assert "CProtoCan::objectId" in cpp_code
        assert "cfgIdNodeid()" in cpp_code
        assert "0x0100" in cpp_code
        assert "CAN_TYPE_PUSH" in cpp_code

        # Verify includes
        assert '#include "dawn/io/dummy.hxx"' in cpp_code
        assert '#include "dawn/proto/can/can.hxx"' in cpp_code


class TestYAMLAnchors:
    """Test YAML anchor/alias handling."""

    def test_anchor_resolution_in_program(self, tmp_path):
        """Test YAML anchor resolution in program bindings."""
        yaml_content = """
ios:
  - &io1
    id: test_io
    type: dummy
    instance: 1
    dtype: bool

programs:
  - id: test_prog
    type: stats
    instance: 1
    inputs:
      - *io1
    outputs: []
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        # Verify anchor was resolved
        assert "TEST_IO," in cpp_code
        assert "TEST_PROG" in cpp_code

    def test_anchor_resolution_in_protocol(self, tmp_path):
        """Test YAML anchor resolution in protocol bindings."""
        yaml_content = """
ios:
  - &io1
    id: test_io
    type: dummy
    instance: 1
    dtype: bool

protocols:
  - id: test_proto
    type: serial
    instance: 1
    bindings:
      - *io1
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        # Verify anchor was resolved
        assert "TEST_IO," in cpp_code
        assert "cfgIdIOBind(1)" in cpp_code


class TestIOWithConfig:
    """Test IO objects with various configuration options."""

    def test_io_with_multiple_config(self, tmp_path):
        """Test IO with both device and interval config."""
        yaml_content = """
ios:
  - id: test_ts
    type: timestamp
    instance: 1
    dtype: uint64
    config:
      device: 0
      interval_us: 500000
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "TEST_TS, 2," in cpp_code
        assert "CIOCommon::cfgIdDevno()" in cpp_code
        assert "0," in cpp_code
        assert "CIOTimestamp::cfgInterval" in cpp_code
        assert "500000," in cpp_code


class TestShellProtocol:
    """Test shell protocol generation."""

    def test_shell_with_bindings(self, tmp_path):
        """Test shell protocol with IO bindings."""
        yaml_content = """
ios:
  - &io1
    id: dummy1
    type: dummy
    instance: 1
    dtype: bool

protocols:
  - id: shell1
    type: shell
    instance: 1
    bindings:
      - *io1
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "CProtoShellPretty::cfgIdIOBind(1)" in cpp_code

    def test_shell_without_bindings(self, tmp_path):
        """Test shell protocol without bindings."""
        yaml_content = """
protocols:
  - id: shell1
    type: shell
    instance: 1
    bindings: []
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "SHELL1, 0," in cpp_code


class TestIOTypes:
    """Test various IO type generations."""

    def test_sensor_io_generation(self, tmp_path):
        """Test sensor IO with subtype."""
        yaml_content = """
ios:
  - id: temp_sensor
    type: sensor
    subtype: temp
    instance: 1
    dtype: float
    timestamp: true
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "CIOSensor::objectIdTemp" in cpp_code
        assert "DTYPE_FLOAT" in cpp_code

    def test_variant_io_generation(self, tmp_path):
        """Test IO with variant (sysinfo)."""
        yaml_content = """
ios:
  - id: uptime
    type: sysinfo
    variant: uptime
    instance: 1
    dtype: uint64
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "CIOSysinfo::objectIdUptime" in cpp_code


class TestConfigLoader:
    """Test configuration loader functionality."""

    def test_proto_uses_standard_bindings(self):
        """Test checking if protocol uses standard bindings."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        assert loader.proto_uses_standard_bindings("serial") is True
        assert loader.proto_uses_standard_bindings("can") is False
        assert loader.proto_uses_standard_bindings("modbus_rtu") is False

    def test_proto_uses_standard_bindings_unknown(self):
        """Test checking unknown protocol type."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        assert loader.proto_uses_standard_bindings("unknown_proto") is False

    def test_get_proto_config_schema(self):
        """Test getting protocol config schema."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        can_schema = loader.get_proto_config_schema("can")
        assert can_schema is not None
        assert isinstance(can_schema.fields, list)

    def test_get_io_config_fields(self):
        """Test getting IO config fields."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        timestamp_fields = loader.get_io_config_fields("timestamp")
        assert len(timestamp_fields) > 0

    def test_get_prog_config_fields(self):
        """Test getting program config fields."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        stats_fields = loader.get_prog_config_fields("stats")
        assert len(stats_fields) > 0

    def test_get_prog_config_fields_unknown_user_type(self):
        """Unknown PROG type yields the standard fields with no extras."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        standard = loader.get_prog_standard_fields()
        unknown = loader.get_prog_config_fields("__no_such_prog__")
        assert unknown == standard


class TestProtoGeneratorRegistry:
    """Validate the proto handler registry shape."""

    def test_get_metadata_fields(self):
        """Test getting metadata fields."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        metadata_fields = loader.get_metadata_fields()
        assert len(metadata_fields) > 0
        # Verify version field exists
        version_field = next(
            (f for f in metadata_fields if f["name"] == "version"), None
        )
        assert version_field is not None
        assert version_field["value_type"] == "version"

    def test_load_metadata_fields_failure_raises_runtimeerror(
        self, monkeypatch
    ):
        """Test metadata header load failure is wrapped as RuntimeError."""
        from dawnpy.descriptor.definitions import loader as loader_mod
        from dawnpy.descriptor.definitions.loader import ConfigLoader
        from dawnpy.headerdefs import HeaderDefsError

        monkeypatch.setattr(
            loader_mod.header_bundle,
            "load_header_bundle",
            lambda: (_ for _ in ()).throw(HeaderDefsError("boom")),
        )
        with pytest.raises(RuntimeError, match="header definitions"):
            ConfigLoader()

    def test_config_loader_reuses_one_header_definition_set(self, monkeypatch):
        """ConfigLoader should not call the header bundle per subsection."""
        from dawnpy.descriptor.definitions import loader as loader_mod
        from dawnpy.descriptor.definitions.loader import ConfigLoader
        from dawnpy.headerdefs.bundle import (
            HeaderBundle,
            HeaderDefinitionGroups,
        )

        calls = 0

        def _load_defs() -> HeaderBundle:
            nonlocal calls
            calls += 1
            return HeaderBundle(
                HeaderDefinitionGroups(
                    header_defs={"dtype": []},
                    type_defs={
                        "io_types": [],
                        "prog_types": [],
                        "proto_types": [],
                    },
                    metadata_defs=[{"name": "version"}],
                )
            )

        monkeypatch.setattr(
            loader_mod.header_bundle,
            "load_header_bundle",
            _load_defs,
        )
        loader = ConfigLoader()

        assert calls == 1
        assert loader.metadata_fields == [{"name": "version"}]

    def test_builtin_io_hydrates_enum_values_from_headers(self, monkeypatch):
        """builtin_types/io_family hydrates enum_prefix via headerdefs."""
        from dawnpy.descriptor.definitions import io_family as builtin_io_mod
        from dawnpy.headerdefs.bundle import (
            HeaderBundle,
            HeaderDefinitionGroups,
            HeaderLookupFunctions,
        )
        from tests.conftest import minimal_header_definition_set

        base = minimal_header_definition_set()
        defs = HeaderBundle(
            HeaderDefinitionGroups(
                header_defs=base.header_defs,
                type_defs=base.type_defs,
                metadata_defs=base.metadata_defs,
                component_defs=base.component_defs,
            ),
            HeaderLookupFunctions(
                enum_map_loader=lambda owner, prefix: {
                    "start": "START",
                    "stop": "STOP",
                }
            ),
        )
        indexed = builtin_io_mod._index_fields_by_type(defs)
        # control.allowed has enum_prefix CIOControl::CTRL_ALLOW_
        allowed = next(f for f in indexed["control"] if f.name == "allowed")
        assert allowed.enum_values == {"start": "START", "stop": "STOP"}

    def test_builtin_proto_hydrates_nested_element_fields(self, monkeypatch):
        """builtin_types/proto_family hydrates enum_prefix in nested fields."""
        from dawnpy.descriptor.definitions import (
            proto_family as builtin_proto_mod,
        )
        from dawnpy.headerdefs.bundle import (
            HeaderBundle,
            HeaderDefinitionGroups,
            HeaderLookupFunctions,
        )
        from tests.conftest import minimal_header_definition_set

        base = minimal_header_definition_set()
        defs = HeaderBundle(
            HeaderDefinitionGroups(
                header_defs=base.header_defs,
                type_defs=base.type_defs,
                metadata_defs=base.metadata_defs,
                component_defs=base.component_defs,
            ),
            HeaderLookupFunctions(
                enum_map_loader=lambda owner, prefix: {"push": "PUSH"}
            ),
        )
        entries = builtin_proto_mod._index_proto_entries(defs)
        objects = next(f for f in entries["can"].fields if f.name == "objects")
        type_field = next(
            f for f in objects.element_fields if f.name == "type"
        )
        assert type_field.enum_values == {"push": "PUSH"}

    def test_get_proto_nested_enum_map_and_prefix(self):
        """Test nested enum map loading for Modbus register type."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        enum_map = loader.get_proto_nested_enum_map(
            "modbus_rtu", "registers", "type"
        )
        enum_prefix = loader.get_proto_nested_enum_prefix(
            "modbus_rtu", "registers", "type"
        )
        assert enum_map.get("holding") == "HOLDING"
        assert enum_prefix == "CProtoModbusRegs::MODBUS_TYPE_"

    def test_get_proto_nested_enum_map_and_prefix_unknown(self):
        """Test nested enum accessors for unknown schema."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        enum_map = loader.get_proto_nested_enum_map(
            "unknown_proto", "registers", "type"
        )
        enum_prefix = loader.get_proto_nested_enum_prefix(
            "unknown_proto", "registers", "type"
        )
        assert enum_map == {}
        assert enum_prefix == ""

    def test_get_proto_nested_enum_map_and_prefix_no_match(self):
        """Test nested enum accessors when schema exists but fields differ."""
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        enum_map = loader.get_proto_nested_enum_map(
            "modbus_rtu", "missing_field", "type"
        )
        enum_prefix = loader.get_proto_nested_enum_prefix(
            "modbus_rtu", "missing_field", "type"
        )
        assert enum_map == {}
        assert enum_prefix == ""


class TestEdgeCases:
    """Test edge cases and defensive code paths."""

    def test_custom_proto_config_with_missing_field(self, mocker):
        """Test custom proto config when field is missing from config."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"field1": 42},
                }
            )

    def test_custom_proto_config_with_nested_field(self, mocker):
        """Test custom proto config with nested field."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"nested_config": {"key": "value"}},
                }
            )

    def test_custom_proto_config_with_int_hex(self, mocker):
        """Test custom proto config with int hex format."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"hex_value": 0x1234},
                }
            )

    def test_custom_proto_config_with_non_standard_type(self, mocker):
        """Test custom proto config with non-int, non-string value."""
        from dawnpy.descriptor.definitions.objects import DescriptorDecodeError

        with pytest.raises(DescriptorDecodeError):
            to_proto_obj(
                {
                    "type": "test_proto",
                    "bindings": [],
                    "config": {"other_value": 42.5},
                }
            )

    def test_can_config_with_none_schema(self, mocker):
        """Test CAN config when schema is None."""
        generator = DescriptorGenerator()
        # handler dispatched via _generate_proto_config

        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=None,
        )

        obj = to_proto_obj(
            {
                "type": "can",
                "bindings": [],
                "config": {"node_id": 0x100},
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO, 0," in lines[0]

    def test_can_config_with_non_hex_simple_field(self, mocker):
        """Test CAN config with non-hex simple field."""
        from dawnpy.descriptor.definitions.type_info import ProtoSchema

        generator = DescriptorGenerator()
        # handler dispatched via _generate_proto_config

        mock_schema = ProtoSchema(
            proto_type="can",
            uses_standard_bindings=False,
            fields=[
                ConfigField(
                    name="simple_int",
                    cpp_helper="CProtoCan::cfgIdSimple",
                    value_type="int",
                    # No format specified, not hex
                ),
            ],
        )
        mocker.patch.object(
            generator.config_loader,
            "get_proto_config_schema",
            return_value=mock_schema,
        )

        obj = to_proto_obj(
            {
                "type": "can",
                "bindings": [],
                "config": {"simple_int": 100},
            }
        )
        lines = generator._generate_proto_config("CAN_PROTO", obj)
        assert "CAN_PROTO," in lines[0]

    def test_can_object_without_bindings_field(self, mocker):
        """CAN element_fields without a bindings entry yields no lines."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [ConfigField(name="type", value_type="enum")]
        obj_config = {"type": "push", "bindings": ["io1"]}
        assert _generate_can_object(obj_config, element_fields, gctx) == []

    def test_can_object_without_size_calculation(self, mocker):
        """CAN element_fields without size_calculation falls back to count."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
            ),
        ]
        obj_config = {"bindings": ["io1", "io2"]}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert len(lines) > 0

    def test_can_object_with_non_standard_value_type(self, mocker):
        """CAN object element with non-int, non-enum value type."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
                size_calculation="2 + count",
            ),
            ConfigField(name="custom_field", value_type="custom"),
        ]
        obj_config = {"bindings": ["io1"], "custom_field": "custom_value"}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert len(lines) > 0

    def test_can_object_with_non_hex_int_field(self, mocker):
        """CAN object element with a decimal integer value."""
        from dawnpy.descriptor.handlers.proto_can import _generate_can_object

        generator = DescriptorGenerator()
        gctx = generator._protocol_config_generator().ctx
        element_fields = [
            ConfigField(
                name="bindings",
                cpp_helper="CProtoCan::cfgIdIOBind",
                value_type="id_array",
                size_calculation="2 + count",
            ),
            ConfigField(name="custom_int", value_type="int"),
        ]
        obj_config = {"bindings": ["io1"], "custom_int": 17}
        lines = _generate_can_object(obj_config, element_fields, gctx)
        assert any("17," in line for line in lines)

    def test_map_dtype_to_initval_param(self):
        """Test dtype to SObjectId::DTYPE_* enum-value mapping."""

        def get_param(dtype):
            return to_io_obj({"dtype": dtype}).initval_param

        assert get_param("bool") == 1
        assert get_param("int8") == 2
        assert get_param("uint8") == 3
        assert get_param("int16") == 4
        assert get_param("uint16") == 5
        assert get_param("int32") == 6
        assert get_param("uint32") == 7
        assert get_param("int64") == 8
        assert get_param("uint64") == 9
        assert get_param("float") == 10
        assert get_param("double") == 11
        # Unknown dtype now raises rather than silently defaulting.
        with pytest.raises(ValueError, match="No SObjectId DTYPE mapping"):
            get_param("unknown")

    def test_map_dtype_to_cpp(self):
        """Test dtype to C++ enum mapping."""

        def get_cpp(dtype):
            return to_io_obj({"dtype": dtype}).dtype_cpp

        assert get_cpp("bool") == "SObjectId::DTYPE_BOOL"
        assert get_cpp("unknown") == "SObjectId::DTYPE_UINT32"

    def test_to_proto_obj_helper(self):
        """Test to_proto_obj helper coverage."""
        obj = to_proto_obj({"type": "can", "bindings": ["io1"]})
        assert obj.proto_type == "can"
        assert "io1" in obj.bindings

    def test_io_allowed_flag_map_from_config(self):
        """Test IO allow-flag enums are loaded from config."""
        from dawnpy.descriptor.handlers import io_control, io_trigger

        control_map = io_control.allowed_symbols
        trigger_map = io_trigger.allowed_symbols
        assert control_map["start"] == "CIOControl::CTRL_ALLOW_START"
        assert control_map["stop"] == "CIOControl::CTRL_ALLOW_STOP"
        assert trigger_map["trigger1"] == "CIOTrigger::TRIG_ALLOW_TRIGGER1"
        assert trigger_map["reset"] == "CIOTrigger::TRIG_ALLOW_RESET"

    def test_io_allowed_symbols_are_handler_owned(self):
        """Test allow-flag mappings live in the IO handlers."""
        from dawnpy.descriptor.handlers import io_control, io_dummy, io_trigger

        control_map = io_control.allowed_symbols
        trigger_map = io_trigger.allowed_symbols
        assert control_map["start"] == "CIOControl::CTRL_ALLOW_START"
        assert trigger_map["trigger3"] == "CIOTrigger::TRIG_ALLOW_TRIGGER3"
        assert not hasattr(io_dummy, "allowed_symbols")

    def test_config_loader_typed_io_fields(self):
        """Test typed IO field schemas are loaded."""
        generator = DescriptorGenerator()
        fields = generator.config_loader.get_io_config_fields("control")
        assert any(
            field.name == "allowed" and "start" in field.enum_values
            for field in fields
        )

    def test_config_loader_typed_proto_schema(self):
        """Test typed protocol schema wrapper."""
        generator = DescriptorGenerator()
        can_schema = generator.config_loader.get_proto_config_schema("can")
        missing = generator.config_loader.get_proto_config_schema(
            "missing_proto"
        )
        assert can_schema is not None
        assert isinstance(can_schema.uses_standard_bindings, bool)
        assert missing is None

    def test_config_field_fixed_bytes(self):
        """Test ConfigField fixed-byte values."""
        schema = ConfigField(
            name="names",
            cpp_helper="Cfg::X",
            value_type="string_array",
            value_format="hex",
            string_fixed_bytes=8,
        )
        assert schema.value_format == "hex"
        assert schema.string_fixed_bytes == 8

    def test_format_float_as_hex(self):
        """Test float to hex formatting."""
        generator = DescriptorGenerator()
        helper = generator._format_helper
        assert helper.format_float_as_hex(-1.1) == "0xbf8ccccd"
        assert helper.format_float_as_hex(100.0) == "0x42c80000"
        assert helper.format_float_as_hex(50.0) == "0x42480000"
        assert helper.format_float_as_hex(0.0) == "0x00000000"

    def test_generate_io_config_with_init_value_float(self):
        """Test IO config generation with init_value for float."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "float",
                "config": {"init_value": -1.1},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # float -> SObjectId::DTYPE_FLOAT = 10
        assert any("cfgIdInitval(10, false, 1)" in line for line in lines)
        assert any("0xbf8ccccd" in line for line in lines)

    def test_generate_io_config_with_init_value_int32(self):
        """Test IO config generation with init_value for int32."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int32",
                "config": {"init_value": 100},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int32 -> SObjectId::DTYPE_INT32 = 6
        assert any("cfgIdInitval(6, false, 1)" in line for line in lines)
        assert any("100," in line for line in lines)

    def test_generate_io_config_with_init_value_negative_int(self):
        """Test IO config generation with negative int init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int32",
                "config": {"init_value": -20},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int32 -> SObjectId::DTYPE_INT32 = 6
        assert any("cfgIdInitval(6, false, 1)" in line for line in lines)
        assert any("(uint32_t)-20," in line for line in lines)

    def test_generate_io_config_with_init_value_bool(self):
        """Test IO config generation with bool init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "bool",
                "config": {"init_value": True},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # bool -> SObjectId::DTYPE_BOOL = 1
        assert any("cfgIdInitval(1, false, 1)" in line for line in lines)
        assert any("true," in line for line in lines)

    def test_generate_io_config_with_dummy_dim(self):
        """Test IO config generation with explicit dummy dimension."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"dim": 4},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        assert any("CIODummy::cfgIdDim()" in line for line in lines)
        assert any("4," in line for line in lines)

    def test_generate_io_config_with_init_value_list(self):
        """Test IO config generation with list-valued init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"dim": 4, "init_value": [1, 2, 3, 4]},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint32 -> SObjectId::DTYPE_UINT32 = 7; dim is the value count.
        assert any("cfgIdInitval(7, false, 4)" in line for line in lines)
        assert lines.count("      1,") >= 1
        assert lines.count("      4,") >= 1

    def test_generate_io_config_with_init_value_uint64(self):
        """Test IO config generation with uint64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint64",
                "config": {"init_value": 0x0123456789ABCDEF},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint64 -> SObjectId::DTYPE_UINT64 = 9; the C++ helper doubles
        # the resulting cfgid size for 64-bit dtypes, so dim is the
        # value count (1) here even though the data takes two words.
        assert any("cfgIdInitval(9, false, 1)" in line for line in lines)
        assert any("0x89abcdef" in line for line in lines)
        assert any("0x01234567" in line for line in lines)

    def test_generate_io_config_with_init_value_uint64_list(self):
        """Test IO config generation with list-valued uint64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint64",
                "config": {
                    "dim": 2,
                    "init_value": [
                        0x0123456789ABCDEF,
                        0xFEDCBA9876543210,
                    ],
                },
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # uint64 list of 2 values -> dim = 2 (value count).
        assert any("cfgIdInitval(9, false, 2)" in line for line in lines)
        assert any("0x89abcdef" in line for line in lines)
        assert any("0x01234567" in line for line in lines)
        assert any("0x76543210" in line for line in lines)
        assert any("0xfedcba98" in line for line in lines)

    def test_generate_io_config_with_init_value_int64(self):
        """Test IO config generation with int64 init_value."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "int64",
                "config": {"init_value": -2},
            }
        )
        lines = generator._generate_io_config("DUMMY1", obj)
        # int64 -> SObjectId::DTYPE_INT64 = 8.
        assert any("cfgIdInitval(8, false, 1)" in line for line in lines)
        assert any("0xfffffffe" in line for line in lines)
        assert any("0xffffffff" in line for line in lines)

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

    def test_io_config_generator_default_param_fallbacks(self):
        """Test default_params fallback for unhandled custom params."""
        generator = DescriptorGenerator()

        class FakeConfigLoader:
            def get_io_config_fields(self, io_type):
                if io_type != "dummy":
                    return []
                return [
                    ConfigField(
                        name="custom",
                        cpp_helper="CFake::cfg",
                        value_type="int",
                        params=["custom_bool", "custom_int"],
                        default_params=[True, 9],
                    )
                ]

        helper = IoConfigGenerator(
            config_loader=FakeConfigLoader(),
            format_helper=generator._format_helper,
            objects=lambda: generator.objects,
            config_rw_grants=lambda: {},
        )
        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"custom": 5},
            }
        )
        lines = helper.generate_io_config("DUMMY1", obj)
        assert any("CFake::cfg(true, 9)" in line for line in lines)
        assert any("      5," == line for line in lines)

        other_obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {},
            }
        )
        assert helper.generate_io_config("GPI1", other_obj) == ["  GPI1, 0,"]

    def test_generate_io_config_with_device_int(self):
        """Test IO config generation with device field (int type)."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {"device": 5},
            },
            obj_id="gpi1",
        )
        lines = generator._generate_io_config("GPI1", obj)
        assert any("cfgIdDevno()" in line for line in lines)
        # Device should be formatted as int, not bool
        assert any("5," in line for line in lines)
        assert not any("true," in line for line in lines)

    def test_generate_io_config_value_type_precedence(self):
        """Test that field value_type takes precedence over object dtype."""
        generator = DescriptorGenerator()
        obj = to_io_obj(
            {
                "type": "gpi",
                "dtype": "bool",
                "config": {"device": 0},
            },
            obj_id="gpi1",
        )
        lines = generator._generate_io_config("GPI1", obj)
        # Should format device as integer 0, not boolean false
        assert any("0," in line for line in lines)
        assert not any("false," in line for line in lines)

    def test_generate_io_config_default_formatting(self, mocker):
        """Test IO config default value formatting fallback."""
        generator = DescriptorGenerator()

        # Mock config loader to return a field with unknown value_type
        mock_fields = [
            ConfigField(
                name="custom_field",
                cpp_helper="TestIO::cfgIdCustom",
                value_type="unknown_type",  # Not int, not auto
            )
        ]
        mocker.patch.object(
            generator.config_loader,
            "get_io_config_fields",
            return_value=mock_fields,
        )

        obj = to_io_obj(
            {
                "type": "dummy",
                "dtype": "uint32",
                "config": {"custom_field": "custom_value"},
            },
            obj_id="test1",
        )
        lines = generator._generate_io_config("TEST1", obj)
        # Should use default formatting
        assert any("custom_value," in line for line in lines)

    def test_generate_custom_proto_config_with_bindings(self):
        """Test generic custom protocol config with bindings."""
        generator = DescriptorGenerator()

        obj = to_proto_obj(
            {
                "type": "nxscope_serial",
                "config": {
                    "iobind2": [
                        {"id": "sensor1", "name": "a"},
                        {"id": "sensor2", "name": "b"},
                        {"id": "sensor3", "name": "c"},
                    ]
                },
            }
        )

        fields = [
            ConfigField(
                name="iobind2",
                cpp_helper="CProtoNxscopeSerial::cfgIdIOBind2",
                value_type="nxscope_iobind2",
            )
        ]

        proto_builder = generator._protocol_config_generator()
        lines = proto_builder._generic.generate(
            "NXSCOPE1", "nxscope_serial", obj, fields
        )

        # Should have 1 config item (iobind2)
        assert "NXSCOPE1, 1," in lines[0]
        assert any("cfgIdIOBind2(3)" in line for line in lines)
        assert any("SENSOR1," in line for line in lines)

    def test_registered_protocol_handlers(self):
        """Per-type proto handlers are registered in PROTO_HANDLER_REGISTRY."""
        from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

        assert "can" in PROTO_HANDLER_REGISTRY
        assert "modbus_rtu" in PROTO_HANDLER_REGISTRY
        assert "nimble" in PROTO_HANDLER_REGISTRY
        assert "nxscope_serial" in PROTO_HANDLER_REGISTRY

    def test_dispatch_uses_registered_handler(self, monkeypatch):
        """generate_proto_config routes to the registered generate_cpp."""
        from dawnpy.descriptor.handlers import (
            PROTO_HANDLER_REGISTRY,
            proto_can,
        )

        generator = DescriptorGenerator()
        obj = to_proto_obj({"type": "can", "bindings": [], "config": {}})

        def fake_generate(macro_name, obj_inst, gctx):
            assert macro_name == "CAN1"
            assert isinstance(obj_inst, ProtocolObject)
            assert obj_inst.proto_type == "can"
            return ["  CAN1, 123,"]

        monkeypatch.setattr(proto_can, "generate_cpp", fake_generate)
        # The registry stores handler instances that delegate to modules.
        assert PROTO_HANDLER_REGISTRY["can"].generate_cpp is fake_generate
        lines = generator._generate_proto_config("CAN1", obj)
        assert lines == ["  CAN1, 123,"]

    def test_modbus_register_type_map_comes_from_schema(self):
        """Test modbus type mapping is derived from YAML schema."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
        )

        generator = DescriptorGenerator()
        type_map = get_register_type_map(generator.config_loader, "modbus_rtu")
        assert type_map.get("holding") == "HOLDING"
        assert type_map.get("coil") == "COIL"

    def test_modbus_register_type_map_fallback(self, monkeypatch):
        """Test modbus type map fallback when schema data is missing."""
        from dawnpy.descriptor.handlers._proto_modbus_common import (
            get_register_type_map,
        )

        generator = DescriptorGenerator()
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_nested_enum_map",
            lambda proto, nested, element: {},
        )
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_nested_enum_prefix",
            lambda proto, nested, element: "",
        )
        type_map = get_register_type_map(generator.config_loader, "modbus_rtu")
        assert type_map.get("holding") is None

    def test_proto_uses_standard_bindings_without_schema(self, monkeypatch):
        """Test protocol binding fallback when schema lookup returns none."""
        generator = DescriptorGenerator()
        monkeypatch.setattr(
            generator.config_loader,
            "get_proto_config_schema",
            lambda _: None,
        )
        assert generator._proto_uses_standard_bindings("unknown") is False

    def test_generate_generic_proto_field_without_cpp_helper(self):
        """Test generic proto field skip when helper is missing."""
        generator = DescriptorGenerator()
        field = ConfigField(name="f", value_type="int")
        proto_gen = generator._protocol_config_generator()
        assert proto_gen._generic.generate_generic_field(10, field) == []

    def test_generate_nxscope_iobind2_field_wrapper(self):
        """Test nxscope_iobind2 wrapper delegates and formats output."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()._generic
        lines = proto_gen.generate_nxscope_iobind2_field(
            value=[{"id": "io1", "name": "chan1"}, "io2"],
            field=ConfigField(name="iobind2", string_fixed_bytes=8),
            cpp_helper="CProtoNxscope::cfgIdIOBind2",
        )
        assert lines[0] == "    CProtoNxscope::cfgIdIOBind2(2),"
        assert "      IO1," in lines
        assert "      IO2," in lines

    def test_count_nimble_config_items(self):
        """Nimble emits 1 item per gap_name + 1 per enabled service."""
        from dawnpy.descriptor.handlers import proto_nimble

        generator = DescriptorGenerator()
        obj = to_proto_obj(
            {
                "type": "nimble",
                "bindings": [],
                "config": {
                    "gap_name": "ble-dev",
                    "services": {"dis": {}, "bas": {}},
                },
            }
        )
        gctx = generator._protocol_config_generator().ctx
        lines = proto_nimble.generate_cpp("NIMBLE1", obj, gctx)
        # First line is "  NIMBLE1, <count>,"
        # 1 (gap_name) + 2 (services dis + bas) = 3
        assert lines[0].strip() == "NIMBLE1, 3,"

    def test_count_generic_proto_config_items(self):
        """Test counting with standard bindings and nested fields."""
        generator = DescriptorGenerator()
        fields = [
            ConfigField(name="a"),
            ConfigField(name="b", nested=True),
            ConfigField(name="c"),
        ]
        config = {"a": 1, "b": {"x": 1}}
        count = (
            generator._protocol_config_generator()._generic.count_config_items(
                fields, config, uses_standard=True, bindings=["io1"]
            )
        )
        assert count == 2

    def test_pack_string_array_field_words_mode(self):
        """Test string-array packing default size mode (words)."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()
        (
            size,
            words,
        ) = proto_gen._generic.pack_string_array_field(
            ["ab"],
            ConfigField(name="names", value_type="string_array"),
        )
        assert size == len(words)
        assert size > 0

    def test_generate_generic_proto_field_int_hex_branch(self):
        """Test generic proto int field formatting in hex mode."""
        generator = DescriptorGenerator()
        proto_gen = generator._protocol_config_generator()
        lines = proto_gen._generic.generate_generic_field(
            value=4660,
            field=ConfigField(
                name="hex_value",
                cpp_helper="CProtoDummy::cfgIdHex",
                value_type="int",
                value_format="hex",
            ),
        )
        assert any("CProtoDummy::cfgIdHex()" in line for line in lines)
        assert any("0x1234" in line for line in lines)

    def test_prog_config_from_config_section(self):
        """Test that program inputs/outputs come from config section."""
        generator = DescriptorGenerator()

        # Simulate parsing a program with inputs/outputs in config
        prog_spec = {
            "id": "stats1",
            "type": "stats",
            "instance": 1,
            "config": {
                "inputs": ["sensor1", "sensor2"],
                "outputs": ["output1"],
            },
        }

        # Manually call the parsing logic
        generator.objects = {}
        generator.object_order = []
        config = prog_spec.get("config", {})
        inputs = generator._resolve_references(config.get("inputs", []))
        outputs = generator._resolve_references(config.get("outputs", []))

        # Verify the references are resolved correctly
        assert inputs == ["sensor1", "sensor2"]
        assert outputs == ["output1"]


def test_pack_fixed_string_truncation():
    generator = DescriptorGenerator()
    words = generator._format_helper.pack_fixed_string(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 4
    )
    assert len(words) == 1


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


def test_generate_proto_config_handles_special_fields(monkeypatch):
    from dawnpy.descriptor.definitions.type_info import ProtoSchema

    generator = DescriptorGenerator()
    schema = ProtoSchema(
        proto_type="nxscope_dummy",
        uses_standard_bindings=False,
        fields=[
            ConfigField(
                name="iobind2",
                cpp_helper="CProtoNxscope::cfgIdIOBind2",
                value_type="nxscope_iobind2",
                string_fixed_bytes=8,
            ),
            ConfigField(
                name="names",
                cpp_helper="CProtoNxscope::cfgIdNames",
                value_type="string_array",
                string_fixed_bytes=4,
                string_array_size="count",
            ),
            ConfigField(
                name="extra_names",
                cpp_helper="CProtoNxscope::cfgIdExtra",
                value_type="string_array",
            ),
        ],
    )

    monkeypatch.setattr(
        generator.config_loader,
        "get_proto_config_schema",
        lambda proto_type: schema if proto_type == "nxscope_dummy" else None,
    )

    obj = to_proto_obj(
        {
            "type": "nxscope_dummy",
            "bindings": ["io1"],
            "config": {
                "iobind2": [
                    "io1",
                    {"id": "io2"},
                    {"io": "io3"},
                    {"ref": "io4"},
                    123,
                ],
                "names": ["alpha", "beta", "a"],
                "extra_names": ["x"],
            },
        }
    )

    lines = generator._generate_proto_config("NX1", obj)
    assert any("cfgIdIOBind2" in line for line in lines)
    assert any("cfgIdNames" in line for line in lines)
    assert any("cfgIdExtra" in line for line in lines)


class TestProgramConfigGenerator:
    """Test ProgramConfigGenerator class."""

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

    def test_emit_gateway_iobind(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        # Successful case
        lines = []
        cpp_helper = "CProgGateway::cfgIdIOBind"
        config = {
            "iobind": [{"io1": "io1", "io2": "io2", "flags": 1, "dim": 2}]
        }
        prog_gen._emit_gateway_iobind(lines, cpp_helper, "iobind", config)
        assert "    CProgGateway::cfgIdIOBind(4)," in lines[0]

        # Negative cases for coverage
        lines = []
        config = {
            "iobind": [
                "not_a_dict",
                {"io1": "io1"},  # missing io2
                {"io1": "io1", "io2": None},  # invalid io2
            ]
        }
        prog_gen._emit_gateway_iobind(lines, cpp_helper, "iobind", config)
        assert "    CProgGateway::cfgIdIOBind(0)," in lines[0]

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

    def test_emit_adjust_params(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgAdjust::cfgParams"
        config = {"params": {"offset": 3, "scale": 2}}
        prog_gen._emit_adjust_params(lines, cpp_helper, "params", config)
        assert lines == [
            "    CProgAdjust::cfgParams(),",
            "      3,",
            "      2,",
        ]

    def test_emit_adjust_iobind(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="adjust1",
            prog_type="adjust",
            instance=0,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={"params": {"offset": 3, "scale": 2}},
        )
        lines = []

        prog_gen._emit_adjust_iobind(lines, obj)

        assert lines == [
            "    CProgAdjust::cfgIdIOBind(),",
            "      SRC0,",
            "      VIRT0,",
        ]

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

    def test_emit_sequencer_states(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        lines = []
        cpp_helper = "CProgSequencer::cfgIdStates"
        config = {
            "states": [
                {"value": 1, "dwell_us": 500000},
                {"value": "2", "dwell_us": "600000"},
            ]
        }
        prog_gen._emit_sequencer_states(lines, cpp_helper, "states", config)
        assert lines == [
            "    CProgSequencer::cfgIdStates(4),",
            "      1,",
            "      500000,",
            "      2,",
            "      600000,",
        ]

    def test_generate_prog_config_stats(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="prog1",
            prog_type="stats",
            instance=0,
            inputs=["io1"],
            outputs=["io2"],
            reset=None,
            config={},
        )
        lines = prog_gen.generate_prog_config("PROG1", obj)
        # stats has no type-specific fields, should use standard iobind
        assert "PROG1, 1," in lines[0]
        assert "    CProgProcess::cfgIdIOBind(2)," in lines[1]
        assert "      IO1," in lines[2]
        assert "      IO2," in lines[3]

    def test_generate_prog_config_sampling(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        prog_gen = ProgramConfigGenerator(
            config_loader=ConfigLoader(), prog_types=PROG_TYPES
        )
        obj = ProgramObject(
            obj_id="prog1",
            prog_type="sampling",
            instance=0,
            inputs=["io1"],
            outputs=["io2"],
            reset=None,
            config={"interval": 1000},
        )
        lines = prog_gen.generate_prog_config("PROG1", obj)
        # sampling has iobind (pairs) and interval (uint32)
        # cfg_count = 0 (custom iobind) + 2 (type fields: iobind, interval) = 2
        assert "PROG1, 2," in lines[0]
        assert any("CProgSampling::cfgIdIOBind" in line for line in lines)
        assert any("CProgSampling::cfgIdIOInterval" in line for line in lines)

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


class TestMultiDescriptor:
    """Tests for multi-descriptor YAML support."""

    @pytest.fixture
    def generator(self):
        """Create a DescriptorGenerator instance."""
        return DescriptorGenerator()

    def _make_yaml(
        self, tmp_path, content: str, name: str = "test.yaml"
    ) -> str:
        """Write YAML content to a temp file and return the path."""
        p = tmp_path / name
        p.write_text(content)
        return str(p)

    def test_is_multi_descriptor_spec_false_for_flat(self, generator):
        """Flat YAML (ios/programs/protocols) is not multi-descriptor."""
        spec = {"ios": [], "programs": [], "protocols": []}
        assert not generator._is_multi_descriptor_spec(spec)

    def test_is_multi_descriptor_spec_true(self, generator):
        """Spec with descriptor0 key is multi-descriptor."""
        spec = {"descriptor0": {"ios": []}, "descriptor1": {"ios": []}}
        assert generator._is_multi_descriptor_spec(spec)

    def test_get_descriptor_indices_single(self, generator):
        """Only descriptor0 returns [0]."""
        spec = {"descriptor0": {"ios": []}}
        assert generator._get_descriptor_indices(spec) == [0]

    def test_get_descriptor_indices_two(self, generator):
        """descriptor0 + descriptor1 returns [0, 1]."""
        spec = {
            "descriptor0": {"ios": []},
            "descriptor1": {"ios": []},
        }
        assert generator._get_descriptor_indices(spec) == [0, 1]

    def test_get_descriptor_indices_gap_stops(self, generator):
        """Stops at first missing index (no descriptor1 → only [0])."""
        spec = {
            "descriptor0": {"ios": []},
            "descriptor2": {"ios": []},
        }
        assert generator._get_descriptor_indices(spec) == [0]

    def test_single_descriptor_no_extra_slot_table(self, generator, tmp_path):
        """Single-descriptor YAML produces no FLASH slot table."""
        yaml_content = """
ios:
  - id: dummy0
    type: dummy
    instance: 0
    dtype: bool
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)
        assert "g_dawn_flash_desc" not in output
        assert "dawn_register_flash_slots" not in output

    def test_multi_descriptor_generates_two_arrays(self, generator, tmp_path):
        """Multi-descriptor YAML produces g_dawn_desc and g_dawn_desc1."""
        yaml_content = """
descriptor0:
  ios:
    - id: dummy0
      type: dummy
      instance: 0
      dtype: bool

descriptor1:
  ios:
    - id: dummy1
      type: dummy
      instance: 0
      dtype: uint32
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)

        assert "uint32_t g_dawn_desc[] =" in output
        assert "size_t g_dawn_desc_size = sizeof(g_dawn_desc);" in output
        assert "uint32_t g_dawn_desc1[] =" in output
        assert "size_t g_dawn_desc1_size = sizeof(g_dawn_desc1);" in output

    def test_multi_descriptor_flash_slot_table(self, generator, tmp_path):
        """Multi-descriptor YAML emits data-only FLASH slot table."""
        yaml_content = """
descriptor0:
  ios:
    - id: dummy0
      type: dummy
      instance: 0
      dtype: bool

descriptor1:
  ios:
    - id: dummy1
      type: dummy
      instance: 0
      dtype: uint32
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)

        assert "g_dawn_flash_descs" in output
        assert "g_dawn_flash_desc_sizes" in output
        assert "g_dawn_flash_desc_count" in output
        assert "g_dawn_desc1" in output
        assert "dawn_register_flash_slots" not in output
        assert "CDevDescriptor" not in output

    def test_multi_descriptor_no_dev_descriptor_include(
        self, generator, tmp_path
    ):
        """Multi-descriptor output does not include dawn/dev/descriptor.hxx."""
        yaml_content = """
descriptor0:
  ios:
    - id: dummy0
      type: dummy
      instance: 0
      dtype: bool

descriptor1:
  ios:
    - id: dummy1
      type: dummy
      instance: 0
      dtype: bool
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)
        assert '#include "dawn/dev/descriptor.hxx"' not in output

    def test_multi_descriptor_macros_undefined_between_sections(
        self, generator, tmp_path
    ):
        """Macro names shared across descriptors are #undef'd between them."""
        yaml_content = """
descriptor0:
  ios:
    - id: shared_io
      type: dummy
      instance: 0
      dtype: bool

descriptor1:
  ios:
    - id: shared_io
      type: dummy
      instance: 0
      dtype: bool
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)
        assert "#undef SHARED_IO" in output

    def test_multi_descriptor_descriptor0_is_default_array(
        self, generator, tmp_path
    ):
        """descriptor0 content lands in g_dawn_desc (no numeric suffix)."""
        yaml_content = """
descriptor0:
  metadata:
    version: "2.0"
  ios:
    - id: adc_main
      type: adc_fetch
      instance: 0
      dtype: uint32

descriptor1:
  ios:
    - id: adc_alt
      type: adc_fetch
      instance: 0
      dtype: uint32
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)

        all_lines = output.split("\n")
        desc0_array_line = next(
            (ln for ln in all_lines if "uint32_t g_dawn_desc[] =" in ln),
            None,
        )
        desc1_array_line = next(
            (ln for ln in all_lines if "uint32_t g_dawn_desc1[] =" in ln),
            None,
        )
        assert desc0_array_line is not None
        assert desc1_array_line is not None
        # g_dawn_desc must appear before g_dawn_desc1
        idx0 = all_lines.index(desc0_array_line)
        idx1 = all_lines.index(desc1_array_line)
        assert idx0 < idx1

    def test_multi_descriptor_three_slots(self, generator, tmp_path):
        """Three descriptors produce g_dawn_desc/1/2 arrays."""
        yaml_content = """
descriptor0:
  ios:
    - id: io_a
      type: dummy
      instance: 0
      dtype: bool

descriptor1:
  ios:
    - id: io_b
      type: dummy
      instance: 0
      dtype: bool

descriptor2:
  ios:
    - id: io_c
      type: dummy
      instance: 0
      dtype: bool
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)

        assert "uint32_t g_dawn_desc[] =" in output
        assert "uint32_t g_dawn_desc1[] =" in output
        assert "uint32_t g_dawn_desc2[] =" in output
        assert "g_dawn_flash_descs" in output
        assert "g_dawn_flash_desc_count   = 2" in output

    def test_multi_descriptor_only_descriptor0_no_slot_table(
        self, generator, tmp_path
    ):
        """YAML with only descriptor0 emits no FLASH slot table."""
        yaml_content = """
descriptor0:
  ios:
    - id: dummy0
      type: dummy
      instance: 0
      dtype: bool
"""
        yaml_path = self._make_yaml(tmp_path, yaml_content)
        output = generator.generate(yaml_path)

        assert "g_dawn_flash_desc" not in output
        assert "dawn_register_flash_slots" not in output
        assert "CDevDescriptor" not in output

    def test_generate_descriptor_array_named(self, generator):
        """generate_descriptor_array_named uses custom variable names."""
        spec = {
            "ios": [
                {
                    "id": "dummy0",
                    "type": "dummy",
                    "instance": 0,
                    "dtype": "bool",
                }
            ]
        }
        generator.parse_spec(spec)
        lines = generator.generate_descriptor_array_named(
            "g_custom_desc", "g_custom_desc_size"
        )
        joined = "\n".join(lines)
        assert "uint32_t g_custom_desc[] =" in joined
        assert "size_t g_custom_desc_size = sizeof(g_custom_desc);" in joined

    def test_generate_descriptor_array_default_names(self, generator):
        """generate_descriptor_array() uses default names."""
        spec = {
            "ios": [
                {
                    "id": "dummy0",
                    "type": "dummy",
                    "instance": 0,
                    "dtype": "bool",
                }
            ]
        }
        generator.parse_spec(spec)
        lines = generator.generate_descriptor_array()
        joined = "\n".join(lines)
        assert "uint32_t g_dawn_desc[] =" in joined
        assert "size_t g_dawn_desc_size = sizeof(g_dawn_desc);" in joined
