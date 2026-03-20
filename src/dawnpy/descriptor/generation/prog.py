# tools/dawnpy/src/dawnpy/descriptor/prog_generators.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Program-specific descriptor generation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper
from dawnpy.descriptor.support.utils import resolve_reference

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProgramObject


def _resolve_id(ref: Any) -> str | None:  # pragma: no cover
    """Resolve a YAML anchor or string reference to an object ID."""
    if isinstance(ref, dict):
        return ref.get("id")  # pragma: no cover
    if ref is not None:
        return str(ref)  # pragma: no cover
    return None  # pragma: no cover


def _resolve_ids(refs: Any) -> list[str]:  # pragma: no cover
    """Resolve a list of YAML references to object ID strings."""
    if not isinstance(refs, list):
        return []  # pragma: no cover
    return [r for r in (_resolve_id(ref) for ref in refs) if r]


class ProgramConfigGenerator:
    """Generate program configuration payloads."""

    def __init__(
        self,
        *,
        config_loader: Any,
        prog_types: dict[str, Any],
        format_helper: DescriptorFormatHelper | None = None,
    ) -> None:
        """Initialize with shared config loader and program type map."""
        self._config_loader = config_loader
        self._prog_types = prog_types
        self._format_helper = format_helper or DescriptorFormatHelper()

    def _emit_id_array_pairs(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        obj: ProgramObject,
        config: dict[str, Any],
    ) -> None:
        sources = _resolve_ids(config.get("sources", obj.inputs))
        outputs = _resolve_ids(config.get("outputs", obj.outputs))
        n = len(sources) + len(outputs)
        if len(sources) != len(outputs):
            raise ValueError(
                f"Program {obj.obj_id} has {len(sources)} sources and "
                f"{len(outputs)} outputs"
            )
        self._format_helper.append_line(lines, 2, f"{cpp_helper}({n}),")
        for src_id, output_id in zip(sources, outputs, strict=True):
            self._format_helper.append_line(lines, 3, f"{src_id.upper()},")
            self._format_helper.append_line(lines, 3, f"{output_id.upper()},")

    def _emit_uint32(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
        default: str = "",
    ) -> None:
        value = config.get(field_name, default if default else 0)
        self._format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        self._format_helper.append_line(lines, 3, f"{value},")

    def _emit_uint32_list(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        values = config.get(field_name, [])
        n = len(values)
        self._format_helper.append_line(lines, 2, f"{cpp_helper}({n}),")
        for v in values:
            self._format_helper.append_line(lines, 3, f"{int(v)},")

    def _emit_id_array(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        obj: ProgramObject,
    ) -> None:
        self._format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        # For standard inputs/outputs, they are in obj.inputs/obj.outputs
        if field_name == "inputs":  # pragma: no cover
            ids = obj.inputs
        elif field_name == "outputs":  # pragma: no cover
            ids = obj.outputs
        else:  # pragma: no cover
            ids = obj.config.get(field_name, [])

        for obj_id in ids:
            self._format_helper.append_line(lines, 3, f"{obj_id.upper()},")

    def _emit_id_list(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        ids = _resolve_ids(config.get(field_name, []))
        self._format_helper.append_line(lines, 2, f"{cpp_helper}({len(ids)}),")
        for obj_id in ids:
            self._format_helper.append_line(lines, 3, f"{obj_id.upper()},")

    def _emit_id_single(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        obj: ProgramObject,
    ) -> None:
        if field_name == "reset":
            obj_id = obj.reset
        else:
            obj_id = obj.config.get(field_name)
            if isinstance(obj_id, list):
                obj_id = obj_id[0] if obj_id else None
        obj_id = resolve_reference(obj_id) if obj_id else None

        self._format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        if obj_id:
            self._format_helper.append_line(lines, 3, f"{obj_id.upper()},")
        else:
            self._format_helper.append_line(lines, 3, "0,")

    def _emit_gateway_iobind(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        entries = config.get(field_name, [])
        if not isinstance(entries, list):  # pragma: no cover
            entries = []

        resolved_gateway: list[tuple[str, str, int, int]] = []
        for entry in entries:
            if not isinstance(entry, dict):  # pragma: no cover
                continue
            io1 = _resolve_id(entry.get("io1"))
            io2 = _resolve_id(entry.get("io2"))
            if not io1 or not io2:  # pragma: no cover
                continue
            flags = int(entry.get("flags", 0))
            dim = int(entry.get("dim", 1))
            resolved_gateway.append((io1, io2, flags, dim))

        self._format_helper.append_line(
            lines, 2, f"{cpp_helper}({4 * len(resolved_gateway)}),"
        )
        for io1, io2, flags, dim in resolved_gateway:
            self._format_helper.append_line(lines, 3, f"{io1.upper()},")
            self._format_helper.append_line(lines, 3, f"{io2.upper()},")
            self._format_helper.append_line(lines, 3, f"{flags},")
            self._format_helper.append_line(lines, 3, f"{dim},")

    def _emit_id_array_quads(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        entries = config.get(field_name, [])
        if not isinstance(entries, list):  # pragma: no cover
            entries = []

        resolved_quads: list[tuple[str, str, str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):  # pragma: no cover
                continue
            src = _resolve_id(entry.get("src"))
            out = _resolve_id(entry.get("out"))
            sel = _resolve_id(entry.get("sel"))
            stat = _resolve_id(entry.get("stat"))
            if not src or not out or not sel or not stat:  # pragma: no cover
                continue
            resolved_quads.append((src, out, sel, stat))

        size = 4 * len(resolved_quads)
        self._format_helper.append_line(lines, 2, f"{cpp_helper}({size}),")
        for src, out, sel, stat in resolved_quads:
            self._format_helper.append_line(lines, 3, f"{src.upper()},")
            self._format_helper.append_line(lines, 3, f"{out.upper()},")
            self._format_helper.append_line(lines, 3, f"{sel.upper()},")
            self._format_helper.append_line(lines, 3, f"{stat.upper()},")

    def _emit_adjust_params(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        params = config.get(field_name, {})
        if not isinstance(params, dict):  # pragma: no cover
            params = {}

        offset = int(params.get("offset", 0))
        scale = int(params.get("scale", 1))
        self._format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        self._format_helper.append_line(lines, 3, f"{offset},")
        self._format_helper.append_line(lines, 3, f"{scale},")

    def _emit_adjust_iobind(  # pragma: no cover
        self,
        lines: list[str],
        obj: ProgramObject,
    ) -> None:
        """Compatibility wrapper for the adjust handler iobind emitter."""
        handler = PROG_HANDLER_REGISTRY["adjust"]
        handler.emit_iobind_cpp(
            lines,
            obj,
            len(obj.inputs) + len(obj.outputs),
            self._format_helper,
            "CProgAdjust",
        )

    def _emit_sequencer_states(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        entries = config.get(field_name, [])
        encoded: list[tuple[int, int]] = []
        entry: Any

        if not isinstance(entries, list):  # pragma: no cover
            entries = []

        for entry in entries:
            value_raw: Any
            dwell_raw: Any
            value: int
            dwell: int

            if not isinstance(entry, dict):  # pragma: no cover
                continue

            value_raw = entry.get("value", 0)
            dwell_raw = entry.get("dwell_us", 0)
            value = int(value_raw)
            dwell = int(dwell_raw)
            encoded.append((value, dwell))

        self._format_helper.append_line(
            lines, 2, f"{cpp_helper}({2 * len(encoded)}),"
        )
        for value, dwell in encoded:
            self._format_helper.append_line(lines, 3, f"{value},")
            self._format_helper.append_line(lines, 3, f"{dwell},")

    def _emit_switch_inputs(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        entries = config.get(field_name, [])
        words = []
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    io = resolve_reference(e.get("io", ""))
                    words.append(io.upper() if io else "0")
                    words.append(str(int(e.get("match", 1))))
        self._format_helper.append_line(
            lines, 2, f"{cpp_helper}({len(words)}),"
        )
        for w in words:
            self._format_helper.append_line(lines, 3, f"{w},")

    def _emit_switch_target(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        target = config.get(field_name, [])
        tgt_ref = resolve_reference(target[0]) if target else ""
        tgt_id = tgt_ref.upper() if tgt_ref else "0"
        on_cmd = str(int(target[1])) if len(target) > 1 else "1"
        off_cmd = str(int(target[2])) if len(target) > 2 else "0"
        self._format_helper.append_line(lines, 2, f"{cpp_helper}(),")
        self._format_helper.append_line(lines, 3, f"{tgt_id},")
        self._format_helper.append_line(lines, 3, f"{on_cmd},")
        self._format_helper.append_line(lines, 3, f"{off_cmd},")

    def _emit_bitpack_inputs(  # pragma: no cover
        self,
        lines: list[str],
        cpp_helper: str,
        field_name: str,
        config: dict[str, Any],
    ) -> None:
        entries = config.get(field_name, [])
        words = []
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    io = resolve_reference(e.get("io", ""))
                    words.append(io.upper() if io else "0")
                    words.append(str(int(e.get("bit", 0))))
        self._format_helper.append_line(
            lines, 2, f"{cpp_helper}({len(words)}),"
        )
        for w in words:
            self._format_helper.append_line(lines, 3, f"{w},")

    def _emit_type_field(  # noqa: C901  # pragma: no cover
        self,
        lines: list[str],
        field_def: ConfigField,
        obj: ProgramObject,
        config: dict[str, Any],
    ) -> None:
        """Emit descriptor lines for one type-specific config field."""
        field_name = field_def.name
        value_type = field_def.value_type
        cpp_helper = field_def.cpp_helper

        if value_type == "id_array_pairs":
            self._emit_id_array_pairs(lines, cpp_helper, obj, config)
        elif value_type == "uint32":
            self._emit_uint32(
                lines, cpp_helper, field_name, config, field_def.default
            )
        elif value_type == "uint32_list":
            self._emit_uint32_list(lines, cpp_helper, field_name, config)
        elif value_type == "id_array":
            self._emit_id_array(lines, cpp_helper, field_name, obj)
        elif value_type == "id_list":
            self._emit_id_list(lines, cpp_helper, field_name, config)
        elif value_type == "id_single":
            self._emit_id_single(lines, cpp_helper, field_name, obj)
        elif value_type == "gateway_iobind":
            self._emit_gateway_iobind(lines, cpp_helper, field_name, config)
        elif value_type == "id_array_quads":
            self._emit_id_array_quads(lines, cpp_helper, field_name, config)
        elif value_type == "adjust_params":
            self._emit_adjust_params(lines, cpp_helper, field_name, config)
        elif value_type == "sequencer_states":
            self._emit_sequencer_states(lines, cpp_helper, field_name, config)
        elif value_type == "switch_inputs":
            self._emit_switch_inputs(lines, cpp_helper, field_name, config)
        elif value_type == "switch_target":
            self._emit_switch_target(lines, cpp_helper, field_name, config)
        elif value_type == "bitpack_inputs":
            self._emit_bitpack_inputs(lines, cpp_helper, field_name, config)

    def generate_prog_config(  # pragma: no cover
        self, macro_name: str, obj: ProgramObject
    ) -> list[str]:
        """Generate configuration for a Program object."""
        lines: list[str] = []
        prog_type = obj.prog_type
        config = obj.config

        # Get program class info
        prog_info = self._prog_types[prog_type]
        cpp_class = prog_info.cpp_class

        # Get standard and type-specific field definitions
        type_fields = self._config_loader.get_prog_type_fields(prog_type)

        # Type-specific custom iobind field replaces the standard iobind item
        has_custom_iobind = any(
            f.value_type
            in {
                "id_array_pairs",
                "gateway_iobind",
                "id_array_quads",
                "id_list",
            }
            for f in type_fields
        )

        # Compute total number of config items
        total_ids = len(obj.inputs) + len(obj.outputs)
        cfg_count = (0 if has_custom_iobind or total_ids == 0 else 1) + len(
            type_fields
        )

        self._format_helper.append_line(
            lines, 1, f"{macro_name}, {cfg_count},"
        )

        handler = PROG_HANDLER_REGISTRY.get(prog_type)
        iobind_handled = False
        if handler is not None and total_ids > 0:
            iobind_handled = handler.emit_iobind_cpp(
                lines, obj, total_ids, self._format_helper, cpp_class
            )

        if not iobind_handled and not has_custom_iobind and total_ids > 0:
            # Standard iobind: interleaved (source, output) pairs
            self._format_helper.append_line(
                lines, 2, f"{cpp_class}::cfgIdIOBind({total_ids}),"
            )
            n_pairs = max(len(obj.inputs), len(obj.outputs))
            for i in range(n_pairs):
                src = obj.inputs[i] if i < len(obj.inputs) else obj.inputs[0]
                dst = (
                    obj.outputs[i] if i < len(obj.outputs) else obj.outputs[0]
                )
                self._format_helper.append_line(lines, 3, f"{src.upper()},")
                self._format_helper.append_line(lines, 3, f"{dst.upper()},")

        # Process type-specific config items (each is a separate config entry)
        for field_def in type_fields:
            self._emit_type_field(lines, field_def, obj, config)

        return lines
