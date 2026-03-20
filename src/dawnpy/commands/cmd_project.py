# tools/dawnpy/src/dawnpy/commands/cmd_project.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""OOT project scaffolding commands."""

import os
from pathlib import Path

import click

from dawnpy import templates
from dawnpy.config import load_dawnrc, write_dawnrc
from dawnpy.sources import DawnSourcesMissing


def _looks_like_dawn_root(path: Path) -> bool:
    return (
        (path / "dawn").is_dir()
        and (path / "Documentation").is_dir()
        and (path / "boards").is_dir()
    )


def _infer_dawn_root(target_root: Path) -> Path | None:
    candidates = [
        target_root.parent / "dawn-src",
        target_root.parent,
        Path.cwd() / "dawn-src",
        Path.cwd(),
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if _looks_like_dawn_root(candidate):
            return candidate
    return None


@click.group(name="project")
def cmd_project() -> None:
    """Scaffold and inspect dawnpy project templates."""


@cmd_project.command(name="list")
def cmd_project_list() -> None:
    """List bundled project templates."""
    for name, description in templates.list_templates(
        templates.PROJECT_KIND
    ).items():
        click.echo(f"{name}: {description}")


@cmd_project.command(name="new")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--template", default="minimal-sim", show_default=True)
@click.option("--dawn-root", type=click.Path(path_type=Path))
@click.option("--name", type=str)
def cmd_project_new(
    path: Path,
    template: str,
    dawn_root: Path | None,
    name: str | None,
) -> None:
    """Create a new out-of-tree Dawn project."""
    target_root = path.resolve()
    if target_root.exists() and any(target_root.iterdir()):
        raise click.ClickException(
            f"Refusing to scaffold into a non-empty directory: {target_root}"
        )

    rc = load_dawnrc(Path.cwd())
    resolved_dawn_root = (
        dawn_root.resolve() if dawn_root else rc.get_path("paths", "dawn_root")
    )
    if resolved_dawn_root is None:
        resolved_dawn_root = _infer_dawn_root(target_root)
    if resolved_dawn_root is None:
        raise DawnSourcesMissing("Could not resolve Dawn root.")

    project_name = name or target_root.name
    try:
        templates.render_tree(
            kind=templates.PROJECT_KIND,
            name=template,
            target_root=target_root,
            substitutions={"PROJECT_NAME": project_name},
        )
    except templates.UnknownTemplateError as exc:
        raise click.ClickException(str(exc)) from exc

    project_rc = {
        "paths": {
            "dawn_root": os.path.relpath(resolved_dawn_root, target_root),
        },
        "project": {
            "oot": True,
            "types_from": "dawnpy_types.py",
        },
    }
    write_dawnrc(target_root / ".dawnrc", project_rc)
    click.echo(f"Scaffolded {template} project at {target_root}")
