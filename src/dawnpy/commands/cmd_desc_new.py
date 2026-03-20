# tools/dawnpy/src/dawnpy/commands/cmd_desc_new.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Create a new descriptor template file."""

from __future__ import annotations

from pathlib import Path

import click


def _normalize_name(name: str) -> str:
    return name if name.endswith(".yaml") else f"{name}.yaml"


def _format_title(name: str) -> str:
    stem = Path(name).stem
    title = stem.replace("_", " ").replace("-", " ").strip()
    if not title:
        return "New Descriptor"
    return " ".join(word.capitalize() for word in title.split())


def _render_descriptor(name: str) -> str:
    title = _format_title(name)
    return f"""metadata:
  title: {title}
  version: "1.0"
  description: |
    New descriptor placeholder.
ios: []
programs: []
protocols: []
"""


def _doc_reminder(path: Path) -> None:
    rel_path = path.as_posix()
    msg = [
        "Reminder:",
        f"- Add {rel_path} to Documentation/examples/descriptors.rst",
        "  (feature index + catalog entry).",
        "- If this descriptor maps to a board example, update the board docs",
        "  under Documentation/examples/boards/..",
        "  and keep build manifests (tools/config-build-all.txt) in sync.",
    ]
    for line in msg:
        click.echo(line)


@click.command(name="desc-new")
@click.argument("name", type=str)
@click.option(
    "--out-dir",
    "out_dir",
    default="descriptors/examples",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Directory where the YAML placeholder will be written",
)
def cmd_desc_new(name: str, out_dir: Path) -> None:
    """Create a new descriptor YAML placeholder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / _normalize_name(name)

    if target.exists():
        raise click.ClickException(f"Descriptor already exists: {target}")

    target.write_text(_render_descriptor(name), encoding="utf-8")
    click.echo(f"Created descriptor placeholder: {target}")
    _doc_reminder(target)
