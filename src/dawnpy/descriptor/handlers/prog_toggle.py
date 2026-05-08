"""Handler for ``toggle`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    iobind_field,
)
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "toggle"
cpp_class: str = "CProgToggle"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``toggle``."""
    return [
        iobind_field(cpp_class),
        ConfigField(
            name="values",
            cpp_helper=f"{cpp_class}::cfgIdValues",
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
    """Append ``toggle``-specific config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)

    config = obj.config if isinstance(obj.config, dict) else {}
    values = config.get("values", [])
    if values:
        cfg_v = header_cfg_id(cpp_class, "cfgIdValues")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, 2, cfg_v),
                [int(values[0]), int(values[1])],
            )
        )
