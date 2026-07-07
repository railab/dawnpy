# tools/dawnpy/src/dawnpy/commands/cmd_desc_valid.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-valid`` CLI command."""

import json
from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.validation.validate import (
    validate_config,
    validate_config_json,
)


@click.command(name="desc-valid")
@click.argument(
    "config_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Only show errors, suppress other output",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed information",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Emit a machine-readable JSON validation report",
)
@pass_environment
def cmd_desc_valid(
    ctx: Environment,
    config_dir: str,
    quiet: bool,
    verbose: bool,
    json_output: bool,
) -> bool:
    """
    Validate descriptor and configuration in a directory.

    CONFIG_DIR should contain descriptor.cxx and defconfig files.
    """
    del ctx
    if json_output:
        data = validate_config_json(Path(config_dir))
        click.echo(json.dumps(data, indent=2))
        return bool(data["valid"])
    return validate_config(Path(config_dir), quiet, verbose)
