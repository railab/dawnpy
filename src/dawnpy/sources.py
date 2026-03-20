# tools/dawnpy/src/dawnpy/sources.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared error types for Dawn source-tree availability.

Dawnpy ships independently of the Dawn C++ tree. Most commands need a
checked-out Dawn repository (and NuttX siblings under ``external/``); only
``dawnpy init``, ``dawnpy project list``, and a few standalone helpers run
without one.

Both gating points -- :class:`dawnpy.dawn.project.Project.resolve` and
:func:`dawnpy.headerdefs._paths._require_repo_root` -- raise
:class:`DawnSourcesMissing` when no checkout can be located so users get the
same actionable hint regardless of which command they ran.

:class:`HeaderDefsError` lives here so :class:`DawnSourcesMissing` can
multi-inherit from both it and :class:`click.ClickException` without an
import cycle.
"""

import click

_HINT = (
    "Run `dawnpy init <path>` to bootstrap a workspace, "
    "or set DAWN_ROOT / pass --dawn-root to point at an existing checkout."
)


class HeaderDefsError(RuntimeError):
    """Raised when header-backed constant loading fails."""


class DawnSourcesMissing(click.ClickException, HeaderDefsError):
    """Raised when no Dawn source checkout can be located.

    Inherits from both :class:`click.ClickException` (so click renders the
    friendly message and exits cleanly) and :class:`HeaderDefsError` (so
    bundled-header fallback paths like
    :meth:`dawnpy.objectid.CObjectId._load_from_headers` keep catching it
    and falling back to bundled YAML).
    """

    def __init__(self, detail: str) -> None:
        """Build the error from ``detail``; hint is appended automatically."""
        super().__init__(f"{detail}\n{_HINT}")
