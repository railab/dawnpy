# tools/dawnpy/src/dawnpy/descriptor/handlers/prog_bitmerge.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for ``bitmerge`` PROG type."""

from typing import Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.descriptor.handlers._prog_config_cpp import ProgFieldCppCtx
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs.bundle import header_cfg_id

yaml_type: str = "bitmerge"
cpp_class: str = "CProgBitMerge"

_MERGE_IO_DTYPES: set[str] = {
    "bool",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
}

_FIELD_BITS = 32

#: Output element width per dtype; a field must fit the real output word.
_DTYPE_BITS: dict[str, int] = {
    "bool": 8,
    "int8": 8,
    "uint8": 8,
    "int16": 16,
    "uint16": 16,
    "int32": 32,
    "uint32": 32,
}


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``bitmerge``."""
    return [
        ConfigField(
            name="inputs",
            cpp_helper=f"{cpp_class}::cfgIdInputs",
            value_type="bitmerge_inputs",
        ),
        ConfigField(
            name="output",
            cpp_helper=f"{cpp_class}::cfgIdOutput",
            value_type="id_single",
        ),
    ]


def _input_words(entries: Any, resolve: Any) -> list[Any]:
    """Flatten input entries into (io, shift, mask) word triples."""
    words: list[Any] = []
    if not isinstance(entries, list):
        return words

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        words.append(resolve(entry.get("io", "")))
        words.append(int(entry.get("shift", 0)))
        words.append(int(entry.get("mask", 0)))

    return words


def emit_config_field_cpp(
    lines: list[str],
    field_def: ConfigField,
    obj: Any,
    config: dict[str, Any],
    ctx: ProgFieldCppCtx,
) -> bool:
    """Emit the ``bitmerge`` inputs block; return whether handled."""
    if field_def.value_type != "bitmerge_inputs":
        return False

    def _ref(value: Any) -> str:
        io = resolve_reference(value)
        return io.upper() if io else "0"

    words = _input_words(config.get(field_def.name, []), _ref)
    ctx.format_helper.append_line(
        lines, 2, f"{field_def.cpp_helper}({len(words)}),"
    )
    for word in words:
        ctx.format_helper.append_line(lines, 3, f"{word},")
    return True


def output_shape_owned_virt_targets(obj: Any) -> set[str]:
    """Return the output whose shape is owned by ``bitmerge``."""
    output_ref = resolve_reference(obj.config.get("output"))
    return {output_ref} if output_ref else set()


def _output_width(config: dict[str, Any], io_map: dict[str, Any]) -> int:
    """Return the output element width in bits (32 when unresolved)."""
    out_ref = resolve_reference(config.get("output"))
    out = io_map.get(out_ref) if out_ref else None
    if out is None:
        return _FIELD_BITS
    return _DTYPE_BITS.get(out.dtype, _FIELD_BITS)


def _validate_field(
    obj: Any,
    io_ref: str | None,
    entry: dict[str, Any],
    used: int,
    width: int = _FIELD_BITS,
) -> tuple[list[str], int]:
    """Check one input's field against the output word and earlier fields."""
    shift = int(entry.get("shift", 0))
    mask = int(entry.get("mask", 0))

    if mask == 0:
        return (
            [
                f"Program {obj.obj_id} invalid: bitmerge input "
                f"'{io_ref}' has an empty mask"
            ],
            used,
        )

    if shift >= width or (mask << shift) >> width:
        return (
            [
                f"Program {obj.obj_id} invalid: bitmerge input "
                f"'{io_ref}' field does not fit the {width}-bit output word"
            ],
            used,
        )

    field = mask << shift
    errors = []
    if used & field:
        errors.append(
            f"Program {obj.obj_id} invalid: bitmerge input "
            f"'{io_ref}' field overlaps an earlier one"
        )

    return errors, used | field


