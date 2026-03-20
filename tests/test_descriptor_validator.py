#!/usr/bin/env python3
# tools/dawnpy/tests/test_descriptor_validator.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for descriptor validator.

Tests descriptor validation, include parsing, and configuration checking.
"""

import tempfile
from pathlib import Path

import pytest

from dawnpy import headerdefs as headerdefs_mod
from dawnpy.descriptor.validation.validator import (
    DescriptorValidator,
    ValidationError,
    ValidationResult,
)


@pytest.fixture
def validator():
    """Fixture to create a DescriptorValidator for testing."""
    return DescriptorValidator()


@pytest.fixture
def temp_config_dir():
    """Fixture to create temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestDescriptorValidatorInitialization:
    """Tests for DescriptorValidator initialization."""

    def test_initialization_loads_config(self, validator):
        """Test that validator loads component configuration."""
        assert len(validator.component_config) > 0
        assert "ios" in validator.component_config
        assert "programs" in validator.component_config
        assert "protocols" in validator.component_config

    def test_ios_components_loaded(self, validator):
        """Test that IO components are loaded."""
        ios = validator.component_config.get("ios", [])
        assert len(ios) > 0

    def test_programs_components_loaded(self, validator):
        """Test that program components are loaded."""
        programs = validator.component_config.get("programs", [])
        assert len(programs) > 0

    def test_protocols_components_loaded(self, validator):
        """Test that protocol components are loaded."""
        protocols = validator.component_config.get("protocols", [])
        assert len(protocols) > 0

    def test_components_have_required_fields(self, validator):
        """Test that components have required fields."""
        ios = validator.component_config.get("ios", [])
        if ios:
            component = ios[0]
            assert "name" in component
            assert "include" in component

    def test_header_component_defs_use_kval_key(self):
        """Header-derived component defs should expose include+kval pairs."""
        data = headerdefs_mod.load_header_component_defs()

        for section in ("ios", "programs", "protocols"):
            for item in data.get(section, []):
                assert isinstance(item, dict)
                assert "name" in item
                assert "include" in item
                assert "kval" in item
                assert str(item["kval"]).startswith("CONFIG_DAWN_")

    def test_header_component_defs_includes_exist(self):
        """All mapped include paths should exist under dawn/include."""
        repo_root = headerdefs_mod.find_repo_root()
        assert repo_root is not None
        data = headerdefs_mod.load_header_component_defs()

        for section in ("ios", "programs", "protocols"):
            for item in data.get(section, []):
                include = item.get("include")
                assert isinstance(include, str) and include
                assert (repo_root / "dawn/include" / include).exists()


class TestParseDescriptorIncludes:
    """Tests for parsing descriptor.cxx includes."""

    def test_parse_simple_includes(self, validator, temp_config_dir):
        """Test parsing simple #include statements."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/io/dummy.hxx"\n'
            '#include "dawn/io/capabilities.hxx"\n'
        )

        includes = validator._parse_descriptor_includes(descriptor)

        assert len(includes) == 2
        assert "dawn/io/dummy.hxx" in includes
        assert "dawn/io/capabilities.hxx" in includes

    def test_parse_ignores_non_dawn_includes(self, validator, temp_config_dir):
        """Test that non-dawn includes are ignored."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            "#include <iostream>\n"
            '#include "dawn/io/dummy.hxx"\n'
            '#include "other/file.hxx"\n'
        )

        includes = validator._parse_descriptor_includes(descriptor)

        assert len(includes) == 1
        assert "dawn/io/dummy.hxx" in includes

    def test_parse_includes_with_spaces(self, validator, temp_config_dir):
        """Test parsing includes with varying whitespace."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include  "dawn/io/dummy.hxx"\n'
            '#include\t"dawn/io/capabilities.hxx"\n'
        )

        includes = validator._parse_descriptor_includes(descriptor)

        assert len(includes) == 2
        assert "dawn/io/dummy.hxx" in includes
        assert "dawn/io/capabilities.hxx" in includes

    def test_parse_nonexistent_file(self, validator, temp_config_dir):
        """Test parsing non-existent file returns empty list."""
        descriptor = temp_config_dir / "nonexistent.cxx"
        includes = validator._parse_descriptor_includes(descriptor)

        assert includes == []

    def test_parse_empty_descriptor(self, validator, temp_config_dir):
        """Test parsing empty descriptor file."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text("")

        includes = validator._parse_descriptor_includes(descriptor)

        assert includes == []


