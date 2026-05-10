# tools/dawnpy/tests/test_cmd_project.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for `dawnpy project` commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from dawnpy.commands.cmd_project import cmd_project
from dawnpy.config import load_dawnrc, write_dawnrc

if TYPE_CHECKING:
    from pathlib import Path


def test_project_list_shows_builtin_template() -> None:
    runner = CliRunner()
    result = runner.invoke(cmd_project, ["list"])

    assert result.exit_code == 0
    assert "minimal-sim" in result.output


def test_project_new_scaffolds_minimal_sim(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    dawn_root = workspace / "dawn-src"
    dawn_root.mkdir(parents=True)
    write_dawnrc(workspace / ".dawnrc", {"paths": {"dawn_root": "./dawn-src"}})
    monkeypatch.chdir(workspace)

    runner = CliRunner()
    result = runner.invoke(cmd_project, ["new", "myproj"])

    assert result.exit_code == 0
    project_root = workspace / "myproj"
    assert (project_root / "README.rst").is_file()
    assert (
        project_root
        / "boards"
        / "sim"
        / "sim"
        / "sim"
        / "configs"
        / "nsh_user_shell"
        / "defconfig"
    ).is_file()

    rc = load_dawnrc(project_root)
    assert rc.get_path("paths", "dawn_root") == dawn_root
    assert rc.get("project", "oot") is True
    assert rc.get("project", "types_from") == "dawnpy_types.py"
    types_module = (project_root / "dawnpy_types.py").read_text(
        encoding="utf-8"
    )
    assert "TypeRegistration" in types_module
    assert "registration = TypeRegistration" in types_module


def test_project_new_infers_workspace_dawn_src(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    dawn_root = workspace / "dawn-src"
    (dawn_root / "dawn").mkdir(parents=True)
    (dawn_root / "boards").mkdir()
    (dawn_root / "Documentation").mkdir()

    runner = CliRunner()
    result = runner.invoke(cmd_project, ["new", str(workspace / "myproj")])

    assert result.exit_code == 0
    rc = load_dawnrc(workspace / "myproj")
    assert rc.get_path("paths", "dawn_root") == dawn_root


def test_project_new_refuses_non_empty_target(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "stale.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cmd_project, ["new", str(target)])
    assert result.exit_code != 0
    assert "Refusing to scaffold" in result.output


def test_project_new_fails_when_dawn_root_unresolvable(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "isolated"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    runner = CliRunner()
    result = runner.invoke(cmd_project, ["new", str(workspace / "myproj")])
    assert result.exit_code != 0


def test_project_new_reports_unknown_template(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    dawn_root = workspace / "dawn-src"
    (dawn_root / "dawn").mkdir(parents=True)
    (dawn_root / "boards").mkdir()
    (dawn_root / "Documentation").mkdir()
    monkeypatch.chdir(workspace)

    runner = CliRunner()
    result = runner.invoke(
        cmd_project,
        [
            "new",
            str(workspace / "myproj"),
            "--template",
            "no-such-template",
        ],
    )
    assert result.exit_code != 0
    assert "no-such-template" in result.output
