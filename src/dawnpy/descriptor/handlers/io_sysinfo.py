# tools/dawnpy/src/dawnpy/descriptor/handlers/io_sysinfo.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``sysinfo`` IO type (variant-driven)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "sysinfo"
cpp_class: str = "CIOSysinfo"
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {"uptime": "uint64"}


def config_fields() -> list[ConfigField]:
    """No per-instance config fields (variant selects the C++ helper)."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
