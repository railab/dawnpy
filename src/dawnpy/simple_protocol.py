#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/simple_protocol.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared helpers for simple Dawn transport protocols."""

import struct
from collections.abc import Callable
from typing import Any, cast

from dawnpy.objectid import ObjectIdDecoder

# Fallback values mirror the constants declared in
# dawn/include/dawn/proto/simplebase.hxx and are used only when the C++
# header is not reachable (e.g. wheel install outside the source tree).
# When the header is reachable, identical values are loaded from it via
# :func:`dawnpy.headerdefs.load_simple_proto_constants`, keeping a single
# source of truth in the C++ definitions.
_FALLBACK_CONSTANTS: dict[str, int] = {
    "FRAME_SYNC": 0xAA,
    "FRAME_MIN_LEN": 6,
    "FRAME_MAX_PAYLOAD": 1024,
    "CMD_PING": 0x00,
    "CMD_PONG": 0x01,
    "CMD_GET_IO": 0x10,
    "CMD_SET_IO": 0x11,
    "CMD_GET_IO_SEEK": 0x14,
    "CMD_SET_IO_SEEK": 0x15,
    "CMD_GET_CFG": 0x12,
    "CMD_SET_CFG": 0x13,
    "CMD_GET_INFO": 0x20,
    "CMD_LIST_IOS": 0x21,
    "CMD_SUBSCRIBE": 0x30,
    "CMD_UNSUBSCRIBE": 0x31,
    "CMD_NOTIFY": 0xF0,
    "CMD_ERROR": 0xFF,
    "STATUS_OK": 0x00,
    "STATUS_INVALID_CMD": 0x01,
    "STATUS_INVALID_OBJ": 0x02,
    "STATUS_INVALID_CFG": 0x03,
    "STATUS_READ_ONLY": 0x04,
    "STATUS_WRITE_ONLY": 0x05,
    "STATUS_INVALID_FORMAT": 0x06,
    "STATUS_ERROR": 0xFF,
    "IO_TYPE_READ_ONLY": 0x01,
    "IO_TYPE_WRITE_ONLY": 0x02,
    "IO_TYPE_READ_WRITE": 0x03,
}


def _load_proto_constants() -> dict[str, int]:
    """Load SimpleBase constants from C++ headers, fall back on failure."""
    try:
        from dawnpy.headerdefs import load_simple_proto_constants
    except ImportError:
        return _FALLBACK_CONSTANTS
    try:
        from_header = load_simple_proto_constants()
    except Exception:  # pragma: no cover
        return _FALLBACK_CONSTANTS
    merged = dict(_FALLBACK_CONSTANTS)
    merged.update(from_header)
    return merged


_PROTO_CONSTANTS = _load_proto_constants()


