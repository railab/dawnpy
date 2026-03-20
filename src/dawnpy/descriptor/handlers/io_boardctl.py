# tools/dawnpy/src/dawnpy/descriptor/handlers/io_boardctl.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``boardctl`` IO type (variant-driven)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "boardctl"
cpp_class: str = "CIOBoardctl"
no_fields: bool = True
pass_through: bool = False
dtype: str | None = "uint32"
variant_dtypes: dict[str, str] = {
    "reset": "int32",
    "reset_cause": "uint32",
    "poweroff": "int32",
}


def config_fields() -> list[ConfigField]:
    """No per-instance config fields (variant selects the C++ helper)."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
