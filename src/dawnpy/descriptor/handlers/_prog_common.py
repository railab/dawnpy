# tools/dawnpy/src/dawnpy/descriptor/handlers/_prog_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared helpers for simple PROG handlers."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.headerdefs import load_header_cfg_id


def iobind_field(cpp_class: str) -> ConfigField:
    """Return the standard program IO binding config field."""
    return ConfigField(
        name="iobind",
        cpp_helper=f"{cpp_class}::cfgIdIOBind",
        value_type="id_array_pairs",
    )


def uint32_field(cpp_class: str, name: str, helper: str) -> ConfigField:
    """Return a uint32 config field bound to ``cpp_class::helper``."""
    return ConfigField(
        name=name,
        cpp_helper=f"{cpp_class}::{helper}",
        value_type="uint32",
    )


def append_standard_iobind(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    cpp_class: str,
) -> None:
    """Append the common sources/outputs IO binding block."""
    config = obj.config if isinstance(obj.config, dict) else {}
    sources = config.get("sources", obj.inputs)
    outputs = config.get("outputs", obj.outputs)
    source_ids = [obj_ids[src] for src in sources if src in obj_ids]
    output_ids = [obj_ids[out] for out in outputs if out in obj_ids]
    if len(source_ids) != len(output_ids):
        raise ValueError(
            f"Program {obj.obj_id} has {len(source_ids)} sources and "
            f"{len(output_ids)} outputs"
        )
    words = [
        word
        for source_id, output_id in zip(source_ids, output_ids, strict=True)
        for word in (source_id, output_id)
    ]
    if not words:
        return

    cfg = load_header_cfg_id(cpp_class, "cfgIdIOBind")
    append_cfg_item(
        items,
        cfg_id(3, prog_cls, 0, False, len(words), cfg),
        words,
    )


def append_uint32_config(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    cpp_class: str,
    fields: list[tuple[str, str, bool]],
) -> None:
    """Append single-word uint32 config items from ``obj.config``."""
    config = obj.config if isinstance(obj.config, dict) else {}
    for name, helper, rw in fields:
        if name not in config:
            continue
        cfg = load_header_cfg_id(cpp_class, helper)
        items.append((cfg_id(3, prog_cls, 0, rw, 1, cfg), [int(config[name])]))
