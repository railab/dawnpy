"""Handler for ``vecsplit`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "vecsplit"
cpp_class: str = "CProgVecSplit"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``vecsplit``."""
    return [
        ConfigField(
            name="source",
            cpp_helper=f"{cpp_class}::cfgIdSource",
            value_type="id_single",
        ),
        ConfigField(
            name="outputs",
            cpp_helper=f"{cpp_class}::cfgIdOutputs",
            value_type="id_list",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return output-side targets whose shape is owned by ``vecsplit``."""
    return set(resolve_references(obj.config.get("outputs", [])))


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate ``vecsplit`` source/output dtype constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    source_ref = resolve_reference(config.get("source"))
    output_refs = resolve_references(config.get("outputs", []))
    errors: list[str] = []

    source = io_map.get(source_ref) if source_ref else None
    for output_ref in output_refs:
        io = io_map.get(output_ref)
        if io is None or source is None:
            continue
        if io.dtype != source.dtype:
            errors.append(
                f"Program {obj.obj_id} invalid: vecsplit output "
                f"'{output_ref}' dtype '{io.dtype}' does not match source "
                f"'{source_ref}' dtype '{source.dtype}'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``vecsplit``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    source_ref = resolve_reference(config.get("source"))
    source_id = obj_ids.get(source_ref, 0) if source_ref else 0
    if source_id:
        cfg_source = load_header_cfg_id(cpp_class, "cfgIdSource")
        items.append(
            (cfg_id(3, prog_cls, 0, False, 1, cfg_source), [source_id])
        )

    output_ids = [
        obj_ids[output_ref]
        for output_ref in resolve_references(config.get("outputs", []))
        if output_ref in obj_ids
    ]
    if output_ids:
        cfg_outputs = load_header_cfg_id(cpp_class, "cfgIdOutputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(output_ids), cfg_outputs),
                output_ids,
            )
        )
