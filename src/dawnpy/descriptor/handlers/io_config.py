# tools/dawnpy/src/dawnpy/descriptor/handlers/io_config.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``config`` IO type.

Config IO stores a target object ID plus the target object's cfg-id.
The target object's own ConfigField schema defines that cfg-id; this
handler only resolves the reference and emits the generic CIOConfig
wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click

from dawnpy.descriptor.config_access import config_field_is_rw
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import (
    _IOSerializeContext,
    resolve_dtype,
)
from dawnpy.descriptor.encoding.words import cfg_id
from dawnpy.headerdefs.bundle import header_cfg_id

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import IoObject, ProgramObject
    from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext


yaml_type: str = "config"
cpp_class: str = "CIOConfig"
no_fields: bool = False
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``config``."""
    return [
        ConfigField(
            name="objid_ref",
            cpp_helper="CIOConfig::cfgIdCfg",
            value_type="config_ref",
        ),
        ConfigField(
            name="objcfg_ref", cpp_helper="", value_type="config_ref_field"
        ),
        ConfigField(
            name="objid_ref_alloc",
            cpp_helper="CIOConfig::cfgIdAlloc",
            value_type="config_alloc",
        ),
    ]


def _ref_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id", ""))
    return str(value or "")


def _value_dim(value: Any) -> int:
    return len(value) if isinstance(value, list) else 1


def _cpp_helper_call(
    field: ConfigField, ref_obj: Any, value: Any, rw: bool = False
) -> str | None:
    if not field.cpp_helper:
        return None
    params = []
    for i, param_name in enumerate(field.params):
        if param_name == "dtype_param":
            params.append(str(ref_obj.initval_param))
        elif param_name == "rw":
            params.append("true" if rw else "false")
        elif param_name == "dim":
            params.append(str(_value_dim(value)))
        elif i < len(field.default_params):
            default_val = field.default_params[i]
            params.append(
                "true"
                if default_val is True
                else "false" if default_val is False else str(default_val)
            )
    return f"{field.cpp_helper}({', '.join(params)}),"


def _choose_config_field(
    fields: list[ConfigField], config: dict[str, Any], objcfg_ref: str
) -> ConfigField | None:
    if objcfg_ref:
        return next((f for f in fields if f.name == objcfg_ref), None)

    configured = [
        f for f in fields if f.name in config and f.cpp_helper and not f.nested
    ]
    if len(configured) == 1:
        return configured[0]
    return None


def _header_owner(cpp_helper: str) -> str:
    return cpp_helper.rsplit("::", 1)[0]


def _header_helper(cpp_helper: str) -> str:
    return cpp_helper.rsplit("::", 1)[1]


def _binary_cfg_id(
    ctx: _IOSerializeContext,
    field: ConfigField,
    ref_value: dict[str, Any],
) -> int:
    ref_type = str(ref_value.get("type", ""))
    ref_cls = ctx.io_cls_map.get(ref_type)
    if ref_cls is None:
        raise click.ClickException(
            f"Unknown IO class '{ref_type}' for config reference"
        )

    ref_dtype = resolve_dtype(
        ctx.decoder, str(ref_value.get("dtype", "uint32")), "config reference"
    )
    ref_config = ref_value.get("config", {})
    if not isinstance(ref_config, dict):
        ref_config = {}
    value = ref_config.get(field.name)
    size = 1
    ref_id = _ref_id(ref_value)
    rw = config_field_is_rw(ctx.config_rw_grants, ref_id, field.name)
    for param_name in field.params:
        if param_name == "dim":
            size = _value_dim(value)
        elif param_name == "rw":
            rw = config_field_is_rw(ctx.config_rw_grants, ref_id, field.name)

    return cfg_id(
        1,
        int(ref_cls),
        ref_dtype,
        rw,
        size,
        header_cfg_id(
            _header_owner(field.cpp_helper), _header_helper(field.cpp_helper)
        ),
    )


def encode_binary(ctx: _IOSerializeContext) -> None:
    """Emit cfg-id pointer + ref-value cfg items."""
    ref_value = ctx.config.get("objid_ref", "")
    ref_id = _ref_id(ref_value)
    ref_objid = ctx.obj_ids.get(ref_id)
    if ref_objid is None:
        return  # pragma: no cover

    ref_cfgid = 0
    if isinstance(ref_value, dict):
        from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY

        ref_config = ref_value.get("config", {})
        if not isinstance(ref_config, dict):
            ref_config = {}
        ref_type = str(ref_value.get("type", ""))
        handler = IO_HANDLER_REGISTRY.get(ref_type)
        fields = handler.config_fields() if handler is not None else []
        field = _choose_config_field(
            fields, ref_config, str(ctx.config.get("objcfg_ref", ""))
        )
        if field is not None and field.cpp_helper:
            ref_cfgid = _binary_cfg_id(ctx, field, ref_value)

    if ref_cfgid == 0:
        return  # pragma: no cover

    ref_cfg_dtype = resolve_dtype(
        ctx.decoder, "uint32", "config reference cfgid"
    )
    ctx.items.append(
        (
            cfg_id(
                1,
                ctx.io_cls,
                int(ref_cfg_dtype),
                False,
                1,
                header_cfg_id(cpp_class, "cfgIdAlloc"),
            ),
            [ref_cfgid],
        )
    )
    ctx.items.append(
        (
            cfg_id(
                1,
                ctx.io_cls,
                ctx.dtype,
                # This is ConfigIO's own pointer to the target object. It is
                # descriptor plumbing, not the target field access grant.
                False,
                1,
                header_cfg_id(cpp_class, "cfgIdCfg"),
            ),
            [ref_objid],
        )
    )


def _program_objcfg_line(  # pragma: no cover
    ref_obj: ProgramObject,
    objcfg_ref: str,
    gctx: IoGeneratorContext,
) -> str | None:
    """Emit cfgIdXxx for a program's referenced config field."""
    from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY

    handler = PROG_HANDLER_REGISTRY.get(ref_obj.prog_type)
    if handler is None:
        return None
    rw = config_field_is_rw(gctx.config_rw_grants, ref_obj.obj_id, objcfg_ref)
    return handler.config_reference_cpp_line(
        ref_obj, objcfg_ref, gctx.config_loader, rw
    )


