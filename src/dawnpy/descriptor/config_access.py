# tools/dawnpy/src/dawnpy/descriptor/config_access.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Resolve descriptor-controlled config-item write access.

The runtime RW bit is a property of ``ObjectCfgId`` items, not of Dawn
objects. YAML ``rw`` is therefore only meaningful for ConfigIO entries: a
writable ConfigIO grants write access to the single target config field it
exposes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from dawnpy.descriptor.support.utils import resolve_reference

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import DescriptorObject
    from dawnpy.descriptor.definitions.type_info import ConfigField

ConfigRwGrants = dict[tuple[str, str], bool]


def _choose_config_field(
    fields: list[ConfigField], config: Mapping[str, object], objcfg_ref: str
) -> ConfigField | None:
    if objcfg_ref:
        return next((f for f in fields if f.name == objcfg_ref), None)

    configured = [
        f for f in fields if f.name in config and f.cpp_helper and not f.nested
    ]
    if len(configured) == 1:
        return configured[0]
    return None


def config_field_is_rw(
    grants: Mapping[tuple[str, str], bool], obj_id: str, field_name: str
) -> bool:
    """Return the generated RW bit for one config field."""
    return bool(grants.get((obj_id, field_name), False))


def _target_config_field(
    target: DescriptorObject | None, objcfg_ref: str
) -> ConfigField | None:
    """Resolve the config field a config IO targets on an IO or program."""
    from dawnpy.descriptor.definitions.objects import IoObject, ProgramObject
    from dawnpy.descriptor.handlers import (
        IO_HANDLER_REGISTRY,
        PROG_HANDLER_REGISTRY,
    )

    # A config IO can target either an IO's or a program's config field.
    if isinstance(target, IoObject):
        fields = IO_HANDLER_REGISTRY.get(str(target.io_type), None)
        field_defs = fields.config_fields() if fields is not None else []
        config = target.config
    elif isinstance(target, ProgramObject):
        progs = PROG_HANDLER_REGISTRY.get(str(target.prog_type), None)
        field_defs = progs.config_fields() if progs is not None else []
        config = target.config
    else:
        return None

    if not isinstance(config, Mapping):
        config = {}
    return _choose_config_field(field_defs, config, objcfg_ref)


def build_config_rw_grants(
    objects: Mapping[str, DescriptorObject],
) -> ConfigRwGrants:
    """Return fields made writable by writable ConfigIO objects."""
    from dawnpy.descriptor.definitions.objects import IoObject

    grants: ConfigRwGrants = {}

    for obj in objects.values():
        if not isinstance(obj, IoObject):
            continue
        if obj.io_type != "config" or not obj.rw:
            continue

        config = obj.config
        if not isinstance(config, Mapping):
            continue

        target_id = resolve_reference(config.get("objid_ref"))
        if not target_id:
            continue

        field = _target_config_field(
            objects.get(target_id), str(config.get("objcfg_ref", ""))
        )
        if field is None:
            continue

        grants[(target_id, field.name)] = True

    return grants
