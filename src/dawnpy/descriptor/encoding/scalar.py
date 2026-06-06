# tools/dawnpy/src/dawnpy/descriptor/encoding/scalar.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Canonical dtype-aware encoding of a scalar value into descriptor words.

A config value's 32-bit word representation depends on its dtype. The C++
runtime reads the stored word(s) with ``cfgToF()``/``cfgtoi32()`` etc., and
``cfgToF()`` bit-reinterprets the word (``memcpy``), so a ``float`` value must
be stored as its IEEE-754 bit pattern -- not ``int(value)``. 64-bit types span
two little-endian words.

This is the single source of truth used by every handler that encodes a typed
scalar (dummy/config init values, IO limits, adjust PROG params, ...), so
float support is uniform instead of re-implemented (or forgotten) per handler.
"""

import struct
from typing import Any

import click

_WORD_DTYPES: frozenset[str] = frozenset(
    {"int8", "int16", "int32", "uint8", "uint16", "uint32", "bool", "char"}
)


def encode_scalar_words(value: Any, dtype_name: str) -> list[int]:
    """Encode one scalar value into little-endian uint32 word(s) for its dtype.

    float  -> 1 word (IEEE-754 bit pattern)
    double -> 2 words
    int64  -> 2 words
    uint64 -> 2 words
    int/uint 8/16/32, bool, char -> 1 word (two's-complement for negatives)
    """
    if dtype_name == "float":
        return [int.from_bytes(struct.pack("<f", float(value)), "little")]
    if dtype_name == "double":
        return list(struct.unpack("<II", struct.pack("<d", float(value))))
    if dtype_name == "int64":
        return list(struct.unpack("<II", struct.pack("<q", int(value))))
    if dtype_name == "uint64":
        return list(struct.unpack("<II", struct.pack("<Q", int(value))))
    if dtype_name in _WORD_DTYPES:
        return [int(value) & 0xFFFFFFFF]
    raise click.ClickException(
        f"Unsupported dtype '{dtype_name}' for scalar value encoding"
    )


def format_scalar_cpp(value: Any, dtype_name: str) -> list[str]:
    """Format one scalar value as C++ uint32 literal(s) for its dtype.

    Wraps :func:`encode_scalar_words`; float/64-bit values render as hex words,
    signed integers keep a readable (possibly negative) literal.
    """
    if dtype_name in ("int8", "int16", "int32"):
        ivalue = int(value)
        return [f"(uint32_t){ivalue}" if ivalue < 0 else f"{ivalue}"]
    if dtype_name in ("uint8", "uint16", "uint32", "bool", "char"):
        return [f"{int(value) & 0xFFFFFFFF}"]
    return [f"{word:#010x}" for word in encode_scalar_words(value, dtype_name)]