class TestParseDefconfig:
    """Tests for parsing defconfig files."""

    def test_parse_simple_config(self, validator, temp_config_dir):
        """Test parsing simple CONFIG options."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "CONFIG_DAWN_IO_CAPABILITIES=y\n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert len(configs) == 2
        assert "CONFIG_DAWN_IO_DUMMY" in configs
        assert "CONFIG_DAWN_IO_CAPABILITIES" in configs

    def test_parse_ignores_disabled_configs(self, validator, temp_config_dir):
        """Test that disabled configs (not =y) are ignored."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n"
            "# CONFIG_DAWN_IO_CAPABILITIES is not set\n"
            "CONFIG_OTHER_OPTION=n\n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert len(configs) == 1
        assert "CONFIG_DAWN_IO_DUMMY" in configs

    def test_parse_ignores_comments(self, validator, temp_config_dir):
        """Test that comment lines are ignored."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "# This is a comment\n"
            "CONFIG_DAWN_IO_DUMMY=y\n"
            "# Another comment\n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert len(configs) == 1
        assert "CONFIG_DAWN_IO_DUMMY" in configs

    def test_parse_handles_whitespace(self, validator, temp_config_dir):
        """Test parsing configs with whitespace."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "  CONFIG_DAWN_IO_DUMMY=y\n" "CONFIG_DAWN_IO_CAPABILITIES=y  \n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert len(configs) == 2
        assert "CONFIG_DAWN_IO_DUMMY" in configs
        assert "CONFIG_DAWN_IO_CAPABILITIES" in configs

    def test_parse_nonexistent_defconfig(self, validator, temp_config_dir):
        """Test parsing non-existent defconfig returns empty list."""
        defconfig = temp_config_dir / "nonexistent"
        configs = validator._parse_defconfig(defconfig)

        assert configs == []

    def test_parse_include_defconfig_fragment(
        self, validator, temp_config_dir
    ):
        """Test parsing CONFIG options from included defconfig fragment."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            '#include "defconfig.dawn"\n' "CONFIG_OTHER_OPTION=n\n"
        )
        fragment = temp_config_dir / "defconfig.dawn"
        fragment.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n"
            "# CONFIG_DAWN_IO_CAPABILITIES is not set\n"
            "CONFIG_DAWN_PROTO_SHELL=y\n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert "CONFIG_DAWN_IO_DUMMY" in configs
        assert "CONFIG_DAWN_PROTO_SHELL" in configs
        assert "CONFIG_DAWN_IO_CAPABILITIES" not in configs

    def test_parse_include_defconfig_cycle(self, validator, temp_config_dir):
        """Test include cycles do not recurse indefinitely."""
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text('#include "defconfig.dawn"\n')
        fragment = temp_config_dir / "defconfig.dawn"
        fragment.write_text(
            '#include "defconfig"\n' "CONFIG_DAWN_IO_DUMMY=y\n"
        )

        configs = validator._parse_defconfig(defconfig)

        assert configs == ["CONFIG_DAWN_IO_DUMMY"]

    def test_parse_kconfig_values(self, validator, temp_config_dir):
        """Test parsing generated .config values."""
        dot_config = temp_config_dir / ".config"
        dot_config.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n"
            'CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="desc.yaml"\n'
            "CONFIG_NUMBER=12\n"
        )

        values = validator._parse_kconfig_values(dot_config)

        assert values["CONFIG_DAWN_IO_DUMMY"] is True
        assert values["CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH"] == "desc.yaml"
        assert values["CONFIG_NUMBER"] == 12

    def test_parse_kconfig_value_keeps_raw_strings(self, validator):
        """Test unquoted non-numeric Kconfig values stay as strings."""
        assert validator._parse_kconfig_value("abc") == "abc"


class TestFindClassByInclude:
    """Tests for finding class by include path."""

    def test_find_io_class(self, validator):
        """Test finding IO class by include."""
        component = validator._find_class_by_include("dawn/io/dummy.hxx")

        assert component is not None
        assert component.get("name") == "CIODummy"

    def test_find_program_class(self, validator):
        """Test finding program class by include."""
        component = validator._find_class_by_include("dawn/prog/adjust.hxx")

        assert component is not None
        assert component.get("name") == "CProgAdjust"

    def test_find_protocol_class(self, validator):
        """Test finding protocol class by include."""
        component = validator._find_class_by_include("dawn/proto/can/can.hxx")

        assert component is not None
        assert component.get("name") == "CProtoCan"

    def test_find_nonexistent_include(self, validator):
        """Test finding non-existent include returns None."""
        component = validator._find_class_by_include("dawn/nonexistent.hxx")

        assert component is None

    def test_found_component_has_kval(self, validator):
        """Test that found component has kval field."""
        component = validator._find_class_by_include("dawn/io/dummy.hxx")

        assert component is not None
        assert "kval" in component


class TestValidateBasic:
    """Tests for basic validation."""

    def test_validate_valid_descriptor(self, validator, temp_config_dir):
        """Test validating a valid descriptor."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        assert result.valid
        assert len(result.errors) == 0
        assert "CIODummy" in result.used_classes

    def test_validate_missing_config(self, validator, temp_config_dir):
        """Test validation fails when config is missing."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("# CONFIG_DAWN_IO_DUMMY is not set\n")

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert len(result.errors) > 0
        assert len(result.missing_configs) > 0

    def test_validate_with_included_defconfig_fragment(
        self, validator, temp_config_dir
    ):
        """Test validation succeeds when config is in included fragment."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text('#include "defconfig.dawn"\n')
        fragment = temp_config_dir / "defconfig.dawn"
        fragment.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        assert result.valid
        assert len(result.errors) == 0
        assert "CIODummy" in result.used_classes

    def test_validate_multiple_components(self, validator, temp_config_dir):
        """Test validating multiple components."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/io/dummy.hxx"\n'
            '#include "dawn/io/capabilities.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "CONFIG_DAWN_IO_CAPABILITIES=y\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid

    def test_validate_fails_when_yaml_uses_disabled_dtype(
        self, validator, temp_config_dir
    ):
        """Test validation fails when descriptor.yaml dtype is disabled."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "# CONFIG_DAWN_DTYPE_FLOAT is not set\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: float\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any(
            "CONFIG_DAWN_DTYPE_FLOAT" in e.message for e in result.errors
        )

    def test_validate_fails_when_yaml_uses_unknown_dtype(
        self, validator, temp_config_dir
    ):
        """Test validation fails when descriptor.yaml dtype is unknown."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: madeup\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any("unknown dtype" in e.message for e in result.errors)

    def test_validate_yaml_dtype_allows_string_alias(
        self, validator, temp_config_dir
    ):
        """Test YAML string dtype maps to Dawn char Kconfig."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/uname.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_UNAME=y\n" "CONFIG_DAWN_DTYPE_CHAR=y\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: hostname1\n"
            "    type: uname\n"
            "    variant: hostname\n"
            "    instance: 0\n"
            "    dtype: string\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid

    def test_validate_fails_when_sensor_uses_b16_without_nuttx_b16(
        self, validator, temp_config_dir
    ):
        """Test sensor b16 descriptors require NuttX b16 sensor data."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/sensor.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_SENSOR=y\n"
            "CONFIG_DAWN_DTYPE_B16=y\n"
            "CONFIG_SENSORS=y\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: sensor1\n"
            "    type: sensor\n"
            "    subtype: temp\n"
            "    instance: 0\n"
            "    dtype: b16\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any(
            "CONFIG_SENSORS_USE_FLOAT" in e.message for e in result.errors
        )

    def test_validate_fails_when_sensor_uses_float_with_nuttx_b16(
        self, validator, temp_config_dir
    ):
        """Test NuttX b16 sensor data requires sensor dtype b16."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/sensor.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_SENSOR=y\n"
            "CONFIG_DAWN_DTYPE_FLOAT=y\n"
            "CONFIG_SENSORS=y\n"
            "CONFIG_SENSORS_USE_B16=y\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: sensor1\n"
            "    type: sensor\n"
            "    subtype: temp\n"
            "    instance: 0\n"
            "    dtype: float\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any(
            "CONFIG_SENSORS_USE_B16" in e.message for e in result.errors
        )

    def test_validate_allows_sensor_b16_with_nuttx_b16(
        self, validator, temp_config_dir
    ):
        """Test sensor b16 descriptors validate with NuttX b16 sensor data."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/sensor.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_SENSOR=y\n"
            "CONFIG_DAWN_DTYPE_B16=y\n"
            "CONFIG_SENSORS=y\n"
            "CONFIG_SENSORS_USE_B16=y\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: sensor1\n"
            "    type: sensor\n"
            "    subtype: temp\n"
            "    instance: 0\n"
            "    dtype: b16\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid

    def test_validate_yaml_dtype_skips_non_list_ios(
        self, validator, temp_config_dir
    ):
        """Test validator ignores non-list ios payload in descriptor.yaml."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text("ios: {}\n")

        result = validator.validate(str(temp_config_dir))

        assert result.valid

    def test_validate_yaml_dtype_skips_non_mapping_entry(
        self, validator, temp_config_dir
    ):
        """Test validator skips non-mapping entries in ios list."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - not_a_mapping\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: uint32\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any(
            "CONFIG_DAWN_DTYPE_UINT32" in e.message for e in result.errors
        )

    def test_validate_yaml_dtype_allows_any(self, validator, temp_config_dir):
        """Test validator accepts dtype 'any' without dtype Kconfig."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: any\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid

    def test_validate_partial_missing_config(self, validator, temp_config_dir):
        """Test validation fails when only some configs are present."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/io/dummy.hxx"\n'
            '#include "dawn/io/capabilities.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert len(result.missing_configs) == 1

    def test_validate_yaml_handler_requires_multiple_nuttx_configs(
        self, validator, temp_config_dir
    ):
        """Test handler-owned NuttX requirements support many symbols."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/pwm.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_PWM=y\n"
            "CONFIG_DAWN_DTYPE_UINT32=y\n"
            "CONFIG_PWM=y\n"
        )

        descriptor_yaml = temp_config_dir / "descriptor.yaml"
        descriptor_yaml.write_text(
            "ios:\n"
            "  - id: pwm1\n"
            "    type: pwm\n"
            "    instance: 0\n"
            "    dtype: uint32\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert "CONFIG_PWM_MULTICHAN" in result.missing_configs
        assert any(
            "pwm1 (pwm) requires CONFIG_PWM_MULTICHAN" in e.message
            for e in result.errors
        )

    def test_validate_generated_config_uses_dot_config(
        self, validator, temp_config_dir
    ):
        """Test build validation checks descriptor YAML against .config."""
        yaml_path = temp_config_dir / "descriptor.yaml"
        yaml_path.write_text(
            "protocols:\n"
            "  - id: udp1\n"
            "    type: udp\n"
            "    bindings: []\n"
        )
        dot_config = temp_config_dir / ".config"
        dot_config.write_text("CONFIG_DAWN_PROTO_UDP=y\n")

        result = validator.validate_generated_config(yaml_path, dot_config)

        assert not result.valid
        assert result.missing_configs == ["CONFIG_NET_UDP"]

    def test_validate_generated_config_dummy_notify_requires_timerfd(
        self, validator, temp_config_dir
    ):
        """Test timer-driven dummy IO validates NuttX timerfd support."""
        yaml_path = temp_config_dir / "descriptor.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: notify1\n"
            "    type: dummy_notify\n"
            "    dtype: uint32\n"
        )
        dot_config = temp_config_dir / ".config"
        dot_config.write_text(
            "CONFIG_DAWN_IO_DUMMY_NOTIFY=y\n"
            "CONFIG_DAWN_DTYPE_UINT32=y\n"
            "CONFIG_TIMER_FD=y\n"
        )

        result = validator.validate_generated_config(yaml_path, dot_config)

        assert not result.valid
        assert result.missing_configs == ["CONFIG_TIMER_FD_POLL"]

    def test_validate_generated_config_serial_has_no_forced_termios(
        self, validator, temp_config_dir
    ):
        """Test serial descriptors do not require CONFIG_SERIAL_TERMIOS."""
        yaml_path = temp_config_dir / "descriptor.yaml"
        yaml_path.write_text(
            "protocols:\n"
            "  - id: serial1\n"
            "    type: serial\n"
            "    bindings: []\n"
        )
        dot_config = temp_config_dir / ".config"
        dot_config.write_text("CONFIG_DAWN_PROTO_SERIAL=y\n")

        result = validator.validate_generated_config(yaml_path, dot_config)

        assert result.valid
        assert "CONFIG_SERIAL_TERMIOS" not in result.missing_configs

    def test_validate_generated_config_marks_dawn_features_used(
        self, validator, temp_config_dir
    ):
        """Test used YAML handlers are not reported as unused Dawn configs."""
        yaml_path = temp_config_dir / "descriptor.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: dummy1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: uint32\n"
        )
        dot_config = temp_config_dir / ".config"
        dot_config.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n"
            "CONFIG_DAWN_IO_PWM=y\n"
            "CONFIG_DAWN_DTYPE_UINT32=y\n"
        )

        result = validator.validate_generated_config(yaml_path, dot_config)

        assert result.valid
        assert "CONFIG_DAWN_IO_DUMMY" not in result.unused_configs
        assert "CONFIG_DAWN_IO_PWM" in result.unused_configs

    def test_validate_handler_requirements_skips_unhandled_objects(
        self, validator, temp_config_dir
    ):
        """Test requirement validation ignores objects without handlers."""
        yaml_path = temp_config_dir / "descriptor.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: no_type\n"
            "    dtype: uint32\n"
            "  - id: custom\n"
            "    type: custom_io\n"
            "    dtype: uint32\n"
        )
        dot_config = temp_config_dir / ".config"
        dot_config.write_text("", encoding="utf-8")

        result = validator.validate_generated_config(yaml_path, dot_config)

        assert result.used_classes == []


