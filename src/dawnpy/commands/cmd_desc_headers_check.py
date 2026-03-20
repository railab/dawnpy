# tools/dawnpy/src/dawnpy/commands/cmd_desc_headers_check.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""``dawnpy desc-headers-check`` CLI command.

All the discovery + validation logic lives in
:mod:`dawnpy.descriptor.validation.headers_check`.
"""

import click

from dawnpy.descriptor.validation.headers_check import (
    check_inline_field_schemas,
    collect_header_summary,
)
from dawnpy.headerdefs import HeaderDefsError
from dawnpy.sources import DawnSourcesMissing


@click.command(name="desc-headers-check")
@click.option(
    "--strict",
    is_flag=True,
    help=(
        "Also verify every cpp_helper and enum_prefix declared on the "
        "handlers under descriptor/handlers/ resolves via headerdefs."
    ),
)
def cmd_desc_headers_check(strict: bool) -> None:
    """Validate runtime C++ header discovery and parsing."""
    try:
        summary = collect_header_summary()
    except DawnSourcesMissing:
        raise
    except HeaderDefsError as exc:
        raise click.ClickException(f"Header parse failed: {exc}") from exc

    click.echo(f"Header root: {summary.root}")
    click.echo(
        "Loaded constants: "
        f"dtype={summary.dtype_count}, "
        f"io_classes={summary.io_class_count}, "
        f"prog_classes={summary.prog_class_count}, "
        f"proto_classes={summary.proto_class_count}"
    )
    click.echo(
        "Loaded type maps: "
        f"io_types={summary.io_types_count}, "
        f"prog_types={summary.prog_types_count}, "
        f"proto_types={summary.proto_types_count}"
    )

    if not strict:
        click.echo("Header check: OK")
        return

    errors = check_inline_field_schemas()
    if errors:
        click.echo("Strict header check: FAIL")
        for err in errors:
            click.echo(f"  - {err}")
        raise click.ClickException(
            f"{len(errors)} unresolved cpp_helper / enum_prefix reference"
            f"{'s' if len(errors) != 1 else ''} in handlers/"
        )
    click.echo("Strict header check: OK (all field references resolved)")
