# tools/dawnpy/src/dawnpy/descriptor/generation/proto_base.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared dependency context for the protocol C++ source generator.

The per-protocol class hierarchy that used to live here has moved to
``dawnpy.descriptor.handlers.proto_*`` (each handler exports
``generate_cpp(macro_name, obj, ctx) -> list[str]`` and optionally
``collect_cpp_headers(config, ctx) -> set[str]``). Only the shared
context dataclass remains here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper


@dataclass
class ProtoGeneratorContext:
    """Shared dependencies passed to every protocol C++ generator call."""

    config_loader: Any
    proto_types: dict[str, Any]
    format_helper: DescriptorFormatHelper
    proto_uses_standard_bindings: Callable[[str], bool]
    proto_cpp_class: Callable[[str], str]
    resolve_references: Callable[[list[Any]], list[str]]
    resolve_reference: Callable[[Any], str | None]
