# tools/dawnpy/src/dawnpy/cli/options.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared Click option helpers for dawnpy tools."""

import logging

import click

from dawnpy.logger import logger


def configure_cli_logging(debug: bool) -> None:
    """Configure package CLI logging consistently."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )
    logger.setLevel(log_level)


def build_kconfig_overrides(
    descriptors: list[str],
    kconfig_var: str | None,
    kconfig_values: str | None,
) -> list[dict[str, object]] | None:
    """Build per-descriptor Kconfig override mappings."""
    if not descriptors:
        return None
    if not kconfig_var and not kconfig_values:
        return None
    if not kconfig_var or not kconfig_values:
        raise click.ClickException(
            "Both --kconfig-var and --kconfig-values are required"
        )

    values = [
        value.strip() for value in kconfig_values.split(",") if value.strip()
    ]
    if not values:
        raise click.ClickException("No Kconfig values provided")

    if len(values) not in (1, len(descriptors)) and len(descriptors) != 1:
        raise click.ClickException(
            "Number of --kconfig-values must be 1 or match descriptor count"
        )

    if len(values) == 1:
        return [{kconfig_var: values[0]} for _ in descriptors]

    if len(values) != len(descriptors):
        return [{kconfig_var: value} for value in values]

    return [{kconfig_var: values[idx]} for idx in range(len(descriptors))]
