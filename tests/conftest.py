#
# SPDX-License-Identifier: Apache-2.0
#

"""Global test guards for standalone dawnpy unit tests."""

import pytest


def blocked_repo_root_lookup() -> None:
    pytest.fail(
        "Unit tests must not discover or read Dawn sources. "
        "Mock the relevant dawnpy.headerdefs loader in the test instead."
    )


@pytest.fixture
def source_free_headers(monkeypatch):
    """Install source-free descriptor headers for tests outside descriptor/."""
    import dawnpy.headerdefs.bundle as header_bundle
    from dawnpy.descriptor.handlers import proto_nimble
    from tests.descriptor.conftest import (
        minimal_header_definition_set,
        minimal_nimble_service_defs,
    )

    monkeypatch.setattr(
        header_bundle,
        "load_header_bundle",
        minimal_header_definition_set,
    )
    proto_nimble._nimble_service_defs.cache_clear()
    monkeypatch.setattr(
        proto_nimble,
        "load_header_nimble_service_defs",
        minimal_nimble_service_defs,
    )
    yield minimal_header_definition_set()
    proto_nimble._nimble_service_defs.cache_clear()


@pytest.fixture(autouse=True)
def block_dawn_source_reads(monkeypatch, request):
    """Prevent tests from accidentally reading the real Dawn checkout."""
    if "headerdefs" in request.node.path.parts:
        yield
        return

    import dawnpy.headerdefs._paths as headerdefs_paths

    monkeypatch.setattr(
        headerdefs_paths, "_repo_root_from_here", blocked_repo_root_lookup
    )

    import dawnpy.descriptor.definitions.registry as registry

    registry.reset_type_registry()
    yield
    registry.reset_type_registry()
