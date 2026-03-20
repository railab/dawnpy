# tools/dawnpy/src/dawnpy/descriptor/generator.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Dawn Descriptor Generator.

Generates C++ descriptor files from YAML specifications.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.config_access import (
    ConfigRwGrants,
    build_config_rw_grants,
)
from dawnpy.descriptor.definitions.loader import ConfigLoader
from dawnpy.descriptor.definitions.objects import (
    IoObject,
    ProgramObject,
    ProtocolObject,
    decode_objects,
)
from dawnpy.descriptor.definitions.registry import PROG_TYPES, PROTO_TYPES
from dawnpy.descriptor.generation import ProtocolConfigGenerator
from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
from dawnpy.descriptor.generation.prog import ProgramConfigGenerator
from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY
from dawnpy.descriptor.support.formatting import DescriptorFormatHelper
from dawnpy.descriptor.support.utils import (
    resolve_reference,
    resolve_references,
)
from dawnpy.descriptor.support.vars import load_yaml_with_vars

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import DescriptorObject


class DescriptorGenerator:
    """Generate C++ descriptor from YAML specification."""

    def __init__(self) -> None:
        """Initialize generator."""
        self.objects: dict[str, DescriptorObject] = {}
        self.object_order: list[str] = []
        self.includes: set[str] = set()
        self.metadata: dict[str, Any] = {}
        self.config_loader = ConfigLoader()
        self.config_rw_grants: ConfigRwGrants = {}
        self._format_helper = DescriptorFormatHelper()
        self._io_config_builder = self._build_io_config_generator()
        self._prog_config_builder = self._build_program_config_generator()
        self._proto_config_builder = self._build_protocol_config_generator()

    def _build_io_config_generator(  # pragma: no cover
        self,
    ) -> IoConfigGenerator:
        return IoConfigGenerator(
            config_loader=self.config_loader,
            format_helper=self._format_helper,
            objects=lambda: self.objects,
            config_rw_grants=lambda: self.config_rw_grants,
        )

    def _build_program_config_generator(  # pragma: no cover
        self,
    ) -> ProgramConfigGenerator:
        return ProgramConfigGenerator(
            config_loader=self.config_loader,
            prog_types=dict(PROG_TYPES),
            format_helper=self._format_helper,
        )

    def _build_protocol_config_generator(  # pragma: no cover
        self,
    ) -> ProtocolConfigGenerator:
        return ProtocolConfigGenerator.create(
            config_loader=self.config_loader,
            proto_types=dict(PROTO_TYPES),
            proto_uses_standard_bindings=lambda proto_type: (
                self._proto_uses_standard_bindings(proto_type)
            ),
            proto_cpp_class=lambda proto: PROTO_TYPES[proto].cpp_class,
            resolve_references=resolve_references,
            resolve_reference=resolve_reference,
            format_helper=self._format_helper,
        )

    def load_yaml(
        self, yaml_path: str, kconfig_path: str | None = None
    ) -> dict[str, Any]:
        """Load and parse YAML descriptor."""
        return load_yaml_with_vars(
            yaml_path,
            kconfig_path=kconfig_path,
            resolve_kconfig_values=False,
        )

    def parse_spec(self, spec: dict[str, Any]) -> None:
        """Parse YAML specification and build object registry."""
        self.metadata = spec.get("metadata", {})

        # Always include common descriptor header
        self.includes.add("dawn/common/descriptor.hxx")

        for obj in decode_objects(spec, strict=True):
            obj_id = obj.obj_id
            self.objects[obj_id] = obj
            self.object_order.append(obj_id)
            self.includes.add(obj.get_header())

            if isinstance(obj, ProtocolObject):
                handler = PROTO_HANDLER_REGISTRY.get(obj.proto_type)
                if handler is not None:
                    handler.validate_descriptor_context(
                        obj_id, obj.config, self.objects
                    )

                headers = self._proto_config_builder.collect_proto_headers(
                    obj.proto_type, obj.config
                )
                self.includes.update(headers)

        self.config_rw_grants = build_config_rw_grants(self.objects)

    def _resolve_references(self, refs: list[Any]) -> list[str]:
        """Resolve YAML anchor references to object IDs."""
        return resolve_references(refs)

    def _resolve_reference(self, ref: Any) -> str | None:
        """Resolve a single YAML anchor reference."""
        return resolve_reference(ref)

    def generate_defines(self) -> list[str]:
        """Generate #define macros for all objects."""
        lines = []

        for obj_id in self.object_order:
            obj = self.objects[obj_id]
            lines.append(
                self._format_helper.define_line(
                    obj.macro_name, obj.get_helper_call()
                )
            )

        return lines

    def generate_descriptor_array(self) -> list[str]:
        """Generate descriptor array data."""
        return self.generate_descriptor_array_named(
            "g_dawn_desc", "g_dawn_desc_size"
        )

    def generate_descriptor_array_named(
        self, array_name: str, size_name: str
    ) -> list[str]:
        """
        Generate descriptor array data with custom variable names.

        :param array_name: Name of the generated uint32_t array variable.
        :param size_name: Name of the generated size_t variable.
        :return: List of C++ code lines.
        """
        lines = [f"uint32_t {array_name}[] =", "{"]
        fmt = self._format_helper

        # Header
        obj_count = len(self.objects)
        metadata_count = 1 if self.metadata else 0
        total_count = obj_count + metadata_count

        fmt.append_line(lines, 1, "// Header")
        lines.append("")
        fmt.append_line(
            lines, 1, f"CDescriptor::DAWN_DESCRIPTOR_HDR, {total_count},"
        )
        lines.append("")

        # Metadata (if present)
        if self.metadata:
            metadata_config_lines = self._generate_metadata_config()
            if metadata_config_lines:
                fmt.append_line(lines, 1, "// Metadata")
                lines.extend(metadata_config_lines)
                lines.append("")

        # Objects
        for obj_id in self.object_order:
            obj = self.objects[obj_id]
            macro_name = obj.macro_name

            fmt.append_line(lines, 1, f"// {obj_id}")

            if isinstance(obj, IoObject):
                lines.extend(self._generate_io_config(macro_name, obj))
                lines.append("")

            elif isinstance(obj, ProgramObject):
                lines.extend(self._generate_prog_config(macro_name, obj))
                lines.append("")

            elif isinstance(obj, ProtocolObject):
                lines.extend(self._generate_proto_config(macro_name, obj))
                lines.append("")

        # Footer
        fmt.append_line(lines, 1, "// Check sum")
        lines.append("")
        fmt.append_line(lines, 1, "CDescriptor::DAWN_DESCRIPTOR_FOOT,")
        fmt.append_line(lines, 2, "0xdeadbeef")
        lines.append("};")
        lines.append("")
        lines.append(f"size_t {size_name} = sizeof({array_name});")

        return lines

    def _encode_version(self, version_str: str) -> str:
        """Encode version string to hex (0xMMMMmmmm format)."""
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) if len(parts) > 1 else 0

        version_int = (major << 16) | minor
        return f"0x{version_int:08x}"

    def _generate_metadata_config(self) -> list[str]:  # noqa: C901
        """
        Generate metadata configuration section.

        :return: List of C++ code lines
        """
        lines: list[str] = []

        if not self.metadata:
            return lines

        # Get metadata field definitions
        metadata_field_defs = self.config_loader.get_metadata_fields()

        # Count how many metadata fields are present and valid
        config_count = 0
        for field_def in metadata_field_defs:
            field_name = field_def["name"]
            if field_name in self.metadata and field_def.get("cpp_helper", ""):
                config_count += 1

        has_no_idle = (
            "no_idle_quit" in self.metadata
            and self.metadata["no_idle_quit"] is True
        )
        if has_no_idle:
            config_count += 1  # pragma: no cover

        if config_count == 0:
            return lines

        fmt = self._format_helper
        fmt.append_line(lines, 1, f"CDescriptor::objectId(1), {config_count},")

        for field_def in metadata_field_defs:
            field_name = field_def["name"]
            if field_name not in self.metadata:
                continue
            cpp_helper = field_def.get("cpp_helper", "")
            if not cpp_helper:
                continue
            value = self.metadata[field_name]
            value_type = field_def.get("value_type", "")
            if value_type == "version":
                fmt.append_line(lines, 2, f"{cpp_helper}(),")
                fmt.append_line(
                    lines, 2, f"{self._encode_version(str(value))},"
                )
            elif value_type == "string":
                packed_words = self._format_helper.pack_string(str(value))
                fmt.append_line(
                    lines, 2, f"{cpp_helper}({len(packed_words)}),"
                )
                fmt.append_words(lines, packed_words, level=2)
            else:
                fmt.append_line(lines, 2, f"{cpp_helper}(),")
                fmt.append_line(lines, 2, f"{value},")

        if has_no_idle:
            fmt.append_line(  # pragma: no cover
                lines, 2, "CDescriptor::cfgIdNoIdleQuit(),"
            )
            fmt.append_line(lines, 2, "1,")  # pragma: no cover

        return lines

    def _generate_io_config(  # noqa: C901
        self, macro_name: str, obj: IoObject
    ) -> list[str]:
        """Generate configuration for an IO object."""
        return self._io_config_generator().generate_io_config(macro_name, obj)

    def _io_config_generator(self) -> IoConfigGenerator:
        """Return cached general IO configuration generator."""
        return self._io_config_builder

    def _generate_prog_config(
        self, macro_name: str, obj: ProgramObject
    ) -> list[str]:
        """Generate configuration for a Program object."""
        return self._prog_config_builder.generate_prog_config(macro_name, obj)

    def _generate_proto_config(
        self, macro_name: str, obj: ProtocolObject
    ) -> list[str]:
        """Generate configuration for a Protocol object."""
        return self._protocol_config_generator().generate_proto_config(
            macro_name, obj
        )

    def _proto_uses_standard_bindings(self, proto_type: str) -> bool:
        """Return whether protocol includes standard IO bindings."""
        proto_schema = self.config_loader.get_proto_config_schema(proto_type)
        if proto_schema is None:
            return False
        return proto_schema.uses_standard_bindings

    def _protocol_config_generator(self) -> ProtocolConfigGenerator:
        """Return cached protocol configuration dispatcher."""
        return self._proto_config_builder

    @staticmethod
    def _is_multi_descriptor_spec(spec: dict[str, Any]) -> bool:
        """
        Return True if the spec uses multi-descriptor format.

        :param spec: Parsed YAML specification.
        :return: True when 'descriptor0' key is present.
        """
        return "descriptor0" in spec

    @staticmethod
    def _get_descriptor_indices(spec: dict[str, Any]) -> list[int]:
        """
        Return sorted list of descriptor indices from a multi-descriptor spec.

        :param spec: Parsed YAML specification.
        :return: Sorted list of integer indices for descriptorN keys.
        """
        indices = []
        i = 0
        while f"descriptor{i}" in spec:
            indices.append(i)
            i += 1
        return indices

    def _generate_file_header(self, yaml_path: str) -> list[str]:
        """
        Generate standard file header comment lines.

        :param yaml_path: Path to the source YAML file.
        :return: List of comment lines.
        """
        yaml_file = Path(yaml_path).name
        return [
            "//" + "*" * 75,
            f"// Auto-generated from {yaml_file}",
            "// DO NOT EDIT - Changes will be overwritten",
            "//" + "*" * 75,
            "",
        ]

    def _generate_includes_section(
        self, includes: set[str] | None = None
    ) -> list[str]:
        """
        Generate include directives section.

        :param includes: Set of include paths. Uses self.includes when None.
        :return: List of C++ include lines.
        """
        inc = includes if includes is not None else self.includes
        lines = ["// Included Files", ""]
        for include in sorted(inc):
            lines.append(f'#include "{include}"')
        lines.append("")
        return lines

    @staticmethod
    def _generate_flash_slot_table(extra_indices: list[int]) -> list[str]:
        """
        Generate FLASH descriptor slot data table for extra slots.

        Emits three data-only declarations that dawn_main uses to register
        compiled-in FLASH slots without any generated logic.

        :param extra_indices: Sorted list of descriptor indices > 0.
        :return: List of C++ code lines.
        """
        descs = ", ".join(f"g_dawn_desc{i}" for i in extra_indices)
        sizes = ", ".join(f"g_dawn_desc{i}_size" for i in extra_indices)
        count = len(extra_indices)
        return [
            "// FLASH Descriptor Slots",
            "",
            f"uint32_t * const g_dawn_flash_descs[]      = {{ {descs} }};",
            f"const size_t     g_dawn_flash_desc_sizes[] = {{ {sizes} }};",
            f"const size_t     g_dawn_flash_desc_count   = {count};",
        ]

    def _generate_multi(self, spec: dict[str, Any], yaml_path: str) -> str:
        """
        Generate C++ for a multi-descriptor YAML file.

        Creates one descriptor array per descriptorN block. Extra slots
        (1..N) are exposed via a small data table so that dawn_main can
        register them without any generated logic.

        :param spec: Parsed multi-descriptor YAML specification.
        :param yaml_path: Path to source YAML (used for header comment).
        :return: Generated C++ code as string.
        """
        indices = self._get_descriptor_indices(spec)

        # Build one DescriptorGenerator per descriptor spec
        generators: list[tuple[int, DescriptorGenerator]] = []
        for idx in indices:
            gen = DescriptorGenerator()
            gen.parse_spec(spec[f"descriptor{idx}"])
            generators.append((idx, gen))

        # Collect includes from all descriptors
        all_includes: set[str] = set()
        for _idx, gen in generators:
            all_includes.update(gen.includes)

        lines: list[str] = []

        # File header
        lines.extend(self._generate_file_header(yaml_path))

        # Includes
        lines.extend(self._generate_includes_section(all_includes))

        lines.append("using namespace dawn;")
        lines.append("")

        # Generate each descriptor section
        for desc_pos, (idx, gen) in enumerate(generators):
            suffix = "" if idx == 0 else str(idx)
            array_name = f"g_dawn_desc{suffix}"
            size_name = f"g_dawn_desc{suffix}_size"

            if idx == 0:
                lines.append("// Descriptor 0 (default)")
            else:
                lines.append(f"// Descriptor {idx}")
            lines.append("")

            if gen.objects:
                lines.append("// Object Definitions")
                lines.append("")
                lines.extend(gen.generate_defines())
                lines.append("")

            lines.append("// Descriptor Array")
            lines.append("")
            lines.extend(
                gen.generate_descriptor_array_named(array_name, size_name)
            )

            # Undef macros to allow redefinition in the next descriptor
            if desc_pos < len(generators) - 1 and gen.objects:
                lines.append("")
                for obj_id in gen.object_order:
                    obj = gen.objects[obj_id]
                    lines.append(f"#undef {obj.macro_name}")

            lines.append("")

        # FLASH slot data table for slots 1..N (data only, no logic)
        extra_indices = [idx for idx, _ in generators if idx > 0]
        if extra_indices:
            lines.extend(self._generate_flash_slot_table(extra_indices))

        return "\n".join(lines)

    def generate(self, yaml_path: str, kconfig_path: str | None = None) -> str:
        """
        Generate C++ descriptor from YAML file.

        Supports both single-descriptor and multi-descriptor (descriptor0,
        descriptor1, ...) YAML formats.  When multiple descriptors are defined,
        each gets its own array (g_dawn_desc, g_dawn_desc1, ...) plus a
        minimal data table so dawn_main can register all FLASH slots at
        boot without an over-the-air upload.

        :param yaml_path: Path to YAML descriptor file
        :return: Generated C++ code as string
        """
        # Load and parse
        spec = self.load_yaml(yaml_path, kconfig_path=kconfig_path)

        if self._is_multi_descriptor_spec(spec):
            return self._generate_multi(spec, yaml_path)

        self.parse_spec(spec)

        # Generate sections
        lines = []

        # Header comment
        lines.extend(self._generate_file_header(yaml_path))

        # Includes
        lines.extend(self._generate_includes_section())

        lines.append("using namespace dawn;")
        lines.append("")

        # Defines
        if self.objects:
            lines.append("// Object Definitions")
            lines.append("")
            lines.extend(self.generate_defines())
            lines.append("")

        # Descriptor array
        lines.append("// Descriptor Array")
        lines.append("")
        lines.extend(self.generate_descriptor_array())

        return "\n".join(lines)


def generate_descriptor(
    yaml_path: str,
    output_path: str | None = None,
    kconfig_path: str | None = None,
) -> None:
    """
    Generate C++ descriptor from YAML file.

    :param yaml_path: Path to YAML descriptor file
    :param output_path: Optional output path for C++ file.
                       If None, prints to stdout.
    """
    generator = DescriptorGenerator()
    cpp_code = generator.generate(yaml_path, kconfig_path=kconfig_path)

    if output_path:
        with open(output_path, "w") as f:
            f.write(cpp_code)
        print(f"Generated: {output_path}")
    else:
        print(cpp_code)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: generator.py <yaml_file> [output_file]")
        sys.exit(1)

    yaml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    generate_descriptor(yaml_file, output_file)
