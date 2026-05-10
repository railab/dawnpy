# tools/dawnpy/tests/test_cmd_dawn.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the Dawn CLI command module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.commands.cmd_batch import cmd_batch
from dawnpy.commands.cmd_build import cmd_build
from dawnpy.commands.cmd_kconfig import cmd_kconfig
from dawnpy.dawn.workflows import (
    BatchRequest,
    BuildRequest,
    KconfigSweepRequest,
)

if TYPE_CHECKING:
    import pytest


def test_cmd_build_batch_kconfig_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    def record(name: str):
        def _call(*args, **kwargs):
            calls.append((name, args))

        return _call

    monkeypatch.setattr(
        "dawnpy.commands.cmd_build.run_build_request", record("build")
    )
    monkeypatch.setattr(
        "dawnpy.commands.cmd_batch.run_batch_request", record("batch")
    )
    monkeypatch.setattr(
        "dawnpy.commands.cmd_kconfig.run_kconfig_request",
        record("kconfig"),
    )

    cmd_build.callback(
        "build",
        "boards/sim/configs/tests",
        "Ninja",
        ("CC=gcc",),
        ("TEST=1",),
        ("CONFIG_X=1",),
        4,
        None,
        None,
        None,
        False,
        False,
        False,
    )
    cmd_batch.callback(
        "configs.txt",
        "Ninja",
        (),
        (),
        None,
        "build",
        False,
        False,
        False,
    )
    cmd_kconfig.callback(
        "boards/sim/configs/tests",
        "CONFIG_X",
        "1,2",
        "Ninja",
        (),
        (),
        None,
        "build",
        False,
        False,
        False,
    )

    assert [call[0] for call in calls] == ["build", "batch", "kconfig"]
    assert isinstance(calls[0][1][0], BuildRequest)
    assert isinstance(calls[1][1][0], BatchRequest)
    assert isinstance(calls[2][1][0], KconfigSweepRequest)
