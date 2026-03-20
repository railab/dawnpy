# tools/dawnpy/src/dawnpy/descriptor/config_loader.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Configuration loader for descriptor generator schemas."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField, ProtoSchema
from dawnpy.headerdefs import (
    HeaderDefsError,
    load_header_metadata_defs,
    load_header_nimble_service_defs,
)


class ConfigLoader:
    """Loads and provides access to all configuration schemas."""

    def __init__(self) -> None:
        """Initialize config loader."""
        self.metadata_fields = self._load_metadata_fields()
        self.nimble_service_config = self._load_nimble_service_config()

    def get_io_config_fields(self, io_type: str) -> list[ConfigField]:
        """Return common + per-type config fields for an IO yaml-token."""
        from dawnpy.descriptor.definitions import io_family as _io
        from dawnpy.descriptor.definitions import registry as _types

        common = list(_io.get_common_fields())
        info = _types.IO_TYPES.get(io_type)
        specific = list(info.config_fields) if info is not None else []
        return common + specific

    def get_prog_config_fields(self, prog_type: str) -> list[ConfigField]:
        """Return standard + per-type config fields for a PROG yaml-token."""
        from dawnpy.descriptor.definitions import prog_family as _prog
        from dawnpy.descriptor.definitions import registry as _types

        standard = list(_prog.get_standard_fields())
        info = _types.PROG_TYPES.get(prog_type)
        specific = list(info.config_fields) if info is not None else []
        return standard + specific

    def get_prog_standard_fields(self) -> list[ConfigField]:
        """Return standard configuration fields shared by all PROG types."""
        from dawnpy.descriptor.definitions import prog_family as _prog

        return list(_prog.get_standard_fields())

    def get_prog_type_fields(self, prog_type: str) -> list[ConfigField]:
        """Return type-specific config fields for a PROG yaml-token."""
        from dawnpy.descriptor.definitions import registry as _types

        info = _types.PROG_TYPES.get(prog_type)
        if info is None:
            return []  # pragma: no cover
        return list(info.config_fields)

    def get_nimble_service_names(self) -> list[str]:
        """Return list of supported Nimble service names."""
        return list(
            self.nimble_service_config.get("by_name", {}).keys()
        )  # pragma: no cover

    def get_proto_config_schema(self, proto_type: str) -> ProtoSchema | None:
        """Return resolved per-protocol config schema, or ``None``."""
        from dawnpy.descriptor.definitions import registry as _types

        info = _types.PROTO_TYPES.get(proto_type)
        if info is None:
            return None
        return ProtoSchema(
            proto_type=proto_type,
            uses_standard_bindings=bool(
                getattr(info, "uses_standard_bindings", True)
            ),
            fields=list(info.config_fields),
        )

    def proto_uses_standard_bindings(self, proto_type: str) -> bool:
        """Return True if protocol uses the standard bindings field."""
        schema = self.get_proto_config_schema(proto_type)
        if schema is None:
            return False  # pragma: no cover
        return schema.uses_standard_bindings

    def _load_metadata_fields(self) -> list[dict[str, Any]]:
        """Load metadata field definitions."""
        try:
            result = load_header_metadata_defs()
        except HeaderDefsError as exc:
            raise RuntimeError(
                f"Failed to load metadata field definitions: {exc}"
            ) from exc
        return result

    def get_metadata_fields(self) -> list[dict[str, Any]]:
        """Return all metadata field definitions."""
        return self.metadata_fields

    def _load_nimble_service_config(self) -> dict[str, Any]:
        """Load nimble service configuration."""
        try:
            defs = load_header_nimble_service_defs()
        except HeaderDefsError as exc:
            raise RuntimeError(
                f"Failed to load nimble service definitions: {exc}"
            ) from exc
        return {"by_name": defs}

    def get_nimble_service_config(
        self, service_name: str
    ) -> dict[str, Any] | None:
        """Return configuration for a nimble service by name."""
        result: dict[str, Any] | None = self.nimble_service_config[
            "by_name"
        ].get(service_name)
        return result

    def get_proto_nested_enum_map(
        self, proto_type: str, nested_field: str, element_field: str
    ) -> dict[str, str]:
        """Return enum mapping for nested protocol element fields."""
        schema = self.get_proto_config_schema(proto_type)
        if schema is None:  # pragma: no cover
            return {}
        nested = schema.find_field(nested_field)
        if nested is None:
            return {}
        for element in nested.element_fields:
            if element.name == element_field:
                return {str(k): str(v) for k, v in element.enum_values.items()}
        return {}  # pragma: no cover

    def get_proto_nested_enum_prefix(
        self, proto_type: str, nested_field: str, element_field: str
    ) -> str:
        """Return enum prefix for nested protocol element fields."""
        schema = self.get_proto_config_schema(proto_type)
        if schema is None:  # pragma: no cover
            return ""
        nested = schema.find_field(nested_field)
        if nested is None:
            return ""
        for element in nested.element_fields:
            if element.name == element_field:
                return element.enum_prefix
        return ""  # pragma: no cover
