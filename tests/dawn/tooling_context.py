# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the Dawn CLI support modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dawnpy.config import DawnRC
from dawnpy.dawn import output
from dawnpy.dawn.build_dir import (
    generate_build_dir_name,
    is_build_configured,
    sanitize_build_component,
)
from dawnpy.dawn.cmake import build_cmake, configure_cmake
from dawnpy.dawn.kconfig import build_kconfig_env, set_kconfig_value
from dawnpy.dawn.workflows import (
    BatchRequest,
    BuildRequest,
    KconfigSweepRequest,
    _maybe_configure,
    _merge_cmake_flags,
    _merge_env_vars,
    _parse_batch_line,
    _resolve_descriptor_yaml_from_config,
    _run_build_only,
    _run_configure_build,
    _validate_generated_config,
    parse_batch_config_file,
    parse_cmake_defines,
    parse_env_vars,
    run_batch_request,
    run_build_request,
    run_kconfig_request,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")


def _completed(
    stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"], returncode=0, stdout=stdout, stderr=stderr
    )


def _fake_project(project_root: Path) -> object:
    from dawnpy.dawn.project import Project

    return Project(
        project_root=project_root,
        dawn_root=project_root,
        nuttx_dir=project_root / "external" / "nuttx",
        nuttx_apps_dir=project_root / "external" / "apps",
        is_oot=False,
        dawnrc=DawnRC(path=None, data={}),
    )


def _fake_dawn_root(root: Path) -> Path:
    (root / "boards").mkdir(parents=True, exist_ok=True)
    (root / "external" / "nuttx").mkdir(parents=True, exist_ok=True)
    (root / "external" / "apps").mkdir(parents=True, exist_ok=True)
    (root / "dawn").mkdir(exist_ok=True)
    (root / "Documentation").mkdir(exist_ok=True)
    return root


__all__ = [name for name in globals() if not name.startswith("__")]
