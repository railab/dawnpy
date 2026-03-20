# tools/dawnpy/src/dawnpy/descriptor/handlers/io_pwm.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``pwm`` IO type."""

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "pwm"
cpp_class: str = "CIOPwm"
nuttx_requirements: tuple[str, ...] = ("CONFIG_PWM", "CONFIG_PWM_MULTICHAN")
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "uint32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return PWM-specific YAML config schema."""
    return [
        ConfigField(
            name="freq",
            cpp_helper="CIOPwm::cfgIdFreq",
            value_type="int",
            params=["rw"],
            default_params=[False],
        )
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit optional frequency config item."""
    if "freq" not in ctx.config:
        return
    ctx.items.append(
        (
            cfg_id(
                1,
                ctx.io_cls,
                int(ctx.io_dtype_map["uint32"]),
                config_field_is_rw(
                    ctx.config_rw_grants, ctx.obj.obj_id, "freq"
                ),
                1,
                load_header_cfg_id(cpp_class, "cfgIdFreq"),
            ),
            [int(ctx.config["freq"])],
        )
    )
