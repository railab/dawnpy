# tools/dawnpy/src/dawnpy/descriptor/handlers/io_adc_stream.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``adc_stream`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "adc_stream"
cpp_class: str = "CIOAdcStream"
nuttx_requirements: tuple[str, ...] = ("CONFIG_ADC",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "int32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML schema (just batch_size)."""
    return [
        ConfigField(
            name="batch_size",
            cpp_helper="CIOAdcStream::cfgIdBatchSize",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Defer to the generic encoder (batch_size is a plain int field)."""
    del ctx  # pragma: no cover
