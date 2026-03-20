# tools/dawnpy/src/dawnpy/descriptor/handlers/io_fileio.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``fileio`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "fileio"
cpp_class: str = "CIOFile"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``fileio``."""
    return [
        ConfigField(
            name="path", cpp_helper="CIOFile::cfgIdPath", value_type="string"
        ),
        ConfigField(
            name="perm",
            cpp_helper="CIOFile::cfgIdPerm",
            value_type="int",
            params=[],
            default_params=[],
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit path + perm cfg items."""
    config = ctx.config
    if "path" in config:
        fmt = DescriptorFormatHelper()
        path_words = fmt.pack_string(str(config["path"]))
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["char"]),
                    False,
                    len(path_words),
                    header_cfg_id(cpp_class, "cfgIdPath"),
                ),
                path_words,
            )
        )
    if "perm" in config:
        ctx.items.append(
            (
                cfg_id(
                    1,
                    ctx.io_cls,
                    int(ctx.io_dtype_map["uint8"]),
                    False,
                    1,
                    header_cfg_id(cpp_class, "cfgIdPerm"),
                ),
                [int(config["perm"])],
            )
        )
