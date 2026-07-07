# tools/dawnpy/src/dawnpy/commands/cmd_desc_graph.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-graph`` CLI command."""

from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.reports.graph import load_descriptor_graph


@click.command(name="desc-graph")
@click.argument(
    "yaml_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a file instead of stdout",
)
@click.option(
    "--kconfig",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Kconfig .config/defconfig used to resolve descriptor vars",
)
@click.option(
    "--indent",
    type=int,
    default=2,
    help="JSON indentation width",
)
@pass_environment
def cmd_desc_graph(
    ctx: Environment,
    yaml_path: str,
    output: str | None,
    kconfig: str | None,
    indent: int,
) -> bool:
    """
    Export a descriptor YAML file as a machine-readable JSON graph.

    YAML_PATH is the descriptor file to export.
    """
    del ctx
    try:
        doc = load_descriptor_graph(yaml_path, kconfig_path=kconfig)
    except Exception as exc:
        click.echo(f"Error: cannot build graph: {exc}", err=True)
        return False
    payload = doc.model_dump_json(indent=indent)
    if output is None:
        click.echo(payload)
    else:
        Path(output).write_text(payload + "\n")
        click.echo(f"Graph written to {output}", err=True)
    return True
