# tools/dawnpy/tests/test_descriptor_generator.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor generator."""

import pytest

from dawnpy.descriptor.definitions.objects import (
    IoObject,
    ProgramObject,
    ProtocolObject,
)
from dawnpy.descriptor.generation.generator import (
    DescriptorGenerator,
    generate_descriptor,
)
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

pytestmark = pytest.mark.usefixtures("source_free_headers")


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

    def test_generate_with_include_block(self, generator, tmp_path):
        """Include blocks expand before descriptor code generation."""
        block_dir = tmp_path / "blocks"
        block_dir.mkdir()
        (block_dir / "common.yaml").write_text("""
outputs:
  - id: led
    ref: led1
ios:
  - id: led1
    type: dummy
    dtype: bool
""")
        yaml_file = tmp_path / "descriptor.yaml"
        yaml_file.write_text("""
includes:
  - id: common
    path: blocks/common.yaml
protocols:
  - id: shell1
    type: shell
    bindings:
      - "@common.led"
""")

        cpp_code = generator.generate(str(yaml_file))

        assert "#define LED" in cpp_code
        assert "COMMON__LED1" not in cpp_code
        assert "@common.led" not in cpp_code

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

    def test_sensor_producer_io_generation(self, tmp_path):
        """Test sensor producer IO with subtype and queue config."""
        yaml_content = """
ios:
  - id: temp_sensor_out
    type: sensor_producer
    subtype: temp
    instance: 10
    dtype: float
    config:
      device: 10
      queue_size: 4
      persist: true
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        generator = DescriptorGenerator()
        cpp_code = generator.generate(str(yaml_file))

        assert "CIOSensorProducer::objectIdTemp" in cpp_code
        assert "CIOSensorProducer::cfgIdQueueSize" in cpp_code
        assert "CIOSensorProducer::cfgIdPersist" in cpp_code
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
        from tests.descriptor.conftest import minimal_header_definition_set

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
        from tests.descriptor.conftest import minimal_header_definition_set

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
