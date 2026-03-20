# tools/dawnpy/src/dawnpy/__init__.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
PyDawn: Python utilities for Dawn Framework.

This package provides the Dawn core Python tooling, including repository
management, descriptor generation, Object ID decoding, and shared device
helpers. Transport and QA commands are provided by separate packages built on
top of core ``dawnpy``.
"""

__version__ = "0.1.0"
__author__ = "Dawn Framework Contributors"

# Import main classes for convenience
try:
    from .descriptor.validation.validator import (
        DescriptorValidator,
        ValidationResult,
    )
except ImportError:
    pass

try:
    from .objectid import DecodedObjectId, ObjectIdDecoder
except ImportError:
    pass

__all__ = [
    "DecodedObjectId",
    "DescriptorValidator",
    "ObjectIdDecoder",
    "ValidationResult",
]