def validate_object_refs(obj: Any, io_map: dict[str, Any]) -> list[str]:
    """Validate ``bitmerge`` dtype and field-layout constraints."""
    config = obj.config if isinstance(obj.config, dict) else {}
    input_entries = config.get("inputs", [])
    errors: list[str] = []
    used = 0
    width = _output_width(config, io_map)
    batched: list[str] = []

    if isinstance(input_entries, list):
        for entry in input_entries:
            if not isinstance(entry, dict):
                continue

            io_ref = resolve_reference(entry.get("io"))
            field_errors, used = _validate_field(
                obj, io_ref, entry, used, width
            )
            errors.extend(field_errors)

            if not io_ref:
                continue

            io = io_map.get(io_ref)
            if io is None:
                continue

            if io.dtype not in _MERGE_IO_DTYPES:
                errors.append(
                    f"Program {obj.obj_id} invalid: bitmerge input "
                    f"'{io_ref}' uses unsupported dtype '{io.dtype}'"
                )

            if _is_batched(io):
                batched.append(io_ref)

    if len(batched) > 1:
        errors.append(
            f"Program {obj.obj_id} invalid: bitmerge supports at most one "
            f"batched input, got {sorted(batched)}"
        )

    errors.extend(_validate_output(obj, io_map, batched))
    return errors


def _is_batched(io: Any) -> bool:
    """Return whether an IO declares a notify batch greater than one.

    Only the IO's own ``notify.batch`` is visible here; a virt batched by
    its producer program is not recognized and is checked by ``init()``.
    """
    config = getattr(io, "config", None)
    if not isinstance(config, dict):
        return False

    notify = config.get("notify")
    if not isinstance(notify, dict):
        return False

    return int(notify.get("batch", 1)) > 1


def _validate_output(
    obj: Any, io_map: dict[str, Any], batched: list[str]
) -> list[str]:
    """Check the output dtype and its element size against a batched input."""
    config = obj.config if isinstance(obj.config, dict) else {}
    out_ref = resolve_reference(config.get("output"))
    errors: list[str] = []

    if not out_ref:
        return errors

    out = io_map.get(out_ref)
    if out is None:
        return errors

    if out.dtype not in _MERGE_IO_DTYPES:
        errors.append(
            f"Program {obj.obj_id} invalid: bitmerge output "
            f"'{out_ref}' uses unsupported dtype '{out.dtype}'"
        )
        return errors

    # The runtime only requires equal element size (int16 -> uint16 is fine).
    if len(batched) == 1:
        src = io_map.get(batched[0])
        if (
            src is not None
            and _DTYPE_BITS.get(src.dtype) != _DTYPE_BITS[out.dtype]
        ):
            errors.append(
                f"Program {obj.obj_id} invalid: bitmerge output "
                f"'{out_ref}' dtype '{out.dtype}' does not match batched "
                f"input '{batched[0]}' dtype '{src.dtype}' element size"
            )

    return errors


def encode_binary(
    items: list[tuple[int, list[int]]],
    obj: Any,
    prog_cls: int,
    obj_ids: dict[str, int],
    decoder: Any,
) -> None:  # pragma: no cover
    """Append ``bitmerge``-specific config items to ``items``."""
    del decoder

    config = obj.config if isinstance(obj.config, dict) else {}

    def _ref(value: Any) -> int:
        io_ref = resolve_reference(value)
        return obj_ids.get(io_ref, 0) if io_ref else 0

    input_words = _input_words(config.get("inputs", []), _ref)
    if input_words:
        cfg_inp = header_cfg_id(cpp_class, "cfgIdInputs")
        items.append(
            (
                cfg_id(3, prog_cls, 0, False, len(input_words), cfg_inp),
                input_words,
            )
        )

    out_id = _ref(config.get("output", ""))
    if out_id:
        cfg_out = header_cfg_id(cpp_class, "cfgIdOutput")
        items.append((cfg_id(3, prog_cls, 0, False, 1, cfg_out), [out_id]))