class TestValidationError:
    """Tests for ValidationError model."""

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError(
            severity="error",
            message="Test error",
            location="test.cxx",
        )

        assert error.severity == "error"
        assert error.message == "Test error"
        assert error.location == "test.cxx"

    def test_validation_error_without_location(self):
        """Test creating ValidationError without location."""
        error = ValidationError(
            severity="warning",
            message="Test warning",
        )

        assert error.severity == "warning"
        assert error.location is None


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        result = ValidationResult(
            valid=True,
            errors=[],
            used_classes=["CIODummy"],
            missing_configs=[],
            unused_configs=[],
        )

        assert result.valid
        assert len(result.errors) == 0
        assert len(result.used_classes) == 1

    def test_validation_result_with_errors(self):
        """Test creating ValidationResult with errors."""
        errors = [
            ValidationError(severity="error", message="Error 1"),
            ValidationError(severity="error", message="Error 2"),
        ]
        result = ValidationResult(
            valid=False,
            errors=errors,
            used_classes=[],
            missing_configs=["CONFIG_1"],
            unused_configs=[],
        )

        assert not result.valid
        assert len(result.errors) == 2
        assert len(result.missing_configs) == 1


class TestAlwaysValidIncludes:
    """Tests for always valid includes."""

    def test_descriptor_include_is_always_valid(self, validator):
        """Test that dawn/common/descriptor.hxx is always valid."""
        assert "dawn/common/descriptor.hxx" in validator.ALWAYS_VALID_INCLUDES

    def test_descriptor_include_no_warning(self, validator, temp_config_dir):
        """Test that descriptor.hxx doesn't produce warning."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/common/descriptor.hxx"\n'
            '#include "dawn/io/dummy.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        # Should have no warnings about descriptor.hxx
        descriptor_warnings = [
            e
            for e in result.errors
            if e.severity == "warning" and "descriptor.hxx" in e.message
        ]
        assert len(descriptor_warnings) == 0

    def test_descriptor_include_not_in_used_classes(
        self, validator, temp_config_dir
    ):
        """Test that descriptor.hxx is not added to used classes."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/common/descriptor.hxx"\n'
            '#include "dawn/io/dummy.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        # descriptor.hxx should not be in used classes
        assert "CDescriptor" not in result.used_classes
        # But dummy should be
        assert "CIODummy" in result.used_classes


