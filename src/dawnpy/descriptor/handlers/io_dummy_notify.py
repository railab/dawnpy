# tools/dawnpy/src/dawnpy/descriptor/handlers/io_dummy_notify.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``dummy_notify`` IO type."""

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._io_dummy_common import encode_dummy_block
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "dummy_notify"
cpp_class: str = "CIODummyNotify"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_TIMER_FD",
    "CONFIG_TIMER_FD_POLL",
)
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``dummy_notify``."""
    return [
        ConfigField(
            name="dim", cpp_helper="CIODummyNotify::cfgIdDim", value_type="int"
        ),
        ConfigField(
            name="init_value",
            cpp_helper="CIODummyNotify::cfgIdInitval",
            value_type="auto",
            params=["dtype_param", "rw", "dim"],
            default_params=["auto", True, 1],
        ),
        ConfigField(
            name="interval_us",
            cpp_helper="CIODummyNotify::cfgInterval",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
        ConfigField(
            name="notify_on_write",
            cpp_helper="CIODummyNotify::cfgNotifyOnWrite",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit dim, init_value, and interval_us cfg items."""
    encode_dummy_block(
        ctx,
        dim_cfg=header_cfg_id(cpp_class, "cfgIdDim"),
        init_cfg=header_cfg_id(cpp_class, "cfgIdInitval"),
    )
    if "interval_us" in ctx.config:
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["uint32"]),
                    config_field_is_rw(
                        ctx.config_rw_grants, ctx.obj.obj_id, "interval_us"
                    ),
                    1,
                    header_cfg_id(cpp_class, "cfgInterval"),
                ),
                [int(ctx.config["interval_us"])],
            )
        )
    if "notify_on_write" in ctx.config:
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["uint32"]),
                    config_field_is_rw(
                        ctx.config_rw_grants,
                        ctx.obj.obj_id,
                        "notify_on_write",
                    ),
                    1,
                    header_cfg_id(cpp_class, "cfgNotifyOnWrite"),
                ),
                [int(bool(ctx.config["notify_on_write"]))],
            )
        )
