# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_ahrs.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for the ``ahrs`` PROG type (AHRS sensor fusion)."""

from typing import Any

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.scalar import (
    encode_scalar_words,
    format_scalar_cpp,
)
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_config_cpp import ProgFieldCppCtx
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "ahrs"
cpp_class: str = "CProgAhrs"

#: Param encode order -- must match ``SProgAhrsParams`` in ahrs.hxx.
PARAM_ORDER: tuple[str, ...] = (
    "gain",
    "accel_rejection",
    "recovery_period",
    "rate",
)
PARAM_DEFAULTS: dict[str, float] = {
    "gain": 0.5,
    "accel_rejection": 10.0,
    "recovery_period": 5.0,
    "rate": 50.0,
}

_ID_FIELDS: tuple[tuple[str, str], ...] = (
    ("accel", "cfgIdAccel"),
    ("gyro", "cfgIdGyro"),
    ("output", "cfgIdOutput"),
)

#: Optional single-id fields (encoded only when present in the config).
_OPTIONAL_ID_FIELDS: tuple[tuple[str, str], ...] = (("mag", "cfgIdMag"),)


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``ahrs``."""
    return [
        ConfigField(
            name="accel",
            cpp_helper=f"{cpp_class}::cfgIdAccel",
            value_type="id_single",
        ),
        ConfigField(
            name="gyro",
            cpp_helper=f"{cpp_class}::cfgIdGyro",
            value_type="id_single",
        ),
        ConfigField(
            name="mag",
            cpp_helper=f"{cpp_class}::cfgIdMag",
            value_type="id_single",
        ),
        ConfigField(
            name="output",
            cpp_helper=f"{cpp_class}::cfgIdOutput",
            value_type="id_single",
        ),
        ConfigField(
            name="params",
            cpp_helper=f"{cpp_class}::cfgParams",
            value_type="ahrs_params",
            # cfgParams(bool rw): a writable config IO targeting these
            # params makes them runtime-writable
            # (CProgAhrs::onSetObjConfig).
            params=["rw"],
        ),
    ]


def params_words(config: dict[str, Any]) -> list[int]:
    """Encode the params dict as float words in ``PARAM_ORDER``."""
    params = config.get("params", {})
    if not isinstance(params, dict):
        params = {}
    words: list[int] = []
    for name in PARAM_ORDER:
        words += encode_scalar_words(
            params.get(name, PARAM_DEFAULTS[name]), "float"
        )
    return words


def emit_config_field_cpp(
    lines: list[str],
    field_def: ConfigField,
    obj: Any,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> bool:
    """Emit the ``ahrs`` params block; return whether handled."""
    if field_def.value_type != "ahrs_params":
        return False

    params = config.get(field_def.name, {})
    if not isinstance(params, dict):
        params = {}

    # rw is true only when a writable config IO targets these params; the
    # config IO's reference emits the same cfgParams(rw) so the runtime
    # cfg-id lookup matches.
    rw = config_field_is_rw(ctx.rw_grants, obj.obj_id, field_def.name)
    rw_arg = "true" if rw else ""
    ctx.format_helper.append_line(
        lines, 2, f"{field_def.cpp_helper}({rw_arg}),"
    )
    for name in PARAM_ORDER:
        raw = params.get(name, PARAM_DEFAULTS[name])
        for literal in format_scalar_cpp(raw, "float"):
            ctx.format_helper.append_line(lines, 3, f"{literal},")
    return True


def validate_object(obj: Any) -> list[str]:
    """Require the accel/gyro/output references."""
    config = obj.config if isinstance(obj.config, dict) else {}
    return [
        f"Program {obj.obj_id} invalid: ahrs requires '{name}'"
        for name, _ in _ID_FIELDS
        if not resolve_reference(config.get(name))
    ]


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """All bound IOs must be float."""
    config = obj.config if isinstance(obj.config, dict) else {}
    errors: list[str] = []
    for name, _ in _ID_FIELDS + _OPTIONAL_ID_FIELDS:
        ref = resolve_reference(config.get(name))
        io = io_map.get(ref) if ref else None
        if io is not None and io.dtype != "float":
            errors.append(
                f"Program {obj.obj_id} invalid: ahrs '{name}' IO "
                f"'{ref}' dtype '{io.dtype}' must be 'float'"
            )
    return errors


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the output virt whose shape is owned by the program."""
    output_ref = resolve_reference(obj.config.get("output"))
    return {output_ref} if output_ref else set()


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:
    """Append ``ahrs``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}
    for name, helper in _ID_FIELDS + _OPTIONAL_ID_FIELDS:
        ref = resolve_reference(config.get(name))
        obj_id = obj_ids.get(ref, 0) if ref else 0
        if obj_id:
            cfg = header_cfg_id(cpp_class, helper)
            items.append((cfg_id(3, prog_cls, 0, False, 1, cfg), [obj_id]))

    words = params_words(config)
    cfg_params = header_cfg_id(cpp_class, "cfgParams")
    items.append(
        (cfg_id(3, prog_cls, 0, False, len(words), cfg_params), words)
    )
