# tools/dawnpy/src/dawnpy/descriptor/definitions/type_info.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""TypeInfo dataclasses for the descriptor type registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class ConfigField:
    """Declarative description of a single descriptor config item.

    OOT projects build a list of these on a TypeInfo's ``config_fields``
    to expose custom cfgIdXxx items in YAML descriptors. The IO/PROG/
    PROTO generators iterate the merged field list verbatim, so user
    fields flow through the same code path as built-in ones.

    :ivar name: YAML key under the object's ``config:`` block.
    :ivar cpp_helper: Fully-qualified C++ helper, e.g.
        ``"oot_demo::CIOMyDummy::cfgIdInitval"``. Use the ``{cpp_class}``
        placeholder for proto types that wrap with the user's class.
    :ivar value_type: One of ``"uint32"``, ``"uint16"``, ``"int32"``,
        ``"int64"``, ``"uint64"``, ``"float"``, ``"double"``,
        ``"bool"``, ``"string"``, ``"id_array"``, ``"id_array_pairs"``,
        ``"int"`` (and a few others - see proto_generators/generic.py
        for the full set).
    :ivar value_format: ``"hex"`` to emit numeric values in hex form,
        ``""`` for the default decimal. For ``"int"`` values only.
    :ivar enum_values: Mapping ``yaml_token -> cpp_token`` for enum-like
        scalar fields.
    :ivar enum_prefix: ``"Owner::PREFIX_"`` declaration that the registry
        builder hydrates into ``enum_values`` via ``load_header_enum_map``.
    :ivar default: Default value emitted when the YAML config omits this
        field. For enum fields this is an ``enum_values`` key.
    :ivar params: Optional helper-call params (``["dtype", "rw", "dim"]``)
        appended inside the parentheses of ``cfgIdXxx(...)``.
    :ivar default_params: Default values for the params above.
    :ivar config_rw: Optional explicit RW bit for binary cfg-id reconstruction.
        Deprecated for IO fields. IO config-item RW is generated from
        writable ConfigIO references and defaults to read-only.
    :ivar string_fixed_bytes: For string fields, fixed-byte width.
    :ivar string_array_size: For string-array fields, sizing strategy.
    :ivar nested: ``True`` when this entry is a container that holds
        ``element_fields`` instead of a scalar value.
    :ivar array: ``True`` when ``nested`` and the YAML value is a list
        of element dicts.
    :ivar element_fields: Sub-fields evaluated against each list item
        when ``nested and array``.
    :ivar size_calculation: Python expression evaluated with ``count``
        in scope to compute the helper's first argument for nested
        binding fields.
    """

    name: str
    cpp_helper: str = ""
    value_type: str = ""
    value_format: str = ""
    enum_values: Mapping[str, str] = field(default_factory=dict)
    enum_prefix: str = ""
    default: str = ""
    params: list[str] = field(default_factory=list)
    default_params: list[Any] = field(default_factory=list)
    config_rw: bool | None = None
    string_fixed_bytes: int | None = None
    string_array_size: str = "words"
    nested: bool = False
    array: bool = False
    element_fields: list[ConfigField] = field(default_factory=list)
    size_calculation: str = ""


def _coerce_field(entry: Any) -> ConfigField:
    """Validate that a config-field entry is a ConfigField."""
    if isinstance(entry, ConfigField):
        return entry
    raise TypeError(
        f"config_fields entries must be ConfigField, got "
        f"{type(entry).__name__}"
    )


def _normalize_config_fields(
    fields: list[Any] | None,
) -> list[ConfigField]:
    """Validate and return config fields."""
    return [_coerce_field(entry) for entry in (fields or [])]


def _hydrate_enum_values(
    cf: ConfigField,
    enum_loader: Any,
) -> ConfigField:
    """Resolve ``enum_prefix`` to ``enum_values`` (best-effort).

    ``enum_loader`` is a callable ``(owner, prefix) -> dict[str, str]``
    that resolves a prefix at registry-build time; pass any callable that
    raises :class:`HeaderDefsError` on miss.
    """
    new_elements = (
        [_hydrate_enum_values(elem, enum_loader) for elem in cf.element_fields]
        if cf.element_fields
        else cf.element_fields
    )
    if cf.enum_prefix and "::" in cf.enum_prefix and not cf.enum_values:
        owner, prefix = cf.enum_prefix.split("::", 1)
        if owner and prefix:
            try:
                enum_values = enum_loader(owner, prefix)
            except Exception:  # pragma: no cover
                enum_values = None
            if enum_values:
                return replace(
                    cf,
                    enum_values=dict(enum_values),
                    element_fields=new_elements,
                )
    if new_elements is not cf.element_fields:
        return replace(cf, element_fields=new_elements)
    return cf


@dataclass(frozen=True)
class ProtoSchema:
    """Resolved per-protocol config schema returned by ConfigLoader."""

    proto_type: str
    uses_standard_bindings: bool
    fields: list[ConfigField] = field(default_factory=list)

    def find_field(self, name: str) -> ConfigField | None:
        """Return the field with ``name``, or ``None`` if absent."""
        for f in self.fields:
            if f.name == name:
                return f
        return None


