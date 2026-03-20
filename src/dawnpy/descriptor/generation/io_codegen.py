# tools/dawnpy/src/dawnpy/descriptor/io_generators.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""IO-specific descriptor generation helpers.

Per-IO-type bespoke C++ emitters live alongside their binary encoders
in ``dawnpy.descriptor.handlers.io_*``. This module owns the generic
schema-driven encoder loop (driven by each handler's ``config_fields()``
``value_type``) and dispatches to ``IO_HANDLER_REGISTRY[t].generate_cpp``
when the handler exposes one.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.config_access import (
    ConfigRwGrants,
    config_field_is_rw,
)
from dawnpy.descriptor.definitions.objects import DescriptorObject, IoObject
from dawnpy.descriptor.definitions.registry import DTYPE_MAP
from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext
from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

_NOTIFY_TYPE_MAP: dict[str, int] = {
    "poll": 0,
    "stream": 1,
}

_LIMIT_HELPERS: tuple[tuple[str, str], ...] = (
    ("min", "CIOCommon::cfgIdLimitMin"),
    ("max", "CIOCommon::cfgIdLimitMax"),
    ("step", "CIOCommon::cfgIdLimitStep"),
)


def _limits_item_count(value: Any) -> int:
    """Return cfg-item count emitted for a ``limits`` block."""
    if not isinstance(value, dict):
        return 0
    return sum(1 for key, _helper in _LIMIT_HELPERS if key in value)


