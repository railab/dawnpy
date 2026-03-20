# tools/dawnpy/tests/descriptor/handlers/test_proto_nimble.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import ProtocolObject
from dawnpy.descriptor.generation.generator import DescriptorGenerator
from tests.descriptor.descriptor_helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def to_proto_obj(spec: dict, obj_id: str = "test_proto") -> ProtocolObject:
    full_spec = {
        "id": obj_id,
        "type": spec.get("type", "serial"),
        "instance": spec.get("instance", 1),
        "config": spec.get("config", {}),
        "bindings": spec.get("bindings", []),
    }
    return ProtocolObject.from_spec(full_spec)


class TestProtoNimbleHandler:

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


def test_nimble_with_services(generator):
    """Test nimble protocol with BLE services."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "temp1",
                "type": "sensor",
                "subtype": "temp",
                "instance": 1,
                "dtype": "float",
                "timestamp": False,
            },
            {
                "id": "humd1",
                "type": "sensor",
                "subtype": "hum",
                "instance": 1,
                "dtype": "float",
                "timestamp": False,
            },
            {
                "id": "btn1",
                "type": "gpi",
                "instance": 1,
                "dtype": "bool",
            },
        ],
        "programs": [],
        "protocols": [
            {
                "id": "ble1",
                "type": "nimble",
                "instance": 1,
                "config": {
                    "device_name": "TestDevice",
                    "gap_name": "TestGapName",
                    "services": {
                        "dis": {"enabled": True},
                        "bas": {"battery_level": "temp1"},
                        "ess": {
                            "characteristics": [
                                {"type": "temperature", "data": "temp1"}
                            ]
                        },
                        "imds": {"humidity": "humd1"},
                        "aios": {
                            "groups": [
                                {
                                    "type": "digital_in",
                                    "bindings": ["btn1"],
                                }
                            ]
                        },
                    },
                },
            }
        ],
    }

    output = generate_from_spec(generator, spec)

    # Check nimble protocol is generated
    expected_lines = [
        '#include "dawn/proto/nimble/prph.hxx"',
        '#include "dawn/proto/nimble/prph_ess.hxx"',
        "CProtoNimblePrph::objectId",
        "CProtoNimblePrph::cfgIdGapname",  # gap_name
        "CProtoNimblePrph::cfgIdIOBindBas()",  # BAS
        "CProtoNimblePrph::cfgIdIOBindEss",  # ESS
        "CProtoNimblePrph::cfgIdIOBindImds",  # IMDS
        "CProtoNimblePrph::cfgIdIOBindAios",  # AIOS
        "CProtoNimblePrphEss::cfgIdIOBindEssCfg",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected nimble line: {expected}"
