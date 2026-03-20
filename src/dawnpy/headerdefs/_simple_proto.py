# tools/dawnpy/src/dawnpy/headerdefs/_simple_proto.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""SimpleBase protocol constant lookup from C++ headers."""

from functools import lru_cache

from ._parser import (
    _extract_constexpr_values_from_tree,
    _extract_enum_constants_from_tree,
    _parse_cpp_header,
)
from ._paths import _require_repo_root

_HEADER_REL = "dawn/include/dawn/proto/simplebase.hxx"
_ENUM_PREFIXES = ("CMD_", "STATUS_", "IO_TYPE_")
_CONSTEXPR_PREFIXES = ("FRAME_",)


@lru_cache(maxsize=None)
def load_simple_proto_constants() -> dict[str, int]:
    """Load CProtoSimpleBase frame/cmd/status/io-type constants.

    :return: Mapping of identifier (e.g. ``CMD_PING``, ``STATUS_OK``,
        ``FRAME_SYNC``) to its integer value as declared in
        ``simplebase.hxx``.
    """
    root = _require_repo_root()
    source, tree_root = _parse_cpp_header(root / _HEADER_REL)

    enums = _extract_enum_constants_from_tree(
        source, tree_root, _ENUM_PREFIXES
    )
    constexprs = _extract_constexpr_values_from_tree(source, tree_root)
    frame_consts = {
        name: value
        for name, value in constexprs.items()
        if any(name.startswith(prefix) for prefix in _CONSTEXPR_PREFIXES)
    }

    out: dict[str, int] = {}
    out.update(frame_consts)
    out.update(enums)
    return out
