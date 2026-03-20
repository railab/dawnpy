"""Handler for ``statsrms`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers._prog_common import (
    append_standard_iobind,
    iobind_field,
)

yaml_type: str = "statsrms"
cpp_class: str = "CProgStatsRms"


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``statsrms``."""
    return [iobind_field(cpp_class)]


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:
    """Append ``statsrms`` config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)
