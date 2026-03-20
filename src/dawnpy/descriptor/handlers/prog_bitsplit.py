"""Handler for ``bitsplit`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    iobind_field,
)
from dawnpy.descriptor.support.utils import resolve_references
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "bitsplit"
cpp_class: str = "CProgBitSplit"

_BITWISE_IO_DTYPES: set[str] = {
    "bool",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "float",
    "double",
    "b16",
    "ub16",
}


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``bitsplit``."""
    return [
        iobind_field(cpp_class),
        ConfigField(
            name="bits",
            cpp_helper=f"{cpp_class}::cfgIdBits",
            value_type="uint32_list",
        ),
    ]


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate ``bitsplit`` source/output dtype constraints."""
    errors: list[str] = []

    config = obj.config if isinstance(obj.config, dict) else {}
    input_refs = resolve_references(config.get("sources", obj.inputs))
    outputs = config.get("outputs", obj.outputs)
    output_refs = resolve_references(
        outputs if isinstance(outputs, list) else []
    )

    for input_ref in input_refs:
        io = io_map.get(input_ref)
        if io is None:
            continue
        if io.dtype not in _BITWISE_IO_DTYPES:
            errors.append(
                f"Program {obj.obj_id} invalid: bitsplit input "
                f"'{input_ref}' uses unsupported dtype '{io.dtype}'"
            )

    for output_ref in output_refs:
        io = io_map.get(output_ref)
        if io is None:
            continue
        if io.dtype not in _BITWISE_IO_DTYPES:
            errors.append(
                f"Program {obj.obj_id} invalid: bitsplit output "
                f"'{output_ref}' uses unsupported dtype '{io.dtype}'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``bitsplit``-specific config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)

    config = obj.config if isinstance(obj.config, dict) else {}
    bits = config.get("bits", [])
    if bits:
        cfg_b = load_header_cfg_id(cpp_class, "cfgIdBits")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(bits), cfg_b),
                [int(b) for b in bits],
            )
        )
