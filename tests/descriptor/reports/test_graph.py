# tools/dawnpy/tests/descriptor/reports/test_graph.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the descriptor graph report."""

import textwrap
from pathlib import Path

import pytest

from dawnpy.descriptor.client import ClientProto
from dawnpy.descriptor.reports.graph import (
    _allocation_rows,
    _config_reference_edges,
    build_descriptor_graph,
    load_descriptor_graph,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _demo_spec() -> dict:
    """Return a small valid descriptor spec."""
    return {
        "ios": [
            {
                "id": "btn0",
                "type": "dummy",
                "dtype": "bool",
                "notify": True,
                "tags": ["input"],
            },
            {"id": "led0", "type": "dummy", "dtype": "bool"},
        ],
        "programs": [
            {
                "id": "tgl0",
                "type": "toggle",
                "config": {
                    "inputs": ["btn0"],
                    "outputs": ["led0"],
                    "reset": "btn0",
                },
            },
        ],
        "protocols": [
            {
                "id": "proto0",
                "type": "dummy",
                "config": {"bindings": ["led0"]},
            },
        ],
    }


def test_build_graph_nodes_typed():
    """Valid objects become typed nodes with metadata."""
    graph = build_descriptor_graph(_demo_spec())
    nodes = {n.id: n for n in graph.nodes}
    assert graph.name == "descriptor0"
    assert set(nodes) == {"btn0", "led0", "tgl0", "proto0"}
    btn = nodes["btn0"]
    assert btn.kind == "io"
    assert btn.type == "dummy"
    assert btn.dtype == "bool"
    assert btn.flags.notify is True
    assert btn.tags == ["input"]
    assert btn.valid is True
    assert nodes["tgl0"].kind == "program"
    assert nodes["proto0"].kind == "protocol"


def test_build_graph_unknown_io_type_generic_node():
    """Unknown object types stay visible as invalid generic nodes."""
    spec = _demo_spec()
    spec["ios"].append({"id": "x0", "type": "no_such_type"})
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "x0")
    assert node.valid is False
    assert node.errors
    assert node.kind == "io"
    assert node.type == "no_such_type"


def test_build_graph_entry_without_id_gets_placeholder():
    """Entries missing an id keep a synthesized placeholder node."""
    spec = _demo_spec()
    spec["ios"].append({"type": "dummy"})
    graph = build_descriptor_graph(spec)
    placeholders = [n for n in graph.nodes if n.id.startswith("__ios_")]
    assert len(placeholders) == 1
    assert placeholders[0].valid is False


def test_build_graph_system_nodes():
    """System entries appear as system-kind nodes."""
    spec = _demo_spec()
    spec["system"] = [{"id": "sys0", "type": "no_such_system"}]
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "sys0")
    assert node.kind == "system"
    assert node.valid is False


def test_build_graph_system_node_typed_valid():
    """A known system type decodes into a typed system node."""
    spec = _demo_spec()
    spec["system"] = [{"id": "sys0", "type": "lte"}]
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "sys0")
    assert node.kind == "system"
    assert node.type == "lte"
    assert node.valid is True
    assert node.errors == []


def test_build_graph_generic_node_non_dict_config_is_dropped():
    """A non-mapping ``config`` on an invalid entry is discarded."""
    spec = _demo_spec()
    spec["ios"].append(
        {"id": "x1", "type": "no_such_type", "config": "not-a-dict"}
    )
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "x1")
    assert node.valid is False
    assert node.config == {}


def test_build_graph_non_numeric_instance_generic_node():
    """A malformed instance field never crashes the builder."""
    spec = {
        "ios": [
            {
                "id": "btn0",
                "type": "dummy",
                "dtype": "bool",
                "instance": "notanumber",
            },
        ],
    }
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "btn0")
    assert node.valid is False
    assert node.instance == 0


def test_build_graph_program_edges():
    """Programs produce input/output/reset edges."""
    graph = build_descriptor_graph(_demo_spec())
    edges = {(e.source, e.target, e.kind) for e in graph.edges}
    assert ("btn0", "tgl0", "program_input") in edges
    assert ("tgl0", "led0", "program_output") in edges
    assert ("btn0", "tgl0", "program_reset") in edges


def test_build_graph_protocol_edges():
    """Protocol bindings produce protocol_binding edges."""
    graph = build_descriptor_graph(_demo_spec())
    edges = {(e.source, e.target, e.kind) for e in graph.edges}
    assert ("proto0", "led0", "protocol_binding") in edges


def test_build_graph_unresolved_edge_flagged():
    """Edges to unknown object ids are flagged unresolved."""
    spec = _demo_spec()
    spec["programs"][0]["config"]["inputs"] = ["ghost"]
    graph = build_descriptor_graph(spec)
    edge = next(e for e in graph.edges if e.source == "ghost")
    assert edge.unresolved is True