class IOTypeInfo:
    """Information about an IO type."""

    def __init__(
        self,
        cpp_class: str,
        header: str,
        helper_func: str,
        params: list[str],
        subtypes: list[str] | None = None,
        variants: list[dict[str, Any]] | None = None,
        config_fields: list[Any] | None = None,
    ):
        """
        Initialize IO type info.

        :param cpp_class: C++ class name (e.g., "CIODummy")
        :param header: Header file path (e.g., "dawn/io/dummy.hxx")
        :param helper_func: Helper function template
                           (e.g., "{cpp_class}::objectId")
        :param params: Parameter list for helper function
        :param subtypes: Optional list of subtypes (for sensor)
        :param variants: Optional list of variant definitions
                        (for sysinfo, etc.)
        :param config_fields: Optional list of :class:`ConfigField` (or
            equivalent dicts) describing per-instance config items.
            Generators iterate this list and emit one ``cfgIdXxx`` block
            per field that is present under the object's YAML
            ``config:`` block.
        """
        self.cpp_class = cpp_class
        self.header = header
        self.helper_func = helper_func
        self.params = params
        self.subtypes = subtypes or []
        self.variants = variants or []
        self.config_fields: list[ConfigField] = _normalize_config_fields(
            config_fields
        )

    def generate_helper_call(
        self,
        cpp_class: str,
        dtype: str,
        flags: dict[str, Any],
        instance: int,
        variant: str | None = None,
    ) -> str:
        """Generate helper function call."""
        format_args = {"cpp_class": cpp_class}
        if "{variant}" in self.helper_func:
            if variant:  # pragma: no cover
                variant_cap = "".join(
                    word.capitalize() for word in variant.split("_")
                )
                format_args["variant"] = variant_cap
            else:
                raise ValueError(
                    f"Variant required but not provided for {cpp_class}"
                )
        func = self.helper_func.format(**format_args)

        params = []
        for param in self.params:
            if param == "dtype":
                params.append(dtype)
            elif param == "instance":
                params.append(str(instance))
            elif param in flags:
                params.append(str(flags[param]).lower())
            else:
                if param == "rw":
                    params.append("false")
                elif param == "timestamp":
                    params.append("false")
                elif param == "notify":
                    params.append("false")

        return f"{func}({', '.join(params)})"


class ProgTypeInfo:
    """Information about a Program type."""

    def __init__(
        self,
        cpp_class: str,
        header: str,
        config_fields: list[Any] | None = None,
    ):
        """
        Initialize Program type info.

        :param cpp_class: C++ class name
        :param header: Header file path
        :param config_fields: Optional list of :class:`ConfigField` (or
            equivalent dicts) describing per-instance config items
            beyond the standard ``inputs``/``outputs`` IDs.
        """
        self.cpp_class = cpp_class
        self.header = header
        self.config_fields: list[ConfigField] = _normalize_config_fields(
            config_fields
        )


class ProtoTypeInfo:
    """Information about a Protocol type."""

    def __init__(
        self,
        cpp_class: str,
        header: str,
        config_fields: list[Any] | None = None,
        uses_standard_bindings: bool = True,
    ):
        """
        Initialize Protocol type info.

        :param cpp_class: C++ class name
        :param header: Header file path
        :param config_fields: Optional list of :class:`ConfigField` (or
            equivalent dicts) describing per-instance config items
            beyond the standard ``bindings:`` list.
        :param uses_standard_bindings: When ``True`` (the default), the
            generic protocol generator appends a
            ``{cpp_class}::cfgIdIOBind(...)`` line for any
            ``bindings:`` declared in YAML, after the typed config
            fields. Set to ``False`` for protocols that do not bind
            IOs through that helper.
        """
        self.cpp_class = cpp_class
        self.header = header
        self.config_fields: list[ConfigField] = _normalize_config_fields(
            config_fields
        )
        self.uses_standard_bindings = uses_standard_bindings


class SystemTypeInfo:
    """Information about a System (OBJTYPE_ANY) type."""

    def __init__(
        self,
        cpp_class: str,
        header: str,
        config_fields: list[Any] | None = None,
    ):
        """
        Initialize System type info.

        :param cpp_class: C++ class name (e.g. "CSystemLte").
        :param header: Header file path (e.g. "dawn/system/lte.hxx").
        :param config_fields: Optional list of :class:`ConfigField`
            describing per-instance config items. Generators iterate this
            list and emit one ``cfgIdXxx`` block per field present under the
            object's YAML ``config:`` block.
        """
        self.cpp_class = cpp_class
        self.header = header
        self.config_fields: list[ConfigField] = _normalize_config_fields(
            config_fields
        )


@dataclass(frozen=True)
class TypeRegistration:
    """User-package contribution to dawnpy's descriptor type registry.

    A ``dawnpy.extensions:descriptor_types`` entry-point returns a
    ``TypeRegistration`` (or an iterable of them). dawnpy merges its
    ``io_types``/``prog_types``/``proto_types`` mappings into the
    module-level :data:`IO_TYPES`, :data:`PROG_TYPES`, :data:`PROTO_TYPES`
    dicts so YAML descriptors can reference custom user types.

    Existing built-in entries with the same yaml_type are overwritten (a
    warning is logged), letting OOT projects override default upstream
    types.

    :ivar name: Human-readable label for diagnostics (typically the
        producing package name).
    :ivar io_types: ``yaml_type -> IOTypeInfo`` for custom IO types.
    :ivar prog_types: ``yaml_type -> ProgTypeInfo`` for custom PROG types.
    :ivar proto_types: ``yaml_type -> ProtoTypeInfo`` for custom PROTO
        types.
    """

    name: str
    io_types: Mapping[str, IOTypeInfo] = field(default_factory=dict)
    prog_types: Mapping[str, ProgTypeInfo] = field(default_factory=dict)
    proto_types: Mapping[str, ProtoTypeInfo] = field(default_factory=dict)
    system_types: Mapping[str, SystemTypeInfo] = field(default_factory=dict)
