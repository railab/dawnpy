# tools/dawnpy/src/dawnpy/descriptor/handlers/io_adc_fetch.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``adc_fetch`` IO type (no per-instance fields)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "adc_fetch"
cpp_class: str = "CIOAdcFetch"
nuttx_requirements: tuple[str, ...] = ("CONFIG_ADC",)
no_fields: bool = True
pass_through: bool = False
dtype: str | None = "int32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """No per-instance config fields."""
    return []


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
