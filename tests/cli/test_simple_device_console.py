# tools/dawnpy/tests/test_simple_device_console.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for shared simple device console helpers."""

from dawnpy.cli.simple_device_console import SimpleDeviceConsole


class _FakeClient:
    def __init__(self) -> None:
        self.calls = []
        self.discovery_ok = True

    def discovery(self) -> None:
        self.calls.append(("discovery",))

    def list_discovered_features(self) -> None:
        self.calls.append(("list",))

    def perform_discovery(self) -> bool:
        self.calls.append(("perform_discovery",))
        return self.discovery_ok

    def parse_object_ids(self, args: str):
        self.calls.append(("parse_object_ids", args))
        if not args:
            return None
        return [int(part.strip(), 16) for part in args.split(",")]

    def parse_object_id(self, arg: str):
        self.calls.append(("parse_object_id", arg))
        try:
            return int(arg, 16)
        except ValueError:
            return None

    def read_io_value(self, objid: int) -> None:
        self.calls.append(("read_io_value", objid))

    def read_seekable_io(self, objid: int) -> None:
        self.calls.append(("read_seekable_io", objid))

    def parse_hex_bytes(self, value: str):
        self.calls.append(("parse_hex_bytes", value))
        if value == "0xAA":
            return b"\xaa"
        if value == "0x":
            return b""
        return None

    def write_io_raw(self, objid: int, data: bytes) -> None:
        self.calls.append(("write_io_raw", objid, data))

    def write_io_value(self, objid: int, value: int) -> None:
        self.calls.append(("write_io_value", objid, value))

    def monitoring(self, **kwargs) -> None:
        self.calls.append(("monitoring", kwargs))


class _TestConsole(SimpleDeviceConsole):
    def __init__(self) -> None:
        super().__init__(prompt="> ", history_file=".test_history")
        self.client = _FakeClient()
        self.exited = False
        self.help_shown = False

    def show_menu(self) -> None:
        self.help_shown = True

    def _on_exit(self) -> None:
        self.exited = True


class _RawConsole(_TestConsole):
    allow_empty_raw_bytes = True


def test_handle_command_dispatches_shared_actions(capsys):
    """handle_command should route common commands through shared handlers."""
    console = _TestConsole()

    console.handle_command("d")
    console.handle_command("l")
    console.handle_command("r 0x1,0x2")
    console.handle_command("s 0x3 extra")
    console.handle_command("w 0x4 0xAA")
    console.handle_command("w 0x5 7")
    console.handle_command("m 0x6,0x7")
    console.handle_command("h")
    console.handle_command("zzz")
    console.handle_command("q")

    assert ("discovery",) in console.client.calls
    assert ("list",) in console.client.calls
    assert ("read_io_value", 0x1) in console.client.calls
    assert ("read_io_value", 0x2) in console.client.calls
    assert ("read_seekable_io", 0x3) in console.client.calls
    assert ("write_io_raw", 0x4, b"\xaa") in console.client.calls
    assert ("write_io_value", 0x5, 7) in console.client.calls
    assert (
        "monitoring",
        {"objids": [0x6, 0x7]},
    ) in console.client.calls
    assert console.help_shown
    assert console.exited

    captured = capsys.readouterr()
    assert "Unknown command: zzz. Type 'h' for help." in captured.out


def test_shared_commands_report_usage_errors(capsys):
    """Shared commands should print consistent usage errors."""
    console = _TestConsole()

    assert console.client.parse_object_ids("") is None
    assert console.client.parse_object_id("nope") is None
    console.cmd_read("")
    console.cmd_seek("")
    console.cmd_write("")
    console.cmd_write("0x1 nope")

    captured = capsys.readouterr()
    assert "ERROR: Usage: r <objid> [,<objid>,...]" in captured.out
    assert "ERROR: Usage: s <objid>" in captured.out
    assert "ERROR: Usage: w <objid> <value>" in captured.out
    assert "ERROR: Invalid value" in captured.out


def test_cmd_write_can_allow_empty_raw_payloads():
    """allow_empty_raw_bytes should preserve empty raw writes."""
    console = _RawConsole()

    console.cmd_write("0x8 0x")

    assert ("write_io_raw", 0x8, b"") in console.client.calls


def test_start_runs_initial_discovery_and_reports_failure(capsys):
    """start should run discovery and stop the console on failure."""
    console = _TestConsole()
    console.start()

    failing = _TestConsole()
    failing.client.discovery_ok = False
    failing.error = print
    failing.start()

    assert ("perform_discovery",) in console.client.calls
    assert console.running
    assert ("perform_discovery",) in failing.client.calls
    assert not failing.running

    captured = capsys.readouterr()
    assert "Initial discovery failed." in captured.out
