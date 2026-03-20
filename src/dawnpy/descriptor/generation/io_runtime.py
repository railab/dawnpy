# tools/dawnpy/src/dawnpy/descriptor/io_generator_runtime.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Leaf module shared by the IO C++ generator and per-type handlers.

Mirrors :mod:`dawnpy.descriptor.encoding.proto_runtime`: holds the dispatch
context dataclass passed to per-IO C++ generators (``generate_cpp``).
Lives at the descriptor package root so handlers under
``descriptor/handlers/io_*.py`` can import it at top-level without
creating an import cycle through ``io_generators``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dawnpy.descriptor.config_access import ConfigRwGrants
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.definitions.objects import DescriptorObject
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper


@dataclass
class IoGeneratorContext:
    """Shared dependencies passed to every per-IO C++ generator call."""

    config_loader: ConfigLoader
    format_helper: DescriptorFormatHelper
    objects: dict[str, DescriptorObject]
    config_rw_grants: ConfigRwGrants = field(default_factory=dict)
