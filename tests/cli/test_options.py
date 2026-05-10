# tools/dawnpy/tests/test_cli_options.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for shared CLI option helpers."""

import logging

import click
import pytest

from dawnpy.cli.options import build_kconfig_overrides, configure_cli_logging
from dawnpy.logger import logger


def test_configure_cli_logging_sets_debug_level():
    """Debug mode should configure the shared dawnpy logger."""
    configure_cli_logging(True)

    assert logger.level == logging.DEBUG


def test_build_kconfig_overrides_single_value():
    """One value should apply to every descriptor."""
    overrides = build_kconfig_overrides(
        ["a.yaml", "b.yaml"], "CONFIG_NODE", "1"
    )

    assert overrides == [{"CONFIG_NODE": "1"}, {"CONFIG_NODE": "1"}]


def test_build_kconfig_overrides_expands_single_descriptor():
    """Multiple values for one descriptor should create multiple overrides."""
    overrides = build_kconfig_overrides(["a.yaml"], "CONFIG_NODE", "1,2")

    assert overrides == [{"CONFIG_NODE": "1"}, {"CONFIG_NODE": "2"}]


def test_build_kconfig_overrides_validates_pairing():
    """Partial Kconfig override options should fail clearly."""
    with pytest.raises(click.ClickException):
        build_kconfig_overrides(["a.yaml"], "CONFIG_NODE", None)


def test_build_kconfig_overrides_empty_inputs():
    """Missing descriptor or override values produce no override mapping."""
    assert build_kconfig_overrides([], "CONFIG_NODE", "1") is None
    assert build_kconfig_overrides(["a.yaml"], None, None) is None


def test_build_kconfig_overrides_rejects_empty_values():
    """Empty comma-separated values are invalid."""
    with pytest.raises(click.ClickException, match="No Kconfig values"):
        build_kconfig_overrides(["a.yaml"], "CONFIG_NODE", ",")


def test_build_kconfig_overrides_rejects_mismatched_values():
    """Multi-descriptor sweeps need one value or one value per descriptor."""
    with pytest.raises(click.ClickException, match="must be 1 or match"):
        build_kconfig_overrides(["a.yaml", "b.yaml"], "CONFIG_NODE", "1,2,3")


def test_build_kconfig_overrides_pairs_descriptor_values():
    """One value per descriptor should preserve descriptor order."""
    overrides = build_kconfig_overrides(
        ["a.yaml", "b.yaml"], "CONFIG_NODE", "1,2"
    )

    assert overrides == [{"CONFIG_NODE": "1"}, {"CONFIG_NODE": "2"}]
