# tools/dawnpy/src/dawnpy/dawn/cmake.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""CMake configuration and build helpers."""

import os
import subprocess
from pathlib import Path

import click

from dawnpy.dawn.output import (
    print_error,
    print_info,
    print_success,
    print_verbose,
)
from dawnpy.dawn.proc import run_capture


def _cmake_env(env_vars: dict[str, str] | None) -> dict[str, str] | None:
    if not env_vars:
        return None
    env = os.environ.copy()
    env.update(env_vars)
    return env


def _print_run_output(
    result: subprocess.CompletedProcess[str], verbose: bool
) -> None:
    if verbose:
        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)
        return

    output_lines = (result.stdout + result.stderr).split("\n")
    errors_and_warnings = [
        line
        for line in output_lines
        if "error:" in line.lower()
        or "warning:" in line.lower()
        or "cmake warning" in line.lower()
        or "cmake error" in line.lower()
    ]

    if errors_and_warnings:
        click.echo()
        for line in errors_and_warnings:
            click.echo(line)


def _print_run_error(message: str, err: subprocess.CalledProcessError) -> None:
    print_error(message)
    if err.stderr:
        click.echo(err.stderr, err=True)
    if err.stdout:
        output_lines = err.stdout.split("\n")
        errors = [line for line in output_lines if "error:" in line.lower()]
        if errors:
            for line in errors:
                click.echo(line, err=True)


def _resolve_direct_config_path(  # pragma: no cover
    boards_search_root: Path, boards_dir: Path, confpath: str
) -> Path | None:
    """Resolve ``confpath`` against absolute, cwd, and project-root anchors."""
    candidates = [
        Path(confpath),
        Path.cwd() / confpath,
        boards_search_root / confpath,
    ]
    for candidate in candidates:
        try:
            abs_path = candidate.resolve()
        except Exception:
            continue
        if not abs_path.is_dir() or not (abs_path / "defconfig").is_file():
            continue
        if str(abs_path).startswith(str(boards_dir)):
            return abs_path
    return None


def _resolve_shorthand_config_path(  # pragma: no cover
    boards_dir: Path, confpath: str
) -> Path | None:
    """Resolve ``<board>/<config>`` shorthand to a path under ``boards/``."""
    if "/" not in confpath:
        return None
    parts = confpath.split("/")
    if len(parts) != 2:
        return None
    board, config = parts
    for match in boards_dir.glob(f"**/{board}/configs/{config}"):
        if (match / "defconfig").is_file():
            return match
    return None


def _find_config_in_boards(  # pragma: no cover
    boards_search_root: Path, confpath: str
) -> Path | None:
    """Search for configuration ONLY in the project's boards directory.

    :param boards_search_root: The project root whose ``boards/`` to search
        (out-of-tree project root for OOT builds, upstream Dawn root
        otherwise).
    :param confpath: User-provided config path or ``<board>/<config>``
        shorthand.
    """
    boards_dir = (boards_search_root / "boards").resolve()
    if not boards_dir.is_dir():
        return None

    direct = _resolve_direct_config_path(
        boards_search_root, boards_dir, confpath
    )
    if direct is not None:
        return direct

    return _resolve_shorthand_config_path(boards_dir, confpath)


def _log_configure_cmake_invocation(  # pragma: no cover
    cmd: list[str],
    *,
    nuttx_dir: Path,
    build_dir: Path,
    confpath: str,
    generator: str,
    env_vars: dict[str, str] | None,
    cmake_flags: list[str] | None,
    verbose: bool,
) -> None:
    print_verbose(f"CMake command: {' '.join(cmd)}", verbose)
    print_verbose(f"Source directory: {nuttx_dir}", verbose)
    print_verbose(f"Build directory: {build_dir}", verbose)
    print_verbose(f"Board config: {confpath}", verbose)
    print_verbose(f"Generator: {generator}", verbose)
    if env_vars:
        print_verbose(f"Environment variables: {env_vars}", verbose)
    if cmake_flags:
        print_verbose(
            f"Additional CMake flags: {' '.join(cmake_flags)}", verbose
        )


