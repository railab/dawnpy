# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_saturate.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for the ``saturate`` PROG type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject
    from dawnpy.objectid import ObjectIdDecoder

yaml_type: str = "saturate"
cpp_class: str = "CProgSaturate"

#: Value range per dtype in YAML units. Real bounds travel as one float
#: word, so double shares the float range; b16 is 16.16 fixed point.
_FLT_MAX = 3.4028234663852886e38
_DTYPE_RANGE: dict[str, tuple[float, float]] = {
    "bool": (0, 1),
    "uint8": (0, 0xFF),
    "int8": (-0x80, 0x7F),
    "uint16": (0, 0xFFFF),
    "int16": (-0x8000, 0x7FFF),
    "uint32": (0, 0xFFFFFFFF),
    "int32": (-0x80000000, 0x7FFFFFFF),
    "float": (-_FLT_MAX, _FLT_MAX),
    "double": (-_FLT_MAX, _FLT_MAX),
    "b16": (-0x8000, 0x7FFF + 0xFFFF / 0x10000),
}

_REAL_DTYPES: frozenset[str] = frozenset({"float", "double"})

_BOUNDS: tuple[tuple[str, str], ...] = (
    ("min", "cfgIdMin"),
    ("max", "cfgIdMax"),
)


def _bound_value(value: Any, dtype: str) -> float:
    """Return a YAML bound as a number in the units of ``dtype``."""
    if dtype in _REAL_DTYPES or dtype == "b16":
        return float(value)
    return int(value)


def _bound_words(value: Any, dtype: str) -> list[int]:
    """Encode a bound the way ``CProgSaturate::decodeBound`` reads it."""
    if dtype in _REAL_DTYPES:
        return encode_scalar_words(value, "float")
    if dtype == "b16":
        return [int(round(float(value) * 0x10000)) & 0xFFFFFFFF]
    return encode_scalar_words(value, dtype)


def _bound_cpp(value: Any, dtype: str) -> list[str]:
    """Format a bound as C++ word literals."""
    if dtype in _REAL_DTYPES:
        return format_scalar_cpp(value, "float")
    if dtype == "b16":
        return [f"{word:#010x}" for word in _bound_words(value, dtype)]
    return format_scalar_cpp(value, dtype)


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``saturate``."""
    fields = [
        ConfigField(
            name="input",
            cpp_helper=f"{cpp_class}::cfgIdInput",
            value_type="id_single",
        ),
        ConfigField(
            name="output",
            cpp_helper=f"{cpp_class}::cfgIdOutput",
            value_type="id_single",
        ),
    ]

    # cfgIdMin/cfgIdMax(bool rw): a writable config IO targeting a bound
    # makes it runtime-writable (CProgSaturate::onSetObjConfig).
    fields += [
        ConfigField(
            name=name,
            cpp_helper=f"{cpp_class}::{helper}",
            value_type="saturate_bound",
            params=["rw"],
        )
        for name, helper in _BOUNDS
    ]

    return fields


def emit_config_field_cpp(
    lines: list[str],
    field_def: ConfigField,
    obj: ProgramObject,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> bool:
    """Emit one optional bound; return whether handled."""
    if field_def.value_type != "saturate_bound":
        return False

    # An absent bound means "leave this side at the dtype limit", so it must
    # emit no item at all rather than a zero.
    if field_def.name not in config:
        return True

    rw = config_field_is_rw(ctx.rw_grants, obj.obj_id, field_def.name)
    rw_arg = "true" if rw else ""
    ctx.format_helper.append_line(
        lines, 2, f"{field_def.cpp_helper}({rw_arg}),"
    )
    for literal in _bound_cpp(config[field_def.name], obj.dtype):
        ctx.format_helper.append_line(lines, 3, f"{literal},")
    return True


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the output whose shape is owned by ``saturate``."""
    output_ref = resolve_reference(obj.config.get("output"))
    return {output_ref} if output_ref else set()


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate ``saturate`` dtype and bound constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    in_ref = resolve_reference(config.get("input"))
    out_ref = resolve_reference(config.get("output"))
    errors: list[str] = []

    src = io_map.get(in_ref) if in_ref else None
    out = io_map.get(out_ref) if out_ref else None

    for io, ref, role in ((src, in_ref, "input"), (out, out_ref, "output")):
        if io is not None and io.dtype not in _DTYPE_RANGE:
            errors.append(
                f"Program {obj.obj_id} invalid: saturate {role} '{ref}' "
                f"uses unsupported dtype '{io.dtype}'"
            )

    # Bounds are encoded in the program dtype, which the runtime decodes
    # as the input dtype, so the two must agree.
    if (
        src is not None
        and src.dtype in _DTYPE_RANGE
        and src.dtype != obj.dtype
    ):
        errors.append(
            f"Program {obj.obj_id} invalid: saturate dtype '{obj.dtype}' "
            f"must match input '{in_ref}' dtype '{src.dtype}'"
        )

    # b16 is clamped as raw fixed point and does not convert.
    if (
        src is not None
        and out is not None
        and (src.dtype == "b16") != (out.dtype == "b16")
    ):
        errors.append(
            f"Program {obj.obj_id} invalid: saturate cannot mix b16 with "
            f"'{src.dtype if out.dtype == 'b16' else out.dtype}'"
        )

    if not any(name in config for name, _helper in _BOUNDS):
        errors.append(
            f"Program {obj.obj_id} invalid: saturate needs at least one of "
            f"'min'/'max'"
        )

    errors.extend(_validate_bounds(obj, config, out, out_ref))
    return errors


