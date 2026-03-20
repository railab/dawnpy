# tools/dawnpy/src/dawnpy/descriptor/handlers/io_dummy.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``dummy`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.handlers._io_dummy_common import encode_dummy_block
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "dummy"
cpp_class: str = "CIODummy"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``dummy``."""
    return [
        ConfigField(
            name="dim", cpp_helper="CIODummy::cfgIdDim", value_type="int"
        ),
        ConfigField(
            name="init_value",
            cpp_helper="CIODummy::cfgIdInitval",
            value_type="auto",
            params=["dtype_param", "rw", "dim"],
            default_params=["auto", True, 1],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit dim + init_value cfg items."""
    encode_dummy_block(
        ctx,
        dim_cfg=load_header_cfg_id(cpp_class, "cfgIdDim"),
        init_cfg=load_header_cfg_id(cpp_class, "cfgIdInitval"),
    )
