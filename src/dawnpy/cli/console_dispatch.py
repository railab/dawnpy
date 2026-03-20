# tools/dawnpy/src/dawnpy/cli/console_dispatch.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared command dispatch helper for interactive consoles."""

from collections.abc import Callable, Mapping


def dispatch_command(
    cmd_line: str,
    *,
    commands_no_args: Mapping[str, Callable[[], None]],
    commands_with_args: Mapping[str, Callable[[str], None]],
    quit_cmd: str = "q",
    help_cmd: str = "h",
    help_func: Callable[[], None] | None = None,
    unknown_func: Callable[[str], None] | None = None,
    unknown_fmt: str = "Unknown command: {cmd}. Type 'h' for help.",
) -> bool:
    """Dispatch a command line to matching handlers."""
    cmd_line = cmd_line.strip()
    if not cmd_line:
        return True

    parts = cmd_line.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == quit_cmd:
        return False
    if cmd == help_cmd and help_func:
        help_func()
        return True
    if cmd in commands_no_args:
        commands_no_args[cmd]()
        return True
    if cmd in commands_with_args:
        commands_with_args[cmd](args)
        return True

    if unknown_func:
        unknown_func(cmd)
    else:
        print(unknown_fmt.format(cmd=cmd))
    return True
