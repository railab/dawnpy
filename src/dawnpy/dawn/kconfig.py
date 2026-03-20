# tools/dawnpy/src/dawnpy/dawn/kconfig.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Kconfig helpers."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from dawnpy.dawn.output import print_error, print_verbose
from dawnpy.dawn.proc import run_capture

if TYPE_CHECKING:
    from pathlib import Path

    from dawnpy.dawn.project import Project


def _require_tool(name: str, message: str) -> bool:
    if not shutil.which(name):
        print_error(message)
        return False
    return True


def _run_kconfig_command(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    verbose: bool,
    error_message: str,
) -> bool:
    result = run_capture(
        cmd,
        cwd=cwd,
        env=env,
        error_message=error_message,
        echo_stdout_on_success=verbose,
    )
    return result is not None


def build_kconfig_env(build_dir: Path, project: Project) -> dict[str, str]:
    """Build Kconfig environment variables for setconfig/olddefconfig."""
    # Ensure all paths are absolute
    build_dir = build_dir.resolve()

    apps_dir = project.nuttx_apps_dir.resolve()
    apps_bindir = (build_dir / apps_dir.name).resolve()
    if not apps_bindir.exists():
        apps_bindir.mkdir(parents=True, exist_ok=True)
    boards_common = (project.dawn_root / "boards" / "common").resolve()
    nuttx_dir = project.nuttx_dir.resolve()

    env = os.environ.copy()
    env.update(
        {
            "KCONFIG_CONFIG": str(build_dir / ".config"),
            "SRCTREE": str(nuttx_dir),
            "srctree": str(nuttx_dir),
            "OBJTREE": str(build_dir),
            "objtree": str(build_dir),
            "EXTERNALDIR": "dummy",
            "APPSDIR": str(apps_dir),
            "APPSBINDIR": str(apps_bindir),
            "BINDIR": str(build_dir),
            "bindir": str(build_dir),
            "DRIVERS_PLATFORM_DIR": "dummy",
            "DAWN_BOARDS_COMMON": str(boards_common),
        }
    )
    return env


def set_kconfig_value(
    build_dir: Path,
    project: Project,
    symbol: str,
    value: str,
    verbose: bool = False,
) -> bool:
    """Set a single Kconfig value in the build directory."""
    config_path = build_dir / ".config"
    if not config_path.is_file():
        print_error(f"Kconfig file not found: {config_path}")
        return False

    if not _require_tool(
        "setconfig", "setconfig not found in PATH (kconfiglib required)"
    ):
        return False

    if not _require_tool(
        "olddefconfig", "olddefconfig not found in PATH (kconfiglib required)"
    ):
        return False

    nuttx_dir = project.nuttx_dir
    kconfig_path = nuttx_dir / "Kconfig"
    env = build_kconfig_env(build_dir, project)

    symbol_name = symbol
    if symbol_name.startswith("CONFIG_"):
        symbol_name = symbol_name[len("CONFIG_") :]

    cmd = [
        "setconfig",
        f"{symbol_name}={value}",
        "--kconfig",
        str(kconfig_path),
    ]
    print_verbose(f"Kconfig set: {' '.join(cmd)}", verbose)

    if not _run_kconfig_command(
        cmd,
        build_dir,
        env,
        verbose,
        f"Failed to set Kconfig value: {symbol}={value}",
    ):
        return False

    return _run_kconfig_command(
        ["olddefconfig"],
        build_dir,
        env,
        verbose,
        "Failed to refresh Kconfig with olddefconfig",
    )


def set_kconfig_values(  # pragma: no cover
    build_dir: Path,
    project: Project,
    overrides: tuple[str, ...],
    verbose: bool = False,
) -> bool:
    """Set multiple Kconfig values in the build directory."""
    if not overrides:
        return True

    config_path = build_dir / ".config"
    if not config_path.is_file():
        print_error(f"Kconfig file not found: {config_path}")
        return False

    if not _require_tool(
        "setconfig", "setconfig not found in PATH (kconfiglib required)"
    ):
        return False

    if not _require_tool(
        "olddefconfig", "olddefconfig not found in PATH (kconfiglib required)"
    ):
        return False

    nuttx_dir = project.nuttx_dir
    kconfig_path = nuttx_dir / "Kconfig"
    env = build_kconfig_env(build_dir, project)

    for override in overrides:
        if "=" not in override:
            print_error(f"Invalid Kconfig override format: {override}")
            return False

        symbol, value = override.split("=", 1)
        symbol_name = symbol.strip()
        if symbol_name.startswith("CONFIG_"):
            symbol_name = symbol_name[len("CONFIG_") :]

        cmd = [
            "setconfig",
            f"{symbol_name}={value.strip()}",
            "--kconfig",
            str(kconfig_path),
        ]
        print_verbose(f"Kconfig set: {' '.join(cmd)}", verbose)

        if not _run_kconfig_command(
            cmd,
            build_dir,
            env,
            verbose,
            f"Failed to set Kconfig value: {override}",
        ):
            return False

    return _run_kconfig_command(
        ["olddefconfig"],
        build_dir,
        env,
        verbose,
        "Failed to refresh Kconfig with olddefconfig",
    )
