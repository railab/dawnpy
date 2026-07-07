# tools/dawnpy/src/dawnpy/descriptor/reports/graph.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Machine-readable descriptor graph export.

Builds a normalized node/edge document from a descriptor spec. Objects
that fail typed decoding are kept as generic invalid nodes so consumers
(e.g. Dawn Workbench) can always render the full graph.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from dawnpy.descriptor.client import ClientIo, ClientProgram, ClientProto
from dawnpy.descriptor.definitions.objects import (
    DescriptorDecodeError,
    DescriptorObject,
    IoObject,
    ProgramObject,
    ProtocolObject,
    SystemObject,
    prepare_spec_instances,
)
from dawnpy.descriptor.definitions.summary import ObjectIdResolver
from dawnpy.descriptor.handlers import (
    IO_HANDLER_REGISTRY,
    PROG_HANDLER_REGISTRY,
    PROTO_HANDLER_REGISTRY,
)
from dawnpy.descriptor.support.utils import (
    resolve_flexible_reference,
    resolve_reference,
    resolve_references,
)
from dawnpy.descriptor.support.vars import load_yaml_with_vars

NodeKind = Literal["io", "program", "protocol", "system"]
EdgeKind = Literal[
    "program_input",
    "program_output",
    "program_reset",
    "protocol_binding",
    "object_ref",
]

# ConfigField.value_type values whose config entries reference other
# descriptor objects and therefore contribute object_ref edges.
_REF_VALUE_TYPES = {
    "id_single",
    "id_list",
    "config_ref",
    "config_alloc",
    "switch_target",
}

# Program config fields already modeled as program_* edges by
# ProgramObject.from_spec; never re-exported as object_ref edges.
_PROGRAM_WIRING_FIELDS = frozenset({"inputs", "outputs", "reset"})

_SECTION_KINDS: list[tuple[str, NodeKind]] = [
    ("ios", "io"),
    ("programs", "program"),
    ("protocols", "protocol"),
    ("system", "system"),
]

ALLOCATION_HEADERS: list[str] = [
    "block",
    "kind",
    "start",
    "end",
    "count",
    "details",
]


class GraphNodeFlags(BaseModel):
    """IO access/behavior flags surfaced on graph nodes."""

    model_config = ConfigDict(frozen=True)

    timestamp: bool = False
    notify: bool = False
    rw: bool = False


class GraphNode(BaseModel):
    """One descriptor object as a graph node."""

    model_config = ConfigDict(frozen=True)

    id: str  # noqa: A003
    kind: NodeKind
    type: str  # noqa: A003
    instance: int = 0
    dtype: str | None = None
    tags: list[str] = []
    flags: GraphNodeFlags = GraphNodeFlags()
    subtype: str | None = None
    variant: str | None = None
    config: dict[str, Any] = {}
    objid: int | None = None
    valid: bool = True
    errors: list[str] = []
    allocation: list[list[str]] | None = None


