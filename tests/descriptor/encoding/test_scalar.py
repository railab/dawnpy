# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

import struct

import click
import pytest

from dawnpy.descriptor.encoding.scalar import (
    encode_scalar_words,
    format_scalar_cpp,
)


def test_encode_scalar_words_dtypes():
    assert encode_scalar_words(1, "uint32") == [1]
    assert encode_scalar_words(-1, "int32") == [0xFFFFFFFF]
    assert encode_scalar_words(True, "bool") == [1]
    assert encode_scalar_words(1.5, "float") == [
        int.from_bytes(struct.pack("<f", 1.5), "little")
    ]
    assert len(encode_scalar_words(1.5, "double")) == 2
    assert len(encode_scalar_words(-1, "int64")) == 2
    assert len(encode_scalar_words(1, "uint64")) == 2
    with pytest.raises(click.ClickException):
        encode_scalar_words(1, "block")


def test_format_scalar_cpp_branches():
    # signed: negative -> (uint32_t) cast, positive -> plain decimal
    assert format_scalar_cpp(-3, "int32") == ["(uint32_t)-3"]
    assert format_scalar_cpp(7, "int16") == ["7"]
    # unsigned -> masked decimal
    assert format_scalar_cpp(5, "uint32") == ["5"]
    # float -> one hex word
    assert format_scalar_cpp(1.0, "float") == ["0x3f800000"]
    # double -> two hex words
    assert len(format_scalar_cpp(1.0, "double")) == 2