class TestFormatReport:
    """Tests for format_report method."""

    def test_format_valid_report(self, validator):
        """Test formatting valid validation report."""
        result = ValidationResult(
            valid=True,
            errors=[],
            used_classes=["CIODummy", "CIOPrint"],
            missing_configs=[],
            unused_configs=[],
        )

        report = validator.format_report(result)

        assert "VALID" in report
        assert "CIODummy" in report
        assert "CIOPrint" in report

    def test_format_invalid_report(self, validator):
        """Test formatting invalid validation report."""
        errors = [
            ValidationError(
                severity="error",
                message="Missing CONFIG_DAWN_IO_DUMMY",
                location="defconfig",
            )
        ]
        result = ValidationResult(
            valid=False,
            errors=errors,
            used_classes=["CIODummy"],
            missing_configs=["CONFIG_DAWN_IO_DUMMY"],
            unused_configs=[],
        )

        report = validator.format_report(result)

        assert "INVALID" in report
        assert "ERROR" in report
        assert "CONFIG_DAWN_IO_DUMMY" in report

    def test_format_report_with_warnings(self, validator):
        """Test formatting report with warnings."""
        errors = [
            ValidationError(
                severity="warning",
                message="Unknown include path",
                location="descriptor.cxx",
            )
        ]
        result = ValidationResult(
            valid=True,
            errors=errors,
            used_classes=[],
            missing_configs=[],
            unused_configs=[],
        )

        report = validator.format_report(result)

        assert "WARNING" in report
        assert "Unknown include path" in report

    def test_format_report_with_unused_configs(self, validator):
        """Test formatting report with unused configs."""
        result = ValidationResult(
            valid=True,
            errors=[],
            used_classes=["CIODummy"],
            missing_configs=[],
            unused_configs=["CONFIG_DAWN_IO_CAPABILITIES"],
        )

        report = validator.format_report(result)

        assert "Unused Configurations" in report
        assert "CONFIG_DAWN_IO_CAPABILITIES" in report


