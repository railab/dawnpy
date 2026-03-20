# tools/dawnpy/src/dawnpy/descriptor/proto_caps.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Protocol capability helpers for client tooling."""

from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY


def is_multi_device(proto_type: str) -> bool:
    """Return True if protocol supports multiple descriptors."""
    handler = PROTO_HANDLER_REGISTRY.get(proto_type)
    if handler is None:
        return False
    return handler.is_multi_device()


def validate_descriptor_args(proto_type: str, descriptors: list[str]) -> None:
    """Validate descriptor list for a protocol."""
    if not descriptors:
        raise ValueError("At least one descriptor must be provided")
    if not is_multi_device(proto_type) and len(descriptors) > 1:
        raise ValueError(
            f"Protocol '{proto_type}' supports only one descriptor"
        )
