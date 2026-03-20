# tools/dawnpy/tests/test_console_base.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for ConsoleBase."""

from unittest.mock import Mock, patch

from dawnpy.cli.console_base import ConsoleBase


class _Console(ConsoleBase):
    def __init__(self):
        super().__init__(prompt="> ", history_file=".dawnpy_test_history")
        self.started = False
        self.stopped = False
        self.commands = []

    def show_menu(self) -> None:
        return None

    def handle_command(self, cmd_line: str) -> None:
        self.commands.append(cmd_line)
        if cmd_line == "q":
            self.running = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_console_base_run_and_history(tmp_path, monkeypatch):
    console = _Console()
    history_file = tmp_path / "hist"
    history_file.write_text("test")
    monkeypatch.setattr(console, "history_file", history_file)

    with (
        patch("dawnpy.cli.console_base.FileHistory") as file_history_cls,
        patch("dawnpy.cli.console_base.PromptSession") as prompt_session_cls,
    ):
        session = Mock()
        session.prompt.side_effect = ["hello", "q"]
        prompt_session_cls.return_value = session

        console.run()

        file_history_cls.assert_called_once_with(str(history_file))
        prompt_session_cls.assert_called_once_with(
            history=file_history_cls.return_value
        )

    assert console.started
    assert console.stopped
    assert console.commands == ["hello", "q"]


def test_console_base_default_dispatch(capsys):
    """Base dispatch should handle help, unknown commands, and quit."""

    calls = []

    class DispatchConsole(ConsoleBase):
        def __init__(self):
            super().__init__(prompt="> ", history_file=".hist")
            self.exited = False

        def commands_no_args(self):
            return {"a": lambda: calls.append("a")}

        def commands_with_args(self):
            return {"b": lambda args: calls.append(f"b:{args}")}

        def show_menu(self) -> None:
            calls.append("help")

        def on_exit_command(self) -> None:
            self.exited = True

    console = DispatchConsole()
    console.handle_command("a")
    console.handle_command("b value")
    console.handle_command("h")
    console.handle_command("missing")
    console.handle_command("q")

    assert calls == ["a", "b:value", "help"]
    assert not console.running
    assert console.exited
    assert (
        "Unknown command: missing. Type 'h' for help."
        in capsys.readouterr().out
    )
