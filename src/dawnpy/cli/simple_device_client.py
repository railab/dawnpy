#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/cli/simple_device_client.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared client logic for simple Dawn device transports."""

from typing import Any, cast

from dawnpy.descriptor.client import (
    find_descriptor_path,
    load_client_descriptor,
)
from dawnpy.descriptor.definitions.summary import ObjectIdResolver
from dawnpy.device.decode import decode_value


class SimpleDeviceClient:
    """Transport-agnostic helpers shared by simple Dawn clients."""

    DTYPE_SHIFT = 16
    DTYPE_MASK = 0xF
    DTYPE_BLOCK = 15

    connect_error = "ERROR: Failed to connect to device"
    ping_error = "ERROR: Failed to ping device"

    def __init__(self, descriptor_path: str | None = None) -> None:
        """Initialize shared client state."""
        self.client: Any = None
        self.debug = False
        self.discovered_ios: dict[int, dict[str, object]] = {}
        self.descriptor_path = descriptor_path
        self.connected = False

    def connect(self) -> bool:
        """Establish connection to device."""
        if not self.client.connect():
            print(self.connect_error)
            return False

        if not self.client.ping():
            print(self.ping_error)
            self.client.disconnect()
            return False

        self.connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from device."""
        if self.connected:
            self.client.disconnect()
            self.connected = False

    def perform_discovery(self) -> bool:
        """Perform initial device discovery and cache results."""
        if not self.connect():
            return False

        self.discovered_ios = self.discover_ios()
        return bool(self.discovered_ios)

    def discover_ios(self) -> dict[int, dict[str, object]]:
        """Discover IOs from descriptor or protocol runtime discovery."""
        if self.descriptor_path:
            return self._discover_descriptor_ios()
        return cast(
            dict[int, dict[str, object]], self.client.discover_all_ios()
        )

    def known_objids(self) -> list[int]:
        """Return object IDs from cached descriptor/discovery state."""
        if self.discovered_ios:
            return sorted(self.discovered_ios)
        if self.descriptor_path:
            return sorted(self._discover_descriptor_ios())
        return []

    def _discover_descriptor_ios(self) -> dict[int, dict[str, object]]:
        """Build an IO snapshot from a YAML descriptor."""
        descriptor = load_client_descriptor(
            find_descriptor_path(self.descriptor_path or "")
        )
        resolver = ObjectIdResolver()
        io_data: dict[int, dict[str, object]] = {}
        for io in descriptor.ios.values():
            objid = resolver.io_objid(io)
            if objid is None:
                continue

            info = self.client.get_io_info(objid) or {}
            dtype = info.get("dtype")
            if dtype is None:
                dtype = (objid >> self.DTYPE_SHIFT) & self.DTYPE_MASK

            entry: dict[str, object] = {
                "source": "descriptor",
                "io_id": io.io_id,
                "io_type_str": info.get("io_type_str", io.io_type),
                "io_type": info.get("io_type"),
                "dimension": info.get("dimension", "unknown"),
                "dtype": dtype,
                "dtype_name": io.dtype,
                "rw": io.rw,
                "tags": io.tags,
            }

            data = self.client.read_io(objid)
            if data is not None:
                entry["data"] = data.hex()
                entry["data_bytes"] = list(data)

            io_data[objid] = entry

        self.discovered_ios = io_data
        return io_data

    def read_io_value(self, objid: int) -> None:
        """Read value from a specific IO object."""
        if not self.connected:
            print("ERROR: Not connected to device")
            return

        dtype = (objid >> self.DTYPE_SHIFT) & self.DTYPE_MASK
        if dtype == self.DTYPE_BLOCK:
            self.read_seekable_io(objid)
            return

        info = self.client.get_io_info(objid)
        if not info:
            print("ERROR: Failed to get IO info")
            return

        data = self.client.read_io(objid)
        if data is not None:
            self.format_value(objid, data, info["dtype"])
        else:
            print("ERROR: Failed to read data")

    def write_io_value(self, objid: int, value: int) -> None:
        """Write value to a specific IO object."""
        if not self.connected:
            print("ERROR: Not connected to device")
            return

        info = self.client.get_io_info(objid)
        if not info:
            print("ERROR: Failed to get IO info")
            return

        if info["io_type"] == self.client.IO_TYPE_READ_ONLY:
            print("ERROR: IO is read-only, cannot write")
            return

        data = self.client.pack_data_by_dtype(info["dtype"], value)
        if data is None:
            print(f"ERROR: Could not pack data for dtype {info['dtype']}")
            return
        if self.client.write_io(objid, data):
            read_back = self.client.read_io(objid)
            if read_back is not None:
                self.format_value(objid, read_back, info["dtype"])
        else:
            print("ERROR: Write failed")

    def write_io_raw(self, objid: int, data: bytes) -> None:
        """Write raw bytes to a specific IO object."""
        if not self.connected:
            print("ERROR: Not connected to device")
            return

        info = self.client.get_io_info(objid)
        if not info:
            print("ERROR: Failed to get IO info")
            return

        if info["io_type"] == self.client.IO_TYPE_READ_ONLY:
            print("ERROR: IO is read-only, cannot write")
            return

        if not self.client.write_io(objid, data):
            print("ERROR: Write failed")
            return

        read_back = self.client.read_io(objid)
        if read_back is not None:
            self.format_value(objid, read_back, info["dtype"])

    def read_seekable_io(self, objid: int) -> None:
        """Read and print a seekable IO value as a hex/ascii dump."""
        if not self.connected:
            print("ERROR: Not connected to device")
            return

        data = self.client.read_io_seek(objid)
        if data is None:
            print(f"ERROR: Failed to read seekable IO 0x{objid:08X}")
            return

        print(f"IO 0x{objid:08X} seekable data ({len(data)} bytes):")
        self._print_hexdump(data)

    def parse_object_id(self, oid_str: str) -> int | None:
        """Parse a single hex object ID string."""
        try:
            return int(oid_str.strip(), 16)
        except ValueError:
            print(f"ERROR: Invalid object ID format: {oid_str}")
            return None

    def parse_object_ids(self, input_str: str) -> list[int] | None:
        """Parse a comma-separated list of hex object IDs."""
        try:
            objids = [int(s.strip(), 16) for s in input_str.split(",")]
            return objids if objids else None
        except ValueError:
            print("ERROR: Invalid object ID format. Use hex (0x40A10001)")
            return None

    @staticmethod
    def parse_hex_bytes(value: str) -> bytes | None:
        """Parse a hex string (with optional 0x prefix) into bytes."""
        value = value.strip()
        if value.startswith("0x") or value.startswith("0X"):
            value = value[2:]
        value = value.replace("_", "")
        if not value or len(value) % 2 != 0:
            return None
        try:
            return bytes.fromhex(value)
        except ValueError:
            return None

    def format_value(
        self, objid: int, data: bytes, dtype: int, include_objid: bool = True
    ) -> None:
        """Format and print a value using dtype when possible."""
        for line in decode_value(
            data,
            dtype,
            self.client.objid_decoder,
            include_objid=include_objid,
            objid=objid,
            debug=self.debug,
        ):
            print(line)

    @staticmethod
    def _print_hexdump(data: bytes) -> None:
        """Print an xxd-style hex/ascii dump."""
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(
                chr(b) if 0x20 <= b < 0x7F else "." for b in chunk
            )
            print(f"  {i:08x}: {hex_part:<47}  {ascii_part}")
