# tools/dawnpy/src/dawnpy/descriptor/generation/system.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""System (OBJTYPE_ANY) descriptor generation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import SystemObject


class SystemConfigGenerator:
    """Generate System object configuration payloads."""

    def __init__(
        self,
        *,
        system_types: dict[str, Any],
        format_helper: DescriptorFormatHelper | None = None,
    ) -> None:
        """Initialize with the System type map."""
        self._system_types = system_types
        self._format_helper = format_helper or DescriptorFormatHelper()

    def generate_system_config(
        self, macro_name: str, obj: SystemObject
    ) -> list[str]:
        """Generate configuration for a System object."""
        lines: list[str] = []
        fmt = self._format_helper
        config = obj.config
        field_defs = self._system_types[obj.system_type].config_fields

        present = [f for f in field_defs if f.name in config]
        fmt.append_line(lines, 1, f"{macro_name}, {len(present)},")

        for field_def in present:
            cpp_helper = field_def.cpp_helper
            value = config[field_def.name]

            if field_def.value_type == "string":
                packed = fmt.pack_string(str(value))
                fmt.append_line(lines, 2, f"{cpp_helper}({len(packed)}),")
                fmt.append_words(lines, packed, level=3)
            else:
                fmt.append_line(lines, 2, f"{cpp_helper}(),")
                fmt.append_line(lines, 3, f"{int(value)},")

        return lines
