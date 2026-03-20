# tools/dawnpy/src/dawnpy/descriptor/handlers/io_uname.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``uname`` IO type (variant-driven)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "uname"
cpp_class: str = "CIOUname"
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {"hostname": "char"}


def config_fields() -> list[ConfigField]:
    """No per-instance config fields (variant selects the C++ helper)."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
