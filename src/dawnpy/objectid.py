#!/usr/bin/env python3
# tools/dawnpy/src/dawnpy/objectid.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Dawn Object ID Decoder.

This module provides utilities to decode and encode Dawn Object IDs.
Mirrors the C++ implementation from dawn/include/dawn/common/objectid.hxx
and loads definitions directly from C++ headers at runtime.
"""

from typing import Any, NamedTuple

import dawnpy.headerdefs.bundle as header_bundle
from dawnpy.headerdefs import HeaderDefsError


class DecodedObjectId(NamedTuple):
    """Decoded Object ID components."""

    objid: int  # Original 32-bit object ID
    type: int  # noqa: A003 - Object type (0-3)
    type_name: str  # Object type name
    cls: int  # Object class (0-511)
    cls_name: str | None  # Object class name (if known)
    dtype: int  # Data type (0-15)
    dtype_name: str  # Data type name
    dtype_size: int  # Data type size in bits
    flags: int  # Type-specific flags (0-3)
    priv: int  # Private/instance ID (0-16383)
    ext: int  # Reserved for future use (0-1)


class ObjectIdDecoder:
    """Decode and encode Dawn Object IDs using header-based definitions."""

    def __init__(self) -> None:
        """Initialize decoder by loading definitions from C++ headers."""
        # Load all type/class definitions
        self.bit_fields: dict[str, dict[str, int]] = {}
        self.object_types: dict[int, str] = {}
        self.dtype_info: dict[int, dict[str, Any]] = {}
        self.io_classes: dict[int, str] = {}
        self.proto_classes: dict[int, str] = {}
        self.prog_classes: dict[int, str] = {}

        if not self._load_from_headers():
            raise HeaderDefsError(
                "Failed to load ObjectId definitions from C++ headers"
            )

    def _set_bit_field_attrs(self) -> None:
        """Expose bit-field shift/max values as instance attributes."""
        for name, props in self.bit_fields.items():
            setattr(self, f"{name.upper()}_SHIFT", props["shift"])
            setattr(self, f"{name.upper()}_MAX", props["max"])

    @staticmethod
    def _defs_have_required_shapes(defs: dict[str, Any]) -> bool:
        """Return True when loaded header definitions have expected shapes."""
        checks = (
            isinstance(defs.get("bit_fields"), dict),
            isinstance(defs.get("object_types"), dict),
            isinstance(defs.get("dtype"), list),
            isinstance(defs.get("io_classes"), dict),
            isinstance(defs.get("proto_classes"), dict),
            isinstance(defs.get("prog_classes"), dict),
        )
        return all(checks)

    def _populate_from_defs(self, defs: dict[str, Any]) -> None:
        """Populate decoder state from validated header definitions."""
        bit_fields = defs["bit_fields"]
        object_types = defs["object_types"]
        dtype = defs["dtype"]
        io_classes = defs["io_classes"]
        proto_classes = defs["proto_classes"]
        prog_classes = defs["prog_classes"]

        self.bit_fields = {
            str(k): {
                "shift": int(v.get("shift", 0)),
                "width": int(v.get("width", 0)),
                "max": int(v.get("max", 0)),
            }
            for k, v in bit_fields.items()
            if isinstance(v, dict)
        }
        self.object_types = {int(k): str(v) for k, v in object_types.items()}

        self.dtype_info = {}
        for item in dtype:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if value is None:
                continue
            self.dtype_info[int(value)] = {
                "type": item.get("type"),
                "size": item.get("size", 0),
            }

        self.io_classes = {int(k): str(v) for k, v in io_classes.items()}
        self.proto_classes = {int(k): str(v) for k, v in proto_classes.items()}
        self.prog_classes = {int(k): str(v) for k, v in prog_classes.items()}

    def _load_from_headers(self) -> bool:
        """Load definitions from C++ headers; return False on failure."""
        try:
            defs = header_bundle.load_header_bundle().header_defs
        except (HeaderDefsError, FileNotFoundError, KeyError):
            return False

        if not self._defs_have_required_shapes(defs):
            return False

        self._populate_from_defs(defs)
        self._set_bit_field_attrs()
        return True

    def get_class_name(self, obj_type: int, cls: int) -> str | None:
        """Return class name based on object type and class ID."""
        if obj_type == 1:  # OBJTYPE_IO
            return self.io_classes.get(cls)
        elif obj_type == 2:  # OBJTYPE_PROTO
            return self.proto_classes.get(cls)
        elif obj_type == 3:  # OBJTYPE_PROG
            return self.prog_classes.get(cls)
        return None

    def find_object_type(self, name: str) -> int | None:
        """Return numeric object type ID for a name, or None.

        Lookup is case-insensitive and accepts the bare name
        (``"io"``) or the C++ enumerator (``"OBJTYPE_IO"``).
        """
        target = name.strip().upper()
        if target.startswith("OBJTYPE_"):
            target = target[len("OBJTYPE_") :]
        for type_id, type_name in self.object_types.items():
            if type_name.upper() == target:
                return type_id
        return None

    def _find_class_in(
        self, table: dict[int, str], name: str, prefix: str
    ) -> int | None:
        """Reverse-lookup helper for class tables."""
        target = name.strip().lower()
        if target.startswith(prefix):
            target = target[len(prefix) :]
        for cls_id, cls_name in table.items():
            if cls_name.lower() == target:
                return cls_id
        return None

    def find_io_class(self, name: str) -> int | None:
        """Return numeric IO class ID for a name, or None."""
        return self._find_class_in(self.io_classes, name, "io_class_")

    def find_proto_class(self, name: str) -> int | None:
        """Return numeric PROTO class ID for a name, or None."""
        return self._find_class_in(self.proto_classes, name, "proto_class_")

    def find_prog_class(self, name: str) -> int | None:
        """Return numeric PROG class ID for a name, or None."""
        return self._find_class_in(self.prog_classes, name, "prog_class_")

    def decode(self, objid: int) -> DecodedObjectId:
        """
        Decode a 32-bit object ID into its components.

        Args:
            objid: 32-bit object ID value

        Returns:
            DecodedObjectId with all components decoded
        """
        # Extract bit fields using loaded definitions
        priv_shift = self.bit_fields.get("priv", {}).get("shift", 0)
        priv_max = self.bit_fields.get("priv", {}).get("max", 0x3FFF)
        flags_shift = self.bit_fields.get("flags", {}).get("shift", 14)
        flags_max = self.bit_fields.get("flags", {}).get("max", 0x3)
        dtype_shift = self.bit_fields.get("dtype", {}).get("shift", 16)
        dtype_max = self.bit_fields.get("dtype", {}).get("max", 0xF)
        ext_shift = self.bit_fields.get("ext", {}).get("shift", 20)
        ext_max = self.bit_fields.get("ext", {}).get("max", 0x1)
        cls_shift = self.bit_fields.get("cls", {}).get("shift", 21)
        cls_max = self.bit_fields.get("cls", {}).get("max", 0x1FF)
        type_shift = self.bit_fields.get("type", {}).get("shift", 30)
        type_max = self.bit_fields.get("type", {}).get("max", 0x3)

        priv = (objid >> priv_shift) & priv_max
        flags = (objid >> flags_shift) & flags_max
        dtype = (objid >> dtype_shift) & dtype_max
        ext = (objid >> ext_shift) & ext_max
        cls = (objid >> cls_shift) & cls_max
        obj_type = (objid >> type_shift) & type_max

        # Get names
        type_name = self.object_types.get(obj_type, f"UNKNOWN({obj_type})")
        dtype_name = self.dtype_info.get(dtype, {}).get(
            "type", f"UNKNOWN({dtype})"
        )
        cls_name = self.get_class_name(obj_type, cls)

        # Get data type size
        dtype_size = self.dtype_info.get(dtype, {}).get("size", 0)

        return DecodedObjectId(
            objid=objid,
            type=obj_type,
            type_name=type_name,
            cls=cls,
            cls_name=cls_name,
            dtype=dtype,
            dtype_name=dtype_name,
            dtype_size=dtype_size,
            flags=flags,
            priv=priv,
            ext=ext,
        )

    def encode(
        self,
        obj_type: int,
        cls: int,
        dtype: int = 0,
        flags: int = 0,
        priv: int = 0,
    ) -> int:
        """
        Encode object ID components into a 32-bit object ID.

        Args:
            obj_type: Object type (0-3)
            cls: Object class (0-511)
            dtype: Data type (0-15), default 0
            flags: Flags (0-3), default 0
            priv: Private/instance ID (0-16383), default 0

        Returns:
            32-bit encoded object ID
        """
        type_shift = self.bit_fields.get("type", {}).get("shift", 30)
        type_max = self.bit_fields.get("type", {}).get("max", 0x3)
        cls_shift = self.bit_fields.get("cls", {}).get("shift", 21)
        cls_max = self.bit_fields.get("cls", {}).get("max", 0x1FF)
        dtype_shift = self.bit_fields.get("dtype", {}).get("shift", 16)
        dtype_max = self.bit_fields.get("dtype", {}).get("max", 0xF)
        flags_shift = self.bit_fields.get("flags", {}).get("shift", 14)
        flags_max = self.bit_fields.get("flags", {}).get("max", 0x3)
        priv_shift = self.bit_fields.get("priv", {}).get("shift", 0)
        priv_max = self.bit_fields.get("priv", {}).get("max", 0x3FFF)

        return (
            ((obj_type & type_max) << type_shift)
            | ((cls & cls_max) << cls_shift)
            | ((dtype & dtype_max) << dtype_shift)
            | ((flags & flags_max) << flags_shift)
            | ((priv & priv_max) << priv_shift)
        )

    def format_compact(self, decoded: DecodedObjectId) -> str:
        """Return formatted decoded ID in compact form."""
        if decoded.cls_name:
            return (
                f"0x{decoded.objid:08X} ({decoded.type_name}/"
                f"{decoded.cls_name}:{decoded.priv}, {decoded.dtype_name})"
            )
        else:
            return (
                f"0x{decoded.objid:08X} ({decoded.type_name}/"
                f"CLS{decoded.cls}:{decoded.priv}, {decoded.dtype_name})"
            )

    def format_detailed(self, decoded: DecodedObjectId) -> str:
        """Return formatted decoded ID in detailed form."""
        output = [
            f"Object ID: 0x{decoded.objid:08X}",
            f"  Type: {decoded.type_name} ({decoded.type})",
            f"  Class: {decoded.cls_name or f'Unknown(CLS{decoded.cls})'} "
            f"(ID: {decoded.cls})",
            f"  Data Type: {decoded.dtype_name} ({decoded.dtype}) "
            f"- {decoded.dtype_size} bits",
            f"  Instance/Private ID: {decoded.priv}",
            f"  Flags: 0x{decoded.flags:02X}",
            f"  Extension: {decoded.ext}",
        ]
        return "\n".join(output)


def main() -> int:  # pragma: no cover
    """Demonstrate example usage and testing."""
    import sys

    # Initialize decoder with header-derived definitions
    decoder = ObjectIdDecoder()

    if len(sys.argv) < 2:
        print("Usage: objectid.py <objid_hex> [<objid_hex> ...]")
        print("\nExample:")
        print("  objectid.py 0x00010001")
        print("  objectid.py 0x00010001 0x00020002 0x00030003")
        return 1

    for arg in sys.argv[1:]:
        try:
            # Parse hex or decimal
            if arg.startswith(("0x", "0X")):
                objid = int(arg, 16)
            else:
                objid = int(arg)

            decoded = decoder.decode(objid)

            print(decoder.format_detailed(decoded))
            print()

        except ValueError:
            print(f"Error: Invalid object ID: {arg}")
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
