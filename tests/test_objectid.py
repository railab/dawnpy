#!/usr/bin/env python3
# tools/dawnpy/tests/test_objectid.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for the ObjectIdDecoder implementation.

Tests Object ID encoding/decoding, YAML loading, and formatting.
"""

import pytest

from dawnpy.objectid import DecodedObjectId, ObjectIdDecoder

pytestmark = pytest.mark.usefixtures("source_free_headers")


@pytest.fixture
def decoder():
    """Fixture to create an ObjectIdDecoder for testing."""
    return ObjectIdDecoder()


class TestObjectIdDecoderInitialization:
    """Tests for ObjectIdDecoder initialization."""

    def test_initialization_loads_bit_fields(self, decoder):
        """Test that initialization loads bit field definitions."""
        assert len(decoder.bit_fields) > 0
        assert "priv" in decoder.bit_fields
        assert "flags" in decoder.bit_fields
        assert "dtype" in decoder.bit_fields
        assert "type" in decoder.bit_fields
        assert "cls" in decoder.bit_fields

    def test_initialization_loads_object_types(self, decoder):
        """Test that initialization loads object type definitions."""
        assert len(decoder.object_types) > 0
        # Standard object types
        assert 0 in decoder.object_types or 1 in decoder.object_types

    def test_initialization_loads_dtype_info(self, decoder):
        """Test that initialization loads data type information."""
        assert len(decoder.dtype_info) > 0

    def test_initialization_loads_block_dtype(self, decoder):
        """DTYPE value 15 is reserved for block byte-stream data."""
        assert 15 in decoder.dtype_info
        assert decoder.dtype_info[15]["type"] == "block"

    def test_initialization_loads_io_classes(self, decoder):
        """Test that initialization loads IO class definitions."""
        assert len(decoder.io_classes) > 0

    def test_initialization_loads_proto_classes(self, decoder):
        """Test that initialization loads protocol class definitions."""
        assert len(decoder.proto_classes) > 0

    def test_initialization_loads_prog_classes(self, decoder):
        """Test that initialization loads program class definitions."""
        assert len(decoder.prog_classes) > 0

    def test_bit_field_attributes_set(self, decoder):
        """Test bit field attributes are exposed."""
        # Check that attributes are dynamically set
        assert hasattr(decoder, "TYPE_SHIFT")
        assert hasattr(decoder, "TYPE_MAX")


class TestObjectIdDecoding:
    """Tests for Object ID decoding."""

    def test_decode_simple_objid(self, decoder):
        """Test decoding a simple object ID."""
        objid = 0x00010001
        decoded = decoder.decode(objid)

        assert decoded.objid == objid
        assert decoded.type >= 0
        assert decoded.cls >= 0
        assert decoded.dtype >= 0

    def test_decoded_object_id_fields(self, decoder):
        """Test that DecodedObjectId contains all required fields."""
        objid = 0x12345678
        decoded = decoder.decode(objid)

        assert isinstance(decoded, DecodedObjectId)
        assert hasattr(decoded, "objid")
        assert hasattr(decoded, "type")
        assert hasattr(decoded, "type_name")
        assert hasattr(decoded, "cls")
        assert hasattr(decoded, "cls_name")
        assert hasattr(decoded, "dtype")
        assert hasattr(decoded, "dtype_name")
        assert hasattr(decoded, "dtype_size")
        assert hasattr(decoded, "flags")
        assert hasattr(decoded, "priv")
        assert hasattr(decoded, "ext")

    def test_decode_preserves_objid(self, decoder):
        """Test that decoding preserves the original object ID."""
        test_ids = [0x00000000, 0x12345678, 0xFFFFFFFF, 0x00010001]
        for objid in test_ids:
            decoded = decoder.decode(objid)
            assert decoded.objid == objid

    def test_decode_field_ranges(self, decoder):
        """Test that decoded fields are within expected ranges."""
        objid = 0x12345678
        decoded = decoder.decode(objid)

        assert 0 <= decoded.type <= 3
        assert 0 <= decoded.cls <= 511
        assert 0 <= decoded.dtype <= 15
        assert 0 <= decoded.flags <= 3
        assert 0 <= decoded.priv <= 16383
        assert 0 <= decoded.ext <= 1

    def test_dtype_name_exists(self, decoder):
        """Test that dtype_name is set for all decodings."""
        objids = [0x00000000, 0x12345678, 0xFFFFFFFF]
        for objid in objids:
            decoded = decoder.decode(objid)
            assert isinstance(decoded.dtype_name, str)
            assert len(decoded.dtype_name) > 0

    def test_type_name_exists(self, decoder):
        """Test that type_name is set for all decodings."""
        objids = [0x00000000, 0x12345678, 0xFFFFFFFF]
        for objid in objids:
            decoded = decoder.decode(objid)
            assert isinstance(decoded.type_name, str)
            assert len(decoded.type_name) > 0


class TestObjectIdEncoding:
    """Tests for Object ID encoding."""

    def test_encode_basic(self, decoder):
        """Test basic Object ID encoding."""
        encoded = decoder.encode(obj_type=1, cls=2, dtype=3)
        assert isinstance(encoded, int)
        assert encoded >= 0

    def test_encode_with_all_parameters(self, decoder):
        """Test encoding with all parameters specified."""
        encoded = decoder.encode(
            obj_type=2, cls=100, dtype=5, flags=1, priv=1000
        )
        assert isinstance(encoded, int)
        assert encoded >= 0

    def test_encode_decode_roundtrip(self, decoder):
        """Test that encode followed by decode preserves values."""
        # Encode
        obj_type = 1
        cls = 50
        dtype = 4
        flags = 2
        priv = 500

        encoded = decoder.encode(
            obj_type=obj_type,
            cls=cls,
            dtype=dtype,
            flags=flags,
            priv=priv,
        )

        # Decode
        decoded = decoder.decode(encoded)

        # Verify roundtrip
        assert decoded.type == obj_type
        assert decoded.cls == cls
        assert decoded.dtype == dtype
        assert decoded.flags == flags
        assert decoded.priv == priv

    def test_encode_zero_values(self, decoder):
        """Test encoding with zero values."""
        encoded = decoder.encode(obj_type=0, cls=0, dtype=0)
        assert encoded >= 0

    def test_encode_max_values(self, decoder):
        """Test encoding with maximum allowed values."""
        encoded = decoder.encode(
            obj_type=3, cls=511, dtype=15, flags=3, priv=16383
        )
        assert isinstance(encoded, int)


class TestGetClassName:
    """Tests for get_class_name method."""

    def test_get_io_class_name(self, decoder):
        """Test retrieving IO class name."""
        if decoder.io_classes:
            # Get first IO class
            first_cls_id = next(iter(decoder.io_classes.keys()))
            name = decoder.get_class_name(obj_type=1, cls=first_cls_id)
            assert name is not None
            assert isinstance(name, str)

    def test_get_proto_class_name(self, decoder):
        """Test retrieving protocol class name."""
        if decoder.proto_classes:
            # Get first protocol class
            first_cls_id = next(iter(decoder.proto_classes.keys()))
            name = decoder.get_class_name(obj_type=2, cls=first_cls_id)
            assert name is not None
            assert isinstance(name, str)

    def test_get_prog_class_name(self, decoder):
        """Test retrieving program class name."""
        if decoder.prog_classes:
            # Get first program class
            first_cls_id = next(iter(decoder.prog_classes.keys()))
            name = decoder.get_class_name(obj_type=3, cls=first_cls_id)
            assert name is not None
            assert isinstance(name, str)

    def test_get_unknown_class_name(self, decoder):
        """Test retrieving unknown class name returns None."""
        name = decoder.get_class_name(obj_type=0, cls=999)
        # Should return None for unknown object type/class combo
        assert name is None

    def test_get_class_name_for_unknown_class_id(self, decoder):
        """Test retrieving class name for non-existent class ID."""
        name = decoder.get_class_name(obj_type=1, cls=9999)
        # Should return None for non-existent class
        assert name is None


class TestFormatCompact:
    """Tests for format_compact method."""

    def test_format_compact_with_known_class(self, decoder):
        """Test compact formatting with a known class."""
        objid = 0x00010001
        decoded = decoder.decode(objid)
        formatted = decoder.format_compact(decoded)

        assert isinstance(formatted, str)
        assert "0x" in formatted
        assert len(formatted) > 0

    def test_format_compact_contains_object_id(self, decoder):
        """Test that formatted output contains hex object ID."""
        objid = 0x12345678
        decoded = decoder.decode(objid)
        formatted = decoder.format_compact(decoded)

        assert "12345678" in formatted

    def test_format_compact_with_unknown_class(self, decoder):
        """Test compact formatting with unknown class."""
        # Create a decoded object with unknown class
        decoded = DecodedObjectId(
            objid=0x12345678,
            type=1,
            type_name="OBJTYPE_IO",
            cls=999,
            cls_name=None,
            dtype=4,
            dtype_name="uint32_t",
            dtype_size=32,
            flags=0,
            priv=100,
            ext=0,
        )
        formatted = decoder.format_compact(decoded)

        assert isinstance(formatted, str)
        assert "CLS999" in formatted

    def test_format_compact_with_known_class_name(self, decoder):
        """Test compact formatting when cls_name is set."""
        # Create a decoded object with known class name
        decoded = DecodedObjectId(
            objid=0x12345678,
            type=1,
            type_name="OBJTYPE_IO",
            cls=42,
            cls_name="CIODummy",
            dtype=4,
            dtype_name="uint32_t",
            dtype_size=32,
            flags=0,
            priv=100,
            ext=0,
        )
        formatted = decoder.format_compact(decoded)

        assert isinstance(formatted, str)
        assert "CIODummy" in formatted
        assert "CLS42" not in formatted


class TestFormatDetailed:
    """Tests for format_detailed method."""

    def test_format_detailed_contains_all_info(self, decoder):
        """Test that detailed format contains all object ID information."""
        objid = 0x00010001
        decoded = decoder.decode(objid)
        formatted = decoder.format_detailed(decoded)

        assert isinstance(formatted, str)
        assert "Object ID:" in formatted
        assert "Type:" in formatted
        assert "Class:" in formatted
        assert "Data Type:" in formatted
        assert "Instance/Private ID:" in formatted

    def test_format_detailed_multiline(self, decoder):
        """Test that detailed format is multiline."""
        objid = 0x12345678
        decoded = decoder.decode(objid)
        formatted = decoder.format_detailed(decoded)

        lines = formatted.split("\n")
        assert len(lines) >= 5

    def test_format_detailed_contains_hex_values(self, decoder):
        """Test that detailed format contains hexadecimal values."""
        objid = 0x12345678
        decoded = decoder.decode(objid)
        formatted = decoder.format_detailed(decoded)

        assert "0x12345678" in formatted


class TestDecodedObjectIdNamedTuple:
    """Tests for DecodedObjectId named tuple."""

    def test_decoded_object_id_creation(self):
        """Test creating a DecodedObjectId instance."""
        decoded = DecodedObjectId(
            objid=0x12345678,
            type=1,
            type_name="OBJTYPE_IO",
            cls=2,
            cls_name="ADC",
            dtype=4,
            dtype_name="uint32_t",
            dtype_size=32,
            flags=0,
            priv=100,
            ext=0,
        )

        assert decoded.objid == 0x12345678
        assert decoded.type == 1
        assert decoded.cls == 2
        assert decoded.cls_name == "ADC"

    def test_decoded_object_id_is_immutable(self):
        """Test that DecodedObjectId is immutable."""
        decoded = DecodedObjectId(
            objid=0x12345678,
            type=1,
            type_name="OBJTYPE_IO",
            cls=2,
            cls_name="ADC",
            dtype=4,
            dtype_name="uint32_t",
            dtype_size=32,
            flags=0,
            priv=100,
            ext=0,
        )

        with pytest.raises(AttributeError):
            decoded.objid = 0x87654321

    def test_decoded_object_id_with_none_class_name(self):
        """Test DecodedObjectId with None class name."""
        decoded = DecodedObjectId(
            objid=0x12345678,
            type=1,
            type_name="OBJTYPE_IO",
            cls=999,
            cls_name=None,
            dtype=4,
            dtype_name="uint32_t",
            dtype_size=32,
            flags=0,
            priv=100,
            ext=0,
        )

        assert decoded.cls_name is None


class TestNameLookups:
    """find_* helpers translate symbolic names to numeric IDs."""

    def test_find_object_type_accepts_short_and_full_name(self, decoder):
        sample = next(iter(decoder.object_types.items()))
        type_id, type_name = sample
        assert decoder.find_object_type(type_name) == type_id
        assert decoder.find_object_type(f"OBJTYPE_{type_name}") == type_id

    def test_find_object_type_returns_none_for_unknown(self, decoder):
        assert decoder.find_object_type("__no_such_type__") is None

    def test_find_io_class_accepts_short_and_prefixed_name(self, decoder):
        if not decoder.io_classes:  # pragma: no cover
            pytest.skip("no io classes loaded")
        cls_id, cls_name = next(iter(decoder.io_classes.items()))
        assert decoder.find_io_class(cls_name) == cls_id
        assert decoder.find_io_class(f"io_class_{cls_name}") == cls_id

    def test_find_io_class_returns_none_for_unknown(self, decoder):
        assert decoder.find_io_class("__no_such_io__") is None

    def test_find_prog_class_returns_id_or_none(self, decoder):
        if decoder.prog_classes:
            cls_id, cls_name = next(iter(decoder.prog_classes.items()))
            assert decoder.find_prog_class(cls_name) == cls_id
        assert decoder.find_prog_class("__no_such_prog__") is None

    def test_find_proto_class_returns_id_or_none(self, decoder):
        if decoder.proto_classes:
            cls_id, cls_name = next(iter(decoder.proto_classes.items()))
            assert decoder.find_proto_class(cls_name) == cls_id
        assert decoder.find_proto_class("__no_such_proto__") is None
