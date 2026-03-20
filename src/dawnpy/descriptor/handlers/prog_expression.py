"""Handler for ``expression`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    iobind_field,
)
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "expression"
cpp_class: str = "CProgExpression"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``expression``."""
    return [
        iobind_field(cpp_class),
        ConfigField(
            name="op",
            cpp_helper=f"{cpp_class}::cfgIdOp",
            value_type="uint32_list",
        ),
    ]


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``expression``-specific config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)

    config = obj.config if isinstance(obj.config, dict) else {}
    op = config.get("op", [])
    if op:
        cfg_o = header_cfg_id(cpp_class, "cfgIdOp")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, 2, cfg_o),
                [int(op[0]), int(op[1])],
            )
        )
