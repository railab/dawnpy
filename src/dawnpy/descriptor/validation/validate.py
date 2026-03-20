# tools/dawnpy/src/dawnpy/descriptor/validate.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor validation pipeline + reporting helpers.

CLI commands under ``commands/cmd_desc_{valid,gen}.py`` call into here.
All app logic - validator orchestration, runtime-descriptor checks,
OOT extension hooks, conflict reporting, object-summary formatting -
lives in this module.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import click
import yaml

from dawnpy.cli.table import print_table
from dawnpy.descriptor.client import ClientDescriptor, load_client_descriptor
from dawnpy.descriptor.definitions.summary import (
    ObjectIdResolver,
    build_io_table,
    build_program_table,
    build_protocol_table,
)
from dawnpy.descriptor.handlers._allocation import try_parse_int
from dawnpy.descriptor.reports.allocation import (
    print_protocol_allocation_summaries,
)
from dawnpy.descriptor.validation.conflicts import check_key_conflicts
from dawnpy.descriptor.validation.validator import DescriptorValidator

GENERATE_CRC_POLICY_MSG = (
    "CRC policy: `desc-gen` keeps footer placeholder "
    "(firmware fills CRC); `desc-bin` pre-fills CRC32."
)


def validate_config(
    config_path: Path,
    quiet: bool,
    verbose: bool,
) -> bool:
    """Validate descriptor.cxx + defconfig pair under ``config_path``."""
    del verbose
    descriptor_path = config_path / "descriptor.cxx"
    defconfig_path = config_path / "defconfig"

    if not descriptor_path.exists():
        click.echo(
            f"Error: descriptor.cxx not found in {config_path}",
            err=True,
        )
        return False

    if not defconfig_path.exists():
        click.echo(
            f"Error: defconfig not found in {config_path}",
            err=True,
        )
        return False

    validator = DescriptorValidator()
    result = validator.validate(str(config_path))

    if not quiet:
        click.echo(validator.format_report(result))

    runtime_valid = validate_runtime_descriptor(
        config_path=config_path,
        quiet=quiet,
    )

    if result.valid and runtime_valid:
        if not quiet:
            click.echo("\n[OK] Validation passed!")
        return True

    return False


def validate_runtime_descriptor(  # noqa: C901
    config_path: Path,
    quiet: bool,
) -> bool:
    """Validate runtime semantics from descriptor.yaml if present."""
    yaml_path = config_path / "descriptor.yaml"
    if not yaml_path.exists():
        return True

    try:
        client_desc = load_client_descriptor(str(yaml_path))
    except Exception as exc:
        if not quiet:
            click.echo(
                f"[ERROR] Invalid descriptor.yaml: {exc} ({yaml_path})",
                err=True,
            )
        return False

    valid = True

    if not quiet:
        spec = _load_descriptor_spec(yaml_path)
        _print_object_summary(client_desc)
        print_protocol_allocation_summaries(client_desc, spec.get("vars", {}))

    valid = _run_descriptor_extensions(
        yaml_path=yaml_path,
        client_desc=client_desc,
        quiet=quiet,
        valid=valid,
    )

    return valid


def _run_descriptor_extensions(
    *,
    yaml_path: Path,
    client_desc: ClientDescriptor,
    quiet: bool,
    valid: bool,
) -> bool:
    """Run optional descriptor checks from installed extension packages."""
    if not client_desc.get_protocol("can"):
        return valid

    try:
        descriptor_mod = importlib.import_module("dawnpy_can.descriptor")
    except ImportError:
        return valid

    try:
        can_desc = descriptor_mod.load_can_descriptor(str(yaml_path))
    except Exception as exc:
        if not quiet:
            click.echo(
                f"[ERROR] CAN mapping validation failed: {exc}",
                err=True,
            )
        return False

    conflicts = check_key_conflicts(
        [(str(yaml_path), descriptor_mod.iter_conflict_keys(can_desc))]
    )
    if conflicts:
        valid = False
        if not quiet:
            click.echo("\nCAN overlap conflicts:")
            for item in conflicts:
                click.echo(
                    f"  - 0x{item.can_id:X}: {item.first} "
                    f"<-> {item.second}"
                )

    return valid


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a descriptor-summary table using shared column widths."""
    max_width = {
        "block": 5,
        "kind": 14,
        "start": 10,
        "end": 10,
        "count": 5,
        "details": 64,
        "objid": 10,
    }
    print_table(headers, rows, printer=click.echo, max_width=max_width)


def _print_object_summary(client_desc: ClientDescriptor) -> None:
    """Print IO/program/protocol object summary tables."""
    resolver = ObjectIdResolver()
    click.echo("\nObject summary:")

    headers, rows = build_io_table(client_desc, resolver=resolver)
    if rows:
        click.echo("\nIO objects:")
        _print_table(headers, rows)

    prog_headers, prog_rows = build_program_table(
        client_desc, resolver=resolver
    )
    if prog_rows:
        click.echo("\nProgram objects:")
        _print_table(prog_headers, prog_rows)

    proto_headers, proto_rows = build_protocol_table(
        client_desc, resolver=resolver
    )
    if proto_rows:
        click.echo("\nProtocol objects:")
        _print_table(proto_headers, proto_rows)


def _load_descriptor_spec(yaml_path: Path) -> dict[str, Any]:
    """Load a descriptor YAML spec file as a dict (best-effort)."""
    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
    except Exception:  # pragma: no cover
        return {}


def _proto_has_unresolved_kconfig(
    config: dict[str, Any],
    keys: list[str],
) -> bool:
    """Return True when any selected key holds an unresolved Kconfig token."""
    for key in keys:
        value = config.get(key)
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                for nested in ("start", "count", "can_id_start", "flags"):
                    if nested in item and try_parse_int(item[nested]) is None:
                        return True
        elif value is not None and try_parse_int(value) is None:
            return True
    return False


def can_has_unresolved_kconfig(client_desc: ClientDescriptor) -> bool:
    """Return True when CAN protocol config still references Kconfig tokens."""
    proto = client_desc.get_protocol("can")
    if not proto:
        return False
    return _proto_has_unresolved_kconfig(
        proto.config,
        ["node_id", "objects"],
    )
