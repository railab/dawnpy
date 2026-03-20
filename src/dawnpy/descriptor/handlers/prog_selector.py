"""Handler for ``selector`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)
from dawnpy.headerdefs import load_header_cfg_id

yaml_type: str = "selector"
cpp_class: str = "CProgSelector"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``selector``."""
    return [
        ConfigField(
            name="control",
            cpp_helper=f"{cpp_class}::cfgIdControl",
            value_type="id_single",
        ),
        ConfigField(
            name="data",
            cpp_helper=f"{cpp_class}::cfgIdData",
            value_type="id_list",
        ),
        ConfigField(
            name="target",
            cpp_helper=f"{cpp_class}::cfgIdTarget",
            value_type="id_single",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the selector target whose shape is owned by the program."""
    target = obj.config.get("target")
    if isinstance(target, list) and target:
        target_ref = resolve_reference(target[0])
    else:
        target_ref = resolve_reference(target)
    return {target_ref} if target_ref else set()


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``selector``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    ctrl = config.get("control", [])
    if isinstance(ctrl, list) and ctrl:
        ctrl_ref = resolve_reference(ctrl[0])
    elif isinstance(ctrl, str):
        ctrl_ref = resolve_reference(ctrl)
    else:
        ctrl_ref = None
    if ctrl_ref:
        ctrl_id = obj_ids.get(ctrl_ref, 0)
        if ctrl_id:
            cfg_ctrl = load_header_cfg_id(cpp_class, "cfgIdControl")
            items.append(
                (cfg_id(3, prog_cls, 0, False, 1, cfg_ctrl), [ctrl_id])
            )

    data = config.get("data", [])
    data_refs = resolve_references(data)
    data_ids = [
        obj_ids[data_ref] for data_ref in data_refs if data_ref in obj_ids
    ]
    if data_ids:
        cfg_data = load_header_cfg_id(cpp_class, "cfgIdData")
        items.append(
            (cfg_id(3, prog_cls, 0, False, len(data_ids), cfg_data), data_ids)
        )

    target = config.get("target", [])
    if isinstance(target, list) and target:
        tgt_ref = resolve_reference(target[0])
    elif isinstance(target, str):
        tgt_ref = resolve_reference(target)
    else:
        tgt_ref = None
    if tgt_ref:
        tgt_id = obj_ids.get(tgt_ref, 0)
        if tgt_id:
            cfg_tgt = load_header_cfg_id(cpp_class, "cfgIdTarget")
            items.append((cfg_id(3, prog_cls, 0, False, 1, cfg_tgt), [tgt_id]))
