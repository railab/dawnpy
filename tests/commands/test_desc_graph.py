# tools/dawnpy/tests/commands/test_desc_graph.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the desc-graph CLI command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dawnpy.commands.cmd_desc_graph import cmd_desc_graph

pytestmark = pytest.mark.usefixtures("source_free_headers")

_YAML = """
ios:
- id: btn0
  type: dummy
  dtype: bool
protocols:
- id: proto0
  type: dummy
  config:
    bindings: [btn0]
"""


def _write_yaml(tmp_path: Path) -> Path:
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text(_YAML)
    return yaml_file


def test_desc_graph_stdout(tmp_path: Path):
    """desc-graph prints a JSON document to stdout."""
    runner = CliRunner()
    result = runner.invoke(cmd_desc_graph, [str(_write_yaml(tmp_path))])
    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["format"] == "dawn-descriptor-graph"
    ids = {n["id"] for n in doc["descriptors"][0]["nodes"]}
    assert ids == {"btn0", "proto0"}


def test_desc_graph_output_file(tmp_path: Path):
    """desc-graph -o writes the JSON to a file."""
    runner = CliRunner()
    out = tmp_path / "graph.json"
    result = runner.invoke(
        cmd_desc_graph, [str(_write_yaml(tmp_path)), "-o", str(out)]
    )
    assert result.exit_code == 0
    doc = json.loads(out.read_text())
    assert doc["version"] == 1


def test_desc_graph_invalid_yaml(tmp_path: Path):
    """desc-graph reports unreadable specs and fails."""
    yaml_file = tmp_path / "descriptor.yaml"
    yaml_file.write_text("ios: [{id: [broken, 1}\n")
    runner = CliRunner()
    result = runner.invoke(cmd_desc_graph, [str(yaml_file)])
    assert "Error" in result.output


def test_desc_graph_registered():
    """desc-graph is registered as a built-in dawnpy command."""
    from dawnpy.plugins_loader import commands_list

    assert any(c.name == "desc-graph" for c in commands_list)
