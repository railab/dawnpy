# tools/dawnpy/src/dawnpy/dawn/output.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Console output helpers for Dawn tooling."""

import click
from rich.console import Console

_render = Console(
    force_terminal=True,
    color_system="standard",
    legacy_windows=False,
    highlight=False,
)


def colored(text: str, color: str) -> str:
    """Wrap ``text`` in ANSI escape codes for the given Rich color name."""
    with _render.capture() as cap:
        _render.print(f"[{color}]{text}[/{color}]", end="")
    return cap.get()


def print_header(title: str) -> None:
    """Print header."""
    bar = "========================================"
    click.echo(colored(bar, "blue"))
    click.echo(colored(f"  {title}", "blue"))
    click.echo(colored(bar, "blue"))
    click.echo()


def print_success(message: str) -> None:
    """Print success message."""
    click.echo(f"{colored('[OK]', 'green')} {message}")


def print_error(message: str) -> None:
    """Print error message."""
    click.echo(f"{colored('[ERR] ERROR:', 'red')} {message}", err=True)


def print_warning(message: str) -> None:
    """Print warning message."""
    click.echo(f"{colored('[WARN] WARNING:', 'yellow')} {message}")


def print_info(message: str) -> None:
    """Print info message."""
    click.echo(f"{colored('[INFO]', 'blue')} {message}")


def print_verbose(message: str, verbose: bool) -> None:
    """Print verbose message if verbose mode is enabled."""
    if verbose:
        click.echo(f"{colored('  ->', 'blue')} {message}")
