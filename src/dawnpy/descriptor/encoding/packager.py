# tools/dawnpy/src/dawnpy/descriptor/encoding/packager.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Low-level descriptor binary packing helpers.

CRC32, u32-word packing, bitmap decoding, and hex-file parsing used by the
descriptor binary builder. Pure byte/int utilities with no YAML/header deps.
"""

import re
import struct
import zlib

import click

_FOOTER_MARKER = 0x02030A0D


def nuttx_crc32(data: bytes) -> int:
    """Compute CRC32 matching NuttX ``crc32()`` (seed=0, no final xor).

    NuttX's ``crc32()`` uses the reflected polynomial 0xEDB88320 with init=0
    and no final XOR. Standard zlib CRC-32 uses init=0xFFFFFFFF with a final
    XOR of 0xFFFFFFFF; passing 0xFFFFFFFF as the prior CRC and XOR-ing the
    result back is mathematically equivalent.
    """
    return zlib.crc32(data, 0xFFFFFFFF) ^ 0xFFFFFFFF


def fill_crc32_footer(binary: bytes) -> bytes:
    """Return a copy of ``binary`` with its final word replaced by CRC32.

    Raises:
        ValueError: if the binary is too short or the footer marker is missing.
    """
    if len(binary) < 8:
        raise ValueError("descriptor binary too small")

    footer_magic = int.from_bytes(binary[-8:-4], "little")
    if footer_magic != _FOOTER_MARKER:
        raise ValueError(
            "descriptor footer marker mismatch (expected 0x02030A0D)"
        )

    payload = bytearray(binary)
    checksum = nuttx_crc32(bytes(payload[:-4]))
    payload[-4:] = checksum.to_bytes(4, "little")
    return bytes(payload)


def pack_u32_words(words: list[int]) -> bytes:
    """Pack a list of u32 words into little-endian bytes."""
    return b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words)


def bitmap_enabled_ids(bitmap: bytes) -> list[int]:
    """Return enabled bit indexes from little-endian bitmap bytes."""
    enabled: list[int] = []
    for byte_idx, value in enumerate(bitmap):
        for bit in range(8):
            if value & (1 << bit):
                enabled.append((byte_idx * 8) + bit)
    return enabled


def parse_hex_file_text(text: str) -> bytes:
    """Parse a hexdump or hex-blob text file into raw bytes."""
    tokens: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if ":" in stripped:
            # Support shell hexdump/xxd-like lines:
            # 00000000: 01 02 ...  ASCII
            payload = stripped.split(":", 1)[1]
            if "|" in payload:
                payload = payload.split("|", 1)[0]
            line_tokens = re.findall(r"\b[0-9A-Fa-f]{2}\b", payload)
            tokens.extend(line_tokens[:16])
        else:
            tokens.extend(re.findall(r"\b[0-9A-Fa-f]{2}\b", stripped))

    if tokens:
        return bytes(int(tok, 16) for tok in tokens)

    cleaned = (
        text.replace(" ", "")
        .replace("\n", "")
        .replace("\t", "")
        .replace("_", "")
        .replace(",", "")
        .replace("0x", "")
        .replace("0X", "")
    )
    if len(cleaned) == 0:
        raise click.ClickException("Hex file is empty")
    if len(cleaned) % 2 != 0:
        raise click.ClickException(
            "Hex file must contain an even number of hex digits"
        )
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise click.ClickException(f"Invalid hex file content: {exc}") from exc
