# tools/dawnpy/tests/test_device_decode.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for transport-neutral device decode helpers."""

import struct

from dawnpy.device.decode import (
    _decode_bytes,
    _decode_char,
    _decode_fallback,
    _decode_numeric,
    _hex_lines,
    _prefix_text,
    _wrap_hex,
    decode_value,
    normalize_dtype,
)


def test_normalize_dtype_strips_suffix_and_case():
    """Normalize dtype names to their canonical lowercase form."""
    assert normalize_dtype("UINT32_T") == "uint32"
    assert normalize_dtype(" float ") == "float"


def test_wrap_and_prefix_helpers():
    lines = _wrap_hex("a" * 40, "0x", max_line=12)
    assert lines[0].startswith("0x")
    assert lines[1].startswith("  ")
    tiny = _wrap_hex("abcdef", "x" * 200, max_line=80)
    assert len(tiny) == 1
    assert tiny[0].endswith("abcdef")
    assert _prefix_text(True, 0x12) == "0x00000012: "
    assert _prefix_text(False, 0x12) == ""
    assert _hex_lines(b"\x01\x02", False, None)[0] == "0x0102"
    assert _hex_lines(b"\x01\x02", True, 0xAB)[0].startswith("0x000000AB: 0x")


def test_decode_bytes_fallback_to_ascii():
    assert _decode_bytes(b"abc") == "abc"
    assert _decode_bytes(b"\xffA") == ".A"


def test_decode_char_paths():
    assert _decode_char(b"\x00\x00", True, 0x1) == ['0x00000001: ""']

    pattern0 = b"A\x00\x00\x00B\x00\x00\x00"
    assert _decode_char(pattern0, True, 0x2) == ["0x00000002: AB"]

    pattern3 = b"\x00\x00\x00C\x00\x00\x00D"
    assert _decode_char(pattern3, False, None) == ["CD"]

    assert _decode_char(b"\x00hello", False, None) == ['""']
    assert _decode_char(b"xyz\x00tail", False, None) == ["xyz"]


def test_decode_numeric_paths():
    assert _decode_numeric(b"\x01", "nope", False, None) is None
    assert _decode_numeric(b"\x02", "uint8", False, None) == ["2"]
    assert _decode_numeric(
        struct.pack("<HH", 1, 2), "uint16", False, None
    ) == ["[1, 2]"]
    fallback = _decode_numeric(b"\x01\x02\x03", "uint16", True, 0x55)
    assert fallback is not None
    assert fallback[0].startswith("0x00000055: 0x")


def test_decode_fallback_paths():
    assert _decode_fallback(b"\x07", False, None) == ["7"]
    assert _decode_fallback(struct.pack("<H", 0x1234), False, None) == ["4660"]
    assert _decode_fallback(struct.pack("<I", 5), False, None) == ["5"]
    assert _decode_fallback(struct.pack("<Q", 9), False, None) == ["9"]
    assert _decode_fallback(b"\x01\x02\x03", False, None)[0] == "0x010203"


def test_decode_value_with_debug_and_decoder_variants():
    class _Decoder:
        dtype_info = {1: {"type": "char"}, 2: {"type": "uint16_t"}}

    lines = decode_value(
        b"A\x00\x00\x00",
        1,
        _Decoder(),
        include_objid=True,
        objid=0x1234,
        debug=True,
    )
    assert lines[0].startswith("DEBUG: objid=0x00001234")
    assert lines[1] == "0x00001234: A"

    assert decode_value(struct.pack("<H", 11), 2, _Decoder(), debug=False) == [
        "11"
    ]

    # Unknown dtype falls back by byte length decoding.
    assert decode_value(b"\x05", 99, _Decoder(), debug=False) == ["5"]
