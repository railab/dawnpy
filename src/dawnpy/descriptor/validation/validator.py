#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/descriptor/validator.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Descriptor configuration validator for Dawn Framework.

Validates descriptor files and configuration to ensure all required
components are properly included and configured.
"""

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from dawnpy.descriptor.handlers import (
    IO_HANDLER_REGISTRY,
    PROG_HANDLER_REGISTRY,
    PROTO_HANDLER_REGISTRY,
)
from dawnpy.descriptor.support.vars import load_yaml_with_vars
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.headerdefs.bundle import header_component_defs


class ValidationError(BaseModel):
    """Represents a validation error."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning", "info"]
    message: str
    location: str | None = None


class ValidationResult(BaseModel):
    """Result of descriptor validation."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    errors: list[ValidationError]
    used_classes: list[str]
    missing_configs: list[str]
    unused_configs: list[str]


class DescriptorValidator:
    """Validate descriptor and configuration files."""

    # Always valid includes that don't need config checking
    ALWAYS_VALID_INCLUDES = {
        "dawn/common/descriptor.hxx",
    }
    DTYPE_KCONFIG_MAP = {
        "bool": "CONFIG_DAWN_DTYPE_BOOL",
        "int8": "CONFIG_DAWN_DTYPE_INT8",
        "uint8": "CONFIG_DAWN_DTYPE_UINT8",
        "int16": "CONFIG_DAWN_DTYPE_INT16",
        "uint16": "CONFIG_DAWN_DTYPE_UINT16",
        "int32": "CONFIG_DAWN_DTYPE_INT32",
        "uint32": "CONFIG_DAWN_DTYPE_UINT32",
        "int64": "CONFIG_DAWN_DTYPE_INT64",
        "uint64": "CONFIG_DAWN_DTYPE_UINT64",
        "float": "CONFIG_DAWN_DTYPE_FLOAT",
        "double": "CONFIG_DAWN_DTYPE_DOUBLE",
        "b16": "CONFIG_DAWN_DTYPE_B16",
        "ub16": "CONFIG_DAWN_DTYPE_UB16",
        "char": "CONFIG_DAWN_DTYPE_CHAR",
        "string": "CONFIG_DAWN_DTYPE_CHAR",
        "block": "CONFIG_DAWN_DTYPE_BLOCK",
    }
    _INCLUDE_PATTERN = re.compile(r'^#include\s+(?:"([^"]+)"|(\S+))\s*$')

    def __init__(self) -> None:
        """Initialize validator."""
        self.component_config: dict[str, list[dict[str, Any]]] = {}
        self._include_index: dict[str, dict[str, Any]] = {}
        self._class_index: dict[str, dict[str, Any]] = {}
        self._dawn_configs: set[str] = set()

        self._load_config()

    def _load_config(self) -> None:
        """Load descriptor component mapping from parsed C++ headers."""
        try:
            data = header_component_defs()
            self.component_config = {
                "ios": data.get("ios", []),
                "programs": data.get("programs", []),
                "protocols": data.get("protocols", []),
            }
            self._build_indexes()
        except HeaderDefsError as e:
            raise RuntimeError(f"Failed to load descriptor config: {e}")

    def _build_indexes(self) -> None:
        """Build lookup indexes for includes and Kconfig options."""
        include_index: dict[str, dict[str, Any]] = {}
        class_index: dict[str, dict[str, Any]] = {}
        dawn_configs: set[str] = set()

        for category in ("ios", "programs", "protocols"):
            for component in self.component_config.get(category, []):
                class_name = component.get("name")
                if class_name:
                    class_index[str(class_name)] = component
                include_path = component.get("include")
                if include_path:
                    include_index[str(include_path)] = component
                config_opt = component.get("kval")
                if config_opt:
                    dawn_configs.add(str(config_opt))

        self._include_index = include_index
        self._class_index = class_index
        self._dawn_configs = dawn_configs

    def _parse_descriptor_includes(self, descriptor_path: Path) -> list[str]:
        """
        Parse descriptor.cxx and extract all include paths.

        Args:
            descriptor_path: Path to descriptor.cxx file

        Returns:
            List of include paths (e.g., ["dawn/io/dummy.hxx", ...])
        """
        includes = []

        try:
            with open(descriptor_path) as f:
                content = f.read()

                # Find all #include statements for dawn components
                pattern = r'#include\s+"(dawn/[^"]+)"'
                matches = re.findall(pattern, content)
                includes.extend(matches)

        except FileNotFoundError:
            pass

        return includes

    def _parse_defconfig(self, defconfig_path: Path) -> list[str]:
        """
        Parse defconfig file and extract enabled CONFIG options.

        Args:
            defconfig_path: Path to defconfig file

        Returns:
            List of enabled CONFIG option names
        """
        values = self._parse_kconfig_values(defconfig_path)
        return [key for key, value in values.items() if value is True]

    def _parse_kconfig_values(self, kconfig_path: Path) -> dict[str, Any]:
        """Parse a Kconfig fragment or generated .config into values."""
        return self._parse_kconfig_values_recursive(kconfig_path, set())

    def _parse_kconfig_values_recursive(
        self, kconfig_path: Path, visited: set[Path]
    ) -> dict[str, Any]:
        """Parse Kconfig values and included fragments recursively."""
        values: dict[str, Any] = {}
        resolved = kconfig_path.resolve()

        if resolved in visited:
            return values
        visited.add(resolved)

        try:
            with open(kconfig_path) as f:
                for raw_line in f:
                    line = raw_line.strip()

                    match = self._INCLUDE_PATTERN.match(line)
                    if match:
                        include_name = match.group(1) or match.group(2)
                        include_path = kconfig_path.parent / include_name
                        values.update(
                            self._parse_kconfig_values_recursive(
                                include_path, visited
                            )
                        )
                        continue

                    if line.startswith("CONFIG_") and "=" in line:
                        key, raw_value = line.split("=", 1)
                        values[key.strip()] = self._parse_kconfig_value(
                            raw_value.strip()
                        )

        except FileNotFoundError:
            pass

        return values

    def _parse_kconfig_value(self, raw_value: str) -> Any:
        """Parse one Kconfig assignment value."""
        if raw_value.startswith('"') and raw_value.endswith('"'):
            return raw_value[1:-1]
        if raw_value in ("y", "n"):
            return raw_value == "y"
        try:
            return int(raw_value, 0)
        except ValueError:
            return raw_value

    def _find_class_by_include(
        self, include_path: str
    ) -> dict[str, Any] | None:
        """
        Find component class definition by include path.

        Args:
            include_path: Include path (e.g., "dawn/io/dummy.hxx")

        Returns:
            Component definition dict or None if not found
        """
        return self._include_index.get(include_path)

    def _get_all_dawn_configs(self) -> set[str]:
        """Get all known DAWN configuration options."""
        return set(self._dawn_configs)

    def _validate_includes(
        self,
        includes: list[str],
        descriptor_path: Path,
        defconfig_path: Path,
        enabled_configs: set[str],
    ) -> tuple[list[ValidationError], list[str], list[str], set[str]]:
        """Validate each include and check configs."""
        errors: list[ValidationError] = []
        used_classes: list[str] = []
        missing_configs: list[str] = []
        used_configs: set[str] = set()

        for include_path in includes:
            # Skip always valid includes
            if include_path in self.ALWAYS_VALID_INCLUDES:
                continue

            component = self._find_class_by_include(include_path)

            if not component:
                errors.append(
                    ValidationError(
                        severity="warning",
                        message=(
                            f"Include not found in config: {include_path}"
                        ),
                        location=str(descriptor_path),
                    )
                )
                continue

            class_name = component.get("name")
            if class_name:
                used_classes.append(class_name)

            config_opt = component.get("kval")
            if config_opt:
                used_configs.add(config_opt)
                if config_opt not in enabled_configs:
                    missing_configs.append(config_opt)
                    errors.append(
                        ValidationError(
                            severity="error",
                            message=(
                                f"Component {class_name} requires "
                                f"{config_opt} in defconfig"
                            ),
                            location=str(defconfig_path),
                        )
                    )

        return errors, used_classes, missing_configs, used_configs

    def _validate_yaml_dtype_enabled(
        self,
        io_id: str,
        dtype_name: str,
        defconfig_path: Path,
        enabled_configs: set[str],
    ) -> list[ValidationError]:
        """Validate one IO dtype against enabled Dawn dtype Kconfig."""
        dtype_cfg = self.DTYPE_KCONFIG_MAP.get(dtype_name)

        if dtype_cfg is None:
            return [
                ValidationError(
                    severity="error",
                    message=f"IO {io_id} uses unknown dtype '{dtype_name}'",
                    location=str(defconfig_path.parent / "descriptor.yaml"),
                )
            ]

        if dtype_cfg in enabled_configs:
            return []

        return [
            ValidationError(
                severity="error",
                message=(
                    f"IO {io_id} uses dtype '{dtype_name}' but "
                    f"{dtype_cfg} is not enabled"
                ),
                location=str(defconfig_path),
            )
        ]

    def _validate_sensor_yaml_dtype(
        self,
        io_id: str,
        dtype_name: str,
        yaml_path: Path,
        enabled_configs: set[str],
    ) -> list[ValidationError]:
        """Validate one sensor IO dtype against NuttX sensor data Kconfig."""
        sensors_use_b16 = "CONFIG_SENSORS_USE_B16" in enabled_configs
        expected_dtype = "b16" if sensors_use_b16 else "float"
        expected_config = (
            "CONFIG_SENSORS_USE_B16"
            if sensors_use_b16
            else "CONFIG_SENSORS_USE_FLOAT"
        )

        if dtype_name == expected_dtype:
            return []

        return [
            ValidationError(
                severity="error",
                message=(
                    f"Sensor IO {io_id} uses dtype '{dtype_name}' but "
                    f"{expected_config} requires dtype '{expected_dtype}'"
                ),
                location=str(yaml_path),
            )
        ]

    def _validate_yaml_dtypes(
        self,
        yaml_path: Path,
        defconfig_path: Path,
        enabled_configs: set[str],
    ) -> list[ValidationError]:
        """Validate descriptor.yaml dtype usage against enabled Kconfig."""
        errors: list[ValidationError] = []
        spec: dict[str, Any]
        ios: Any

        if not yaml_path.exists():
            return errors

        try:
            spec = load_yaml_with_vars(
                str(yaml_path), kconfig_path=str(defconfig_path)
            )
        except Exception as exc:
            errors.append(
                ValidationError(
                    severity="error",
                    message=f"Failed to parse descriptor.yaml: {exc}",
                    location=str(yaml_path),
                )
            )
            return errors

        ios = spec.get("ios", [])
        if not isinstance(ios, list):
            return errors

        for index, io in enumerate(ios):
            io_id: str
            dtype_name: str

            if not isinstance(io, dict):
                continue

            io_id = str(io.get("id", f"ios[{index}]"))
            dtype_name = str(io.get("dtype", "uint32")).lower()

            if dtype_name == "any":
                continue

            dtype_errors = self._validate_yaml_dtype_enabled(
                io_id, dtype_name, defconfig_path, enabled_configs
            )
            errors.extend(dtype_errors)
            if dtype_errors:
                continue

            if io.get("type") in ("sensor", "sensor_producer"):
                errors.extend(
                    self._validate_sensor_yaml_dtype(
                        io_id, dtype_name, yaml_path, enabled_configs
                    )
                )

        return errors

    def _validate_object_requirements(
        self,
        *,
        label: str,
        section: str,
        index: int,
        obj: dict[str, Any],
        handler: Any,
        kconfig_path: Path,
        enabled_configs: set[str],
        config_values: dict[str, Any],
    ) -> tuple[list[ValidationError], list[str], set[str]]:
        """Validate one descriptor object against handler requirements."""
        errors: list[ValidationError] = []
        missing_configs: list[str] = []
        used_configs: set[str] = set()

        object_id = str(obj.get("id", f"{section}[{index}]"))
        yaml_type = str(obj["type"])
        component = self._class_index.get(handler.cpp_class)
        dawn_config = component.get("kval") if component else None
        if dawn_config:
            used_configs.add(str(dawn_config))
            if dawn_config not in enabled_configs:
                missing_configs.append(str(dawn_config))
                errors.append(
                    ValidationError(
                        severity="error",
                        message=(
                            f"{label} {object_id} ({yaml_type}) "
                            f"requires {dawn_config} in Kconfig file"
                        ),
                        location=str(kconfig_path),
                    )
                )
        for requirement in handler.nuttx_requirements:
            used_configs.add(requirement)
            if requirement in enabled_configs:
                continue
            missing_configs.append(requirement)
            errors.append(
                ValidationError(
                    severity="error",
                    message=(
                        f"{label} {object_id} ({yaml_type}) "
                        f"requires {requirement} in Kconfig file"
                    ),
                    location=str(kconfig_path),
                )
            )

        for name, op, limit in handler.nuttx_value_requirements:
            used_configs.add(name)
            value = config_values.get(name)
            valid = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and self._compare_int_config(value, op, limit)
            )
            if valid:
                continue
            missing_configs.append(name)
            errors.append(
                ValidationError(
                    severity="error",
                    message=(
                        f"{label} {object_id} ({yaml_type}) "
                        f"requires {name} {op} {limit} in Kconfig file"
                    ),
                    location=str(kconfig_path),
                )
            )

        return errors, missing_configs, used_configs

    def _compare_int_config(self, value: int, op: str, limit: int) -> bool:
        """Evaluate one integer Kconfig requirement."""
        if op == ">=":
            return value >= limit
        if op == ">":
            return value > limit
        if op == "<=":
            return value <= limit
        if op == "<":
            return value < limit
        if op in ("=", "=="):
            return value == limit
        raise ValueError(f"Unsupported Kconfig requirement operator: {op}")

    def _validate_handler_requirements(
        self,
        yaml_path: Path,
        kconfig_path: Path,
        enabled_configs: set[str],
        config_values: dict[str, Any],
    ) -> tuple[list[ValidationError], list[str], list[str], set[str]]:
        """Validate YAML object handlers against NuttX Kconfig symbols."""
        errors: list[ValidationError] = []
        used_classes: list[str] = []
        missing_configs: list[str] = []
        used_configs: set[str] = set()

        if not yaml_path.exists():
            return errors, used_classes, missing_configs, used_configs

        try:
            spec = load_yaml_with_vars(
                str(yaml_path), kconfig_path=str(kconfig_path)
            )
        except Exception as exc:
            errors.append(
                ValidationError(
                    severity="error",
                    message=f"Failed to parse descriptor.yaml: {exc}",
                    location=str(yaml_path),
                )
            )
            return errors, used_classes, missing_configs, used_configs

        sections = (
            ("ios", IO_HANDLER_REGISTRY, "IO"),
            ("programs", PROG_HANDLER_REGISTRY, "Program"),
            ("protocols", PROTO_HANDLER_REGISTRY, "Protocol"),
        )
        for section, registry, label in sections:
            objects = spec.get(section, [])
            if not isinstance(objects, list):
                continue
            for index, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    continue
                object_type = obj.get("type")
                if object_type is None:
                    continue
                yaml_type = str(object_type)
                handler = registry.get(yaml_type)
                if handler is None:
                    continue
                err, miss_cfg, used_cfg = self._validate_object_requirements(
                    label=label,
                    section=section,
                    index=index,
                    obj=obj,
                    handler=handler,
                    kconfig_path=kconfig_path,
                    enabled_configs=enabled_configs,
                    config_values=config_values,
                )
                errors.extend(err)
                used_classes.append(handler.cpp_class)
                missing_configs.extend(miss_cfg)
                used_configs.update(used_cfg)

        return errors, used_classes, missing_configs, used_configs

    def validate(self, config_dir_path: str) -> ValidationResult:
        """
        Validate descriptor and configuration in a directory.

        Args:
            config_dir_path: Path to directory containing descriptor.cxx
                            and defconfig files

        Returns:
            ValidationResult with validation status and errors
        """
        config_path = Path(config_dir_path)
        descriptor_path = config_path / "descriptor.cxx"
        defconfig_path = config_path / "defconfig"
        yaml_path = config_path / "descriptor.yaml"

        errors: list[ValidationError] = []
        used_classes: list[str] = []
        missing_configs: list[str] = []
        unused_configs: list[str] = []

        # Parse files
        includes = self._parse_descriptor_includes(descriptor_path)
        config_values = self._parse_kconfig_values(defconfig_path)
        enabled_configs: set[str] = {
            key for key, value in config_values.items() if value is True
        }

        if not includes:
            errors.append(
                ValidationError(
                    severity="error",
                    message="No dawn includes found in descriptor.cxx",
                    location=str(descriptor_path),
                )
            )

        # Validate includes and configs
        err, used_cls, miss_cfg, used_cfg = self._validate_includes(
            includes, descriptor_path, defconfig_path, enabled_configs
        )
        errors.extend(err)
        used_classes.extend(used_cls)
        missing_configs.extend(miss_cfg)
        errors.extend(
            self._validate_yaml_dtypes(
                yaml_path, defconfig_path, enabled_configs
            )
        )
        err, used_cls, miss_cfg, used_cfg_yaml = (
            self._validate_handler_requirements(
                yaml_path, defconfig_path, enabled_configs, config_values
            )
        )
        errors.extend(err)
        used_classes.extend(used_cls)
        missing_configs.extend(miss_cfg)
        used_cfg.update(used_cfg_yaml)

        # Check for unused configs
        dawn_configs = self._get_all_dawn_configs()
        for config in enabled_configs:
            if config in dawn_configs and config not in used_cfg:
                unused_configs.append(config)

        valid = len([e for e in errors if e.severity == "error"]) == 0

        return ValidationResult(
            valid=valid,
            errors=errors,
            used_classes=used_classes,
            missing_configs=missing_configs,
            unused_configs=unused_configs,
        )

    def validate_generated_config(
        self, yaml_path: Path, kconfig_path: Path
    ) -> ValidationResult:
        """Validate descriptor YAML against a generated NuttX .config."""
        errors: list[ValidationError] = []
        used_classes: list[str] = []
        missing_configs: list[str] = []
        unused_configs: list[str] = []

        config_values = self._parse_kconfig_values(kconfig_path)
        enabled_configs = {
            key for key, value in config_values.items() if value is True
        }
        err, used_cls, miss_cfg, used_cfg = (
            self._validate_handler_requirements(
                yaml_path, kconfig_path, enabled_configs, config_values
            )
        )
        errors.extend(err)
        used_classes.extend(used_cls)
        missing_configs.extend(miss_cfg)
        errors.extend(
            self._validate_yaml_dtypes(
                yaml_path, kconfig_path, enabled_configs
            )
        )

        dawn_configs = self._get_all_dawn_configs()
        for config in enabled_configs:
            if config in dawn_configs and config not in used_cfg:
                unused_configs.append(config)

        valid = len([e for e in errors if e.severity == "error"]) == 0

        return ValidationResult(
            valid=valid,
            errors=errors,
            used_classes=used_classes,
            missing_configs=missing_configs,
            unused_configs=unused_configs,
        )

    def _format_item_list(self, items: list[str], title: str) -> list[str]:
        """Format a list of items with title."""
        lines: list[str] = []
        if items:
            lines.append(f"\n{title}:")
            for item in sorted(set(items)):
                lines.append(f"  - {item}")
        return lines

    def _format_errors_by_severity(
        self, result: ValidationResult
    ) -> list[str]:
        """Format errors and warnings by severity."""
        lines: list[str] = []
        for severity in ["error", "warning"]:
            items = [e for e in result.errors if e.severity == severity]
            if items:
                severity_upper = severity.upper()
                lines.append(f"\n{severity_upper}s ({len(items)}):")
                for item in items:
                    location = f" ({item.location})" if item.location else ""
                    lines.append(
                        f"  [{severity_upper}] {item.message}{location}"
                    )
        return lines

    def format_report(self, result: ValidationResult) -> str:
        """
        Format validation result as human-readable report.

        Args:
            result: ValidationResult from validate()

        Returns:
            Formatted report string
        """
        lines: list[str] = []

        # Header
        status = "VALID" if result.valid else "INVALID"
        lines.append(f"Descriptor Validation: {status}")
        lines.append("=" * 60)

        # Used classes
        lines.extend(
            self._format_item_list(result.used_classes, "\nUsed Components")
        )

        # Errors and warnings
        lines.extend(self._format_errors_by_severity(result))

        # Missing configs
        lines.extend(
            self._format_item_list(
                result.missing_configs, "\nMissing Configurations"
            )
        )

        # Unused configs
        lines.extend(
            self._format_item_list(
                result.unused_configs, "\nUnused Configurations"
            )
        )

        return "\n".join(lines)
