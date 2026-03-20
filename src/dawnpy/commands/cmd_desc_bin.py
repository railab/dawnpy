# tools/dawnpy/src/dawnpy/commands/cmd_desc_bin.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-bin`` CLI command.

All serialization logic lives in ``descriptor.encoding``. This module wires
CLI args to that entry point.
"""

from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.encoding.binary_serializer import (
    generate_descriptor_binary,
)


@click.command(name="desc-bin")
@click.argument(
    "yaml_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Output file path (default: descriptor.bin in same directory)",
)
@click.option(
    "--kconfig",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to Kconfig .config/defconfig for variable resolution",
)
@pass_environment
def cmd_desc_bin(
    ctx: Environment,
    yaml_file: str,
    output: str,
    kconfig: str,
) -> bool:
    r"""
    Generate raw descriptor binary from YAML file.

    This command serializes descriptor words directly in Python (little-endian)
    and fills footer CRC32. No host C++ compilation is required.
    """
    del ctx
    yaml_path = Path(yaml_file)
    output_path = (
        Path(output) if output else (yaml_path.parent / "descriptor.bin")
    )
    final_bin = generate_descriptor_binary(yaml_path, kconfig)

    output_path.write_bytes(final_bin)
    click.echo(f"[OK] Generated binary: {output_path}")
    click.echo(f"  Size: {len(final_bin)} bytes")
    return True
