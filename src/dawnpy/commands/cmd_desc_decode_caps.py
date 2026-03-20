# tools/dawnpy/src/dawnpy/commands/cmd_desc_decode_caps.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-decode-caps`` CLI command.

All blob parsing and report formatting lives in
:mod:`dawnpy.descriptor.reports.capabilities_blob`. This module wires CLI
args to that entry point.
"""

from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.encoding.packager import parse_hex_file_text
from dawnpy.descriptor.reports.capabilities_blob import (
    build_capabilities_report,
)


@click.command(name="desc-decode-caps")
@click.argument("input_data", type=str)
@click.option(
    "--hex-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Read capabilities blob as hex text from file.",
)
@pass_environment
def cmd_desc_decode_caps(
    ctx: Environment,
    input_data: str,
    hex_file: str,
) -> bool:
    """
    Decode Dawn capabilities IO blob into human-readable report.

    INPUT_DATA must be a binary file path unless ``--hex-file`` is used.
    """
    del ctx
    if hex_file:
        raw_hex = Path(hex_file).read_text(encoding="utf-8")
        blob = parse_hex_file_text(raw_hex)
    else:
        path = Path(input_data)
        if not path.exists():
            raise click.ClickException(f"Input file not found: {path}")
        blob = path.read_bytes()

    for line in build_capabilities_report(blob):
        click.echo(line)
    return True