def test_build_graph_generic_node_edges_from_raw_config():
    """Invalid programs still contribute best-effort edges."""
    spec = _demo_spec()
    spec["programs"].append(
        {
            "id": "bad0",
            "type": "no_such_prog",
            "config": {"inputs": ["btn0"], "outputs": ["led0"]},
        }
    )
    graph = build_descriptor_graph(spec)
    edges = {(e.source, e.target, e.kind) for e in graph.edges}
    assert ("btn0", "bad0", "program_input") in edges
    assert ("bad0", "led0", "program_output") in edges


def test_build_graph_generic_protocol_edges_from_raw_config():
    """Invalid protocols still contribute best-effort binding edges."""
    spec = _demo_spec()
    spec["protocols"].append(
        {
            "id": "badproto0",
            "type": "no_such_proto",
            "config": {"bindings": ["btn0"]},
        }
    )
    graph = build_descriptor_graph(spec)
    edges = {(e.source, e.target, e.kind) for e in graph.edges}
    assert ("badproto0", "btn0", "protocol_binding") in edges


def test_build_graph_generic_protocol_non_list_bindings_ignored():
    """A non-list ``bindings`` on an invalid protocol yields no edges."""
    spec = _demo_spec()
    spec["protocols"].append(
        {
            "id": "badproto1",
            "type": "no_such_proto",
            "config": {"bindings": "not-a-list"},
        }
    )
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "badproto1")
    assert node.valid is False
    assert not any(e.source == "badproto1" for e in graph.edges)


def test_build_graph_generic_io_entry_yields_no_edges():
    """Invalid non-program/protocol entries contribute no edges."""
    spec = _demo_spec()
    spec["ios"].append({"id": "x2", "type": "no_such_type", "config": {}})
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "x2")
    assert node.valid is False
    assert not any(e.source == "x2" or e.target == "x2" for e in graph.edges)


def test_build_graph_raw_program_non_list_inputs_ignored():
    """Malformed non-list inputs on an invalid program add no edges."""
    spec = _demo_spec()
    spec["programs"].append(
        {
            "id": "bad0",
            "type": "no_such_prog",
            "config": {"inputs": "btn0", "outputs": "led0"},
        }
    )
    graph = build_descriptor_graph(spec)
    bad_edges = [e for e in graph.edges if "bad0" in (e.source, e.target)]
    assert bad_edges == []


def test_build_graph_objids_present():
    """Valid nodes carry a resolved 32-bit ObjectID."""
    graph = build_descriptor_graph(_demo_spec())
    nodes = {n.id: n for n in graph.nodes}
    assert isinstance(nodes["btn0"].objid, int)
    assert isinstance(nodes["tgl0"].objid, int)
    assert isinstance(nodes["proto0"].objid, int)


def test_build_graph_invalid_node_has_no_objid():
    """Invalid nodes carry no ObjectID."""
    spec = _demo_spec()
    spec["ios"].append({"id": "x0", "type": "no_such_type"})
    graph = build_descriptor_graph(spec)
    node = next(n for n in graph.nodes if n.id == "x0")
    assert node.objid is None


def test_build_graph_protocol_allocation_rows():
    """Valid protocol nodes carry allocation summary rows."""
    graph = build_descriptor_graph(_demo_spec())
    proto = next(n for n in graph.nodes if n.id == "proto0")
    assert proto.allocation is not None
    io_node = next(n for n in graph.nodes if n.id == "btn0")
    assert io_node.allocation is None


def test_allocation_rows_missing_handler_returns_none():
    """Protocol types without a registered handler yield no rows."""
    proto = ClientProto(
        proto_id="p0",
        proto_type="no_such_proto_type",
        instance=0,
        config={},
        bindings=[],
    )
    assert _allocation_rows(proto) is None


_SINGLE_YAML = """
metadata:
  title: demo
ios:
- id: btn0
  type: dummy
  dtype: bool
programs: []
protocols:
- id: proto0
  type: dummy
  config:
    bindings: [btn0]
"""

_MULTI_YAML = """
descriptor0:
  ios:
  - id: a0
    type: dummy
descriptor1:
  ios:
  - id: b0
    type: dummy
"""


def test_load_descriptor_graph_single(tmp_path: Path):
    """Single-descriptor YAML produces one graph unit."""
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(_SINGLE_YAML)
    doc = load_descriptor_graph(str(yaml_file))
    assert doc.format == "dawn-descriptor-graph"
    assert doc.version == 1
    assert doc.source == str(yaml_file)
    assert doc.metadata.get("title") == "demo"
    assert len(doc.descriptors) == 1
    assert doc.descriptors[0].name == "descriptor0"
    ids = {n.id for n in doc.descriptors[0].nodes}
    assert ids == {"btn0", "proto0"}


