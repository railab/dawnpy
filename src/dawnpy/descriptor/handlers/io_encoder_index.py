# tools/dawnpy/src/dawnpy/descriptor/handlers/io_encoder_index.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``encoder_index`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "encoder_index"
cpp_class: str = "CIOEncoderIndex"
nuttx_requirements: tuple[str, ...] = ("CONFIG_SENSORS_QENCODER",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``encoder_index``."""
    return [
        ConfigField(
            name="posmax",
            cpp_helper="CIOEncoderIndex::cfgIdPosmax",
            value_type="int",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit the posmax cfg item."""
    if "posmax" not in ctx.config:
        return  # pragma: no cover
    ctx.items.append(
        (
            cfg_id(
                1,
                ctx.io_cls,
                int(ctx.io_dtype_map["uint32"]),
                False,
                1,
                header_cfg_id(cpp_class, "cfgIdPosmax"),
            ),
            [int(ctx.config["posmax"])],
        )
    )
