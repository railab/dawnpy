# tools/dawnpy/src/dawnpy/cli/console_base.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared interactive console utilities for dawnpy."""

from collections.abc import Callable, Mapping
from pathlib import Path

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from dawnpy.cli.console_dispatch import dispatch_command


class ConsoleBase:  # pragma: no cover
    """Base class for interactive consoles."""

    def __init__(self, prompt: str, history_file: str) -> None:
        """Initialize console settings."""
        self.prompt = prompt
        self.history_file = Path.home() / history_file
        self.running = True
        self._session: PromptSession[str] | None = None

    def setup_history(self) -> None:
        """Set up prompt_toolkit history and session."""
        history = FileHistory(str(self.history_file))
        self._session = PromptSession(history=history)

    def print_menu(self, title: str, lines: list[str]) -> None:
        """Print a boxed menu with aligned lines."""
        if not lines:
            lines = [""]
        width = max(len(title), max(len(line) for line in lines)) + 4
        border = "+" + "-" * (width - 2) + "+"
        print()
        print(border)
        print(f"| {title.ljust(width - 4)} |")
        print(border)
        for line in lines:
            print(f"| {line.ljust(width - 4)} |")
        print(border)

    def info(self, message: str) -> None:
        """Print informational message."""
        print_formatted_text(HTML(f"<ansicyan>{message}</ansicyan>"))

    def ok(self, message: str) -> None:
        """Print success message."""
        print_formatted_text(HTML(f"<ansigreen>{message}</ansigreen>"))

    def warn(self, message: str) -> None:
        """Print warning message."""
        print_formatted_text(HTML(f"<ansiyellow>{message}</ansiyellow>"))

    def error(self, message: str) -> None:
        """Print error message."""
        print_formatted_text(HTML(f"<ansired>{message}</ansired>"))

    def commands_no_args(self) -> Mapping[str, Callable[[], None]]:
        """Return console commands that do not accept arguments."""
        return {}

    def commands_with_args(self) -> Mapping[str, Callable[[str], None]]:
        """Return console commands that accept an argument string."""
        return {}

    def unknown_command(self, cmd: str) -> None:
        """Render a normalized unknown-command message."""
        print(f"Unknown command: {cmd}. Type 'h' for help.")

    def on_exit_command(self) -> None:
        """Run optional logic when the quit command is received."""

    def show_menu(self) -> None:
        """Show console menu."""
        raise NotImplementedError

    def handle_command(self, cmd_line: str) -> None:
        """Handle a single command line."""
        self.running = dispatch_command(
            cmd_line,
            commands_no_args=self.commands_no_args(),
            commands_with_args=self.commands_with_args(),
            quit_cmd="q",
            help_cmd="h",
            help_func=self.show_menu,
            unknown_func=self.unknown_command,
        )
        if not self.running:
            self.on_exit_command()

    def start(self) -> None:
        """Run optional setup before entering loop."""

    def stop(self) -> None:
        """Run optional cleanup after leaving loop."""

    def run(self) -> None:
        """Run the console loop."""
        self.setup_history()
        self.start()
        self.show_menu()
        while self.running:
            try:
                session = self._session
                if session is None:
                    self.setup_history()
                    session = self._session
                if session is None:
                    raise RuntimeError("Prompt session is not initialized")
                cmd = session.prompt(self.prompt).strip()
                if cmd:
                    self.handle_command(cmd)
            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
                self.running = False
            except EOFError:
                print("\n\nExiting.")
                self.running = False
            except Exception as exc:
                print(f"Error: {exc}")
        self.stop()