def _io_objcfg_line(
    ref_obj: IoObject,
    objcfg_ref: str,
    gctx: IoGeneratorContext,
) -> str | None:
    ref_config = ref_obj.config
    field_defs = gctx.config_loader.get_io_config_fields(ref_obj.io_type)
    field = _choose_config_field(field_defs, ref_config, objcfg_ref)
    if field is None:
        return None
    rw = config_field_is_rw(gctx.config_rw_grants, ref_obj.obj_id, field.name)
    return _cpp_helper_call(field, ref_obj, ref_config.get(field.name), rw)


def _system_objcfg_line(  # pragma: no cover
    ref_obj: Any,
    objcfg_ref: str,
    gctx: IoGeneratorContext,
) -> str | None:
    """Emit cfgIdXxx for a SYSTEM object's referenced config field.

    Lets a ``config`` IO target a system manager (e.g. the GNSS manager's
    ``enabled`` switch) so its config item can be driven over LwM2M, mirroring
    the IO/program reference paths.
    """
    from dawnpy.descriptor.definitions.registry import SYSTEM_TYPES

    info = SYSTEM_TYPES.get(ref_obj.system_type)
    if info is None:
        return None
    field = _choose_config_field(
        list(info.config_fields), ref_obj.config, objcfg_ref
    )
    if field is None:
        return None
    rw = config_field_is_rw(gctx.config_rw_grants, ref_obj.obj_id, field.name)
    return _cpp_helper_call(field, ref_obj, ref_obj.config.get(field.name), rw)


