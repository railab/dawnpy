# tools/dawnpy/src/dawnpy/descriptor/handlers/io_adc_sync.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``adc_sync`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "adc_sync"
cpp_class: str = "CIOAdcSync"
nuttx_requirements: tuple[str, ...] = ("CONFIG_ADC",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "int32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Hardware trigger frequency."""
    return [
        ConfigField(
            name="trigger_freq",
            cpp_helper="CIOAdcSync::cfgIdTriggerFreq",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Defer to the generic encoder (trigger_freq is a plain int field)."""
    del ctx  # pragma: no cover