def _validate_bounds_for(
    obj: Any, config: dict[str, Any], dtype: str, where: str
) -> list[str]:
    """Check the bounds fit a dtype range."""
    span = _DTYPE_RANGE[dtype]
    return [
        f"Program {obj.obj_id} invalid: saturate '{name}' {config[name]} "
        f"outside the range of {where} dtype '{dtype}'"
        for name, _helper in _BOUNDS
        if name in config
        and not span[0] <= _bound_value(config[name], dtype) <= span[1]
    ]


def _validate_bounds(
    obj: Any, config: dict[str, Any], out: Any, out_ref: str | None
) -> list[str]:
    """Check bounds against the program and output ranges and each other."""
    if obj.dtype not in _DTYPE_RANGE:
        return [
            f"Program {obj.obj_id} invalid: saturate dtype '{obj.dtype}' is "
            f"not supported"
        ]

    errors = _validate_bounds_for(obj, config, obj.dtype, "program")

    # Clamping into a range the output can hold is what makes a narrowing
    # store safe, so the bounds are checked against the output type too.
    if out is not None and out.dtype in _DTYPE_RANGE:
        errors.extend(
            _validate_bounds_for(obj, config, out.dtype, f"'{out_ref}'")
        )

    if "min" in config and "max" in config:
        if _bound_value(config["min"], obj.dtype) > _bound_value(
            config["max"], obj.dtype
        ):
            errors.append(
                f"Program {obj.obj_id} invalid: saturate 'min' above 'max'"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: ObjectIdDecoder,
) -> None:
    """Append ``saturate``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}

    for name, helper in (("input", "cfgIdInput"), ("output", "cfgIdOutput")):
        ref = resolve_reference(config.get(name))
        objid = obj_ids.get(ref, 0) if ref else 0
        if objid:
            cfg = header_cfg_id(cpp_class, helper)
            items.append((cfg_id(3, prog_cls, 0, False, 1, cfg), [objid]))

    for name, helper in _BOUNDS:
        if name not in config:
            continue
        words = _bound_words(config[name], obj.dtype)
        cfg = header_cfg_id(cpp_class, helper)
        items.append((cfg_id(3, prog_cls, 0, False, len(words), cfg), words))
