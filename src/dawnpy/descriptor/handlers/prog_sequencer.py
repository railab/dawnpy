# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_sequencer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``sequencer`` PROG type.

Owns the cpp_class binding, the user-facing YAML config schema, and the
binary serializer block (target list, state pairs, and start_index
scalar).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import resolve_references
from dawnpy.headerdefs import load_header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder


yaml_type: str = "sequencer"
cpp_class: str = "CProgSequencer"

# Per-type scalar config slots.  Field name -> (cfg_item_id, rw flag).
_SCALAR_FIELDS: dict[str, tuple[int, bool]] = {
    "start_index": (3, True),
}

_STATE_FIELD_ALIASES: dict[str, str] = {
    "value_off": "value_0",
    "dwell_off": "dwell_0",
    "dwell_us_off": "dwell_0",
    "value_on": "value_1",
    "dwell_on": "dwell_1",
    "dwell_us_on": "dwell_1",
}


def resolve_config_subfield(
    objcfg_ref: str, field: str
) -> tuple[int, int] | None:  # pragma: no cover
    """Return the ``(offset, size)`` tuple for a sequencer config sub-field.

    Called by ConfigIO during code generation to translate a symbolic
    field name into descriptor-level offset+size when ``field:`` is
    used in YAML instead of explicit ``offset``/``size``.
    """
    if objcfg_ref != "states":
        return None

    name = _STATE_FIELD_ALIASES.get(field, field)

    for prefix, is_value in (
        ("value_", True),
        ("dwell_", False),
        ("dwell_us_", False),
    ):
        if name.startswith(prefix):
            try:
                idx = int(name[len(prefix) :])
            except ValueError:
                continue
            if idx < 0:
                return None
            return (2 * idx, 1) if is_value else (2 * idx + 1, 1)

    return None


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``sequencer``."""
    return [
        ConfigField(
            name="targets",
            cpp_helper="CProgSequencer::cfgIdTargets",
            value_type="id_list",
        ),
        ConfigField(
            name="states",
            cpp_helper="CProgSequencer::cfgIdStates",
            value_type="sequencer_states",
        ),
        ConfigField(
            name="start_index",
            cpp_helper="CProgSequencer::cfgIdStartIndex",
            value_type="uint32",
        ),
    ]


def output_shape_owned_virt_targets(obj: ProgramObject) -> set[str]:
    """Return all configured sequencer output-side targets."""
    return set(resolve_references(obj.config.get("targets", [])))


def config_reference_cpp_line(
    obj: ProgramObject, field_name: str, config_loader: object
) -> str | None:
    """Return cfgId line for ConfigIO references to sequencer fields."""
    del config_loader
    if field_name == "start_index":
        return "CProgSequencer::cfgIdStartIndex(),"
    if field_name == "states":
        states = obj.config.get("states", [])
        if not isinstance(states, list):
            return None
        words = len(states) * 2
        if words <= 0:
            return None
        return f"CProgSequencer::cfgIdStates({words}),"
    return None


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: ProgramObject,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:  # pragma: no cover
    """Append the ``sequencer`` cfg blocks to ``items``."""
    del decoder
    config = obj.config if isinstance(obj.config, dict) else {}

    targets = config.get("targets", [])
    target_words = [obj_ids[target] for target in targets if target in obj_ids]
    if target_words:
        cfg_t = load_header_cfg_id(cpp_class, "cfgIdTargets")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(target_words), cfg_t),
                target_words,
            )
        )

    states = config.get("states", [])
    state_words: list[int] = []
    if isinstance(states, list):
        for state in states:
            if not isinstance(state, dict):
                continue
            state_words.append(int(state.get("value", 0)))
            state_words.append(int(state.get("dwell_us", 0)))
    if state_words:
        cfg_s = load_header_cfg_id(cpp_class, "cfgIdStates")
        items.append(
            (
                cfg_id(3, prog_cls, 0, True, len(state_words), cfg_s),
                state_words,
            )
        )

    for name, (cfgid_item, rw) in _SCALAR_FIELDS.items():
        if name in config:
            items.append(
                (
                    cfg_id(3, prog_cls, 0, rw, 1, cfgid_item),
                    [int(config[name])],
                )
            )
