# tools/dawnpy/src/dawnpy/commands/cmd_init.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Workspace bootstrap command for dawnpy."""

from pathlib import Path

import click

from dawnpy.dawn.workspace_init import InitRequest, run_init_request


@click.command(name="init")
@click.argument(
    "path",
    required=False,
    default=".",
    type=click.Path(path_type=Path),
)
@click.option(
    "--layout",
    type=click.Choice(["workspace", "inline"], case_sensitive=False),
    default="workspace",
    show_default=True,
)
@click.option("--dawn-ref", default="latest", show_default=True)
@click.option(
    "--dawn-url",
    default="https://github.com/railab/dawn",
    show_default=True,
)
@click.option(
    "--dawn-source",
    type=click.Choice(["release", "git"], case_sensitive=False),
    default="release",
    show_default=True,
)
@click.option("--with-nuttx/--no-nuttx", default=True, show_default=True)
@click.option("--nuttx-ref", default="master", show_default=True)
@click.option(
    "--nuttx-url",
    default="https://github.com/railab/nuttx",
    show_default=True,
)
@click.option(
    "--nuttx-apps-url",
    default="https://github.com/railab/nuttx-apps",
    show_default=True,
)
@click.option("--nuttx-apps-ref", default="master", show_default=True)
@click.option(
    "--write-global-dawnrc",
    is_flag=True,
    help="Write ~/.config/dawn/dawnrc for the bootstrapped sources",
)
@click.option("--force", is_flag=True, help="Overwrite an existing layout")
def cmd_init(
    path: Path,
    layout: str,
    dawn_ref: str,
    dawn_url: str,
    dawn_source: str,
    with_nuttx: bool,
    nuttx_ref: str,
    nuttx_url: str,
    nuttx_apps_url: str,
    nuttx_apps_ref: str,
    write_global_dawnrc: bool,
    force: bool,
) -> None:
    """Bootstrap a Dawn workspace or inline install."""
    run_init_request(
        InitRequest(
            path=path,
            layout=layout,
            dawn_ref=dawn_ref,
            dawn_url=dawn_url,
            dawn_source=dawn_source,
            with_nuttx=with_nuttx,
            nuttx_ref=nuttx_ref,
            nuttx_url=nuttx_url,
            nuttx_apps_url=nuttx_apps_url,
            nuttx_apps_ref=nuttx_apps_ref,
            write_global_dawnrc=write_global_dawnrc,
            force=force,
        )
    )