def configure_cmake(  # pragma: no cover
    build_dir: Path,
    confpath: str,
    project_root: Path,
    generator: str = "Ninja",
    env_vars: dict[str, str] | None = None,
    cmake_flags: list[str] | None = None,
    verbose: bool = False,
    dawn_root: Path | None = None,
    boards_search_root: Path | None = None,
    nuttx_dir: Path | None = None,
) -> bool:
    """Configure project with CMake.

    :param project_root: The project root used as cmake working directory.
    :param dawn_root: Upstream Dawn repo (where ``external/nuttx`` lives).
        Defaults to ``project_root``.
    :param boards_search_root: Project root whose ``boards/`` to search for
        the requested config. Defaults to ``project_root``.
    """
    print_info(f"Configuring CMake build in '{build_dir}'...")

    if dawn_root is None:
        dawn_root = project_root
    if boards_search_root is None:
        boards_search_root = project_root
    if nuttx_dir is None:
        nuttx_dir = dawn_root / "external" / "nuttx"

    if not nuttx_dir.is_dir():
        print_error(f"NuttX directory not found at {nuttx_dir}")
        print_info("Please run 'init' command first to setup repositories")
        return False

    local_confpath = _find_config_in_boards(boards_search_root, confpath)
    if not local_confpath:
        print_error(
            f"Configuration '{confpath}' not found in local boards/ "
            "directory."
        )
        print_info("dawnpy build only supports local configurations.")
        return False

    confpath_rel = os.path.relpath(local_confpath, nuttx_dir)
    print_verbose(f"Using local config: {confpath} -> {confpath_rel}", verbose)

    cmd = [
        "cmake",
        "-B",
        str(build_dir),
        "-S",
        str(nuttx_dir),
        f"-DBOARD_CONFIG={confpath_rel}",
        "-DCMAKE_SUPPRESS_DEVELOPER_WARNINGS=ON",
        f"-G{generator}",
    ]
    if cmake_flags:
        cmd.extend(cmake_flags)

    _log_configure_cmake_invocation(
        cmd,
        nuttx_dir=nuttx_dir,
        build_dir=build_dir,
        confpath=confpath,
        generator=generator,
        env_vars=env_vars,
        cmake_flags=cmake_flags,
        verbose=verbose,
    )

    result = run_capture(
        cmd,
        cwd=dawn_root,
        env=_cmake_env(env_vars),
        error_handler=lambda e: _print_run_error(
            f"CMake configuration failed: {e}", e
        ),
    )
    if result is None:
        return False
    _print_run_output(result, verbose)
    print_success(f"CMake configuration successful in '{build_dir}'")
    return True


def build_cmake(
    build_dir: Path,
    project_root: Path,
    jobs: int | None = None,
    verbose: bool = False,
) -> bool:
    """Build project with CMake."""
    print_info(f"Building project in '{build_dir}'...")

    if not build_dir.is_dir():
        print_error(f"Build directory not found: {build_dir}")
        print_info("Please configure the build directory first")
        return False

    cmd = ["cmake", "--build", str(build_dir)]

    if jobs:
        cmd.extend(["-j", str(jobs)])

    if verbose:
        cmd.append("--verbose")

    print_verbose(f"Build command: {' '.join(cmd)}", verbose)
    print_verbose(f"Build directory: {build_dir}", verbose)
    if jobs:
        print_verbose(f"Parallel jobs: {jobs}", verbose)

    result = run_capture(
        cmd,
        cwd=project_root,
        error_handler=lambda e: _print_run_error(f"Build failed: {e}", e),
    )
    if result is None:
        return False
    _print_run_output(result, verbose)
    print_success(f"Build successful in '{build_dir}'")
    return True
