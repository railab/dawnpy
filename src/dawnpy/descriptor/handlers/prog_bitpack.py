"""Handler for ``bitpack`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "bitpack"
cpp_class: str = "CProgBitPack"

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
    """Return the user-facing YAML config schema for ``bitpack``."""
    return [
        ConfigField(
            name="inputs",
            cpp_helper=f"{cpp_class}::cfgIdInputs",
            value_type="bitpack_inputs",
        ),
        ConfigField(
            name="output",
            cpp_helper=f"{cpp_class}::cfgIdOutput",
            value_type="id_single",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the configured output-side target for ``bitpack``."""
    output_ref = resolve_reference(obj.config.get("output"))
    return {output_ref} if output_ref else set()


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate ``bitpack`` input/output dtype constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    input_entries = config.get("inputs", [])
    output_ref = config.get("output")
    errors: list[str] = []

    if isinstance(input_entries, list):
        for entry in input_entries:
            if not isinstance(entry, dict):
                continue
            io_ref = resolve_reference(entry.get("io"))
            if not io_ref:
                continue
            io = io_map.get(io_ref)
            if io is None:
                continue
            if io.dtype not in _BITWISE_IO_DTYPES:
                errors.append(
                    f"Program {obj.obj_id} invalid: bitpack input "
                    f"'{io_ref}' uses unsupported dtype '{io.dtype}'"
                )

    out_ref = resolve_reference(output_ref) if output_ref else None
    if out_ref:
        io = io_map.get(out_ref)
        if io is not None and io.dtype not in _BITWISE_IO_DTYPES:
            errors.append(
                f"Program {obj.obj_id} invalid: bitpack output "
                f"'{out_ref}' uses unsupported dtype '{io.dtype}'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``bitpack``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    input_entries = config.get("inputs", [])
    input_words: list[int] = []
    if isinstance(input_entries, list):
        for inp in input_entries:
            if isinstance(inp, dict):
                io_ref = resolve_reference(inp.get("io", ""))
                io_id = obj_ids.get(io_ref, 0) if io_ref else 0
                bit_val = int(inp.get("bit", 0))
                input_words.append(io_id)
                input_words.append(bit_val)

    if input_words:
        cfg_inp = header_cfg_id(cpp_class, "cfgIdInputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(input_words), cfg_inp),
                input_words,
            )
        )

    output = config.get("output", "")
    out_ref = resolve_reference(output) if output else None
    out_id = obj_ids.get(out_ref, 0) if out_ref else 0
    if out_id:
        cfg_out = header_cfg_id(cpp_class, "cfgIdOutput")
        items.append((cfg_id(3, prog_cls, 0, False, 1, cfg_out), [out_id]))
