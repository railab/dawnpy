"""Handler for ``manytoone`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "manytoone"
cpp_class: str = "CProgManyToOne"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``manytoone``."""
    return [
        ConfigField(
            name="inputs",
            cpp_helper=f"{cpp_class}::cfgIdInputs",
            value_type="id_list",
        ),
        ConfigField(
            name="output",
            cpp_helper=f"{cpp_class}::cfgIdOutput",
            value_type="id_single",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the bridge output whose shape is owned by the program."""
    output = obj.config.get("output")
    if isinstance(output, list) and output:
        output_ref = resolve_reference(output[0])
    else:
        output_ref = resolve_reference(output)
    return {output_ref} if output_ref else set()


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate input/output dtype constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    input_refs = resolve_references(config.get("inputs", []))
    output_ref = resolve_reference(config.get("output"))
    errors: list[str] = []

    output = io_map.get(output_ref) if output_ref else None
    for input_ref in input_refs:
        io = io_map.get(input_ref)
        if io is None or output is None:
            continue
        if io.dtype != output.dtype:
            errors.append(
                f"Program {obj.obj_id} invalid: manytoone input "
                f"'{input_ref}' dtype '{io.dtype}' does not match output "
                f"'{output_ref}' dtype '{output.dtype}'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``manytoone``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    input_ids = [
        obj_ids[input_ref]
        for input_ref in resolve_references(config.get("inputs", []))
        if input_ref in obj_ids
    ]
    if input_ids:
        cfg_inputs = load_header_cfg_id(cpp_class, "cfgIdInputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(input_ids), cfg_inputs),
                input_ids,
            )
        )

    output_ref = resolve_reference(config.get("output"))
    output_id = obj_ids.get(output_ref, 0) if output_ref else 0
    if output_id:
        cfg_output = load_header_cfg_id(cpp_class, "cfgIdOutput")
        items.append(
            (cfg_id(3, prog_cls, 0, False, 1, cfg_output), [output_id])
        )
