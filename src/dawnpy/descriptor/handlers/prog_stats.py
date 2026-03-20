"""Handler for the ``stats`` PROG YAML token."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers._prog_common import append_standard_iobind

yaml_type: str = "stats"
cpp_class: str = "CProgStatsAvg"


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``stats``."""
    return []


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:
    """Append ``stats`` config items to ``items``."""
    del decoder
    append_standard_iobind(items, obj, prog_cls, obj_ids, cpp_class)
