# tools/dawnpy/src/dawnpy/descriptor/handlers/io_pulsecount.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``pulsecount`` IO type."""

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "pulsecount"
cpp_class: str = "CIOPulseCount"
nuttx_requirements: tuple[str, ...] = ("CONFIG_PULSECOUNT",)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = "uint32"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return pulsecount-specific YAML config schema."""
    return [
        ConfigField(
            name="high_ns",
            cpp_helper="CIOPulseCount::cfgIdHighNs",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
        ConfigField(
            name="low_ns",
            cpp_helper="CIOPulseCount::cfgIdLowNs",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit optional pulse timing config items."""
    if "high_ns" in ctx.config:
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["uint32"]),
                    config_field_is_rw(
                        ctx.config_rw_grants, ctx.obj.obj_id, "high_ns"
                    ),
                    1,
                    header_cfg_id(cpp_class, "cfgIdHighNs"),
                ),
                [int(ctx.config["high_ns"])],
            )
        )

    if "low_ns" in ctx.config:
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["uint32"]),
                    config_field_is_rw(
                        ctx.config_rw_grants, ctx.obj.obj_id, "low_ns"
                    ),
                    1,
                    header_cfg_id(cpp_class, "cfgIdLowNs"),
                ),
                [int(ctx.config["low_ns"])],
            )
        )
