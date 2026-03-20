# tools/dawnpy/tests/test_console_dispatch.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for console command dispatch helper."""

from dawnpy.cli.console_dispatch import dispatch_command


def test_dispatch_command_basic():
    calls = []

    def no_args():
        calls.append("no")

    def with_args(arg: str):
        calls.append(f"arg:{arg}")

    def help_func():
        calls.append("help")

    commands_no_args = {"a": no_args}
    commands_with_args = {"b": with_args}

    assert dispatch_command(
        "a",
        commands_no_args=commands_no_args,
        commands_with_args=commands_with_args,
        help_func=help_func,
    )
    assert dispatch_command(
        "b value",
        commands_no_args=commands_no_args,
        commands_with_args=commands_with_args,
        help_func=help_func,
    )
    assert dispatch_command(
        "h",
        commands_no_args=commands_no_args,
        commands_with_args=commands_with_args,
        help_func=help_func,
    )
    assert not dispatch_command(
        "q",
        commands_no_args=commands_no_args,
        commands_with_args=commands_with_args,
        help_func=help_func,
    )

    assert calls == ["no", "arg:value", "help"]


def test_dispatch_command_unknown(capsys):
    assert dispatch_command(
        "x",
        commands_no_args={},
        commands_with_args={},
        help_func=None,
    )
    out = capsys.readouterr().out
    assert "Unknown command: x" in out


def test_dispatch_command_empty():
    assert dispatch_command(
        "   ",
        commands_no_args={},
        commands_with_args={},
        help_func=None,
    )


def test_dispatch_command_unknown_func():
    calls = []

    def unknown(cmd: str) -> None:
        calls.append(cmd)

    assert dispatch_command(
        "x",
        commands_no_args={},
        commands_with_args={},
        help_func=None,
        unknown_func=unknown,
    )
    assert calls == ["x"]
