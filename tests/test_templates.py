# tools/dawnpy/tests/test_templates.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the bundled-template registry and renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dawnpy.templates import (
    DEVICE_KIND,
    PROJECT_KIND,
    UnknownTemplateError,
    UnknownTemplateKindError,
    known_kinds,
    list_templates,
    render_tree,
    template_dir,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_known_kinds_lists_project_and_device() -> None:
    assert known_kinds() == (PROJECT_KIND, DEVICE_KIND)


def test_list_templates_returns_known_project() -> None:
    projects = list_templates(PROJECT_KIND)
    assert "minimal-sim" in projects


def test_list_templates_rejects_unknown_kind() -> None:
    with pytest.raises(UnknownTemplateKindError):
        list_templates("unknown-kind")


def test_template_dir_rejects_unknown_template() -> None:
    with pytest.raises(UnknownTemplateError):
        template_dir(PROJECT_KIND, "no-such-template")


def test_render_tree_skips_pycache_and_bytecode_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    fake_root = tmp_path / "fake-templates" / "project" / "demo"
    fake_root.mkdir(parents=True)
    (fake_root / "README").write_text("hello $NAME", encoding="utf-8")
    pyc = fake_root / "stale.pyc"
    pyc.write_bytes(b"\x00")
    cache = fake_root / "__pycache__"
    cache.mkdir()
    (cache / "stale.cpython-314.pyc").write_bytes(b"\x00")

    monkeypatch.setattr(
        "dawnpy.templates.template_dir",
        lambda kind, name: fake_root,
    )

    target = tmp_path / "out"
    render_tree(
        kind=PROJECT_KIND,
        name="demo",
        target_root=target,
        substitutions={"NAME": "world"},
    )

    assert (target / "README").read_text(encoding="utf-8") == "hello world"
    assert not (target / "stale.pyc").exists()
    assert not (target / "__pycache__").exists()


def test_load_manifest_handles_non_dict_section(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "index.toml"
    manifest.write_text(
        'device = "scalar"\n[project]\nminimal-sim = "demo"\n',
        encoding="utf-8",
    )
    fake_root = tmp_path
    monkeypatch.setattr("dawnpy.templates.templates_root", lambda: fake_root)

    assert list_templates(DEVICE_KIND) == {}
    assert list_templates(PROJECT_KIND) == {"minimal-sim": "demo"}
