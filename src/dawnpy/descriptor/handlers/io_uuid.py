# tools/dawnpy/src/dawnpy/descriptor/handlers/io_uuid.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``uuid`` IO type (no per-instance fields)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "uuid"
cpp_class: str = "CIOUuid"
nuttx_requirements: tuple[str, ...] = ("CONFIG_BOARDCTL_UNIQUEID",)
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """No per-instance config fields."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
