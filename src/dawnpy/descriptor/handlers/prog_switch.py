"""Handler for ``switch`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "switch"
cpp_class: str = "CProgSwitch"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``switch``."""
    return [
        ConfigField(
            name="inputs",
            cpp_helper=f"{cpp_class}::cfgIdInputs",
            value_type="switch_inputs",
        ),
        ConfigField(
            name="target",
            cpp_helper=f"{cpp_class}::cfgIdTarget",
            value_type="switch_target",
        ),
    ]


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the switch target whose shape is owned by the program."""
    target = obj.config.get("target", [])
    if not isinstance(target, list) or not target:
        return set()
    target_ref = resolve_reference(target[0])
    return {target_ref} if target_ref else set()


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``switch``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    input_entries = config.get("inputs", [])
    input_words: list[int] = []
    if isinstance(input_entries, list):
        for inp in input_entries:
            if isinstance(inp, dict):
                io_ref = resolve_reference(inp.get("io", ""))
                io_id = obj_ids.get(io_ref, 0) if io_ref else 0
                match_val = int(inp.get("match", 1))
                input_words.append(io_id)
                input_words.append(match_val)
    if input_words:
        cfg_inp = header_cfg_id(cpp_class, "cfgIdInputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(input_words), cfg_inp),
                input_words,
            )
        )

    target = config.get("target", [])
    if target:
        tgt_ref = resolve_reference(target[0]) if target else None
        tgt_id = obj_ids.get(tgt_ref, 0) if tgt_ref else 0
        on_cmd = int(target[1]) if len(target) > 1 else 1
        off_cmd = int(target[2]) if len(target) > 2 else 0
        cfg_tgt = header_cfg_id(cpp_class, "cfgIdTarget")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, 3, cfg_tgt),
                [tgt_id, on_cmd, off_cmd],
            )
        )
