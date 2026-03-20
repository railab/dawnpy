# tools/dawnpy/src/dawnpy/device/decode.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Decode and normalize device values independent of transport."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dawnpy.objectid import ObjectIdDecoder


def normalize_dtype(dtype: str) -> str:
    """Normalize dtype strings to canonical names."""
    dtype = dtype.strip().lower()
    if dtype.endswith("_t"):
        return dtype[:-2]
    return dtype


def _wrap_hex(hexstr: str, prefix: str, max_line: int = 80) -> list[str]:
    available = max_line - len(prefix)
    if available < 8:
        available = 8
    lines = []
    for i in range(0, len(hexstr), available):
        chunk = hexstr[i : i + available]
        if i == 0:
            lines.append(f"{prefix}{chunk}")
        else:
            lines.append(f"{' ' * len(prefix)}{chunk}")
    return lines


def _prefix_text(include_objid: bool, objid: int | None) -> str:
    if include_objid and objid is not None:
        return f"0x{objid:08X}: "
    return ""


def _hex_lines(
    data: bytes, include_objid: bool, objid: int | None
) -> list[str]:
    prefix = "0x"
    if include_objid and objid is not None:
        prefix = f"0x{objid:08X}: 0x"
    return _wrap_hex(data.hex(), prefix, max_line=80)


def _decode_bytes(buf: bytes) -> str:
    try:
        return buf.decode("utf-8")
    except UnicodeDecodeError:
        return bytes((b if 32 <= b <= 126 else ord(".")) for b in buf).decode(
            "ascii"
        )


def _decode_char(
    data: bytes, include_objid: bool, objid: int | None
) -> list[str]:
    if all(b == 0 for b in data):
        return [f'{_prefix_text(include_objid, objid)}""']

    if len(data) % 4 == 0 and len(data) >= 4:
        words = [data[i : i + 4] for i in range(0, len(data), 4)]
        pattern0 = all(w[1] == w[2] == w[3] == 0 for w in words)
        pattern3 = all(w[0] == w[1] == w[2] == 0 for w in words)
        if pattern0:
            chars = bytes(w[0] for w in words)
            text = chars.split(b"\x00", 1)[0]
            return [
                f"{_prefix_text(include_objid, objid)}{_decode_bytes(text)}"
            ]
        if pattern3:
            chars = bytes(w[3] for w in words)
            text = chars.split(b"\x00", 1)[0]
            return [
                f"{_prefix_text(include_objid, objid)}{_decode_bytes(text)}"
            ]

    text = data.split(b"\x00", 1)[0]
    if not text:
        return [f'{_prefix_text(include_objid, objid)}""']
    return [f"{_prefix_text(include_objid, objid)}{_decode_bytes(text)}"]


def _decode_numeric(
    data: bytes,
    dtype_name_base: str,
    include_objid: bool,
    objid: int | None,
) -> list[str] | None:
    formats = {
        "bool": ("B", 1),
        "int8": ("b", 1),
        "uint8": ("B", 1),
        "int16": ("<h", 2),
        "uint16": ("<H", 2),
        "int32": ("<i", 4),
        "uint32": ("<I", 4),
        "int64": ("<q", 8),
        "uint64": ("<Q", 8),
        "float": ("<f", 4),
        "double": ("<d", 8),
    }
    if dtype_name_base not in formats:
        return None

    fmt, expected = formats[dtype_name_base]
    length = len(data)
    if length == expected:
        value = struct.unpack(fmt, data)[0]
        return [f"{_prefix_text(include_objid, objid)}{value}"]
    if length % expected == 0:
        count = length // expected
        values = struct.unpack(f"<{count}{fmt[-1]}", data)
        joined = ", ".join(str(v) for v in values)
        return [f"{_prefix_text(include_objid, objid)}[{joined}]"]
    return _hex_lines(data, include_objid, objid)


def _decode_fallback(
    data: bytes, include_objid: bool, objid: int | None
) -> list[str]:
    length = len(data)
    if length == 1:
        return [f"{_prefix_text(include_objid, objid)}{data[0]}"]
    if length == 2:
        value = struct.unpack("<H", data)[0]
        return [f"{_prefix_text(include_objid, objid)}{value}"]
    if length == 4:
        value = struct.unpack("<I", data)[0]
        return [f"{_prefix_text(include_objid, objid)}{value}"]
    if length == 8:
        value = struct.unpack("<Q", data)[0]
        return [f"{_prefix_text(include_objid, objid)}{value}"]
    return _hex_lines(data, include_objid, objid)


def decode_value(
    data: bytes,
    dtype: int,
    objid_decoder: ObjectIdDecoder | None,
    *,
    include_objid: bool = True,
    objid: int | None = None,
    debug: bool = False,
) -> list[str]:
    """Decode data by dtype and return printable lines."""
    dtype_info = {}
    if objid_decoder:
        dtype_info = objid_decoder.dtype_info.get(dtype, {})
    dtype_name = dtype_info.get("type", "")
    dtype_name_base = normalize_dtype(dtype_name)

    debug_line = None
    if debug:
        debug_line = (
            "DEBUG: "
            + f"objid=0x{(objid or 0):08X} "
            + f"dtype={dtype} name={dtype_name or 'unknown'} "
            + f"len={len(data)} hex=0x{data.hex()}"
        )

    if dtype_name_base == "char":
        lines = _decode_char(data, include_objid, objid)
        return [debug_line] + lines if debug_line else lines

    decoded = _decode_numeric(data, dtype_name_base, include_objid, objid)
    if decoded is not None:
        return [debug_line] + decoded if debug_line else decoded

    lines = _decode_fallback(data, include_objid, objid)
    return [debug_line] + lines if debug_line else lines
