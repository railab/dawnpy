# tools/dawnpy/src/dawnpy/descriptor/handlers/io_virt.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``virt`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "virt"
cpp_class: str = "CIOVirt"
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return no YAML config fields; virt shape is producer-owned."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:  # pragma: no cover
    """Virt IO has no descriptor-owned binary config."""
    del ctx
