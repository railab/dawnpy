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
    generate_descriptor_binaries,
)


def _slot_output_path(
    output: Path | None, yaml_dir: Path, slot_idx: int, num_slots: int
) -> Path:
    """Compute output path for a given slot.

    Single-slot: ``-o`` or ``descriptor.bin`` (no slot suffix).
    Multi-slot:  ``-o base.bin`` → ``base_slot0.bin``, ``base_slot1.bin``, ...
                 default → ``descriptor_slot0.bin``, etc.
    """
    if num_slots == 1:
        return output if output is not None else (yaml_dir / "descriptor.bin")

    if output is not None:
        stem = output.stem
        suffix = output.suffix
        return output.parent / f"{stem}_slot{slot_idx}{suffix}"

    return yaml_dir / f"descriptor_slot{slot_idx}.bin"


@click.command(name="desc-bin")
@click.argument(
    "yaml_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    help=(
        "Output file path. For multi-slot YAML, this is used as a prefix "
        "(e.g. -o desc.bin → desc_slot0.bin, desc_slot1.bin). "
        "Default: descriptor.bin (single) or descriptor_slotN.bin (multi)."
    ),
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

    For multi-descriptor YAML (``descriptor0:``, ``descriptor1:``, ...),
    one binary file is produced per slot.
    """
    del ctx
    yaml_path = Path(yaml_file)
    output_arg = Path(output) if output else None

    binaries = generate_descriptor_binaries(yaml_path, kconfig)
    num_slots = len(binaries)

    for slot_idx, blob in sorted(binaries.items()):
        output_path = _slot_output_path(
            output_arg, yaml_path.parent, slot_idx, num_slots
        )
        output_path.write_bytes(blob)
        label = f"slot {slot_idx}" if num_slots > 1 else ""
        click.echo(f"[OK] Generated binary {label}: {output_path}")
        click.echo(f"  Size: {len(blob)} bytes")

    return True
