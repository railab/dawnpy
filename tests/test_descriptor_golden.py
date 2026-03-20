# tools/dawnpy/tests/test_descriptor_golden.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Golden file tests for descriptor generator.

These tests compare generated C++ descriptors against known-good expected
outputs to catch regressions in the generator.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from dawnpy.descriptor.generation.generator import DescriptorGenerator


class TestDescriptorGolden:
    """Golden file tests for descriptor generation."""

    @pytest.fixture
    def generator(self):
        """Create a DescriptorGenerator instance."""
        return DescriptorGenerator()

    def _generate_from_spec(self, generator, spec):
        """Helper to generate descriptor from spec dict."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(spec, f)
            yaml_path = f.name

        try:
            return generator.generate(yaml_path)
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_simple_dummy_io(self, generator):
        """Test simple dummy IO descriptor generation."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "bool",
                }
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected output
        expected_lines = [
            "  // dummy1",
            "  DUMMY1, 0,",
        ]

        # Check critical lines are present
        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

        # Check macro definition
        assert "CIODummy::objectId(SObjectId::DTYPE_BOOL, false, 1)" in output

    def test_dummy_io_with_init_value(self, generator):
        """Test dummy IO with initial value configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                    "config": {"init_value": 42},
                }
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: should have config item with init value
        expected_lines = [
            "  DUMMY1, 1,",
            "    CIODummy::cfgIdInitval(7, false, 1),",
            "      42,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_timestamp_io_with_interval(self, generator):
        """Test timestamp IO with interval configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "ts1",
                    "type": "timestamp",
                    "instance": 1,
                    "dtype": "uint64",
                    "timestamp": False,
                    "config": {"interval_us": 1000000},
                }
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: should use cfgInterval (not cfgIdInterval)
        expected_lines = [
            "  TS1, 1,",
            "    CIOTimestamp::cfgInterval(false),",
            "      1000000,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_config_io_binding(self, generator):
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

        output = self._generate_from_spec(generator, spec)

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

    def test_statsmin_program(self, generator):
        """Test StatsMin program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "input1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
                {
                    "id": "output1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "float",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "min1",
                    "type": "statsmin",
                    "instance": 1,
                    "config": {
                        "inputs": ["input1"],
                        "outputs": ["output1"],
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: StatsMin has exactly 2 IDs (input, output)
        expected_lines = [
            "  MIN1, 1,",
            "    CProgStatsMin::cfgIdIOBind(2),",
            "      INPUT1,",
            "      OUTPUT1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_latest_program(self, generator):
        """Test Latest program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "input1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                },
                {
                    "id": "output1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "uint32",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "latest1",
                    "type": "latest",
                    "instance": 1,
                    "config": {
                        "inputs": ["input1"],
                        "outputs": ["output1"],
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  LATEST1, 1,",
            "    CProgLatest::cfgIdIOBind(2),",
            "      INPUT1,",
            "      OUTPUT1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_stats_rms_program(self, generator):
        """Test StatsRms program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "input1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                },
                {
                    "id": "output1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "uint32",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "rms1",
                    "type": "statsrms",
                    "instance": 1,
                    "config": {
                        "inputs": ["input1"],
                        "outputs": ["output1"],
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  RMS1, 1,",
            "    CProgStatsRms::cfgIdIOBind(2),",
            "      INPUT1,",
            "      OUTPUT1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_dummy_program(self, generator):
        """Test Dummy program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "input1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                },
                {
                    "id": "output1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "uint32",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "dummy_prog1",
                    "type": "dummy",
                    "instance": 1,
                    "config": {
                        "inputs": ["input1"],
                        "outputs": ["output1"],
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  DUMMY_PROG1, 1,",
            "    CProgDummy::cfgIdIOBind(2),",
            "      INPUT1,",
            "      OUTPUT1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_redirect_program(self, generator):
        """Test Redirect program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "in1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                },
                {
                    "id": "out1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "uint32",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "redir1",
                    "type": "redirect",
                    "instance": 1,
                    "config": {
                        "inputs": ["in1"],
                        "outputs": ["out1"],
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  REDIR1, 1,",
            "    CProgRedirect::cfgIdIOBind(2),",
            "      IN1,",
            "      OUT1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_movingavg_program(self, generator):
        """Test MovingAverage program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "in1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
                {
                    "id": "out1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "float",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "mov1",
                    "type": "movingavg",
                    "instance": 1,
                    "config": {
                        "inputs": ["in1"],
                        "outputs": ["out1"],
                        "window": 8,
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  MOV1, 2,",
            "    CProgMovingAverage::cfgIdIOBind(2),",
            "      IN1,",
            "      OUT1,",
            "    CProgMovingAverage::cfgIdWindow(),",
            "      8,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_iirfilter_program(self, generator):
        """Test IIRFilter program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "in1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
                {
                    "id": "out1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "float",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "iir1",
                    "type": "iirfilter",
                    "instance": 1,
                    "config": {
                        "inputs": ["in1"],
                        "outputs": ["out1"],
                        "alpha_num": 1,
                        "alpha_den": 4,
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  IIR1, 3,",
            "    CProgIIRFilter::cfgIdIOBind(2),",
            "      IN1,",
            "      OUT1,",
            "    CProgIIRFilter::cfgIdAlphaNum(),",
            "      1,",
            "    CProgIIRFilter::cfgIdAlphaDen(),",
            "      4,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_shell_protocol(self, generator):
        """Test shell protocol configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "io1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                }
            ],
            "programs": [],
            "protocols": [
                {
                    "id": "shell1",
                    "type": "shell",
                    "instance": 1,
                    "config": {"prompt": "test> "},
                    "bindings": ["io1"],
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: Shell config count should be 2 (prompt + bindings)
        expected_lines = [
            "  SHELL1, 2,",
            "    CProtoShellPretty::cfgIdPrompt",
            "    CProtoShellPretty::cfgIdIOBind(1)",
            "      IO1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_dummy_protocol(self, generator):
        """Test Dummy protocol configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "io1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint32",
                }
            ],
            "programs": [],
            "protocols": [
                {
                    "id": "proto_dummy1",
                    "type": "dummy",
                    "instance": 1,
                    "bindings": ["io1"],
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        expected_lines = [
            "  PROTO_DUMMY1, 1,",
            "    CProtoDummy::cfgIdIOBind(1),",
            "      IO1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_can_protocol_basic(self, generator):
        """Test basic CAN protocol configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "io1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "uint64",
                }
            ],
            "programs": [],
            "protocols": [
                {
                    "id": "can1",
                    "type": "can",
                    "instance": 1,
                    "config": {
                        "node_id": 256,
                        "objects": [
                            {
                                "type": "read",
                                "flags": 0,
                                "can_id_start": 256,
                                "count": 1,
                                "bindings": ["io1"],
                            }
                        ],
                    },
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: CAN config with node_id and object
        expected_lines = [
            "  CAN1,",
            "    CProtoCan::cfgIdNodeid(),",
            "      0x0100,",
            "    CProtoCan::cfgIdIOBind(4),",
            "      CProtoCan::CAN_TYPE_READ,",
            "      0x0100,",
            "      1,",
            "      IO1,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

    def test_rand_io_with_timestamp(self, generator):
        """Test rand IO with timestamp parameter."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "rand1",
                    "type": "rand",
                    "instance": 1,
                    "dtype": "uint64",
                    "timestamp": False,
                }
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: rand objectId should have dtype, timestamp, instance
        # (not duplicate instance)
        expected = "CIORand::objectId(SObjectId::DTYPE_UINT64, false, 1)"
        assert expected in output, f"Expected objectId not found: {expected}"

    def test_complete_descriptor_structure(self, generator):
        """Test complete descriptor structure with all sections."""
        spec = {
            "metadata": {"version": "1.0", "description": "test"},
            "ios": [
                {
                    "id": "io1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "bool",
                }
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Check required sections are present
        required_sections = [
            "// Included Files",
            "using namespace dawn;",
            "// Object Definitions",
            "// Descriptor Array",
            "uint32_t g_dawn_desc[] =",
            "// Header",
            "CDescriptor::DAWN_DESCRIPTOR_HDR,",
            "// Metadata",
            "CDescriptor::objectId(1),",
            "// Check sum",
            "CDescriptor::DAWN_DESCRIPTOR_FOOT,",
            "0xdeadbeef",
            "size_t g_dawn_desc_size = sizeof(g_dawn_desc);",
        ]

        for section in required_sections:
            assert section in output, f"Required section not found: {section}"

    def test_metadata_version_encoding(self, generator):
        """Test metadata version encoding."""
        spec = {
            "metadata": {"version": "2.1"},
            "ios": [],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Version 2.1 should be encoded as 0x00020001
        expected = "0x00020001"
        assert expected in output, f"Expected version encoding: {expected}"

    def test_header_includes(self, generator):
        """Test that required headers are included."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "dummy1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "bool",
                }
            ],
            "programs": [
                {
                    "id": "min1",
                    "type": "statsmin",
                    "instance": 1,
                    "config": {
                        "inputs": ["dummy1"],
                        "outputs": ["dummy1"],
                    },
                }
            ],
            "protocols": [
                {
                    "id": "shell1",
                    "type": "shell",
                    "instance": 1,
                    "bindings": [],
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        # Check all required headers
        expected_includes = [
            '#include "dawn/common/descriptor.hxx"',
            '#include "dawn/io/dummy.hxx"',
            '#include "dawn/prog/statsmin.hxx"',
            '#include "dawn/proto/shell/pretty.hxx"',
        ]

        for include in expected_includes:
            assert include in output, f"Expected include not found: {include}"

    def test_object_count_in_header(self, generator):
        """Test that object count in header is correct."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {"id": "io1", "type": "dummy", "instance": 1, "dtype": "bool"},
                {"id": "io2", "type": "dummy", "instance": 2, "dtype": "bool"},
                {"id": "io3", "type": "dummy", "instance": 3, "dtype": "bool"},
            ],
            "programs": [],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Should have 4 objects: metadata + 3 IOs
        # Header format: HDR, count
        lines = output.split("\n")
        header_found = False
        for i, line in enumerate(lines):
            if "CDescriptor::DAWN_DESCRIPTOR_HDR" in line:
                # Next line or same line should have count
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Count = 1 (metadata) + 3 (ios) = 4
                    if next_line.startswith("4"):  # pragma: no cover
                        header_found = True
                        break
                # Or same line
                if ", 4" in line or ",4" in line:
                    header_found = True
                    break

        assert header_found, "Correct object count not found in header"

    def test_config_io_with_different_dtypes(self, generator):
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

        output = self._generate_from_spec(generator, spec)

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

    def test_nimble_with_services(self, generator):
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

        output = self._generate_from_spec(generator, spec)

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

    def test_long_string_padding(self, generator):
        """Test string padding for strings longer than 16 bytes."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [],
            "programs": [],
            "protocols": [
                {
                    "id": "shell1",
                    "type": "shell",
                    "instance": 1,
                    "config": {
                        "prompt": (
                            "This is a very long prompt "
                            "string that exceeds sixteen bytes"
                        )
                    },
                    "bindings": [],
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        # Should generate shell with long prompt
        assert "CProtoShellPretty::cfgIdPrompt" in output

    def test_serial_with_uint32_baudrate(self, generator):
        """Test serial protocol with uint32 baudrate config."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [],
            "programs": [],
            "protocols": [
                {
                    "id": "serial1",
                    "type": "serial",
                    "instance": 1,
                    "config": {
                        "device": "/dev/ttyUSB0",
                        "baudrate": 115200,  # uint32 config
                    },
                    "bindings": [],
                }
            ],
        }

        output = self._generate_from_spec(generator, spec)

        # Check that serial protocol is generated with baudrate
        expected_lines = [
            "CProtoSerial::objectId",
            "CProtoSerial::cfgIdBaud",
            "115200,",  # uint32 value without hex format
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line: {expected}"

    def test_sampling_program(self, generator):
        """Test Sampling program configuration."""
        spec = {
            "metadata": {"version": "1.0"},
            "ios": [
                {
                    "id": "src1",
                    "type": "dummy",
                    "instance": 1,
                    "dtype": "float",
                },
                {
                    "id": "src2",
                    "type": "dummy",
                    "instance": 2,
                    "dtype": "float",
                },
                {
                    "id": "virt1",
                    "type": "virt",
                    "instance": 1,
                    "dtype": "float",
                    "notify": False,
                },
                {
                    "id": "virt2",
                    "type": "virt",
                    "instance": 2,
                    "dtype": "float",
                    "notify": False,
                },
            ],
            "programs": [
                {
                    "id": "sampling1",
                    "type": "sampling",
                    "instance": 1,
                    "config": {
                        "sources": ["src1", "src2"],
                        "outputs": ["virt1", "virt2"],
                        "interval": 10000,
                    },
                }
            ],
            "protocols": [],
        }

        output = self._generate_from_spec(generator, spec)

        # Expected: 2 config items (iobind + interval)
        expected_lines = [
            "  SAMPLING1, 2,",
            "    CProgSampling::cfgIdIOBind(4),",
            "      SRC1,",
            "      SRC2,",
            "      VIRT1,",
            "      VIRT2,",
            "    CProgSampling::cfgIdIOInterval(),",
            "      10000,",
        ]

        for expected in expected_lines:
            assert any(
                expected in line for line in output.split("\n")
            ), f"Expected line not found: {expected}"

        # Check macro definition uses CProgSampling::objectId
        assert "CProgSampling::objectId(1)" in output