class TestNoIncludes:
    """Tests for validation with no includes in descriptor."""

    def test_validate_empty_descriptor(self, validator, temp_config_dir):
        """Test validation fails when descriptor has no includes."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text("")

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("")

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert len(result.errors) > 0
        error_messages = [e.message for e in result.errors]
        assert any("No dawn includes" in msg for msg in error_messages)

    def test_validate_descriptor_with_non_dawn_includes(
        self, validator, temp_config_dir
    ):
        """Test validation fails when descriptor has only non-dawn includes."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            "#include <iostream>\n" '#include "other/file.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("")

        result = validator.validate(str(temp_config_dir))

        assert not result.valid
        assert any("No dawn includes" in e.message for e in result.errors)


class TestUnknownIncludes:
    """Tests for validation with unknown includes."""

    def test_validate_unknown_include(self, validator, temp_config_dir):
        """Test validation with unknown include path."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/unknown/nonexistent.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("")

        result = validator.validate(str(temp_config_dir))

        assert len(result.errors) > 0
        warning_messages = [
            e.message for e in result.errors if e.severity == "warning"
        ]
        assert any("not found in config" in msg for msg in warning_messages)

    def test_validate_mixed_known_and_unknown_includes(
        self, validator, temp_config_dir
    ):
        """Test validation with both known and unknown includes."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/io/dummy.hxx"\n'
            '#include "dawn/unknown/bad.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = validator.validate(str(temp_config_dir))

        # Should have mixed: valid component + warning for unknown
        assert "CIODummy" in result.used_classes
        assert any(e.severity == "warning" for e in result.errors)


