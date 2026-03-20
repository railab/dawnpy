# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_gateway.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``gateway`` PROG type.

Owns the cpp_class binding, the user-facing YAML config schema, and the
binary serializer block (one cfg item built from the io1/io2/flags/dim
quadruples in ``config.iobind``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs import load_header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder


yaml_type: str = "gateway"
cpp_class: str = "CProgGateway"


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``gateway``."""
    return [
        ConfigField(
            name="iobind",
            cpp_helper="CProgGateway::cfgIdIOBind",
            value_type="gateway_iobind",
        ),
    ]


def output_shape_owned_virt_targets(obj: ProgramObject) -> set[str]:
    """Return gateway endpoints that may be shape-owned by the program."""
    refs: set[str] = set()
    binds = obj.config.get("iobind", [])
    if not isinstance(binds, list):
        return refs

    for entry in binds:
        if not isinstance(entry, dict):
            continue
        for key in ("io1", "io2"):
            ref = resolve_reference(entry.get(key))
            if ref:
                refs.add(ref)
    return refs


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: ProgramObject,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append the ``gateway`` cfg block to ``items``."""
    del decoder
    config = obj.config if isinstance(obj.config, dict) else {}
    raw_binds = config.get("iobind", [])
    if not isinstance(raw_binds, list):
        return  # pragma: no cover
    words: list[int] = []
    for entry in raw_binds:
        if not isinstance(entry, dict):
            continue
        io1 = entry.get("io1")
        io2 = entry.get("io2")
        if io1 not in obj_ids or io2 not in obj_ids:
            continue
        words.extend(
            [
                obj_ids[io1],
                obj_ids[io2],
                int(entry.get("flags", 0)),
                int(entry.get("dim", 1)),
            ]
        )
    if not words:
        return  # pragma: no cover
    cfg = load_header_cfg_id(cpp_class, "cfgIdIOBind")
    items.append((cfg_id(3, prog_cls, 0, False, len(words), cfg), words))
