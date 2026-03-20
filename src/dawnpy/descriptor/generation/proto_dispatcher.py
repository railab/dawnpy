# tools/dawnpy/src/dawnpy/descriptor/generation/proto_dispatcher.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Registry-driven protocol config dispatcher.

Per-type C++ generators live in ``dawnpy.descriptor.handlers.proto_*``
alongside the binary encoders. This dispatcher consults
``PROTO_HANDLER_REGISTRY[t].generate_cpp`` first and falls through to
the generic schema-driven generator for OOT protocol types.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

from .proto_base import ProtoGeneratorContext
from .proto_generic import GenericProtoConfigGenerator

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper


class ProtocolConfigGenerator:
    """Dispatch protocol config generation to per-type handlers."""

    def __init__(self, ctx: ProtoGeneratorContext) -> None:
        """Store the shared dependency context + generic fallback."""
        self.ctx = ctx
        self._generic = GenericProtoConfigGenerator(ctx)

    @classmethod
    def create(
        cls,
        *,
        config_loader: Any,
        proto_types: dict[str, Any],
        proto_uses_standard_bindings: Callable[[str], bool],
        proto_cpp_class: Callable[[str], str],
        resolve_references: Callable[[list[Any]], list[str]],
        resolve_reference: Callable[[Any], str | None],
        format_helper: DescriptorFormatHelper,
    ) -> ProtocolConfigGenerator:
        """Build dispatcher from raw dependency callbacks."""
        ctx = ProtoGeneratorContext(
            config_loader=config_loader,
            proto_types=proto_types,
            format_helper=format_helper,
            proto_uses_standard_bindings=proto_uses_standard_bindings,
            proto_cpp_class=proto_cpp_class,
            resolve_references=resolve_references,
            resolve_reference=resolve_reference,
        )
        return cls(ctx)

    def generate_proto_config(
        self, macro_name: str, obj: ProtocolObject
    ) -> list[str]:
        """Generate configuration for a Protocol object."""
        proto_type = obj.proto_type
        config = obj.config
        bindings = obj.bindings

        proto_schema = self.ctx.config_loader.get_proto_config_schema(
            proto_type
        )
        if proto_schema is None:  # pragma: no cover
            return [self.ctx.format_helper.line(1, f"{macro_name}, 0,")]

        if proto_schema.uses_standard_bindings and not config:
            # pragma: no cover
            return self.generate_simple_proto_bindings(
                macro_name, proto_type, bindings
            )

        # Per-type handler owns its own C++ emitter when present.
        handler = PROTO_HANDLER_REGISTRY.get(proto_type)
        if handler is not None and hasattr(handler, "generate_cpp"):
            result = handler.generate_cpp(macro_name, obj, self.ctx)
            return list(result)

        if not proto_schema.fields:
            return self.generate_simple_proto_bindings(
                macro_name, proto_type, bindings
            )

        return self._generic.generate(
            macro_name, proto_type, obj, proto_schema.fields
        )

    def generate_simple_proto_bindings(
        self, macro_name: str, proto_type: str, bindings: list[str]
    ) -> list[str]:
        """Generate simple protocol bindings."""
        lines: list[str] = []
        cpp_class = self.ctx.proto_types[proto_type].cpp_class

        if bindings:
            self.ctx.format_helper.append_line(lines, 1, f"{macro_name}, 1,")
            self.ctx.format_helper.append_line(
                lines, 2, f"{cpp_class}::cfgIdIOBind({len(bindings)}),"
            )
            for binding_id in bindings:
                self.ctx.format_helper.append_line(
                    lines, 3, f"{binding_id.upper()},"
                )
        else:
            self.ctx.format_helper.append_line(lines, 1, f"{macro_name}, 0,")

        return lines

    def collect_proto_headers(
        self, proto_type: str, config: dict[str, Any]
    ) -> set[str]:
        """Collect protocol-specific include headers for one object config."""
        handler = PROTO_HANDLER_REGISTRY.get(proto_type)
        if handler is None or not hasattr(handler, "collect_cpp_headers"):
            return set()
        result = handler.collect_cpp_headers(config, self.ctx)
        return set(result)
