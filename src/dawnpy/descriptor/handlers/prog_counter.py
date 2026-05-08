"""Handler for ``counter`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    iobind_field,
)
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "counter"
cpp_class: str = "CProgCounter"


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``counter``."""
    return [
        iobind_field(cpp_class),
        ConfigField(
            name="params",
            cpp_helper=f"{cpp_class}::cfgIdParams",
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
    """Append ``counter``-specific config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)

    config = obj.config if isinstance(obj.config, dict) else {}
    params = config.get("params", [])
    if params:
        words = [int(param) for param in params]
        while len(words) < 4:
            words.append(0)
        cfg_p = header_cfg_id(cpp_class, "cfgIdParams")
        items.append((cfg_id(3, prog_cls, 0, False, 4, cfg_p), words[:4]))
