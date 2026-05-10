# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for runtime C++ header definition loading."""

from pathlib import Path

import pytest

import dawnpy.descriptor.definitions.io_family as builtin_io_mod
import dawnpy.descriptor.definitions.prog_family as builtin_prog_mod
import dawnpy.descriptor.definitions.proto_family as builtin_proto_mod
import dawnpy.headerdefs as headerdefs
import dawnpy.headerdefs._components as headerdefs_components_mod
import dawnpy.headerdefs._constants as headerdefs_constants_mod
import dawnpy.headerdefs._enums as headerdefs_enums_mod
import dawnpy.headerdefs._loader as headerdefs_loader_mod
import dawnpy.headerdefs._nimble as headerdefs_nimble_mod
import dawnpy.headerdefs._parser as headerdefs_parser_mod
import dawnpy.headerdefs._paths as headerdefs_paths_mod
import dawnpy.headerdefs._typespec as headerdefs_types_mod
import dawnpy.headerdefs.bundle as header_bundle_mod
import dawnpy.objectid as objectid_mod
from dawnpy.sources import DawnSourcesMissing
from tests.headerdefs.helpers import blank_objectid_decoder, cache_clear
from tests.headerdefs.helpers import definition_set as _definition_set
from tests.headerdefs.helpers import empty_type_defs as _empty_type_defs
from tests.headerdefs.helpers import enum_type_defs as _enum_type_defs
from tests.headerdefs.helpers import patch_builtin_type_indexers
from tests.headerdefs.helpers import stub_class_header as _stub_class_header
from tests.headerdefs.helpers import stub_enum_header as _stub_enum_header
from tests.headerdefs.helpers import ts_node


@pytest.fixture(autouse=True)
def clear_header_caches():
    """Ensure header loader caches are cleared per test."""
    cache_clear(header_bundle_mod.load_header_bundle)
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()
    headerdefs.load_simple_proto_constants.cache_clear()
    yield
    cache_clear(header_bundle_mod.load_header_bundle)
    headerdefs.load_header_defs.cache_clear()
    headerdefs.load_header_type_defs.cache_clear()
    headerdefs.load_header_component_defs.cache_clear()
    headerdefs.load_header_metadata_defs.cache_clear()
    headerdefs.load_header_nimble_service_defs.cache_clear()
    headerdefs.load_header_enum_map.cache_clear()
    headerdefs.load_header_cfg_id.cache_clear()
    headerdefs.load_header_object_class_name.cache_clear()
    headerdefs.load_header_enum_value_ids.cache_clear()
    headerdefs.load_simple_proto_constants.cache_clear()


@pytest.fixture(autouse=True)
def block_live_repo_lookup(monkeypatch, request):
    """Prevent unit tests from discovering the real Dawn checkout."""
    allowed = {
        "test_repo_root_from_file_search_path",
        "test_repo_root_from_cwd_search_path",
        "test_repo_root_from_nested_layout",
        "test_repo_root_returns_none_when_all_search_paths_fail",
        "test_find_repo_root_delegates",
    }
    if request.node.name not in allowed:
        monkeypatch.setattr(
            headerdefs_paths_mod, "_repo_root_from_here", lambda: None
        )


def _header_type_defs(defs):
    return _definition_set(type_defs=defs)


__all__ = [name for name in globals() if not name.startswith("__")]
