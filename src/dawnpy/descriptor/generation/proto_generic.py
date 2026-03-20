# tools/dawnpy/src/dawnpy/descriptor/generation/proto_generic.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Generic schema-driven protocol descriptor generation (fallback)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.support.utils import resolve_flexible_reference

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject

    from .proto_base import ProtoGeneratorContext


class GenericProtoConfigGenerator:
    """Generate custom protocol fields from generic schema definitions.

    This is the fallback used when no protocol-specific generator is
    registered for a given ``proto_type``. It is *not* registered itself -
    the dispatcher invokes it explicitly when no specialized handler matches.
    """

    def __init__(self, ctx: ProtoGeneratorContext) -> None:
        """Store the shared dependency context."""
        self.ctx = ctx

    def count_config_items(
        self,
        fields: list[ConfigField],
        config: dict[str, Any],
        uses_standard: bool,
        bindings: list[str],
    ) -> int:
        """Count custom protocol config items to emit."""
        config_count = 0
        if uses_standard and bindings:
            config_count += 1

        for field in fields:
            if field.nested:
                continue
            if field.name in config:
                config_count += 1

        return config_count

    def pack_string_array_field(
        self, value: Any, field: ConfigField
    ) -> tuple[int, list[int]]:
        """Pack string arrays and return size argument plus packed words."""
        all_words: list[int] = []
        fixed_bytes = field.string_fixed_bytes
        values = value if isinstance(value, list) else []

        for item in values:
            if fixed_bytes is not None:
                size = int(fixed_bytes)
                all_words.extend(
                    self.ctx.format_helper.pack_fixed_string(str(item), size)
                )
            else:
                all_words.extend(self.ctx.format_helper.pack_string(str(item)))

        if field.string_array_size == "count":
            return len(values), all_words
        return len(all_words), all_words

    def generate_nxscope_iobind2_field(
        self, value: Any, field: ConfigField, cpp_helper: str
    ) -> list[str]:
        """Generate nxscope iobind2 config field."""
        lines: list[str] = []
        entries = value if isinstance(value, list) else []
        resolved_entries = []
        for entry in entries:
            if isinstance(entry, str):
                name = ""
            elif isinstance(entry, dict):
                name = entry.get("name", "")
            else:
                continue
            resolved_id = resolve_flexible_reference(entry)
            if resolved_id:
                resolved_entries.append((resolved_id, name))

        self.ctx.format_helper.append_line(
            lines, 2, f"{cpp_helper}({len(resolved_entries)}),"
        )
        fixed_bytes = int(field.string_fixed_bytes or 12)
        for obj_id, name in resolved_entries:
            self.ctx.format_helper.append_line(lines, 3, f"{obj_id.upper()},")
            self.ctx.format_helper.append_words(
                lines,
                self.ctx.format_helper.pack_fixed_string(
                    str(name), fixed_bytes
                ),
                level=3,
            )
        return lines

    def generate_generic_field(
        self, value: Any, field: ConfigField
    ) -> list[str]:
        """Generate lines for one generic custom protocol field."""
        lines: list[str] = []
        cpp_helper = field.cpp_helper
        value_type = field.value_type

        if not cpp_helper:
            return lines

        if value_type == "string":
            packed_words = self.ctx.format_helper.pack_string(str(value))
            self.ctx.format_helper.append_line(
                lines, 2, f"{cpp_helper}({len(packed_words)}),"
            )
            self.ctx.format_helper.append_words(lines, packed_words, level=3)
            return lines

        if value_type == "nxscope_iobind2":
            return self.generate_nxscope_iobind2_field(
                value, field, cpp_helper
            )

        if value_type == "string_array":
            size_value, all_words = self.pack_string_array_field(value, field)
            self.ctx.format_helper.append_line(
                lines, 2, f"{cpp_helper}({size_value}),"
            )
            self.ctx.format_helper.append_words(lines, all_words, level=3)
            return lines

        self.ctx.format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        if value_type == "int" and field.value_format == "hex":
            formatted_hex = self.ctx.format_helper.format_numeric(
                value, hex_format=True
            )
            self.ctx.format_helper.append_line(lines, 3, f"{formatted_hex},")
        else:
            self.ctx.format_helper.append_line(
                lines, 3, f"{self.ctx.format_helper.format_numeric(value)},"
            )
        return lines

    def generate(
        self,
        macro_name: str,
        proto_type: str,
        obj: ProtocolObject,
        fields: list[ConfigField],
    ) -> list[str]:
        """Generate custom protocol config for non-specialized protocols."""
        lines: list[str] = []
        config = obj.config
        bindings = obj.bindings
        uses_standard = self.ctx.proto_uses_standard_bindings(proto_type)
        config_count = self.count_config_items(
            fields, config, uses_standard, bindings
        )

        self.ctx.format_helper.append_line(
            lines, 1, f"{macro_name}, {config_count},"
        )

        for field in fields:
            if field.nested:
                continue  # pragma: no cover
            if field.name not in config:
                continue  # pragma: no cover
            lines.extend(
                self.generate_generic_field(config[field.name], field)
            )

        if uses_standard and bindings:
            cpp_class = self.ctx.proto_cpp_class(proto_type)
            self.ctx.format_helper.append_line(
                lines, 2, f"{cpp_class}::cfgIdIOBind({len(bindings)}),"
            )
            for binding_id in bindings:  # pragma: no cover
                self.ctx.format_helper.append_line(
                    lines, 3, f"{binding_id.upper()},"
                )

        return lines