def generate_cpp(  # noqa: C901  # pragma: no cover
    macro_name: str, obj: IoObject, gctx: IoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a ``config`` IO object."""
    lines: list[str] = []
    fmt = gctx.format_helper
    config = obj.config
    ref_id = _ref_id(config.get("objid_ref", ""))
    objcfg_ref = str(config.get("objcfg_ref", ""))
    ref_obj = gctx.objects.get(ref_id)

    if not ref_id or not ref_obj:  # pragma: no cover
        fmt.append_line(lines, 1, f"{macro_name}, 0,")
        return lines

    # Duck-type the referenced object; importing IoObject/ProgramObject
    # at top-level would cycle through dawnpy.descriptor.definitions.registry.
    from dawnpy.descriptor.definitions.objects import IoObject as _IoObject
    from dawnpy.descriptor.definitions.objects import (
        ProgramObject as _ProgramObject,
    )
    from dawnpy.descriptor.definitions.objects import (
        SystemObject as _SystemObject,
    )

    cfg_id_line: str | None = None
    if isinstance(ref_obj, _IoObject):
        cfg_id_line = _io_objcfg_line(ref_obj, objcfg_ref, gctx)
    elif isinstance(ref_obj, _ProgramObject):
        if objcfg_ref:
            cfg_id_line = _program_objcfg_line(ref_obj, objcfg_ref, gctx)
    elif isinstance(ref_obj, _SystemObject):
        if objcfg_ref:
            cfg_id_line = _system_objcfg_line(ref_obj, objcfg_ref, gctx)

    if cfg_id_line is None:
        fmt.append_line(lines, 1, f"{macro_name}, 0,")
        return lines

    # Limits live in the CIOCommon block; the config IO uses them to
    # validate setData payloads. Count and emit them here so the
    # special-cased generate_cpp stays consistent with the binary path.
    from dawnpy.descriptor.generation.io_codegen import (
        _LIMIT_HELPERS,
        _limits_item_count,
    )

    limits_cfg = config.get("limits")
    limits_count = _limits_item_count(limits_cfg) if limits_cfg else 0

    rw_str = "false"
    extra_count = 0
    extra_lines: list[str] = []

    field_name = config.get("field")
    cfg_offset = config.get("offset")
    cfg_size_val = config.get("size")

    # Ask the referenced program's handler to resolve field -> offset/size
    if isinstance(field_name, str) and isinstance(ref_obj, _ProgramObject):
        from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY

        prog_handler = PROG_HANDLER_REGISTRY.get(ref_obj.prog_type)
        if prog_handler is not None and hasattr(
            prog_handler, "resolve_config_subfield"
        ):
            resolved = prog_handler.resolve_config_subfield(
                objcfg_ref, field_name
            )
            if resolved is not None:
                cfg_offset, cfg_size_val = resolved[0], resolved[1]

    if cfg_offset is not None:
        extra_count += 1
        fmt.append_line(extra_lines, 2, "CIOConfig::cfgIdOffset(),")
        fmt.append_line(extra_lines, 3, f"{int(cfg_offset)},")
    if cfg_size_val is not None:
        extra_count += 1
        fmt.append_line(extra_lines, 2, "CIOConfig::cfgIdSize(),")
        fmt.append_line(extra_lines, 3, f"{int(cfg_size_val)},")

    fmt.append_line(
        lines, 1, f"{macro_name}, {2 + limits_count + extra_count},"
    )
    if limits_count > 0 and isinstance(limits_cfg, dict):
        for key, helper in _LIMIT_HELPERS:
            if key not in limits_cfg:
                continue
            entry = limits_cfg[key]
            size = len(entry) if isinstance(entry, list) else 1
            fmt.append_line(lines, 2, f"{helper}({obj.dtype_cpp}, {size}),")
            values = entry if isinstance(entry, list) else [entry]
            for value in values:
                fmt.append_line(
                    lines, 3, f"{_limit_cpp_literal(value, obj.dtype)},"
                )
    fmt.append_line(lines, 2, "CIOConfig::cfgIdCfg(),")
    fmt.append_line(lines, 3, cfg_id_line)
    fmt.append_line(
        lines, 2, f"CIOConfig::cfgIdAlloc({obj.dtype_cpp}, {rw_str}, 1),"
    )
    fmt.append_line(lines, 3, f"{ref_id.upper()},")
    lines.extend(extra_lines)
    return lines


def _limit_cpp_literal(value: object, obj_dtype: str) -> str:
    """Render a YAML limit value as a C++ uint32 literal."""
    assert isinstance(
        value, (int, float)
    ), f"limit value must be numeric, got {type(value).__name__}"
    if obj_dtype == "float":
        from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

        return DescriptorFormatHelper().format_float_as_hex(float(value))
    if obj_dtype in ("int8", "int16", "int32"):
        v = int(value)
        if v < 0:
            return f"(uint32_t){v}"
        return str(v)
    return str(int(value))