class IoConfigGenerator:
    """Generate general IO configuration payloads."""

    def __init__(
        self,
        *,
        config_loader: ConfigLoader,
        format_helper: DescriptorFormatHelper,
        objects: Callable[[], dict[str, DescriptorObject]],
        config_rw_grants: Callable[[], ConfigRwGrants],
    ) -> None:
        """Initialize IO config builder with shared helpers."""
        self._config_loader = config_loader
        self._format_helper = format_helper
        self._objects = objects
        self._config_rw_grants = config_rw_grants

    def _value_dim(self, value: Any) -> int:
        """Return the number of scalar values encoded by a config item.

        Consumers (cfgIdInitval, cfgIdLimit*) take a value-count and let
        the C++ helper derive the underlying word count from the dtype
        enum, so callers must not pre-multiply for 64-bit types here.
        """
        if isinstance(value, list):
            return len(value)
        return 1

    def _format_scalar_value(
        self, value: Any, value_type: str, obj_dtype: str
    ) -> str:
        """Format one scalar config value as C++ source."""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if value_type == "int" or (
            value_type == "auto"
            and obj_dtype
            in ("int32", "int16", "int8", "uint32", "uint16", "uint8")
            and isinstance(value, int)
        ):
            if value < 0:
                return f"(uint32_t){value}"
            return f"{value}"
        if (
            value_type == "auto"
            and obj_dtype == "float"
            and isinstance(value, (int, float))
        ):
            return self._format_helper.format_float_as_hex(float(value))
        return f"{value}"

    def _format_scalar_words(
        self, value: Any, value_type: str, obj_dtype: str
    ) -> list[str]:
        """Format one scalar value as one or more uint32 words."""
        if value_type == "auto" and obj_dtype == "uint64":
            return [
                f"{word:#010x}"
                for word in self._format_helper.pack_words_le(
                    struct.pack("<Q", int(value))
                )
            ]

        if value_type == "auto" and obj_dtype == "int64":
            return [
                f"{word:#010x}"
                for word in self._format_helper.pack_words_le(
                    struct.pack("<q", int(value))
                )
            ]

        if value_type == "auto" and obj_dtype == "double":
            return [
                f"{word:#010x}"
                for word in self._format_helper.pack_words_le(
                    struct.pack("<d", float(value))
                )
            ]

        return [self._format_scalar_value(value, value_type, obj_dtype)]

    def _append_limits_lines(
        self, lines: list[str], value: Any, obj_dtype: str
    ) -> None:
        """Emit cfgIdLimit{Min,Max,Step} for a YAML ``limits`` block."""
        if not isinstance(value, dict):
            return

        for key, cpp_helper in _LIMIT_HELPERS:
            if key not in value:
                continue
            entry = value[key]
            size = self._value_dim(entry)
            dtype_cpp = DTYPE_MAP.get(obj_dtype, "SObjectId::DTYPE_UINT32")
            self._format_helper.append_line(
                lines, 2, f"{cpp_helper}({dtype_cpp}, {size}),"
            )
            self._append_config_value_lines(lines, entry, "auto", obj_dtype)

    def _append_config_value_lines(
        self, lines: list[str], value: Any, value_type: str, obj_dtype: str
    ) -> None:
        """Append one or more emitted config value lines."""
        if isinstance(value, list):
            for item in value:
                for formatted in self._format_scalar_words(
                    item, value_type, obj_dtype
                ):
                    self._format_helper.append_line(lines, 3, f"{formatted},")
            return

        for formatted in self._format_scalar_words(
            value, value_type, obj_dtype
        ):
            self._format_helper.append_line(lines, 3, f"{formatted},")

    def generate_io_config(  # noqa: C901
        self, macro_name: str, obj: IoObject
    ) -> list[str]:
        """Generate configuration for an IO object."""
        lines: list[str] = []
        config = obj.config
        io_type = obj.io_type

        # Per-type C++ emitter takes priority. Each complex IO handler
        # (config / control / trigger) owns its own generate_cpp() in
        # handlers/io_*.py - adding a new complex IO type means dropping
        # one new file and listing it in IO_HANDLER_REGISTRY.
        handler = IO_HANDLER_REGISTRY.get(io_type)
        if handler is not None and hasattr(handler, "generate_cpp"):
            # Config IO uses a custom emitter only when it references
            # another object; plain config fields use the generic loop.
            if (
                io_type == "config" and "objid_ref" not in config
            ):  # pragma: no cover
                pass  # fall through to generic field-driven loop
            else:
                gctx = IoGeneratorContext(
                    config_loader=self._config_loader,
                    format_helper=self._format_helper,
                    objects=self._objects(),
                    config_rw_grants=self._config_rw_grants(),
                )
                result = handler.generate_cpp(macro_name, obj, gctx)
                return list(result)

        # Get available config fields for this IO type
        field_defs = (
            self._config_loader.get_io_config_fields(io_type)
            if io_type
            else []
        )

        # Count how many config items are present. ``limits`` expands
        # into three cfg items (min/max/step), every other field is one.
        config_count = 0
        for field_def in field_defs:
            if field_def.name not in config:
                continue
            if field_def.value_type == "limits":
                config_count += _limits_item_count(config[field_def.name])
            else:
                config_count += 1

        self._format_helper.append_line(
            lines, 1, f"{macro_name}, {config_count},"
        )

        # Generate config for each field
        for field_def in field_defs:
            field_name = field_def.name
            if field_name in config:
                cpp_helper = field_def.cpp_helper
                value = config[field_name]
                value_type = field_def.value_type or "auto"

                # Handle notify type: dict with type + priority
                if value_type == "notify":
                    notify_cfg = value if isinstance(value, dict) else {}
                    notify_type = _NOTIFY_TYPE_MAP.get(
                        str(notify_cfg.get("type", "poll")), 0
                    )
                    notify_prio = int(notify_cfg.get("priority", 0))
                    notify_batch = int(notify_cfg.get("batch", 1))
                    self._format_helper.append_line(
                        lines, 2, f"{cpp_helper}(),"
                    )
                    self._format_helper.append_line(
                        lines, 3, f"{notify_type},"
                    )
                    self._format_helper.append_line(
                        lines, 3, f"{notify_prio},"
                    )
                    self._format_helper.append_line(
                        lines, 3, f"{notify_batch},"
                    )
                    continue

                # Handle limits type: dict with min/max/step (each scalar
                # or list of values, typed as the IO's dtype). Emits three
                # cfgIdLimit{Min,Max,Step} cfg items.
                if value_type == "limits":
                    self._append_limits_lines(lines, value, obj.dtype)
                    continue

                # Handle string type: pack chars into 32-bit words

                if value_type == "string":  # pragma: no cover
                    packed_words = self._format_helper.pack_string(str(value))
                    self._format_helper.append_line(
                        lines, 2, f"{cpp_helper}({len(packed_words)}),"
                    )
                    self._format_helper.append_words(
                        lines, packed_words, level=3
                    )
                    continue

                # Generate helper call with params
                params = field_def.params
                default_params = field_def.default_params

                if params:
                    # Compute actual parameters
                    actual_params = []
                    for i, param_name in enumerate(params):
                        if param_name == "dtype_param":
                            # Map object's dtype to cfgIdInitval parameter
                            actual_params.append(str(obj.initval_param))
                        elif param_name == "rw":
                            rw = config_field_is_rw(
                                self._config_rw_grants(),
                                obj.obj_id,
                                field_name,
                            )
                            actual_params.append("true" if rw else "false")
                        elif param_name == "dim":
                            actual_params.append(str(self._value_dim(value)))
                        elif i < len(default_params):
                            default_val = default_params[i]
                            if isinstance(
                                default_val, bool
                            ):  # pragma: no cover
                                actual_params.append(
                                    "true" if default_val else "false"
                                )
                            else:
                                actual_params.append(str(default_val))

                    param_str = ", ".join(actual_params)
                    self._format_helper.append_line(
                        lines, 2, f"{cpp_helper}({param_str}),"
                    )
                else:
                    self._format_helper.append_line(
                        lines, 2, f"{cpp_helper}(),"
                    )

                self._append_config_value_lines(
                    lines, value, value_type, obj.dtype
                )

        return lines
