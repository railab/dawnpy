# tools/dawnpy/src/dawnpy/cli/main.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containint the CLI logic for dawnpy."""

import logging
from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.config import load_dawnrc
from dawnpy.descriptor.definitions.registry import (
    apply_registration_to_module,
    load_registrations_from_path,
)
from dawnpy.logger import logger
from dawnpy.plugins_loader import commands_list

###############################################################################
# Function: main
###############################################################################


@click.group()
@click.option(
    "--debug/--no-debug",
    default=False,
    is_flag=True,
    envvar="DAWNPY_DEBUG",
)
@click.option(
    "--types-from",
    "types_from",
    multiple=True,
    type=click.Path(exists=True, dir_okay=True, file_okay=True),
    help=(
        "Path to a Python file or package directory whose module-level "
        "'registration' (or 'registrations' iterable) provides additional "
        "TypeRegistration entries for the descriptor type registry. "
        "May be passed multiple times. Loaded directly, no install needed. "
        "See Documentation/api/oot.rst."
    ),
)
@pass_environment
def main(
    ctx: Environment,
    debug: bool,
    types_from: tuple[str, ...],
) -> bool:
    """Dawnpy - Command-line tool for Dawn."""
    ctx.debug = debug
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )
    logger.setLevel(log_level)

    resolved_types_from: list[str] = []
    seen_paths: set[str] = set()
    for path in [
        *types_from,
        *[str(item) for item in load_dawnrc().implicit_types_from()],
    ]:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        resolved_types_from.append(path)

    for path in resolved_types_from:
        for reg in load_registrations_from_path(Path(path)):
            apply_registration_to_module(reg)
            logger.info(
                "Applied --types-from registration '%s' from %s "
                "(io=%d prog=%d proto=%d)",
                reg.name,
                path,
                len(reg.io_types),
                len(reg.prog_types),
                len(reg.proto_types),
            )

    click.get_current_context().call_on_close(cli_on_close)

    return True


@pass_environment
def cli_on_close(ctx: Environment) -> bool:
    """Handle requested plugins on click close."""
    return True


###############################################################################
# Function: click_final_init
###############################################################################


def click_final_init() -> None:
    """Handle final Click initialization."""
    # add interfaces
    for cmd in commands_list:
        main.add_command(cmd)


# final click initialization
click_final_init()
