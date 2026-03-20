# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_nxscope_dummy.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``nxscope_dummy`` PROTO type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.handlers._proto_nxscope_common import (
    encode_nxscope_iobind2,
    iobind2_field,
    nxscope_allocation_rows,
    resolve_nxscope_bindings,
)

yaml_type: str = "nxscope_dummy"
cpp_class: str = "CProtoNxscopeDummy"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_LOGGING_NXSCOPE",
    "CONFIG_LOGGING_NXSCOPE_INTF_DUMMY",
    "CONFIG_LOGGING_NXSCOPE_PROTO_SER",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "nxscope_iobind": ("CProtoNxscopeDummy", "cfgIdIOBind"),
    "nxscope_iobind2": ("CProtoNxscopeDummy", "cfgIdIOBind2"),
}
dtype_names: dict[str, str] = {}
enum_value_maps: dict[str, tuple[str, str]] = {}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {"nxscope_name": 12}
resolve_bindings = resolve_nxscope_bindings


def allocation_rows(proto: Any) -> list[list[str]]:  # pragma: no cover
    """Return NXScope allocation summary rows."""
    return nxscope_allocation_rows(proto.config, proto.bindings)


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema."""
    return [iobind2_field(cpp_class)]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Emit the iobind2 + standard bindings blocks."""
    encode_nxscope_iobind2(ctx)