class GraphEdge(BaseModel):
    """One relationship between two descriptor objects."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    kind: EdgeKind
    unresolved: bool = False
    field: str | None = None


class DescriptorGraph(BaseModel):
    """Graph for one descriptor."""

    model_config = ConfigDict(frozen=True)

    name: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class DescriptorGraphDocument(BaseModel):
    """Top-level graph export document."""

    model_config = ConfigDict(frozen=True)

    format: Literal["dawn-descriptor-graph"] = (  # noqa: A003
        "dawn-descriptor-graph"
    )
    version: int = 1
    source: str | None = None
    metadata: dict[str, Any] = {}
    descriptors: list[DescriptorGraph]


def build_descriptor_graph(
    spec: dict[str, Any], name: str = "descriptor0"
) -> DescriptorGraph:
    """Build a graph from one normalized descriptor spec.

    Note: mutates ``spec`` in place (instance auto-assignment); pass a
    copy when reusing the spec.
    """
    prepare_spec_instances(spec)
    resolver = ObjectIdResolver()
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for section, kind in _SECTION_KINDS:
        for index, entry in enumerate(spec.get(section, [])):
            node, obj = _decode_node(entry, section, kind, index, resolver)
            nodes.append(node)
            edges.extend(_node_edges(node, obj, entry))
    known = {node.id for node in nodes}
    edges = [
        edge.model_copy(
            update={
                "unresolved": edge.source not in known
                or edge.target not in known
            }
        )
        for edge in edges
    ]
    return DescriptorGraph(name=name, nodes=nodes, edges=edges)


def _node_edges(
    node: GraphNode, obj: DescriptorObject | None, entry: dict[str, Any]
) -> list[GraphEdge]:
    """Return edges contributed by one node."""
    if isinstance(obj, ProgramObject):
        edges = _program_edges(node.id, obj.inputs, obj.outputs, obj.reset)
        edges.extend(
            _config_reference_edges(
                node.id,
                PROG_HANDLER_REGISTRY.get(obj.prog_type),
                obj.config,
                skip_fields=_PROGRAM_WIRING_FIELDS,
            )
        )
        return edges
    if isinstance(obj, IoObject):
        return _config_reference_edges(
            node.id, IO_HANDLER_REGISTRY.get(obj.io_type), obj.config
        )
    if isinstance(obj, ProtocolObject):
        return [
            GraphEdge(source=node.id, target=ref, kind="protocol_binding")
            for ref in obj.bindings
        ]
    if obj is None:
        return _raw_entry_edges(node, entry)
    return []


def _config_reference_edges(
    node_id: str,
    handler: Any,
    config: dict[str, Any],
    skip_fields: frozenset[str] = frozenset(),
) -> list[GraphEdge]:
    """Return object_ref edges from schema-declared reference fields.

    Handlers mark object-reference config fields via
    ``ConfigField.value_type`` (see ``_REF_VALUE_TYPES``); every value
    of such a top-level field becomes an ``object_ref`` edge from the
    owning object to the referenced one, labeled with the field name.
    """
    if handler is None or not isinstance(config, dict):
        return []
    edges: list[GraphEdge] = []
    for field in handler.config_fields():
        if field.value_type not in _REF_VALUE_TYPES:
            continue
        if field.name in skip_fields or field.name not in config:
            continue
        value = config[field.name]
        raw_refs = value if isinstance(value, list) else [value]
        for raw in raw_refs:
            ref = resolve_flexible_reference(raw)
            if not ref:
                continue
            edges.append(
                GraphEdge(
                    source=node_id,
                    target=ref,
                    kind="object_ref",
                    field=field.name,
                )
            )
    return edges


def _program_edges(
    prog_id: str,
    inputs: list[str],
    outputs: list[str],
    reset: str | None,
) -> list[GraphEdge]:
    """Return program data-flow edges."""
    edges = [
        GraphEdge(source=ref, target=prog_id, kind="program_input")
        for ref in inputs
    ]
    edges.extend(
        GraphEdge(source=prog_id, target=ref, kind="program_output")
        for ref in outputs
    )
    if reset is not None:
        edges.append(
            GraphEdge(source=reset, target=prog_id, kind="program_reset")
        )
    return edges


def _raw_entry_edges(
    node: GraphNode, entry: dict[str, Any]
) -> list[GraphEdge]:
    """Return best-effort edges for an entry that failed decoding."""
    config = entry.get("config")
    if not isinstance(config, dict):
        return []
    if node.kind == "program":
        inputs = config.get("inputs", [])
        outputs = config.get("outputs", [])
        reset_ref = config.get("reset")
        return _program_edges(
            node.id,
            resolve_references(inputs if isinstance(inputs, list) else []),
            resolve_references(outputs if isinstance(outputs, list) else []),
            resolve_reference(reset_ref) if reset_ref else None,
        )
    if node.kind == "protocol":
        bindings = config.get("bindings", entry.get("bindings", []))
        if not isinstance(bindings, list):
            return []
        return [
            GraphEdge(source=node.id, target=ref, kind="protocol_binding")
            for ref in resolve_references(bindings)
        ]
    return []


def _decode_node(
    entry: dict[str, Any],
    section: str,
    kind: NodeKind,
    index: int,
    resolver: ObjectIdResolver,
) -> tuple[GraphNode, DescriptorObject | None]:
    """Decode one spec entry into a node, falling back to generic."""
    try:
        obj = _from_spec(entry, kind)
    except (DescriptorDecodeError, ValueError, TypeError) as exc:
        return _generic_node(entry, section, kind, index, str(exc)), None
    return _typed_node(obj, kind, resolver), obj


def _from_spec(entry: dict[str, Any], kind: NodeKind) -> DescriptorObject:
    """Decode one entry via the matching typed object."""
    obj: DescriptorObject | None
    if kind == "io":
        obj = IoObject.from_spec(entry, strict=True)
    elif kind == "program":
        obj = ProgramObject.from_spec(entry, strict=True)
    elif kind == "protocol":
        obj = ProtocolObject.from_spec(entry, strict=True)
    else:
        obj = SystemObject.from_spec(entry, strict=True)
    if obj is None:  # pragma: no cover - strict decode raises instead
        raise DescriptorDecodeError("entry could not be decoded")
    return obj


def _typed_node(
    obj: DescriptorObject, kind: NodeKind, resolver: ObjectIdResolver
) -> GraphNode:
    """Build a node from a successfully decoded object."""
    if isinstance(obj, IoObject):
        client_io = ClientIo(
            io_id=obj.obj_id,
            io_type=obj.io_type,
            instance=obj.instance,
            dtype=obj.dtype,
            tags=obj.tags,
            config=obj.config,
            timestamp=obj.timestamp,
            notify=obj.notify,
            rw=obj.rw,
            subtype=obj.subtype,
            variant=obj.variant,
        )
        return GraphNode(
            id=obj.obj_id,
            kind=kind,
            type=obj.io_type,
            instance=obj.instance,
            dtype=obj.dtype,
            tags=obj.tags,
            flags=GraphNodeFlags(
                timestamp=obj.timestamp, notify=obj.notify, rw=obj.rw
            ),
            subtype=obj.subtype,
            variant=obj.variant,
            config=obj.config,
            objid=resolver.io_objid(client_io),
        )
    if isinstance(obj, ProgramObject):
        client_prog = ClientProgram(
            prog_id=obj.obj_id,
            prog_type=obj.prog_type,
            instance=obj.instance,
            inputs=obj.inputs,
            outputs=obj.outputs,
            config=obj.config,
        )
        return GraphNode(
            id=obj.obj_id,
            kind=kind,
            type=obj.prog_type,
            instance=obj.instance,
            dtype=obj.dtype,
            config=obj.config,
            objid=resolver.program_objid(client_prog),
        )
    if isinstance(obj, ProtocolObject):
        client_proto = ClientProto(
            proto_id=obj.obj_id,
            proto_type=obj.proto_type,
            instance=obj.instance,
            config=obj.config,
            bindings=obj.bindings,
        )
        return GraphNode(
            id=obj.obj_id,
            kind=kind,
            type=obj.proto_type,
            instance=obj.instance,
            config=obj.config,
            objid=resolver.protocol_objid(client_proto),
            allocation=_allocation_rows(client_proto),
        )
    assert isinstance(obj, SystemObject)
    return GraphNode(
        id=obj.obj_id,
        kind=kind,
        type=obj.system_type,
        instance=obj.instance,
        config=obj.config,
    )


def _allocation_rows(proto: ClientProto) -> list[list[str]] | None:
    """Return handler allocation rows for a protocol, if available."""
    handler = PROTO_HANDLER_REGISTRY.get(proto.proto_type)
    if handler is None:
        return None
    return [
        [str(cell) for cell in row] for row in handler.allocation_rows(proto)
    ]


def _generic_node(
    entry: dict[str, Any],
    section: str,
    kind: NodeKind,
    index: int,
    error: str,
) -> GraphNode:
    """Build a generic invalid node from a raw entry."""
    entry_id = entry.get("id") or f"__{section}_{index}"
    config = entry.get("config") or {}
    if not isinstance(config, dict):
        config = {}
    return GraphNode(
        id=str(entry_id),
        kind=kind,
        type=str(entry.get("type", "")),
        instance=_safe_instance(entry.get("instance", 0)),
        dtype=_optional_str(entry.get("dtype")),
        config=config,
        valid=False,
        errors=[error],
    )


def _safe_instance(value: Any) -> int:
    """Return ``value`` as an int, falling back to 0."""
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def _optional_str(value: Any) -> str | None:
    """Return ``value`` as ``str`` or ``None``."""
    return None if value is None else str(value)


def load_descriptor_graph(
    yaml_path: str,
    kconfig_path: str | None = None,
    kconfig_overrides: dict[str, Any] | None = None,
) -> DescriptorGraphDocument:
    """Load a descriptor YAML file into a graph document."""
    spec = load_yaml_with_vars(
        yaml_path,
        kconfig_path=kconfig_path,
        kconfig_overrides=kconfig_overrides,
    )
    metadata = spec.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return DescriptorGraphDocument(
        source=yaml_path,
        metadata=metadata,
        descriptors=_descriptor_graphs(spec),
    )


def _descriptor_graphs(spec: dict[str, Any]) -> list[DescriptorGraph]:
    """Return one graph per descriptor section in a multi-descriptor spec.

    Falls back to a single graph built from the whole spec when no
    ``descriptor0`` key is present.
    """
    if "descriptor0" not in spec:
        return [build_descriptor_graph(spec)]
    keys = sorted(
        (key for key in spec if _is_descriptor_key(key, spec)),
        key=lambda k: int(k.removeprefix("descriptor")),
    )
    return [build_descriptor_graph(spec[key], name=key) for key in keys]


def _is_descriptor_key(key: str, spec: dict[str, Any]) -> bool:
    """Return True for descriptorN sub-spec keys."""
    return (
        key.startswith("descriptor")
        and key.removeprefix("descriptor").isdigit()
        and isinstance(spec[key], dict)
    )
