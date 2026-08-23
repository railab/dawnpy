# tools/dawnpy/src/dawnpy/commands/cmd_desc_compat.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-compat`` CLI command.

Compares a descriptor against a target's capabilities IO blob. The
comparison itself lives in
:mod:`dawnpy.descriptor.validation.compat`; this module wires CLI args
to that entry point.
"""

import copy
from pathlib import Path

import click

from dawnpy.cli.environment import Environment, pass_environment
from dawnpy.descriptor.encoding.packager import parse_hex_file_text
from dawnpy.descriptor.reports.graph import build_descriptor_graph
from dawnpy.descriptor.support.vars import load_yaml_with_vars
from dawnpy.descriptor.validation.compat import (
    check_compatibility,
    format_report,
)


def _read_blob(caps: str, hex_file: str | None) -> bytes:
    """Return the capabilities blob from a binary or hex source."""
    if hex_file:
        return parse_hex_file_text(Path(hex_file).read_text(encoding="utf-8"))
    path = Path(caps)
    if not path.exists():
        raise click.ClickException(f"Capabilities file not found: {path}")
    return path.read_bytes()


@click.command(name="desc-compat")
@click.argument(
    "yaml_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.argument("caps", type=str, required=False)
@click.option(
    "--hex-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Read capabilities blob as hex text from file.",
)
@click.option(
    "--slot", type=int, default=None, help="Target descriptor slot index."
)
@click.option(
    "--descriptor",
    "descriptor_name",
    default="descriptor0",
    help="Descriptor slot key for multi-descriptor YAML files.",
)
@pass_environment
def cmd_desc_compat(
    ctx: Environment,
    yaml_file: str,
    caps: str,
    hex_file: str,
    slot: int,
    descriptor_name: str,
) -> bool:
    """
    Check whether a target firmware can run a descriptor.

    YAML_FILE is the descriptor to upload. CAPS is the capabilities IO
    blob read from the target, unless ``--hex-file`` is used.

    A descriptor is data and may be written long after the firmware was
    built, so the target advertises the object classes and dtypes it was
    compiled with. This reports every class or dtype the descriptor needs
    that the target does not provide.
    """
    del ctx
    if not caps and not hex_file:
        raise click.ClickException("Provide CAPS or --hex-file")

    blob = _read_blob(caps, hex_file)
    spec = load_yaml_with_vars(yaml_file)
    if descriptor_name in spec:
        spec = spec[descriptor_name]

    graph = build_descriptor_graph(copy.deepcopy(spec), descriptor_name)
    objids = {
        node.id: node.objid for node in graph.nodes if node.objid is not None
    }
    if not objids:
        raise click.ClickException(
            f"No decodable objects found in {yaml_file}"
        )

    result = check_compatibility(objids, blob, slot=slot)
    for line in format_report(result):
        click.echo(line)
    if not result.compatible:
        raise click.ClickException("Descriptor is not compatible with target")
    return True
