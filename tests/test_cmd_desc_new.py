#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for ``dawnpy desc-new``."""

from pathlib import Path

from click.testing import CliRunner

from dawnpy.commands.cmd_desc_new import (
    _format_title,
    _normalize_name,
    _render_descriptor,
    cmd_desc_new,
)


def test_name_helpers_cover_common_cases() -> None:
    """Helper functions normalize filenames and derive a readable title."""
    assert _normalize_name("demo") == "demo.yaml"
    assert _normalize_name("demo.yaml") == "demo.yaml"
    assert _format_title("hello_world.yaml") == "Hello World"
    assert _format_title("---.yaml") == "New Descriptor"
    assert "title: Hello World" in _render_descriptor("hello_world.yaml")


def test_desc_new_creates_placeholder_and_prints_doc_reminder(
    tmp_path: Path,
) -> None:
    """Command writes the placeholder file and reminder text."""
    runner = CliRunner()

    result = runner.invoke(
        cmd_desc_new,
        ["demo", "--out-dir", str(tmp_path)],
    )

    target = tmp_path / "demo.yaml"
    assert result.exit_code == 0
    assert target.exists()
    assert "Created descriptor placeholder" in result.output
    assert "Documentation/examples/descriptors.rst" in result.output
    assert "title: Demo" in target.read_text(encoding="utf-8")


def test_desc_new_rejects_existing_target(tmp_path: Path) -> None:
    """Command fails cleanly when the target file already exists."""
    target = tmp_path / "demo.yaml"
    target.write_text("metadata: {}\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        cmd_desc_new,
        ["demo", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "Descriptor already exists" in result.output
