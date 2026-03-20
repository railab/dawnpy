# tools/dawnpy/src/dawnpy/descriptor/formatting.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared value formatting helpers for descriptor code generation."""

from typing import Any


class DescriptorFormatHelper:
    """Provide common numeric/string formatting for descriptor generators."""

    indent_width: int = 2

    def indent(self, level: int) -> str:
        """Return C++ descriptor indentation for a nesting level."""
        return " " * (self.indent_width * level)

    def line(self, level: int, text: str = "") -> str:
        """Return one generated C++ line at ``level`` indentation."""
        return f"{self.indent(level)}{text}" if text else self.indent(level)

    def append_line(
        self, lines: list[str], level: int, text: str = ""
    ) -> None:
        """Append one generated C++ line at ``level`` indentation."""
        lines.append(self.line(level, text))

    def define_line(self, name: str, value: str) -> str:
        """Return one generated C++ ``#define`` line."""
        return f"#define {name}{self.indent(1)}{value}"

    def pack_string(self, s: str, min_words: int = 4) -> list[int]:
        """Pack string into uint32 words with null terminator and padding."""
        s_bytes = s.encode("utf-8") + b"\x00"
        padding = (4 - len(s_bytes) % 4) % 4
        s_bytes += b"\x00" * padding

        if min_words > 0:
            min_size = min_words * 4
            if len(s_bytes) < min_size:
                s_bytes += b"\x00" * (min_size - len(s_bytes))

        return self.pack_words_le(s_bytes)

    def pack_fixed_string(self, s: str, size: int) -> list[int]:
        """Pack string into fixed-size byte buffer as uint32 words."""
        s_bytes = str(s).encode("utf-8")
        if len(s_bytes) >= size:
            s_bytes = s_bytes[: size - 1] + b"\x00"
        else:
            s_bytes = s_bytes + b"\x00"
            s_bytes += b"\x00" * (size - len(s_bytes))

        return self.pack_words_le(s_bytes)

    def pack_words_le(self, s_bytes: bytes) -> list[int]:
        """Pack bytes into little-endian uint32 words."""
        words: list[int] = []
        for i in range(0, len(s_bytes), 4):
            word = (
                s_bytes[i]
                | (s_bytes[i + 1] << 8)
                | (s_bytes[i + 2] << 16)
                | (s_bytes[i + 3] << 24)
            )
            words.append(word)
        return words

    def append_words(
        self, lines: list[str], words: list[int], level: int = 3
    ) -> None:
        """Append packed words in hex format with the given indentation."""
        for word in words:
            self.append_line(lines, level, f"{word:#010x},")

    def format_float_as_hex(self, value: float) -> str:
        """Format float value as hex uint32_t."""
        import struct

        bytes_val = struct.pack("f", value)
        uint32_val = struct.unpack("I", bytes_val)[0]
        return f"{uint32_val:#010x}"

    def format_numeric(self, value: Any, *, hex_format: bool = False) -> str:
        """Format numeric value for generated C++ output."""
        if isinstance(value, str):
            return value
        if hex_format:
            return f"{value:#06x}"
        return f"{value}"
