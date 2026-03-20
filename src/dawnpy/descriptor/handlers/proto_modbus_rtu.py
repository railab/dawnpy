# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_modbus_rtu.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``modbus_rtu`` PROTO type.

Owns cpp_class binding, user-facing config schema (incl. nested
``registers`` element fields with ``CProtoModbusRegs::MODBUS_TYPE_*``
hydrated at registry build time), and the binary serializer. Shares
the register-group encoder with :mod:`proto_modbus_tcp` via
:mod:`_proto_modbus_common`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.descriptor.handlers._proto_modbus_common import (
    emit_modbus_registers_cpp,
    encode_modbus_registers,
    modbus_allocation_rows,
    resolve_modbus_bindings,
)
from dawnpy.descriptor.support.utils import resolve_references

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import (
        DescriptorObject,
        ProtocolObject,
    )
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext


yaml_type: str = "modbus_rtu"
cpp_class: str = "CProtoModbusRtu"
nuttx_requirements: tuple[str, ...] = ("CONFIG_INDUSTRY_NXMODBUS",)
uses_standard_bindings: bool = False
multi_device: bool = True
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "modbus_iobind": ("CProtoModbusRtu", "cfgIdIOBind"),
    "modbus_path": ("CProtoModbusRtu", "cfgIdPath"),
    "modbus_baudrate": ("CProtoModbusRtu", "cfgIdBaud"),
}
dtype_names: dict[str, str] = {"string": "char", "int": "uint32"}
enum_value_maps: dict[str, tuple[str, str]] = {
    "modbus_type": ("CProtoModbusRegs", "MODBUS_TYPE_"),
}
defaults: dict[str, int] = {"modbus_config": 0, "modbus_start": 0}
fixed_string_bytes: dict[str, int] = {}


def _is_list_of_dicts(value: object) -> bool:
    """Return True when value is a list of mappings."""
    if not isinstance(value, list):
        return False
    return all(isinstance(item, dict) for item in value)


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return Modbus RTU allocation summary rows."""
    return modbus_allocation_rows(proto)


resolve_bindings = resolve_modbus_bindings


def validate_object(obj: Any) -> list[str]:
    """Validate the registers payload is a list of mappings."""
    registers = obj.config.get("registers")
    if registers is not None and not _is_list_of_dicts(registers):
        return ["config.registers must be a list of mappings"]
    return []


def validate_descriptor_context(
    proto_id: str,
    config: dict[str, Any],
    objects: dict[str, "DescriptorObject"],
) -> None:
    """Reject overlapping Modbus register ranges in one address space."""
    registers = config.get("registers")
    if not isinstance(registers, list):
        return  # pragma: no cover

    used: dict[str, list[tuple[int, int, int, str]]] = {
        "coil": [],
        "discrete": [],
        "holding": [],
        "input": [],
    }
    for idx, reg in enumerate(registers):
        if not isinstance(reg, dict):
            continue  # pragma: no cover

        reg_type = str(reg.get("type", "")).lower()
        space = _modbus_address_space(reg_type)
        if space is None:
            continue  # pragma: no cover

        start = int(reg.get("start", 0))
        bindings = resolve_references(reg.get("bindings", []))
        span = sum(
            _modbus_binding_registers(reg_type, binding, objects)
            for binding in bindings
        )
        end = start + span
        if span <= 0:
            continue  # pragma: no cover

        for prev_start, prev_end, prev_idx, prev_type in used[space]:
            if start < prev_end and prev_start < end:
                raise ValueError(
                    "modbus register overlap in "
                    f"{space} space for protocol '{proto_id}': "
                    f"block #{idx} ({reg_type}@{start}..{end - 1}) "
                    f"overlaps block #{prev_idx} "
                    f"({prev_type}@{prev_start}..{prev_end - 1})"
                )

        used[space].append((start, end, idx, reg_type))


def _modbus_address_space(reg_type: str) -> str | None:
    """Map register type to Modbus address space."""
    if reg_type in ("coil", "coil_packed"):
        return "coil"  # pragma: no cover
    if reg_type in ("discrete", "discrete_packed"):
        return "discrete"  # pragma: no cover
    if reg_type == "holding":
        return "holding"  # pragma: no cover
    if reg_type == "input":
        return "input"  # pragma: no cover
    return None  # pragma: no cover


def _modbus_binding_registers(
    reg_type: str,
    binding_id: str,
    objects: dict[str, "DescriptorObject"],
) -> int:
    """Return register/coil width for one binding in a Modbus block."""
    if reg_type in ("coil", "coil_packed", "discrete", "discrete_packed"):
        return 1  # pragma: no cover

    from dawnpy.descriptor.definitions.objects import IoObject

    obj = objects.get(binding_id)
    if not isinstance(obj, IoObject):
        return 1

    dtype = str(obj.dtype).lower()
    if dtype in ("uint64", "int64", "double"):
        return 4  # pragma: no cover
    if dtype in ("uint32", "int32", "float"):
        return 2  # pragma: no cover
    return 1  # pragma: no cover


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``modbus_rtu``."""
    return [
        ConfigField(
            name="path",
            cpp_helper="CProtoModbusRtu::cfgIdPath",
            value_type="string",
        ),
        ConfigField(
            name="registers",
            nested=True,
            array=True,
            element_fields=[
                ConfigField(
                    name="type",
                    value_type="enum",
                    enum_prefix="CProtoModbusRegs::MODBUS_TYPE_",
                ),
                ConfigField(name="config", value_type="int"),
                ConfigField(name="start", value_type="int"),
                ConfigField(name="count", value_type="computed"),
                ConfigField(
                    name="bindings",
                    cpp_helper="CProtoModbusRtu::cfgIdIOBind",
                    value_type="id_array",
                    size_calculation="4 + count",
                ),
            ],
        ),
    ]


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Encode Modbus RTU binary block into ``ctx.items``."""
    if "path" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["path"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                True,
                len(packed),
                ctx.cfg_id("modbus_path", 2),
            ),
            packed,
        )
    if "baudrate" in ctx.config:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("int"),
                True,
                1,
                ctx.cfg_id("modbus_baudrate", 3),
            ),
            [int(ctx.config["baudrate"])],
        )
    encode_modbus_registers(ctx, "modbus_iobind", 1)


def generate_cpp(
    macro_name: str, obj: ProtocolObject, gctx: ProtoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a Modbus RTU object."""
    lines: list[str] = []
    config = obj.config
    registers = config.get("registers", [])

    config_count = 0
    if "path" in config:
        config_count += 1
    if "port" in config:
        config_count += 1  # pragma: no cover
    if registers:
        config_count += 1
    gctx.format_helper.append_line(lines, 1, f"{macro_name}, {config_count},")

    if "path" in config:
        packed_words = gctx.format_helper.pack_string(str(config["path"]))
        gctx.format_helper.append_line(
            lines, 2, f"CProtoModbusRtu::cfgIdPath({len(packed_words)}),"
        )
        gctx.format_helper.append_words(lines, packed_words, level=3)
    if "port" in config:  # pragma: no cover
        gctx.format_helper.append_line(lines, 2, f"{cpp_class}::cfgIdPort(),")
        gctx.format_helper.append_line(lines, 3, f"{config['port']},")
    if registers:
        emit_modbus_registers_cpp(
            lines, registers, cpp_class, "modbus_rtu", gctx
        )
    return lines