class SimpleProtocolBase:
    """Transport-agnostic helpers shared by simple Dawn protocols."""

    # Frame format constants
    FRAME_SYNC = _PROTO_CONSTANTS["FRAME_SYNC"]
    FRAME_MIN_LEN = _PROTO_CONSTANTS["FRAME_MIN_LEN"]
    FRAME_MAX_PAYLOAD = _PROTO_CONSTANTS["FRAME_MAX_PAYLOAD"]

    # Command IDs
    CMD_PING = _PROTO_CONSTANTS["CMD_PING"]
    CMD_PONG = _PROTO_CONSTANTS["CMD_PONG"]
    CMD_GET_IO = _PROTO_CONSTANTS["CMD_GET_IO"]
    CMD_SET_IO = _PROTO_CONSTANTS["CMD_SET_IO"]
    CMD_GET_IO_SEEK = _PROTO_CONSTANTS["CMD_GET_IO_SEEK"]
    CMD_SET_IO_SEEK = _PROTO_CONSTANTS["CMD_SET_IO_SEEK"]
    CMD_GET_CFG = _PROTO_CONSTANTS["CMD_GET_CFG"]
    CMD_SET_CFG = _PROTO_CONSTANTS["CMD_SET_CFG"]
    CMD_GET_INFO = _PROTO_CONSTANTS["CMD_GET_INFO"]
    CMD_LIST_IOS = _PROTO_CONSTANTS["CMD_LIST_IOS"]
    CMD_SUBSCRIBE = _PROTO_CONSTANTS["CMD_SUBSCRIBE"]
    CMD_UNSUBSCRIBE = _PROTO_CONSTANTS["CMD_UNSUBSCRIBE"]
    CMD_NOTIFY = _PROTO_CONSTANTS["CMD_NOTIFY"]
    CMD_ERROR = _PROTO_CONSTANTS["CMD_ERROR"]

    # Status codes
    STATUS_OK = _PROTO_CONSTANTS["STATUS_OK"]
    STATUS_INVALID_CMD = _PROTO_CONSTANTS["STATUS_INVALID_CMD"]
    STATUS_INVALID_OBJ = _PROTO_CONSTANTS["STATUS_INVALID_OBJ"]
    STATUS_INVALID_CFG = _PROTO_CONSTANTS["STATUS_INVALID_CFG"]
    STATUS_READ_ONLY = _PROTO_CONSTANTS["STATUS_READ_ONLY"]
    STATUS_WRITE_ONLY = _PROTO_CONSTANTS["STATUS_WRITE_ONLY"]
    STATUS_INVALID_FORMAT = _PROTO_CONSTANTS["STATUS_INVALID_FORMAT"]
    STATUS_ERROR = _PROTO_CONSTANTS["STATUS_ERROR"]

    # IO types
    IO_TYPE_READ_ONLY = _PROTO_CONSTANTS["IO_TYPE_READ_ONLY"]
    IO_TYPE_WRITE_ONLY = _PROTO_CONSTANTS["IO_TYPE_WRITE_ONLY"]
    IO_TYPE_READ_WRITE = _PROTO_CONSTANTS["IO_TYPE_READ_WRITE"]

    def __init__(self, *, verbose: bool = False) -> None:
        """Initialize shared protocol state."""
        self.verbose = verbose
        self.io_list: list[int] = []
        self.io_info: dict[int, dict[str, Any]] = {}

        try:
            self.objid_decoder = self._create_objid_decoder()
        except Exception as e:
            print(f"Warning: Could not initialize ObjectIdDecoder: {e}")
            self.objid_decoder = None

    def _create_objid_decoder(self) -> ObjectIdDecoder | None:
        """Create the object ID decoder for this protocol."""
        return ObjectIdDecoder()

    def decode_object_id(self, objid: int) -> str:
        """Decode an object ID and return a formatted string."""
        if not self.objid_decoder:
            return f"0x{objid:08X}"

        try:
            decoded = self.objid_decoder.decode(objid)
            return self.objid_decoder.format_compact(decoded)
        except Exception:
            return f"0x{objid:08X}"

    def pack_data_by_dtype(self, dtype: int, *values: Any) -> bytes | None:
        """Pack data according to dtype specification."""
        if not self.objid_decoder:
            return None

        try:
            dtype_info = self.objid_decoder.dtype_info.get(dtype, {})
            dtype_name = dtype_info.get("type", "")

            if not dtype_name or dtype_name in ("invalid", "res", "block"):
                return None

            dtype_name_base = (
                dtype_name[:-2] if dtype_name.endswith("_t") else dtype_name
            )

            dtype_formats = {
                "bool": "B",
                "int8": "b",
                "uint8": "B",
                "int16": "<h",
                "uint16": "<H",
                "int32": "<i",
                "uint32": "<I",
                "int64": "<q",
                "uint64": "<Q",
                "float": "<f",
                "double": "<d",
                "char": "s",
            }

            fmt = dtype_formats.get(dtype_name_base)
            if not fmt:
                return None

            if dtype_name_base == "char" and len(values) == 1:
                if isinstance(values[0], str):
                    return values[0].encode("utf-8")
                if isinstance(values[0], bytes):
                    return values[0]
                return None

            if len(values) != 1:
                return None

            return struct.pack(fmt, values[0])

        except (struct.error, ValueError, KeyError):
            return None

    @staticmethod
    def calculate_crc(data: bytes) -> int:
        """Calculate 16-bit CRC-CCITT for frame data."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc

    def _log(self, message: str) -> None:
        """Print a message only when verbose is enabled."""
        if self.verbose:
            print(message)

    def _err(self, message: str) -> None:
        """Print error output."""
        print(message)

    def _ping_with_messages(
        self,
        *,
        start_message: str,
        success_message: str,
        failure_message: str,
    ) -> bool:
        """Send a ping and validate that the response is a pong."""
        protocol = cast("Any", self)
        self._log(start_message)
        if not protocol.send_frame(self.CMD_PING):
            return False

        response = protocol.receive_frame()
        if response and response[0] == self.CMD_PONG:
            self._log(success_message)
            return True

        self._err(failure_message)
        return False

    def _parse_io_list_payload(
        self,
        payload: bytes,
        *,
        log_decoded_ids: bool = False,
    ) -> list[int]:
        """Parse and cache a LIST_IOS payload."""
        count = struct.unpack("<H", payload[0:2])[0]
        self._log(f"Found {count} IO objects")

        io_list: list[int] = []
        for index in range(count):
            offset = 2 + (index * 4)
            if offset + 4 > len(payload):
                break

            objid = struct.unpack("<I", payload[offset : offset + 4])[0]
            io_list.append(objid)
            if log_decoded_ids:
                decoded_id = self.decode_object_id(objid)
                self._log(f"  IO {index}: {decoded_id}")

        self.io_list = io_list
        return io_list

    def _build_io_info(
        self,
        objid: int,
        response: bytes,
        *,
        detailed_unknown: bool = False,
        log_details: bool = False,
    ) -> dict[str, Any]:
        """Build and cache IO metadata from a GET_INFO response."""
        io_type = response[0]
        type_str = {
            self.IO_TYPE_READ_ONLY: "Read-Only",
            self.IO_TYPE_WRITE_ONLY: "Write-Only",
            self.IO_TYPE_READ_WRITE: "Read-Write",
        }.get(
            io_type,
            f"Unknown(0x{io_type:02X})" if detailed_unknown else "Unknown",
        )

        info = {
            "objid": objid,
            "io_type": io_type,
            "io_type_str": type_str,
            "dimension": response[1],
            "dtype": response[2],
        }

        if log_details:
            decoded_id = self.decode_object_id(objid)
            self._log(
                f"  {decoded_id}: type={type_str} "
                f"dim={response[1]} dtype={response[2]}"
            )

        self.io_info[objid] = info
        return info

    def _read_io_seek_all(
        self,
        objid: int,
        *,
        empty_chunk_error: str | None = None,
    ) -> bytes | None:
        """Read an entire seekable IO by fetching chunks until complete."""
        protocol = cast("Any", self)
        result = protocol.read_io_seek_chunk(objid, 0)
        if result is None:
            return None

        total_size, first_chunk = result
        data = bytearray(first_chunk)
        offset = len(first_chunk)

        while offset < total_size:
            result = protocol.read_io_seek_chunk(objid, offset)
            if result is None:
                return None

            _, chunk = result
            if not chunk:
                if empty_chunk_error:
                    self._err(empty_chunk_error.format(offset=offset))
                return None

            data.extend(chunk)
            offset += len(chunk)

        return bytes(data)

    def _exchange(
        self, cmd: int, payload: bytes = b""
    ) -> tuple[int, bytes] | None:
        """Send a command and return the response frame."""
        protocol = cast("Any", self)
        if not protocol.send_frame(cmd, payload):
            return None
        return cast("tuple[int, bytes] | None", protocol.receive_frame())

    def _exchange_objid(
        self, cmd: int, objid: int
    ) -> tuple[int, bytes] | None:
        """Send a command with an object ID payload."""
        return self._exchange(cmd, struct.pack("<I", objid))

    def _exchange_write(
        self, cmd: int, objid: int, data: bytes
    ) -> tuple[int, bytes] | None:
        """Send a command with object ID + raw data payload."""
        return self._exchange(cmd, struct.pack("<I", objid) + data)

    def _collect_io_snapshot(
        self,
        *,
        set_none_for_write_only: bool,
        set_none_for_failed_read: bool,
        read_values: bool = True,
        fetch_info: bool = True,
        on_data: Callable[[dict[str, Any], bytes], None] | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Collect current IO metadata and readable values."""
        protocol = cast("Any", self)
        io_data: dict[int, dict[str, Any]] = {}

        for objid in self.io_list:
            if fetch_info:
                info = protocol.get_io_info(objid)
                if not info:
                    continue
            else:
                info = self._fallback_io_info_from_objid(objid)

            if info["io_type"] == self.IO_TYPE_WRITE_ONLY:
                if set_none_for_write_only:
                    info["data"] = None
                io_data[objid] = info
                continue

            should_read = read_values
            if should_read and (
                # Descriptor-like payloads are exposed as block dtype and are
                # often large/seekable; skip raw GET_IO during discovery.
                self._io_info_has_block_dtype(info)
                or self._objid_has_block_dtype(objid)
            ):
                should_read = False

            if not should_read:
                info["data"] = None
                io_data[objid] = info
                continue

            self._attach_snapshot_data(
                info,
                objid,
                protocol=protocol,
                set_none_for_failed_read=set_none_for_failed_read,
                on_data=on_data,
            )

            io_data[objid] = info

        return io_data

    def _attach_snapshot_data(
        self,
        info: dict[str, Any],
        objid: int,
        *,
        protocol: Any,
        set_none_for_failed_read: bool,
        on_data: Callable[[dict[str, Any], bytes], None] | None,
    ) -> None:
        """Attach current IO payload to snapshot entry when available."""
        data = protocol.read_io(objid)
        if data is not None:
            info["data"] = data.hex()
            info["data_bytes"] = list(data)
            if on_data:
                on_data(info, data)
            return

        if set_none_for_failed_read:
            info["data"] = None

    def _fallback_io_info_from_objid(self, objid: int) -> dict[str, Any]:
        """Create minimal IO info from object-id decode only."""
        dtype = 0
        decoder = self.objid_decoder
        if decoder is not None:
            try:
                decoded = decoder.decode(objid)
                dtype = int(getattr(decoded, "dtype", 0))
            except (
                Exception
            ):  # pragma: no cover - decode failures are tolerated
                pass
        return {
            "objid": objid,
            "io_type": 0,
            "io_type_str": "Unknown",
            "dimension": 0,
            "dtype": dtype,
        }

    def _io_info_has_block_dtype(self, info: dict[str, Any]) -> bool:
        """Return True when IO metadata declares block dtype."""
        decoder = self.objid_decoder
        if decoder is None:
            return False

        dtype_val = info.get("dtype")
        if not isinstance(dtype_val, int):
            return False

        dtype_info = decoder.dtype_info.get(dtype_val, {})
        dtype_name = str(dtype_info.get("type", "")).lower()
        return dtype_name == "block"

    def _objid_has_block_dtype(self, objid: int) -> bool:
        """Return True when object ID bitfields declare block dtype."""
        decoder = self.objid_decoder
        if decoder is None:
            return False
        try:
            decoded = decoder.decode(objid)
        except Exception:
            return False
        return str(getattr(decoded, "dtype_name", "")).lower() == "block"

    def _build_frame(
        self, cmd: int, payload: bytes = b""
    ) -> tuple[bytes, int]:
        """Build a framed command payload and return it with its CRC."""
        frame = bytearray()
        frame.append(self.FRAME_SYNC)
        frame.extend(struct.pack("<H", len(payload)))
        frame.append(cmd)

        if payload:
            frame.extend(payload)

        crc_data = bytes([cmd]) + payload
        crc = self.calculate_crc(crc_data)
        frame.extend(struct.pack("<H", crc))

        return bytes(frame), crc

    def _parse_frame_bytes(
        self,
        data: bytes,
        *,
        short_frame_message: str,
        invalid_sync_message: str,
        length_mismatch_message: str,
        log_message_factory: Callable[[int], str],
    ) -> tuple[int, bytes] | None:
        """Validate and decode a complete frame."""
        if len(data) < self.FRAME_MIN_LEN:
            self._err(short_frame_message.format(length=len(data)))
            return None

        if data[0] != self.FRAME_SYNC:
            self._err(invalid_sync_message.format(sync=data[0]))
            return None

        length = struct.unpack("<H", data[1:3])[0]
        expected_len = self.FRAME_MIN_LEN + length
        if len(data) != expected_len:
            self._err(
                length_mismatch_message.format(
                    expected=expected_len,
                    actual=len(data),
                )
            )
            return None

        crc_calc = self.calculate_crc(data[3 : 4 + length])
        crc_recv = struct.unpack("<H", data[4 + length : 6 + length])[0]

        if crc_calc != crc_recv:
            self._err(
                "CRC mismatch: "
                f"calculated=0x{crc_calc:04X} "
                f"received=0x{crc_recv:04X}"
            )
            return None

        cmd = data[3]
        payload = data[4 : 4 + length] if length > 0 else b""
        self._log(log_message_factory(length))
        return cmd, payload
