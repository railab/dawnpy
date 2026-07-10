# tools/dawnpy/src/dawnpy/descriptor/generation/prog_base.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared dependency context for the program C++ source generator.

Mirrors :mod:`dawnpy.descriptor.generation.io_runtime` and
:mod:`dawnpy.descriptor.generation.proto_base`: holds the dispatch context
passed to a program handler's optional ``generate_cpp(macro_name, obj, ctx)``
whole-object override.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dawnpy.descriptor.config_access import ConfigRwGrants
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper


@dataclass
class ProgGeneratorContext:
    """Shared dependencies passed to a per-program C++ generator call."""

    config_loader: Any
    prog_types: dict[str, Any]
    format_helper: DescriptorFormatHelper
    config_rw_grants: ConfigRwGrants = field(default_factory=dict)
