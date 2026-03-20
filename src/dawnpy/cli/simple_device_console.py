#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/cli/simple_device_console.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared console helpers for simple device transports."""

from collections.abc import Callable, Mapping
from typing import Any

from dawnpy.cli.console_base import ConsoleBase


class SimpleDeviceConsole(ConsoleBase):  # pragma: no cover
    """Shared command handling for transport-backed device consoles."""

    read_usage = "ERROR: Usage: r <objid> [,<objid>,...]"
    seek_usage = "ERROR: Usage: s <objid>"
    write_usage = "ERROR: Usage: w <objid> <value>"
    invalid_value_error = "ERROR: Invalid value"
    initial_discovery_error = "Initial discovery failed."
    allow_empty_raw_bytes = False

    client: Any

    def commands_no_args(self) -> Mapping[str, Callable[[], None]]:
        """Return supported commands that do not take arguments."""
        return {
            "d": self.client.discovery,
            "devices": self.client.list_discovered_features,
            "l": self.client.list_discovered_features,
        }

    def commands_with_args(
        self,
    ) -> Mapping[str, Callable[[str], None]]:
        """Return supported commands that require arguments."""
        return {
            "i": self.cmd_info,
            "r": self.cmd_read,
            "s": self.cmd_seek,
            "w": self.cmd_write,
            "m": self.cmd_monitoring,
        }

    def _console_header(self) -> str:
        """Return the transport-specific startup banner."""
        return ""

    def _on_exit(self) -> None:
        """Run optional cleanup messaging after quit."""

    def _monitoring_kwargs(self) -> dict[str, Any]:
        """Return transport-specific monitoring defaults."""
        return {}

    def on_exit_command(self) -> None:
        """Run optional cleanup messaging after quit."""
        self._on_exit()

    def cmd_info(self, args: str) -> None:
        """Show details for one or more object IDs."""
        if not args:
            print("ERROR: Usage: i <objid> [,<objid>,...]")
            return
        objids = self.client.parse_object_ids(args)
        if objids:
            for objid in objids:
                self.client.read_io_value(objid)

    def cmd_read(self, args: str) -> None:
        """Read one or more object IDs."""
        if not args:
            print(self.read_usage)
            return

        objids = self.client.parse_object_ids(args)
        if objids:
            for objid in objids:
                self.client.read_io_value(objid)

    def cmd_seek(self, args: str) -> None:
        """Read a seekable IO object by ID."""
        if not args:
            print(self.seek_usage)
            return

        objid = self.client.parse_object_id(args.split()[0])
        if objid is not None:
            self.client.read_seekable_io(objid)

    def cmd_write(self, args: str) -> None:
        """Write raw bytes or an integer value to an IO object."""
        parts = args.split()
        if len(parts) < 2:
            print(self.write_usage)
            return

        objid = self.client.parse_object_id(parts[0])
        if objid is None:
            return

        raw = self.client.parse_hex_bytes(parts[1])
        if raw is not None and (raw or self.allow_empty_raw_bytes):
            self.client.write_io_raw(objid, raw)
            return

        try:
            self.client.write_io_value(objid, int(parts[1]))
        except ValueError:
            print(self.invalid_value_error)

    def cmd_monitoring(self, args: str) -> None:
        """Start continuous monitoring for all or selected object IDs."""
        objids = self.client.parse_object_ids(args) if args else None
        self.client.monitoring(objids=objids, **self._monitoring_kwargs())

    def start(self) -> None:
        """Run initial discovery before entering the command loop."""
        print(self._console_header())
        if not self.client.perform_discovery():
            self.error(self.initial_discovery_error)
            self.running = False
