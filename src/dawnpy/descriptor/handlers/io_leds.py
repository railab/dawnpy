# tools/dawnpy/src/dawnpy/descriptor/handlers/io_leds.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``leds`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "leds"
cpp_class: str = "CIOLeds"
nuttx_requirements: tuple[str, ...] = ("CONFIG_USERLED",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "uint32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the per-instance YAML config schema for ``leds``."""
    return [
        ConfigField(
            name="init_val",
            cpp_helper="CIOLeds::cfgIdInitVal",
            value_type="uint32",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:  # pragma: no cover
    """No per-instance binary encoding - init_val handled by standard path."""
    del ctx
