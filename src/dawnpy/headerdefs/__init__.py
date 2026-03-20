# tools/dawnpy/src/dawnpy/headerdefs/__init__.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Runtime loading of Dawn constant definitions from C++ headers.

The package is split into focused submodules - see ``_paths``, ``_parser``,
``_constants``, ``_typespec``, ``_components``, ``_nimble``, ``_enums``, and
``_loader``. Internal helpers live in their respective submodule and are
NOT re-exported here; import them from the submodule directly when needed.
"""

from ._components import (
    load_header_component_defs,
    load_header_metadata_defs,
)
from ._enums import (
    load_header_cfg_id,
    load_header_enum_map,
    load_header_enum_value_ids,
    load_header_object_class_name,
)
from ._loader import load_header_defs
from ._nimble import load_header_nimble_service_defs
from ._paths import HeaderDefsError, find_repo_root
from ._simple_proto import load_simple_proto_constants
from ._typespec import load_header_type_defs

__all__ = [
    "HeaderDefsError",
    "find_repo_root",
    "load_header_defs",
    "load_header_type_defs",
    "load_header_component_defs",
    "load_header_metadata_defs",
    "load_header_nimble_service_defs",
    "load_header_enum_map",
    "load_header_cfg_id",
    "load_header_object_class_name",
    "load_header_enum_value_ids",
    "load_simple_proto_constants",
]
