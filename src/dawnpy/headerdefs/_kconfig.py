# tools/dawnpy/src/dawnpy/headerdefs/_kconfig.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Kconfig choice extraction from the Dawn source tree."""

import re
from functools import lru_cache

from ._paths import _require_repo_root

KconfigChoice = tuple[str, tuple[str, ...], tuple[str, ...]]


def _scan_choices(text: str) -> list[KconfigChoice]:
    """Return (default, members, guards) per choice block in one Kconfig."""
    entries: list[KconfigChoice] = []
    guards: list[str] = []
    in_choice = False
    default = ""
    members: list[str] = []
    choice_guards: tuple[str, ...] = ()

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("endchoice"):
            if in_choice and default:
                entries.append((default, tuple(members), choice_guards))
            in_choice = False
        elif line.startswith("choice"):
            in_choice, default, members = True, "", []
            choice_guards = tuple(guards)
        elif in_choice:
            found = re.match(r"default\s+(\w+)$", line)
            if found:
                default = f"CONFIG_{found.group(1)}"
            found = re.match(r"config\s+(\w+)", line)
            if found:
                members.append(f"CONFIG_{found.group(1)}")
        # Track `if SYMBOL` scope so an unreachable choice is ignored.
        elif line.startswith("if "):
            found = re.match(r"if\s+([A-Z0-9_]+)$", line)
            guards.append(f"CONFIG_{found.group(1)}" if found else "")
        elif line.startswith("endif") and guards:
            guards.pop()

    return entries


@lru_cache(maxsize=1)
def load_header_kconfig_choices() -> tuple[KconfigChoice, ...]:
    """Load Dawn Kconfig choices as (default, members, guards) tuples.

    A choice's default member is set by Kconfig itself and so never
    appears in a defconfig; descriptor validation needs it to avoid
    reporting that symbol as missing.
    """
    root = _require_repo_root()
    entries: list[KconfigChoice] = []
    for kconfig in sorted((root / "dawn").rglob("Kconfig")):
        try:
            text = kconfig.read_text(errors="ignore")
        except OSError:
            continue
        entries.extend(_scan_choices(text))
    return tuple(entries)


def implicit_choice_configs(
    enabled: set[str], choices: tuple[KconfigChoice, ...]
) -> set[str]:
    """Return choice defaults active for the given enabled config set.

    A default applies when every enclosing ``if`` guard is enabled and no
    sibling of the choice was selected explicitly.
    """
    implicit: set[str] = set()
    for default, members, guards in choices:
        if any(guard and guard not in enabled for guard in guards):
            continue
        if not set(members) & enabled:
            implicit.add(default)
    return implicit