def test_load_descriptor_graph_multi(tmp_path: Path):
    """Multi-descriptor YAML produces one graph unit per descriptor."""
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(_MULTI_YAML)
    doc = load_descriptor_graph(str(yaml_file))
    names = [g.name for g in doc.descriptors]
    assert names == ["descriptor0", "descriptor1"]
    assert {n.id for n in doc.descriptors[1].nodes} == {"b0"}


def test_load_descriptor_graph_ignores_non_descriptor_keys(tmp_path: Path):
    """Non-descriptor keys and non-numeric-suffix keys are excluded."""
    yaml_text = textwrap.dedent("""
        descriptor0:
          ios:
          - id: a0
            type: dummy
        descriptor1:
          ios:
          - id: b0
            type: dummy
        descriptor_extra:
          ios:
          - id: c0
            type: dummy
        descriptor: {}
        other: value
        """)
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(yaml_text)
    doc = load_descriptor_graph(str(yaml_file))
    names = [g.name for g in doc.descriptors]
    assert names == ["descriptor0", "descriptor1"]


def test_load_descriptor_graph_ignores_non_dict_descriptor_value(
    tmp_path: Path,
):
    """A ``descriptorN`` key whose value is not a mapping is skipped."""
    yaml_text = textwrap.dedent("""
        descriptor0:
          ios:
          - id: a0
            type: dummy
        descriptor1: not-a-mapping
        """)
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(yaml_text)
    doc = load_descriptor_graph(str(yaml_file))
    names = [g.name for g in doc.descriptors]
    assert names == ["descriptor0"]


def test_load_descriptor_graph_non_dict_metadata_falls_back_to_empty(
    tmp_path: Path,
):
    """A non-mapping top-level ``metadata`` value is discarded."""
    yaml_text = textwrap.dedent("""
        metadata: not-a-mapping
        ios:
        - id: btn0
          type: dummy
        """)
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(yaml_text)
    doc = load_descriptor_graph(str(yaml_file))
    assert doc.metadata == {}


def test_build_graph_config_reference_edges():
    """Schema-declared ref fields (targets/objid_ref) become edges."""
    spec = {
        "ios": [
            {"id": "led0", "type": "dummy", "dtype": "bool"},
            {
                "id": "ctl0",
                "type": "control",
                "dtype": "uint32",
                "config": {"targets": ["seq0"], "allowed": ["start"]},
            },
            {
                "id": "cfg0",
                "type": "config",
                "dtype": "uint32",
                "config": {"objid_ref": "seq0", "objcfg_ref": "start_index"},
            },
        ],
        "programs": [
            {
                "id": "seq0",
                "type": "sequencer",
                "config": {
                    "targets": ["led0"],
                    "states": [{"value": 0, "dwell_us": 1000}],
                },
            },
        ],
    }
    graph = build_descriptor_graph(spec)
    refs = {
        (e.source, e.target, e.field)
        for e in graph.edges
        if e.kind == "object_ref"
    }
    assert ("ctl0", "seq0", "targets") in refs
    assert ("cfg0", "seq0", "objid_ref") in refs
    assert ("seq0", "led0", "targets") in refs
    assert all(not e.unresolved for e in graph.edges if e.kind == "object_ref")


def test_build_graph_config_reference_no_duplicate_io_edges():
    """Fields already modeled as program inputs/outputs are not re-added."""
    graph = build_descriptor_graph(_demo_spec())
    ref_edges = [e for e in graph.edges if e.kind == "object_ref"]
    assert ref_edges == []


def test_build_graph_config_reference_dict_form():
    """Single refs in {id: ...} dict form resolve to edges."""
    spec = {
        "ios": [
            {"id": "led0", "type": "dummy", "dtype": "bool"},
            {
                "id": "cfg0",
                "type": "config",
                "dtype": "uint32",
                "config": {
                    "objid_ref": {"id": "led0"},
                    "objcfg_ref": "initval",
                },
            },
        ],
    }
    graph = build_descriptor_graph(spec)
    refs = {
        (e.source, e.target) for e in graph.edges if e.kind == "object_ref"
    }
    assert ("cfg0", "led0") in refs


def test_config_reference_edges_no_handler_or_bad_config():
    """Missing handler or non-dict config yields no reference edges."""
    assert _config_reference_edges("x0", None, {}) == []


def test_build_graph_config_reference_unresolvable_ref_skipped():
    """Reference values that cannot resolve to an id are skipped."""
    spec = {
        "ios": [
            {
                "id": "cfg0",
                "type": "config",
                "dtype": "uint32",
                "config": {
                    "objid_ref": {"bad": "form"},
                    "objcfg_ref": "initval",
                },
            },
        ],
    }
    graph = build_descriptor_graph(spec)
    assert not any(e.kind == "object_ref" for e in graph.edges)
