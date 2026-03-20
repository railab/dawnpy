# tools/dawnpy/src/dawnpy/descriptor/handlers/io_timestamp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``timestamp`` IO type."""

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "timestamp"
cpp_class: str = "CIOTimestamp"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``timestamp``."""
    return [
        ConfigField(
            name="interval_us",
            cpp_helper="CIOTimestamp::cfgInterval",
            value_type="int",
            params=["rw"],
            default_params=[False],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit the interval_us cfg item."""
    if "interval_us" not in ctx.config:
        return  # pragma: no cover
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
                load_header_cfg_id(cpp_class, "cfgInterval"),
            ),
            [int(ctx.config["interval_us"])],
        )
    )
