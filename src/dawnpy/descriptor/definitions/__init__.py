# tools/dawnpy/src/dawnpy/descriptor/definitions/__init__.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor object model, schemas, and built-in type registrations."""

from dawnpy.descriptor.definitions.type_info import TypeRegistration
from dawnpy.headerdefs.bundle import HeaderBundle


def load_builtin_registrations(
    defs: HeaderBundle,
) -> list[TypeRegistration]:
    """Build the list of built-in :class:`TypeRegistration` objects."""
    from dawnpy.descriptor.definitions.io_family import (
        build_registration as _build_io,
    )
    from dawnpy.descriptor.definitions.prog_family import (
        build_registration as _build_prog,
    )
    from dawnpy.descriptor.definitions.proto_family import (
        build_registration as _build_proto,
    )

    return [_build_io(defs), _build_prog(defs), _build_proto(defs)]


__all__ = ["load_builtin_registrations"]
