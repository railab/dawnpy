# tools/dawnpy/src/dawnpy/descriptor/reports/allocation.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Generic protocol allocation-table printer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click

from dawnpy.cli.table import print_table
from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

if TYPE_CHECKING:
    from dawnpy.descriptor.client import ClientDescriptor

_TABLE_COL_WIDTHS: dict[str, int] = {
    "block": 5,
    "kind": 14,
    "start": 10,
    "end": 10,
    "count": 5,
    "details": 64,
    "objid": 10,
}


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    print_table(headers, rows, printer=click.echo, max_width=_TABLE_COL_WIDTHS)


def _print_vars_summary(vars_spec: dict[str, Any]) -> None:
    if not isinstance(vars_spec, dict) or not vars_spec:
        return
    click.echo("\nVariables:")
    for name, value in vars_spec.items():
        if isinstance(value, dict):
            if "kconfig" in value:
                item = f"kconfig={value.get('kconfig')}"
            elif "value" in value:
                item = f"value={value.get('value')}"
            else:
                item = "value=?"
            if "type" in value:
                item += f", type={value.get('type')}"
        else:
            item = f"value={value}"
        click.echo(f"  - {name}: {item}")


def print_protocol_allocation_summaries(
    client_desc: ClientDescriptor,
    vars_spec: dict[str, Any],
) -> None:
    """Print per-protocol allocation summaries for every protocol declared."""
    if not client_desc.protocols:
        return

    click.echo("\nProtocol allocation summary:")
    _print_vars_summary(vars_spec)
    for proto in client_desc.protocols:
        click.echo(f"\n- {proto.proto_id} ({proto.proto_type})")

        headers = ["block", "kind", "start", "end", "count", "details"]
        handler = PROTO_HANDLER_REGISTRY.get(proto.proto_type)
        if handler is not None:
            for note in handler.allocation_notes(proto):
                click.echo(note)
        rows = (
            handler.allocation_rows(proto)
            if handler is not None
            else [["0", "n/a", "n/a", "n/a", "0", "unsupported protocol"]]
        )

        _print_table(headers, rows)
