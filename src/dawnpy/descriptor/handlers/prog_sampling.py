"""Handler for ``sampling`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    append_uint32_config,
    iobind_field,
    uint32_field,
)

yaml_type: str = "sampling"
cpp_class: str = "CProgSampling"


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``sampling``."""
    return [
        iobind_field(cpp_class),
        uint32_field(cpp_class, "interval", "cfgIdIOInterval"),
    ]


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:
    """Append ``sampling`` config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)
    append_uint32_config(
        items,
        obj,
        prog_cls,
        cpp_class,
        [("interval", "cfgIdIOInterval", True)],
    )
