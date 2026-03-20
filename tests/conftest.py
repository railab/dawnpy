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


@pytest.fixture(autouse=True)
def block_dawn_source_reads(monkeypatch, request):
    """Prevent tests from accidentally reading the real Dawn checkout."""
    if request.node.path.name == "test_headerdefs.py":
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
