"""Handler for ``iodemux`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "iodemux"
cpp_class: str = "CProgIODemux"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``iodemux``."""
    return [
        ConfigField(
            name="control",
            cpp_helper=f"{cpp_class}::cfgIdControl",
            value_type="id_single",
        ),
        ConfigField(
            name="input",
            cpp_helper=f"{cpp_class}::cfgIdInput",
            value_type="id_single",
        ),
        ConfigField(
            name="outputs",
            cpp_helper=f"{cpp_class}::cfgIdOutputs",
            value_type="id_list",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return output-side targets whose shape is owned by the program."""
    return set(resolve_references(obj.config.get("outputs", [])))


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate input/output dtype constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    input_ref = resolve_reference(config.get("input"))
    output_refs = resolve_references(config.get("outputs", []))
    errors: list[str] = []

    input_io = io_map.get(input_ref) if input_ref else None
    for output_ref in output_refs:
        io = io_map.get(output_ref)
        if io is None or input_io is None:
            continue
        if io.dtype != input_io.dtype:
            errors.append(
                f"Program {obj.obj_id} invalid: iodemux output "
                f"'{output_ref}' dtype '{io.dtype}' does not match input "
                f"'{input_ref}' dtype '{input_io.dtype}'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``iodemux``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    control_ref = resolve_reference(config.get("control"))
    control_id = obj_ids.get(control_ref, 0) if control_ref else 0
    if control_id:
        cfg_control = header_cfg_id(cpp_class, "cfgIdControl")
        items.append(
            (cfg_id(3, prog_cls, 0, False, 1, cfg_control), [control_id])
        )

    input_ref = resolve_reference(config.get("input"))
    input_id = obj_ids.get(input_ref, 0) if input_ref else 0
    if input_id:
        cfg_input = header_cfg_id(cpp_class, "cfgIdInput")
        items.append((cfg_id(3, prog_cls, 0, False, 1, cfg_input), [input_id]))

    output_ids = [
        obj_ids[output_ref]
        for output_ref in resolve_references(config.get("outputs", []))
        if output_ref in obj_ids
    ]
    if output_ids:
        cfg_outputs = header_cfg_id(cpp_class, "cfgIdOutputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(output_ids), cfg_outputs),
                output_ids,
            )
        )
