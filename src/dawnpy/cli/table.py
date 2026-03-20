# tools/dawnpy/src/dawnpy/cli/table.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Table rendering helpers for CLI output."""

from collections.abc import Callable
from io import StringIO

from rich.box import MARKDOWN
from rich.console import Console
from rich.table import Table


def print_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    printer: Callable[[str], None] | None = None,
    max_width: dict[str, int] | None = None,
) -> None:
    """Print a table with wrapped columns.

    Renders via :mod:`rich`. The Markdown-style box is used so output stays
    plain ASCII that pipes cleanly into logs and grep.
    """
    if printer is None:
        printer = print

    max_width = max_width or {}

    table = Table(box=MARKDOWN, show_lines=True, pad_edge=False)
    for header in headers:
        cap = max_width.get(header, 24)
        table.add_column(header, max_width=cap, overflow="fold")

    for row in rows:
        table.add_row(*row)

    buf = StringIO()
    Console(file=buf, width=240, force_terminal=False, no_color=True).print(
        table
    )
    for line in buf.getvalue().rstrip("\n").splitlines():
        printer(line)
