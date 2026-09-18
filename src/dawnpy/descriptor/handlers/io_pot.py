# tools/dawnpy/src/dawnpy/descriptor/handlers/io_pot.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``pot`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "pot"
cpp_class: str = "CIOPot"
nuttx_requirements: tuple[str, ...] = ("CONFIG_POT",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "int32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the per-instance YAML config schema for ``pot``."""
    return [
        ConfigField(
            name="wiper",
            cpp_helper="CIOPot::cfgIdWiper",
            value_type="uint32",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit optional wiper config item."""
    if "wiper" not in ctx.config:
        return
    ctx.items.append(
        (
            cfg_id(
                1,
                ctx.io_cls,
                int(ctx.io_dtype_map["uint32"]),
                False,
                1,
                header_cfg_id(cpp_class, "cfgIdWiper"),
            ),
            [int(ctx.config["wiper"])],
        )
    )
