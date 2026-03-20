# tools/dawnpy/src/dawnpy/dawn/proc.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Subprocess helpers with consistent error handling.

Centralizes the try/except boilerplate around :func:`subprocess.run` so
each caller can focus on what's specific (command, env, error message)
instead of repeating the same plumbing.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import click

from dawnpy.dawn.output import print_error


def run_capture(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    error_message: str | None = None,
    error_handler: Callable[[subprocess.CalledProcessError], None] | None = (
        None
    ),
    echo_stdout_on_success: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    """Run a captured command and return the result on success.

    :param cmd: Command argv list.
    :param cwd: Working directory.
    :param env: Full environment mapping (e.g. from ``os.environ.copy()``).
    :param error_message: Default ``print_error`` text on non-zero exit.
        Captured stderr is echoed after it. Ignored if ``error_handler``
        is provided.
    :param error_handler: Custom callback receiving the
        :class:`CalledProcessError`. Lets callers do tool-specific
        formatting (e.g. scanning stdout for compiler errors).
    :param echo_stdout_on_success: When ``True``, echo stdout to the
        console after a successful run (verbose mode).
    :return: ``CompletedProcess`` on success, ``None`` on failure.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if error_handler is not None:
            error_handler(exc)
        elif error_message is not None:
            print_error(error_message)
            if exc.stderr:
                click.echo(exc.stderr, err=True)
        return None

    if echo_stdout_on_success and result.stdout:
        click.echo(result.stdout)
    return result


def run_capture_echo(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    error_message: str = "Command failed",
) -> bool:
    """Run a captured command, always echoing stdout/stderr.

    Used by pipeline steps where the user should see tool output
    regardless of success or failure (e.g. format check, tox).
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print_error(f"{error_message}: {exc}")
        return False

    if result.stdout:
        click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)

    if result.returncode != 0:
        print_error(f"{error_message} (exit code {result.returncode})")
        return False
    return True


def run_stream(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    error_message: str = "Command failed",
) -> bool:
    """Run a command without capturing output. Return ``True`` on success."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
        )
    except Exception as exc:
        print_error(f"{error_message}: {exc}")
        return False
    if result.returncode != 0:
        print_error(error_message)
        return False
    return True
