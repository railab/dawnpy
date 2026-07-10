# tools/dawnpy/src/dawnpy/descriptor/generation/prog.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Program descriptor C++ generation orchestrator.

Each program's type-specific config emission lives in its handler
(``handlers/prog_*.py``), symmetric with the binary ``encode_binary`` path.
This module only drives the shared per-object structure: the config-count
header, the iobind item, and the delegation to the handler's config emitter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.config_access import ConfigRwGrants
from dawnpy.descriptor.generation.prog_base import ProgGeneratorContext
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.descriptor.handlers._prog_config_cpp import (
    ProgFieldCppCtx,
    emit_config_fields_cpp,
)
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject

#: Value-types whose handler emits its own iobind item, replacing the
#: standard interleaved (source, output) iobind pairs.
_CUSTOM_IOBIND_VALUE_TYPES = frozenset(
    {"id_array_pairs", "gateway_iobind", "id_array_quads", "id_list"}
)


class ProgramConfigGenerator:
    """Generate program configuration payloads."""

    def __init__(
        self,
        *,
        config_loader: Any,
        prog_types: dict[str, Any],
        format_helper: DescriptorFormatHelper | None = None,
        config_rw_grants: Callable[[], ConfigRwGrants] | None = None,
    ) -> None:
        """Initialize with shared config loader and program type map."""
        self._config_loader = config_loader
        self._prog_types = prog_types
        self._format_helper = format_helper or DescriptorFormatHelper()
        self._config_rw_grants = config_rw_grants or (lambda: {})

    def generate_prog_config(  # pragma: no cover
        self, macro_name: str, obj: ProgramObject
    ) -> list[str]:
        """Generate configuration for a Program object."""
        lines: list[str] = []
        prog_type = obj.prog_type
        config = obj.config

        handler = PROG_HANDLER_REGISTRY.get(prog_type)

        # Per-type C++ emitter takes priority: a handler that owns its whole
        # config block exposes generate_cpp(macro_name, obj, ctx) - symmetric
        # with the IO/PROTO escape hatch. Handlers with only type-specific
        # fields use the emit_config_field_cpp hook below instead.
        if handler is not None and hasattr(handler, "generate_cpp"):
            gctx = ProgGeneratorContext(
                config_loader=self._config_loader,
                prog_types=self._prog_types,
                format_helper=self._format_helper,
                config_rw_grants=self._config_rw_grants(),
            )
            return list(handler.generate_cpp(macro_name, obj, gctx))

        # Get program class info
        prog_info = self._prog_types[prog_type]
        cpp_class = prog_info.cpp_class

        # Get standard and type-specific field definitions
        type_fields = self._config_loader.get_prog_type_fields(prog_type)

        # Type-specific custom iobind field replaces the standard iobind item
        has_custom_iobind = any(
            f.value_type in _CUSTOM_IOBIND_VALUE_TYPES for f in type_fields
        )

        # Compute total number of config items
        total_ids = len(obj.inputs) + len(obj.outputs)
        cfg_count = (0 if has_custom_iobind or total_ids == 0 else 1) + len(
            type_fields
        )

        self._format_helper.append_line(
            lines, 1, f"{macro_name}, {cfg_count},"
        )

        iobind_handled = False
        if handler is not None and total_ids > 0:
            iobind_handled = handler.emit_iobind_cpp(
                lines, obj, total_ids, self._format_helper, cpp_class
            )

        if not iobind_handled and not has_custom_iobind and total_ids > 0:
            # Standard iobind: interleaved (source, output) pairs
            self._format_helper.append_line(
                lines, 2, f"{cpp_class}::cfgIdIOBind({total_ids}),"
            )
            n_pairs = max(len(obj.inputs), len(obj.outputs))
            for i in range(n_pairs):
                src = obj.inputs[i] if i < len(obj.inputs) else obj.inputs[0]
                dst = (
                    obj.outputs[i] if i < len(obj.outputs) else obj.outputs[0]
                )
                self._format_helper.append_line(lines, 3, f"{src.upper()},")
                self._format_helper.append_line(lines, 3, f"{dst.upper()},")

        # Type-specific config items are owned by the program's handler; the
        # handler's per-field hook covers program-specific value-types and the
        # shared generic emitters cover the rest. A program type with config
        # fields but no handler module (e.g. OOT types using only generic
        # value-types) emits through the generic path directly.
        if type_fields:
            ctx = ProgFieldCppCtx(
                self._format_helper, self._config_rw_grants()
            )
            if handler is not None:
                handler.emit_config_cpp(lines, obj, config, type_fields, ctx)
            else:
                emit_config_fields_cpp(
                    None, prog_type, lines, obj, config, type_fields, ctx
                )

        return lines
