# tools/dawnpy/src/dawnpy/commands/cmd_desc_gen.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-gen`` CLI command."""

from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.generation.generator import generate_descriptor
from dawnpy.descriptor.validation.validate import (
    GENERATE_CRC_POLICY_MSG,
    validate_config,
    validate_runtime_descriptor,
)


@click.command(name="desc-gen")
@click.argument(
    "yaml_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Output file path (default: descriptor.cxx in same directory)",
)
@click.option(
    "--kconfig",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to Kconfig .config/defconfig for variable resolution",
)
@pass_environment
def cmd_desc_gen(
    ctx: Environment,
    yaml_file: str,
    output: str,
    kconfig: str,
) -> bool:
    r"""
    Generate C++ descriptor from YAML file.

    YAML_FILE should contain the descriptor specification.

    \b
    Example:
        dawnpy desc-gen descriptor.yaml
        dawnpy desc-gen descriptor.yaml -o output.cxx

    Note:
        This command keeps the C++ footer checksum placeholder. Firmware
        fills/checks descriptor CRC at runtime.
    """
    yaml_path = Path(yaml_file)
    output_path = output or str(yaml_path.parent / "descriptor.cxx")

    try:
        generate_descriptor(str(yaml_path), output_path, kconfig_path=kconfig)
    except Exception as exc:
        click.echo(f"Error generating descriptor: {exc}", err=True)
        if ctx.debug:  # pragma: no cover
            raise
        return False

    click.echo(f"[OK] Generated: {output_path}")
    click.echo(GENERATE_CRC_POLICY_MSG)

    config_path = yaml_path.parent
    if (config_path / "defconfig").exists():
        valid = validate_config(config_path, quiet=False, verbose=False)
    else:
        valid = validate_runtime_descriptor(
            config_path=config_path, quiet=False
        )

    if not valid:
        click.echo("Descriptor generated, but validation failed.", err=True)
    return valid
