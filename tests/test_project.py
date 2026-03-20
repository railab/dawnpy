#!/usr/bin/env python3
# tools/dawnpy/tests/test_project.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for the Project dataclass and OOT detection.
"""

from pathlib import Path

import pytest

from dawnpy.config import DawnRC, write_dawnrc
from dawnpy.dawn.project import Project
from dawnpy.sources import DawnSourcesMissing


def _mk_dawn_root(base: Path) -> Path:
    """Create a fake upstream Dawn repo layout under ``base``."""
    root = base / "fake_dawn"
    (root / "boards").mkdir(parents=True)
    (root / "external").mkdir()
    (root / "dawn").mkdir()
    (root / "Documentation").mkdir()
    return root


def _mk_oot_root(base: Path, name: str = "fake_oot") -> Path:
    """Create a fake out-of-tree project layout under ``base``."""
    root = base / name
    (root / "boards" / "sim" / "configs" / "demo").mkdir(parents=True)
    return root


class TestProjectResolveDefault:
    """Tests for Project.resolve() with no explicit path."""

    def test_default_resolution_returns_upstream_dawn(self):
        """Without a confpath, Project.resolve() finds the real Dawn root."""
        project = Project.resolve()
        assert project.project_root == project.dawn_root
        assert project.nuttx_dir == project.dawn_root / "external" / "nuttx"
        assert project.is_oot is False
        assert (project.dawn_root / "dawn").is_dir()
        assert (project.dawn_root / "Documentation").is_dir()


class TestProjectResolveFromPath:
    """Tests for Project.resolve(start_path)."""

    def test_intree_path_yields_intree_project(self, tmp_path):
        """A path inside the upstream Dawn repo gives an in-tree Project."""
        project = Project.resolve(Path(__file__))
        assert project.is_oot is False
        assert project.project_root == project.dawn_root

    def test_oot_path_yields_oot_project(self, tmp_path):
        """A path inside an OOT project gives an OOT Project."""
        oot_root = _mk_oot_root(tmp_path)
        confpath = oot_root / "boards" / "sim" / "configs" / "demo"

        project = Project.resolve(confpath)

        assert project.project_root == oot_root
        assert project.nuttx_dir == project.dawn_root / "external" / "nuttx"
        assert project.is_oot is True
        assert project.dawn_root != oot_root
        assert (project.dawn_root / "dawn").is_dir()

    def test_dawn_checkout_path_prefers_that_checkout_as_dawn_root(
        self, tmp_path
    ):
        """A standalone Dawn checkout should not be misclassified as OOT."""
        dawn_root = _mk_dawn_root(tmp_path)
        config_path = dawn_root / "boards" / "sim" / "configs" / "demo"
        config_path.mkdir(parents=True)

        project = Project.resolve(config_path)

        assert project.project_root == dawn_root
        assert project.dawn_root == dawn_root
        assert project.nuttx_dir == dawn_root / "external" / "nuttx"
        assert project.is_oot is False

    def test_dawnrc_can_override_dawn_and_nuttx_paths(
        self, tmp_path, monkeypatch
    ):
        workspace = tmp_path / "workspace"
        oot_root = _mk_oot_root(workspace, "myproj")
        dawn_root = _mk_dawn_root(workspace)
        relocated_nuttx = workspace / "vendor" / "nuttx"
        relocated_apps = workspace / "vendor" / "apps"
        relocated_nuttx.mkdir(parents=True)
        relocated_apps.mkdir(parents=True)
        write_dawnrc(
            workspace / ".dawnrc",
            {
                "paths": {
                    "dawn_root": "fake_dawn",
                    "nuttx_dir": "vendor/nuttx",
                    "nuttx_apps_dir": "vendor/apps",
                }
            },
        )

        monkeypatch.chdir(oot_root)
        project = Project.resolve(oot_root / "boards")

        assert project.dawn_root == dawn_root
        assert project.nuttx_dir == relocated_nuttx
        assert project.nuttx_apps_dir == relocated_apps
        assert isinstance(project.dawnrc, DawnRC)


class TestProjectCmakeEnv:
    """Tests for Project.cmake_env()."""

    def test_intree_env_lacks_oot_root(self):
        """In-tree builds export DAWN_BOARDS_COMMON only."""
        project = Project.resolve()
        env = project.cmake_env()

        assert "DAWN_BOARDS_COMMON" in env
        assert env["DAWN_BOARDS_COMMON"].endswith("boards/common")
        assert "DAWN_EXTENSION_APPS_KCONFIG" in env
        assert env["DAWN_EXTENSION_APPS_KCONFIG"].endswith(
            ".dawn-no-extension-apps.Kconfig"
        )
        assert "DAWN_OOT_ROOT" not in env

    def test_oot_env_includes_oot_root(self, tmp_path):
        """OOT builds export DAWN_OOT_ROOT pointing at the project root."""
        oot_root = _mk_oot_root(tmp_path)
        project = Project.resolve(oot_root / "boards")

        env = project.cmake_env()

        assert env.get("DAWN_OOT_ROOT") == str(oot_root)
        assert "DAWN_BOARDS_COMMON" in env
        # boards_common still points at the upstream Dawn repo
        assert env["DAWN_BOARDS_COMMON"].startswith(str(project.dawn_root))
        assert env["DAWN_EXTENSION_APPS_KCONFIG"].endswith(
            ".dawn-no-extension-apps.Kconfig"
        )

    def test_oot_env_includes_extension_apps_kconfig(self, tmp_path):
        """OOT builds export an explicit app-extension Kconfig path."""
        oot_root = _mk_oot_root(tmp_path)
        apps_kconfig = oot_root / "external" / "apps" / "Kconfig"
        apps_kconfig.parent.mkdir(parents=True)
        apps_kconfig.write_text("# apps\n", encoding="utf-8")

        project = Project.resolve(oot_root / "boards")
        env = project.cmake_env()

        assert env["DAWN_EXTENSION_APPS_KCONFIG"] == str(apps_kconfig)

    def test_oot_cmake_file_detected_when_present(self, tmp_path):
        """OOT projects may expose an explicit CMake extension entry point."""
        oot_root = _mk_oot_root(tmp_path)
        cmake_file = oot_root / "external" / "dawn_oot.cmake"
        cmake_file.parent.mkdir(parents=True)
        cmake_file.write_text("# oot\n", encoding="utf-8")

        project = Project.resolve(oot_root / "boards")

        assert project.oot_cmake_file() == cmake_file

    def test_oot_cmake_file_none_when_missing(self, tmp_path):
        """OOT projects without a CMake hook simply omit that cache entry."""
        oot_root = _mk_oot_root(tmp_path)
        project = Project.resolve(oot_root / "boards")

        assert project.oot_cmake_file() is None


class TestProjectResolveErrors:
    """Tests for the failure paths in Project.resolve()."""

    def test_raises_when_dawn_root_cannot_be_resolved(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "dawnpy.dawn.project._walk_up_for_dawn_root", lambda *_: None
        )
        with pytest.raises(DawnSourcesMissing):
            Project.resolve(tmp_path)

    def test_uses_dawnrc_root_for_oot_when_no_boards_above(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        workspace = tmp_path / "workspace"
        oot_root = workspace / "oot-only"
        oot_root.mkdir(parents=True)
        write_dawnrc(
            oot_root / ".dawnrc",
            {
                "paths": {"dawn_root": "../dawn-src"},
                "project": {"oot": True},
            },
        )
        dawn_src = workspace / "dawn-src"
        (dawn_src / "boards").mkdir(parents=True)
        (dawn_src / "external").mkdir()
        (dawn_src / "dawn").mkdir()
        (dawn_src / "Documentation").mkdir()

        monkeypatch.chdir(oot_root)
        project = Project.resolve(oot_root)

        assert project.project_root == oot_root
        assert project.dawn_root == dawn_src.resolve()
