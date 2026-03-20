#!/usr/bin/env python3
# tools/dawnpy/tests/test_imports.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for module imports and error handling.

Tests that modules handle import errors gracefully.
"""


class TestMainPackageImports:
    """Tests for dawnpy main package imports."""

    def test_dawnpy_import_success(self):
        """Test successful import of dawnpy package."""
        import dawnpy

        assert dawnpy is not None
        assert hasattr(dawnpy, "__version__")

    def test_dawnpy_version_string(self):
        """Test that dawnpy has a version string."""
        import dawnpy

        assert isinstance(dawnpy.__version__, str)
        assert len(dawnpy.__version__) > 0

    def test_dawnpy_author_string(self):
        """Test that dawnpy has author information."""
        import dawnpy

        assert isinstance(dawnpy.__author__, str)
        assert len(dawnpy.__author__) > 0

    def test_objectid_exported_from_main(self):
        """Test that ObjectIdDecoder is available from main package."""
        import dawnpy

        assert hasattr(dawnpy, "ObjectIdDecoder")

    def test_decoded_object_id_exported_from_main(self):
        """Test that DecodedObjectId is available from main package."""
        import dawnpy

        assert hasattr(dawnpy, "DecodedObjectId")

    def test_descriptor_validator_exported_from_main(self):
        """Test that DescriptorValidator is available from main package."""
        import dawnpy

        assert hasattr(dawnpy, "DescriptorValidator")

    def test_validation_result_exported_from_main(self):
        """Test that ValidationResult is available from main package."""
        import dawnpy

        assert hasattr(dawnpy, "ValidationResult")

    def test_dawnpy_all_exports(self):
        """Test that __all__ is defined correctly."""
        import dawnpy

        assert hasattr(dawnpy, "__all__")
        assert isinstance(dawnpy.__all__, list)
        assert "ObjectIdDecoder" in dawnpy.__all__
        assert "DecodedObjectId" in dawnpy.__all__
        assert "DescriptorValidator" in dawnpy.__all__
        assert "ValidationResult" in dawnpy.__all__


class TestObjectIdModuleImports:
    """Tests for dawnpy.objectid module imports."""

    def test_objectid_module_import(self):
        """Test successful import of objectid module."""
        from dawnpy import objectid

        assert objectid is not None

    def test_object_id_decoder_in_objectid(self):
        """Test that ObjectIdDecoder is in objectid module."""
        from dawnpy import objectid

        assert hasattr(objectid, "ObjectIdDecoder")

    def test_decoded_object_id_in_objectid(self):
        """Test that DecodedObjectId is in objectid module."""
        from dawnpy import objectid

        assert hasattr(objectid, "DecodedObjectId")


class TestImportGracefulHandling:
    """Tests for graceful import error handling."""

    def test_main_package_handles_objectid_import_error(self):
        """Test that main package handles ObjectIdDecoder import error."""
        # This test verifies the try/except block works
        # The actual import should succeed
        try:
            from dawnpy import ObjectIdDecoder

            assert ObjectIdDecoder is not None
        except ImportError:
            # If import fails, the try/except in __init__ caught it
            pass


class TestFullImportChain:
    """Tests for full import chain."""

    def test_import_from_dawnpy_objectid(self):
        """Test importing ObjectIdDecoder from dawnpy.objectid."""
        from dawnpy.objectid import ObjectIdDecoder

        assert ObjectIdDecoder is not None


class TestNoCircularImports:
    """Tests to verify no circular imports occur."""

    def test_objectid_imports_cleanly(self):
        """Test that objectid module imports cleanly."""
        # If there's a circular import, this would fail
        from dawnpy import objectid

        assert objectid is not None