class TestUnusedConfigs:
    """Tests for detection of unused configurations."""

    def test_detect_unused_configs(self, validator, temp_config_dir):
        """Test detection of configurations not used in descriptor."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "CONFIG_DAWN_IO_CAPABILITIES=y\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid
        assert "CONFIG_DAWN_IO_CAPABILITIES" in result.unused_configs
        assert "CONFIG_DAWN_IO_DUMMY" not in result.unused_configs

    def test_no_unused_configs_when_all_used(self, validator, temp_config_dir):
        """Test no unused configs reported when all are used."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text(
            '#include "dawn/io/dummy.hxx"\n'
            '#include "dawn/io/capabilities.hxx"\n'
        )

        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "CONFIG_DAWN_IO_CAPABILITIES=y\n"
        )

        result = validator.validate(str(temp_config_dir))

        assert result.valid
        assert len(result.unused_configs) == 0


class TestMissingConfigFile:
    """Tests for handling of missing config files."""

    def test_missing_descriptor_file(self, validator, temp_config_dir):
        """Test validation when descriptor.cxx doesn't exist."""
        # Don't create descriptor.cxx file
        defconfig = temp_config_dir / "defconfig"
        defconfig.write_text("")

        result = validator.validate(str(temp_config_dir))

        # Should fail because no includes found
        assert not result.valid

    def test_missing_defconfig_file(self, validator, temp_config_dir):
        """Test validation when defconfig doesn't exist."""
        descriptor = temp_config_dir / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        # Don't create defconfig file

        result = validator.validate(str(temp_config_dir))

        # Should fail because config is missing
        assert not result.valid
        assert len(result.missing_configs) > 0

    def test_header_component_defs_load_failure_raises(self, monkeypatch):
        """Header mapping load failures should raise runtime config errors."""
        target = (
            "dawnpy.descriptor.validation.validator."
            "load_header_component_defs"
        )
        monkeypatch.setattr(
            target,
            lambda: (_ for _ in ()).throw(
                headerdefs_mod.HeaderDefsError("no header mapping")
            ),
        )
        with pytest.raises(
            RuntimeError, match="Failed to load descriptor config"
        ):
            DescriptorValidator()
