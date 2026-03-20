# tools/dawnpy/src/dawnpy/descriptor/handlers/io_descselector.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``descselector`` IO type (pass-through)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "descselector"
cpp_class: str = "CIODescSelector"
no_fields: bool = False
pass_through: bool = True
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Pass-through types have no user-facing fields."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Pass-through: the encoder writes the pre-built block as-is."""
    del ctx
