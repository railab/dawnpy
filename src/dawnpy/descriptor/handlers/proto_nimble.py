# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_nimble.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``nimble`` PROTO type (BLE peripheral)."""

from __future__ import annotations

import struct
import uuid
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.descriptor.handlers._allocation import fmt_bindings
from dawnpy.descriptor.support.utils import (
    resolve_flexible_reference,
    resolve_reference,
)
from dawnpy.headerdefs._nimble import load_header_nimble_service_defs

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext


yaml_type: str = "nimble"
cpp_class: str = "CProtoNimblePrph"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_NIMBLE",
    "CONFIG_NIMBLE_ROLE_PERIPHERAL",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "nimble_gap_name": ("CProtoNimblePrph", "cfgIdGapname"),
    "nimble_iobind_dis": ("CProtoNimblePrph", "cfgIdIOBindDis"),
    "nimble_iobind_bas": ("CProtoNimblePrph", "cfgIdIOBindBas"),
    "nimble_iobind_aios": ("CProtoNimblePrph", "cfgIdIOBindAios"),
    "nimble_iobind_ess": ("CProtoNimblePrph", "cfgIdIOBindEss"),
    "nimble_iobind_imds": ("CProtoNimblePrph", "cfgIdIOBindImds"),
    "nimble_iobind_ots": ("CProtoNimblePrph", "cfgIdIOBindOts"),
    "nimble_iobind_custom": ("CProtoNimblePrph", "cfgIdIOBindCustom"),
}
dtype_names: dict[str, str] = {"string": "char"}
enum_value_maps: dict[str, tuple[str, str]] = {
    "nimble_aios_type": ("CProtoNimblePrphAios", "PRPH_AIOS_TYPE_"),
    "nimble_ess_type": ("CProtoNimblePrphEss", "PRPH_ESS_TYPE_"),
    "nimble_imds_type": ("CProtoNimblePrphImds", "PRPH_IMDS_TYPE_"),
}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}
NIMBLE_SERVICE_ORDER = (
    "dis",
    "bas",
    "aios",
    "ess",
    "imds",
    "ots",
)


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return Nimble allocation summary rows."""
    rows: list[list[str]] = []
    gap_name = str(proto.config.get("gap_name", "n/a"))
    rows.append(
        ["0", "gap", "n/a", "n/a", "0", f"gap_name={gap_name}, ios=none"]
    )

    services = proto.config.get("services", {})
    if not isinstance(services, dict):
        return rows

    block = 1
    block = _append_dis_allocation_row(rows, services, block)
    block = _append_bas_allocation_row(rows, services, block)
    block = _append_aios_allocation_rows(rows, services, block)
    block = _append_ess_allocation_row(rows, services, block)
    _append_imds_allocation_row(rows, services, block)

    return rows


def _append_dis_allocation_row(
    rows: list[list[str]], services: dict[str, Any], block: int
) -> int:
    dis_cfg = services.get("dis", {})
    if isinstance(dis_cfg, dict):
        enabled = bool(dis_cfg.get("enabled", False))
        rows.append(
            [
                str(block),
                "dis",
                "n/a",
                "n/a",
                "0",
                f"enabled={str(enabled).lower()}, ios=none",
            ]
        )
        block += 1
    return block


def _append_bas_allocation_row(
    rows: list[list[str]], services: dict[str, Any], block: int
) -> int:
    bas_cfg = services.get("bas", {})
    if isinstance(bas_cfg, dict):
        battery_io = resolve_reference(bas_cfg.get("battery_level"))
        bas_ios = [battery_io] if battery_io else []
        rows.append(
            [
                str(block),
                "bas",
                "n/a",
                "n/a",
                str(len(bas_ios)),
                f"ios={fmt_bindings(bas_ios)}",
            ]
        )
        block += 1
    return block


def _append_aios_allocation_rows(
    rows: list[list[str]], services: dict[str, Any], block: int
) -> int:
    aios_cfg = services.get("aios", {})
    if isinstance(aios_cfg, dict):
        groups = aios_cfg.get("groups", [])
        if isinstance(groups, list):
            for grp_idx, grp in enumerate(groups):
                if not isinstance(grp, dict):
                    continue
                grp_ios: list[str] = []
                for key in (
                    "digital_inputs",
                    "digital_outputs",
                    "analog_inputs",
                    "analog_outputs",
                ):
                    refs = grp.get(key, [])
                    if isinstance(refs, list):
                        grp_ios.extend(
                            io_id
                            for io_id in (
                                _aios_binding_ref(ref) for ref in refs
                            )
                            if io_id
                        )

                rows.append(
                    [
                        str(block),
                        f"aios.group{grp_idx}",
                        "n/a",
                        "n/a",
                        str(len(grp_ios)),
                        f"ios={fmt_bindings(grp_ios)}",
                    ]
                )
                block += 1
    return block


def _append_ess_allocation_row(
    rows: list[list[str]], services: dict[str, Any], block: int
) -> int:
    ess_cfg = services.get("ess", {})
    if isinstance(ess_cfg, dict):
        ess_ios: list[str] = []
        entries = ess_cfg.get("characteristics", [])
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                io_id = resolve_reference(entry.get("data"))
                if io_id:
                    ess_ios.append(io_id)
            rows.append(
                [
                    str(block),
                    "ess",
                    "n/a",
                    "n/a",
                    str(len(ess_ios)),
                    f"ios={fmt_bindings(ess_ios)}",
                ]
            )
            block += 1
    return block


def _append_imds_allocation_row(
    rows: list[list[str]], services: dict[str, Any], block: int
) -> None:
    imds_cfg = services.get("imds", {})
    if isinstance(imds_cfg, dict):
        imds_ios: list[str] = []
        for _, ref in imds_cfg.items():
            io_id = resolve_reference(ref)
            if io_id:
                imds_ios.append(io_id)
        rows.append(
            [
                str(block),
                "imds",
                "n/a",
                "n/a",
                str(len(imds_ios)),
                f"ios={fmt_bindings(imds_ios)}",
            ]
        )


def validate_object(obj: Any) -> list[str]:
    """Ensure Nimble service blocks are mappings."""
    services = obj.config.get("services")
    if services is not None and not isinstance(services, dict):
        return ["config.services must be a mapping"]
    return []


# OTS object-cfg enum mappings -- must match prph_ots.hxx PRPH_OTS_TYPE_*
# and PRPH_OTS_ACCESS_* values.
_OTS_TYPE_VALUES: dict[str, int] = {
    "file": 0,
    "descriptor": 1,
    "capabilities": 2,
}

_OTS_ACCESS_VALUES: dict[str, int] = {
    "read": 0,
    "write": 1,
    "rw": 2,
}

_ESS_DESC_USER_DESCRIPTION = 0x01
_ESS_DESC_VALID_RANGE = 0x02
_ESS_DESC_MEASUREMENT = 0x04
_ESS_DESC_CONFIGURATION = 0x08
_ESS_DESC_TRIGGER_SETTING = 0x10
_ESS_EXT_USER_DESCRIPTION = 1
_ESS_EXT_VALID_RANGE = 2
_ESS_EXT_MEASUREMENT = 3
_ESS_EXT_CONFIGURATION = 4
_ESS_EXT_TRIGGER_SETTING = 5
_ESS_USER_DESCRIPTION_BYTES = 16
_IMDS_DESC_USER_DESCRIPTION = 0x01
_IMDS_EXT_USER_DESCRIPTION = 1
_IMDS_USER_DESCRIPTION_BYTES = 16
_AIOS_DESC_USER_DESCRIPTION = 0x01
_AIOS_DESC_NUMBER_OF_DIGITALS = 0x02
_AIOS_DESC_VALUE_TRIGGER_SETTING = 0x04
_AIOS_DESC_TIME_TRIGGER_SETTING = 0x08
_AIOS_DESC_PRESENTATION_FORMAT = 0x10
_AIOS_DESC_EXTENDED_PROPERTIES = 0x20
_AIOS_EXT_USER_DESCRIPTION = 1
_AIOS_EXT_NUMBER_OF_DIGITALS = 2
_AIOS_EXT_VALUE_TRIGGER_SETTING = 3
_AIOS_EXT_TIME_TRIGGER_SETTING = 4
_AIOS_EXT_PRESENTATION_FORMAT = 5
_AIOS_EXT_EXTENDED_PROPERTIES = 6
_AIOS_USER_DESCRIPTION_BYTES = 16


def config_fields() -> list[ConfigField]:  # pragma: no cover
    """Return the user-facing YAML config schema for ``nimble``."""
    return [
        ConfigField(
            name="gap_name",
            cpp_helper="CProtoNimblePrph::cfgIdGapname",
            value_type="string",
        ),
        ConfigField(name="services", nested=True),
    ]


def _uuid_to_words(raw: Any) -> list[int]:  # pragma: no cover
    text = str(raw).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) == 4:
        text = f"0000{text}-0000-1000-8000-00805f9b34fb"
    value = uuid.UUID(text)
    # NimBLE stores 128-bit UUID payload bytes in full little-endian order.
    # The cfg blob is word-oriented, so emit four little-endian u32 words
    # whose in-memory byte layout matches that reversed 16-byte sequence.
    return list(struct.unpack("<4I", value.bytes[::-1]))


def encode_binary(  # noqa: C901
    ctx: _ProtoSerializeContext,
) -> None:  # pragma: no cover
    """Encode the Nimble peripheral binary block into ``ctx.items``."""
    if "gap_name" in ctx.config:
        packed = ctx.fmt.pack_string(str(ctx.config["gap_name"]))
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                ctx.dtype_id("string"),
                False,
                len(packed),
                ctx.cfg_id("nimble_gap_name", 1),
            ),
            packed,
        )

    services = ctx.config.get("services", {})
    if not isinstance(services, dict):
        services = {}

    if "dis" in services:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                0,
                ctx.cfg_id("nimble_iobind_dis", 2),
            ),
            [],
        )

    bas = services.get("bas", {})
    if isinstance(bas, dict) and "bas" in services:
        battery_id = resolve_flexible_reference(bas.get("battery_level", None))
        battery_word = (
            ctx.obj_ids[battery_id] if battery_id in ctx.obj_ids else 0
        )
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                1,
                ctx.cfg_id("nimble_iobind_bas", 3),
            ),
            [battery_word],
        )

    aios = services.get("aios", {})
    aios_words: list[int] = []
    if isinstance(aios, dict):
        aggregate = 1 if bool(aios.get("aggregate", False)) else 0
        groups = aios.get("groups", [])
        if isinstance(groups, list):
            entries: list[tuple[int, int, int, list[int]]] = []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for key, type_val_raw in ctx.enum_map(
                    "nimble_aios_type"
                ).items():
                    refs = group.get(key, [])
                    if not isinstance(refs, list):
                        continue
                    type_val = int(type_val_raw)
                    for ref in refs:
                        io_id = _aios_binding_ref(ref)
                        if io_id and io_id in ctx.obj_ids:
                            (
                                desc_mask,
                                user_desc,
                                number_of_digitals,
                                value_trigger_setting_ref,
                                time_trigger_setting_ref,
                                presentation_format_words,
                                extended_properties,
                            ) = _aios_metadata(ref)
                            aios_extensions: list[int] = []
                            ext_count = 0
                            if desc_mask & _AIOS_DESC_USER_DESCRIPTION:
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_USER_DESCRIPTION, 4
                                        ),
                                        *ctx.fmt.pack_fixed_string(
                                            user_desc,
                                            _AIOS_USER_DESCRIPTION_BYTES,
                                        ),
                                    ]
                                )
                            if desc_mask & _AIOS_DESC_VALUE_TRIGGER_SETTING:
                                value_trigger_setting_word = ctx.obj_ids.get(
                                    value_trigger_setting_ref or "", 0
                                )
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_VALUE_TRIGGER_SETTING,
                                            1,
                                        ),
                                        value_trigger_setting_word,
                                    ]
                                )
                            if desc_mask & _AIOS_DESC_TIME_TRIGGER_SETTING:
                                time_trigger_setting_word = ctx.obj_ids.get(
                                    time_trigger_setting_ref or "", 0
                                )
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_TIME_TRIGGER_SETTING,
                                            1,
                                        ),
                                        time_trigger_setting_word,
                                    ]
                                )
                            if desc_mask & _AIOS_DESC_NUMBER_OF_DIGITALS:
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_NUMBER_OF_DIGITALS, 1
                                        ),
                                        number_of_digitals,
                                    ]
                                )
                            if desc_mask & _AIOS_DESC_PRESENTATION_FORMAT:
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_PRESENTATION_FORMAT,
                                            2,
                                        ),
                                        *presentation_format_words,
                                    ]
                                )
                            if desc_mask & _AIOS_DESC_EXTENDED_PROPERTIES:
                                ext_count += 1
                                aios_extensions.extend(
                                    [
                                        _aios_ext_cfg(
                                            _AIOS_EXT_EXTENDED_PROPERTIES,
                                            1,
                                        ),
                                        extended_properties,
                                    ]
                                )
                            entries.append(
                                (
                                    type_val,
                                    ctx.obj_ids[io_id],
                                    ext_count,
                                    aios_extensions,
                                )
                            )
            aios_words.extend([len(entries), aggregate, 0])
            for type_val, objid_word, ext_count, aios_extensions in entries:
                aios_words.extend([type_val, objid_word, ext_count])
                aios_words.extend(aios_extensions)
    if aios_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(aios_words),
                ctx.cfg_id("nimble_iobind_aios", 4),
            ),
            aios_words,
        )

    ess_cfg = services.get("ess", {})
    ess_words: list[int] = []
    if isinstance(ess_cfg, dict):
        ess_entries: list[tuple[int, int, int, list[int]]] = []
        for entry in _ess_characteristic_entries(ess_cfg):
            type_name = str(entry.get("type", ""))
            ess_type_val_raw = ctx.enum_map("nimble_ess_type").get(type_name)
            io_id = resolve_flexible_reference(entry.get("data"))
            if (
                ess_type_val_raw is None
                or not io_id
                or io_id not in ctx.obj_ids
            ):
                continue
            (
                desc_mask,
                valid_min,
                valid_max,
                measurement_flags_ref,
                sampling_function_ref,
                measurement_period_ref,
                update_interval_ref,
                application_ref,
                uncertainty_ref,
                configuration_ref,
                trigger_setting_ref,
                user_desc,
            ) = _ess_metadata(entry)
            extensions: list[int] = []
            ext_count = 0
            if desc_mask & _ESS_DESC_USER_DESCRIPTION:
                ext_count += 1
                extensions.append(_ess_ext_cfg(_ESS_EXT_USER_DESCRIPTION, 4))
                extensions.extend(
                    ctx.fmt.pack_fixed_string(
                        user_desc, _ESS_USER_DESCRIPTION_BYTES
                    )
                )
            if desc_mask & _ESS_DESC_VALID_RANGE:
                ext_count += 1
                extensions.extend(
                    [
                        _ess_ext_cfg(_ESS_EXT_VALID_RANGE, 2),
                        valid_min,
                        valid_max,
                    ]
                )
            if desc_mask & _ESS_DESC_MEASUREMENT:
                ext_count += 1
                extensions.extend(
                    [
                        _ess_ext_cfg(_ESS_EXT_MEASUREMENT, 6),
                        ctx.obj_ids.get(measurement_flags_ref or "", 0),
                        ctx.obj_ids.get(sampling_function_ref or "", 0),
                        ctx.obj_ids.get(measurement_period_ref or "", 0),
                        ctx.obj_ids.get(update_interval_ref or "", 0),
                        ctx.obj_ids.get(application_ref or "", 0),
                        ctx.obj_ids.get(uncertainty_ref or "", 0),
                    ]
                )
            if desc_mask & _ESS_DESC_CONFIGURATION:
                ext_count += 1
                extensions.extend(
                    [
                        _ess_ext_cfg(_ESS_EXT_CONFIGURATION, 1),
                        ctx.obj_ids.get(configuration_ref or "", 0),
                    ]
                )
            if desc_mask & _ESS_DESC_TRIGGER_SETTING:
                ext_count += 1
                extensions.extend(
                    [
                        _ess_ext_cfg(_ESS_EXT_TRIGGER_SETTING, 1),
                        ctx.obj_ids.get(trigger_setting_ref or "", 0),
                    ]
                )
            ess_entries.append(
                (
                    int(ess_type_val_raw),
                    ctx.obj_ids[io_id],
                    ext_count,
                    extensions,
                )
            )
        ess_words.extend([len(ess_entries), 0, 0])
        for type_val, objid_word, ext_count, extensions in ess_entries:
            ess_words.extend([type_val, objid_word, ext_count])
            ess_words.extend(extensions)
    if ess_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(ess_words),
                ctx.cfg_id("nimble_iobind_ess", 5),
            ),
            ess_words,
        )

    imds_cfg = services.get("imds", {})
    imds_words: list[int] = []
    if isinstance(imds_cfg, dict):
        imds_entries: list[tuple[int, int, int, list[int]]] = []
        for key, type_val_raw in ctx.enum_map("nimble_imds_type").items():
            binding = imds_cfg.get(key, None)
            io_id = _imds_binding_ref(binding)
            if io_id and io_id in ctx.obj_ids:
                desc_mask, user_desc = _imds_metadata(binding)
                imds_extensions: list[int] = []
                ext_count = 0
                if desc_mask & _IMDS_DESC_USER_DESCRIPTION:
                    ext_count += 1
                    imds_extensions.append(
                        _imds_ext_cfg(_IMDS_EXT_USER_DESCRIPTION, 4)
                    )
                    imds_extensions.extend(
                        ctx.fmt.pack_fixed_string(
                            user_desc, _IMDS_USER_DESCRIPTION_BYTES
                        )
                    )
                imds_entries.append(
                    (
                        int(type_val_raw),
                        ctx.obj_ids[io_id],
                        ext_count,
                        imds_extensions,
                    )
                )
        imds_words.extend([len(imds_entries), 0, 0])
        for type_val, objid_word, ext_count, extensions in imds_entries:
            imds_words.extend([type_val, objid_word, ext_count])
            imds_words.extend(extensions)
    if imds_words:
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(imds_words),
                ctx.cfg_id("nimble_iobind_imds", 6),
            ),
            imds_words,
        )

    ots = services.get("ots", {})
    if isinstance(ots, dict):
        ots_objects = ots.get("objects", []) or []
        ots_entries: list[tuple[int, str, int]] = []
        for entry in ots_objects:
            if not isinstance(entry, dict):
                continue
            io_id = resolve_flexible_reference(entry.get("io"))
            if not io_id or io_id not in ctx.obj_ids:
                continue
            kind = _OTS_TYPE_VALUES.get(str(entry.get("type", "file")), 0)
            access = _OTS_ACCESS_VALUES.get(str(entry.get("access", "rw")), 2)
            cfg_word = (kind & 0xF) | ((access & 0x3) << 4)
            ots_entries.append(
                (cfg_word, str(entry.get("name", "")), ctx.obj_ids[io_id])
            )
        if ots_entries:
            ots_words: list[int] = [len(ots_entries), 0, 0]
            for cfg_word, name, objid_word in ots_entries:
                ots_words.append(cfg_word)
                ots_words.extend(ctx.fmt.pack_fixed_string(name, 16))
                ots_words.append(objid_word)
            append_cfg_item(
                ctx.items,
                cfg_id(
                    2,
                    ctx.cls,
                    0,
                    False,
                    len(ots_words),
                    ctx.cfg_id("nimble_iobind_ots", 7),
                ),
                ots_words,
            )

    custom = services.get("custom", [])
    if isinstance(custom, list):
        for service in custom:
            if not isinstance(service, dict):
                continue
            svc_uuid = service.get("uuid")
            chars = service.get("characteristics", [])
            if svc_uuid is None or not isinstance(chars, list):
                continue

            custom_entries: list[tuple[list[int], int, int]] = []
            for char in chars:
                if not isinstance(char, dict):
                    continue
                io_id = resolve_flexible_reference(char.get("io"))
                char_uuid = char.get("uuid")
                if (
                    io_id is None
                    or io_id not in ctx.obj_ids
                    or char_uuid is None
                ):
                    continue
                flags = char.get("flags", [])
                if not isinstance(flags, list):
                    flags = []
                flag_word = 0
                if "read" in flags:
                    flag_word |= 0x01
                if "write" in flags:
                    flag_word |= 0x02
                if "notify" in flags:
                    flag_word |= 0x04
                custom_entries.append(
                    (_uuid_to_words(char_uuid), flag_word, ctx.obj_ids[io_id])
                )

            if not custom_entries:
                continue

            custom_words: list[int] = [len(custom_entries), 0, 0]
            custom_words.extend(_uuid_to_words(svc_uuid))
            for uuid_words, flag_word, objid_word in custom_entries:
                custom_words.append(flag_word)
                custom_words.extend(uuid_words)
                custom_words.append(objid_word)

            append_cfg_item(
                ctx.items,
                cfg_id(
                    2,
                    ctx.cls,
                    0,
                    False,
                    len(custom_words),
                    ctx.cfg_id("nimble_iobind_custom", 8),
                ),
                custom_words,
            )


# ---------------------------------------------------------------------------
# C++ source generator (was proto_generators/nimble.py)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _nimble_service_defs() -> dict[str, dict[str, Any]]:
    """Return Nimble service schemas owned by this protocol handler."""
    return load_header_nimble_service_defs()


def _nimble_service_schema(svc_name: str) -> dict[str, Any] | None:
    """Return one Nimble service schema by YAML service name."""
    return _nimble_service_defs().get(svc_name)


def _is_service_enabled(  # pragma: no cover
    svc_name: str, services_config: dict[str, Any]
) -> bool:
    """Return True when service is present and has a registered schema."""
    if svc_name not in services_config:
        return False
    return _nimble_service_schema(svc_name) is not None


def _service_header(svc_name: str) -> str | None:  # pragma: no cover
    """Return C++ header path for a Nimble service."""
    schema = _nimble_service_schema(svc_name)
    if not schema:  # pragma: no cover
        return None
    return str(schema.get("header", ""))


def collect_cpp_headers(  # pragma: no cover
    config: dict[str, Any], gctx: ProtoGeneratorContext
) -> set[str]:
    """Collect Nimble service include headers required for one config."""
    headers: set[str] = set()
    services_config = config.get("services", {})
    for svc_name in NIMBLE_SERVICE_ORDER:
        if _is_service_enabled(svc_name, services_config):
            header = _service_header(svc_name)
            if header:
                headers.add(header)
    if isinstance(services_config.get("custom"), list):
        headers.add("dawn/proto/nimble/prph_custom.hxx")
    return headers


def generate_cpp(  # noqa: C901  # pragma: no cover
    macro_name: str, obj: ProtocolObject, gctx: ProtoGeneratorContext
) -> list[str]:
    """Emit per-instance C++ source lines for a Nimble peripheral object."""
    lines: list[str] = []
    config = obj.config
    fmt = gctx.format_helper
    services_config = config.get("services", {})

    config_count = 0
    if "gap_name" in config:
        config_count += 1
    for svc_name in NIMBLE_SERVICE_ORDER:
        if _is_service_enabled(svc_name, services_config):
            config_count += 1
    custom_services = services_config.get("custom", [])
    if isinstance(custom_services, list):
        config_count += sum(
            1 for item in custom_services if isinstance(item, dict)
        )
    fmt.append_line(lines, 1, f"{macro_name}, {config_count},")

    if "gap_name" in config:
        gap_name = str(config["gap_name"])
        packed_words = fmt.pack_string(gap_name)
        fmt.append_line(
            lines,
            2,
            f"CProtoNimblePrph::cfgIdGapname({len(packed_words)}),",
        )
        fmt.append_words(lines, packed_words, level=3)
        lines.append("")

    for svc_name in NIMBLE_SERVICE_ORDER:
        if _is_service_enabled(svc_name, services_config):
            svc_config = services_config.get(svc_name, {})
            lines.extend(_generate_service(svc_name, svc_config, gctx))
    if isinstance(custom_services, list):
        for svc_config in custom_services:
            if isinstance(svc_config, dict):
                lines.extend(_generate_custom_service(svc_config, gctx))
    return lines


def _generate_service(  # pragma: no cover
    svc_name: str, svc_config: dict[str, Any], gctx: ProtoGeneratorContext
) -> list[str]:
    """Emit one Nimble service block."""
    schema = _nimble_service_schema(svc_name)
    if not schema:  # pragma: no cover
        return []
    if svc_name == "dis":
        return [
            gctx.format_helper.line(2, "CProtoNimblePrph::cfgIdIOBindDis(),")
        ]
    if svc_name == "bas":
        fmt = gctx.format_helper
        lines = [fmt.line(2, "CProtoNimblePrph::cfgIdIOBindBas(),")]
        battery_level = gctx.resolve_reference(svc_config.get("battery_level"))
        if battery_level:  # pragma: no cover
            fmt.append_line(lines, 3, f"{battery_level.upper()},")
        return lines
    if svc_name in ("ess", "imds"):
        return _generate_ess_imds_service(svc_name, svc_config, schema, gctx)
    if svc_name == "aios":
        return _generate_aios_service(svc_config, schema, gctx)
    if svc_name == "ots":
        return _generate_ots_service(svc_config, schema, gctx)
    return []  # pragma: no cover


def _generate_ess_imds_service(  # pragma: no cover
    svc_name: str,
    svc_config: dict[str, Any],
    schema: dict[str, Any],
    gctx: ProtoGeneratorContext,
) -> list[str]:
    lines: list[str] = []
    cpp_helper = str(schema.get("cpp_helper", ""))
    cpp_service_class = str(schema.get("cpp_service_class", ""))
    fmt = gctx.format_helper
    sensor_types = schema.get("sensor_types", [])
    if svc_name == "ess":
        return _generate_ess_service(svc_config, schema, gctx)
    active_sensors: list[tuple[str, str, str, list[str]]] = []
    for sensor_def in sensor_types:
        yaml_name = str(sensor_def.get("yaml_name", ""))
        cpp_enum = str(sensor_def.get("cpp_enum", ""))
        if yaml_name not in svc_config:
            continue
        binding = svc_config[yaml_name]
        obj_id = _imds_binding_ref(binding)
        if not obj_id:
            continue
        active_sensors.append(
            (
                cpp_enum,
                obj_id,
                str(yaml_name),
                _imds_ext_lines(cpp_service_class, binding, fmt),
            )
        )
    count = len(active_sensors)
    total_size = 3 + sum(
        3 + len(ext_lines) for _, _, _, ext_lines in active_sensors
    )
    fmt.append_line(lines, 2, f"{cpp_helper}({total_size}),")
    svc_cap = svc_name.capitalize()
    fmt.append_line(
        lines,
        3,
        f"{cpp_service_class}::cfgIdIOBind{svc_cap}Cfg0({count}),",
    )
    fmt.append_line(
        lines, 3, f"{cpp_service_class}::cfgIdIOBind{svc_cap}Cfg1(0),"
    )
    fmt.append_line(
        lines, 3, f"{cpp_service_class}::cfgIdIOBind{svc_cap}Cfg2(0),"
    )
    for (
        cpp_enum,
        obj_id,
        _yaml_name,
        ext_lines,
    ) in active_sensors:  # pragma: no cover
        fmt.append_line(
            lines,
            4,
            f"{cpp_service_class}::"
            f"cfgIdIOBind{svc_cap}CfgObj({cpp_enum}),",
        )
        fmt.append_line(lines, 4, f"{obj_id.upper()},")
        ext_count = sum(
            1 for line in ext_lines if "cfgIdIOBindImdsExt" in line
        )
        fmt.append_line(lines, 4, f"{ext_count},")
        for ext_line in ext_lines:
            fmt.append_line(lines, 4, ext_line)
    return lines


def _ess_characteristic_entries(
    svc_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return normalized ESS characteristic entries from YAML config."""
    entries = svc_config.get("characteristics", [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _ess_metadata(
    entry: dict[str, Any],
) -> tuple[
    int,
    int,
    int,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str,
]:
    """Pack ESS optional metadata into descriptor-mask fields."""
    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    desc_mask = 0
    valid_min = 0
    valid_max = 0
    measurement_flags = None
    sampling_function = None
    measurement_period = None
    update_interval = None
    application = None
    uncertainty = None
    configuration = None
    trigger_setting = None
    user_desc = ""

    raw_desc = metadata.get("user_description")
    if raw_desc is not None:
        user_desc = str(raw_desc)
        desc_mask |= _ESS_DESC_USER_DESCRIPTION

    valid_range = metadata.get("valid_range")
    if isinstance(valid_range, dict):
        valid_min = int(valid_range.get("min", 0))
        valid_max = int(valid_range.get("max", 0))
        desc_mask |= _ESS_DESC_VALID_RANGE

    measurement = metadata.get("measurement")
    if isinstance(measurement, dict):
        measurement_flags = resolve_flexible_reference(
            measurement.get("flags")
        )
        sampling_function = resolve_flexible_reference(
            measurement.get("sampling_function")
        )
        measurement_period = resolve_flexible_reference(
            measurement.get("measurement_period")
        )
        update_interval = resolve_flexible_reference(
            measurement.get("update_interval")
        )
        application = resolve_flexible_reference(
            measurement.get("application")
        )
        uncertainty = resolve_flexible_reference(
            measurement.get("uncertainty")
        )
        desc_mask |= _ESS_DESC_MEASUREMENT

    configuration = resolve_flexible_reference(metadata.get("configuration"))
    if configuration:
        desc_mask |= _ESS_DESC_CONFIGURATION

    trigger_setting = resolve_flexible_reference(
        metadata.get("trigger_setting")
    )
    if trigger_setting:
        desc_mask |= _ESS_DESC_TRIGGER_SETTING

    return (
        desc_mask,
        valid_min,
        valid_max,
        measurement_flags,
        sampling_function,
        measurement_period,
        update_interval,
        application,
        uncertainty,
        configuration,
        trigger_setting,
        user_desc,
    )


def _aios_binding_ref(entry: Any) -> str | None:
    """Return AIOS IO id from a scalar, IO object, or metadata wrapper."""
    if isinstance(entry, dict) and ("data" in entry or "io" in entry):
        return resolve_flexible_reference(entry.get("data", entry.get("io")))
    return resolve_flexible_reference(entry)


def _imds_binding_ref(entry: Any) -> str | None:
    """Return IMDS IO id from a scalar, IO object, or metadata wrapper."""
    if isinstance(entry, dict) and ("data" in entry or "io" in entry):
        return resolve_flexible_reference(entry.get("data", entry.get("io")))
    return resolve_flexible_reference(entry)


def _imds_metadata(entry: Any) -> tuple[int, str]:
    """Pack IMDS optional metadata into descriptor-mask fields."""
    if not isinstance(entry, dict):
        return 0, ""

    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    desc_mask = 0
    user_desc = ""
    raw_desc = metadata.get("user_description")
    if raw_desc is not None:
        user_desc = str(raw_desc)
        desc_mask |= _IMDS_DESC_USER_DESCRIPTION

    return desc_mask, user_desc


def _aios_metadata(
    entry: Any,
) -> tuple[int, str, int, str | None, str | None, list[int], int]:
    """Pack AIOS optional metadata into descriptor-mask fields."""
    if not isinstance(entry, dict):
        return 0, "", 0, None, None, [], 0

    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    desc_mask = 0
    user_desc = ""
    number_of_digitals = 0
    value_trigger_setting_ref = None
    time_trigger_setting_ref = None
    presentation_format_words: list[int] = []
    extended_properties = 0
    raw_desc = metadata.get("user_description")
    if raw_desc is not None:
        user_desc = str(raw_desc)
        desc_mask |= _AIOS_DESC_USER_DESCRIPTION

    raw_number_of_digitals = metadata.get("number_of_digitals")
    if raw_number_of_digitals is not None:
        number_of_digitals = int(raw_number_of_digitals) & 0xFF
        desc_mask |= _AIOS_DESC_NUMBER_OF_DIGITALS

    value_trigger_setting_ref = resolve_flexible_reference(
        metadata.get("value_trigger_setting")
    )
    if value_trigger_setting_ref:
        desc_mask |= _AIOS_DESC_VALUE_TRIGGER_SETTING

    time_trigger_setting_ref = resolve_flexible_reference(
        metadata.get("time_trigger_setting")
    )
    if time_trigger_setting_ref:
        desc_mask |= _AIOS_DESC_TIME_TRIGGER_SETTING

    raw_presentation_format = metadata.get("presentation_format")
    if isinstance(raw_presentation_format, dict):
        presentation_format_words = _aios_presentation_format_words(
            raw_presentation_format
        )
        desc_mask |= _AIOS_DESC_PRESENTATION_FORMAT

    if "extended_properties" in metadata:
        extended_properties = (
            int(metadata.get("extended_properties", 0)) & 0xFFFF
        )
        desc_mask |= _AIOS_DESC_EXTENDED_PROPERTIES

    return (
        desc_mask,
        user_desc,
        number_of_digitals,
        value_trigger_setting_ref,
        time_trigger_setting_ref,
        presentation_format_words,
        extended_properties,
    )


def _aios_presentation_format_words(metadata: dict[str, Any]) -> list[int]:
    """Return packed Characteristic Presentation Format payload words."""
    fmt = int(metadata.get("format", 0)) & 0xFF
    exponent = int(metadata.get("exponent", 0)) & 0xFF
    unit = int(metadata.get("unit", 0)) & 0xFFFF
    namespace = int(metadata.get("namespace", 1)) & 0xFF
    description = int(metadata.get("description", 0)) & 0xFFFF
    word0 = fmt | (exponent << 8) | (unit << 16)
    word1 = namespace | (description << 8)
    return [word0, word1]


def _ess_objid_line(ref: str | None) -> str:
    """Return a generated C++ object-id word for an optional ESS IO ref."""
    return f"{ref.upper()}," if ref else "0,"


def _ess_ext_cfg(kind: int, size: int) -> int:
    """Return ESS compact extension cfg word."""
    return (kind & 0xFF) | ((size & 0xFF) << 8)


def _imds_ext_cfg(kind: int, size: int) -> int:
    """Return IMDS compact extension cfg word."""
    return (kind & 0xFF) | ((size & 0xFF) << 8)


def _aios_ext_cfg(kind: int, size: int) -> int:
    """Return AIOS compact extension cfg word."""
    return (kind & 0xFF) | ((size & 0xFF) << 8)


def _ess_ext_cfg_line(
    cpp_service_class: str, kind_name: str, size: int
) -> str:
    """Return generated C++ helper call for an ESS compact extension."""
    return (
        f"{cpp_service_class}::cfgIdIOBindEssExt("
        f"{cpp_service_class}::{kind_name}, {size}),"
    )


def _aios_ext_cfg_line(
    cpp_service_class: str, kind_name: str, size: int
) -> str:
    """Return generated C++ helper call for an AIOS compact extension."""
    return (
        f"{cpp_service_class}::cfgIdIOBindAiosExt("
        f"{cpp_service_class}::{kind_name}, {size}),"
    )


def _imds_ext_cfg_line(
    cpp_service_class: str, kind_name: str, size: int
) -> str:
    """Return generated C++ helper call for an IMDS compact extension."""
    return (
        f"{cpp_service_class}::cfgIdIOBindImdsExt("
        f"{cpp_service_class}::{kind_name}, {size}),"
    )


def _imds_ext_lines(
    cpp_service_class: str, binding: Any, fmt: Any
) -> list[str]:
    """Return generated C++ lines for compact IMDS extensions."""
    desc_mask, user_desc = _imds_metadata(binding)
    ext_lines: list[str] = []
    if desc_mask & _IMDS_DESC_USER_DESCRIPTION:
        ext_lines.append(
            _imds_ext_cfg_line(
                cpp_service_class, "IMDS_EXT_USER_DESCRIPTION", 4
            )
        )
        ext_lines.extend(
            _word_lines(
                fmt.pack_fixed_string(user_desc, _IMDS_USER_DESCRIPTION_BYTES)
            )
        )
    return ext_lines


def _aios_ext_lines(
    cpp_service_class: str, binding: Any, fmt: Any
) -> list[str]:
    """Return generated C++ lines for compact AIOS extensions."""
    (
        desc_mask,
        user_desc,
        number_of_digitals,
        value_trigger_setting_ref,
        time_trigger_setting_ref,
        presentation_format_words,
        extended_properties,
    ) = _aios_metadata(binding)
    ext_lines: list[str] = []
    if desc_mask & _AIOS_DESC_USER_DESCRIPTION:
        ext_lines.append(
            _aios_ext_cfg_line(
                cpp_service_class, "AIOS_EXT_USER_DESCRIPTION", 4
            )
        )
        ext_lines.extend(
            _word_lines(
                fmt.pack_fixed_string(user_desc, _AIOS_USER_DESCRIPTION_BYTES)
            )
        )
    if desc_mask & _AIOS_DESC_NUMBER_OF_DIGITALS:
        ext_lines.extend(
            [
                _aios_ext_cfg_line(
                    cpp_service_class, "AIOS_EXT_NUMBER_OF_DIGITALS", 1
                ),
                f"{number_of_digitals:#010x},",
            ]
        )
    if desc_mask & _AIOS_DESC_VALUE_TRIGGER_SETTING:
        ext_lines.extend(
            [
                _aios_ext_cfg_line(
                    cpp_service_class,
                    "AIOS_EXT_VALUE_TRIGGER_SETTING",
                    1,
                ),
                _ess_objid_line(value_trigger_setting_ref),
            ]
        )
    if desc_mask & _AIOS_DESC_TIME_TRIGGER_SETTING:
        ext_lines.extend(
            [
                _aios_ext_cfg_line(
                    cpp_service_class,
                    "AIOS_EXT_TIME_TRIGGER_SETTING",
                    1,
                ),
                _ess_objid_line(time_trigger_setting_ref),
            ]
        )
    if desc_mask & _AIOS_DESC_PRESENTATION_FORMAT:
        ext_lines.append(
            _aios_ext_cfg_line(
                cpp_service_class,
                "AIOS_EXT_PRESENTATION_FORMAT",
                2,
            )
        )
        ext_lines.extend(_word_lines(presentation_format_words))
    if desc_mask & _AIOS_DESC_EXTENDED_PROPERTIES:
        ext_lines.extend(
            [
                _aios_ext_cfg_line(
                    cpp_service_class,
                    "AIOS_EXT_EXTENDED_PROPERTIES",
                    1,
                ),
                f"{extended_properties:#010x},",
            ]
        )
    return ext_lines


def _word_lines(words: list[int]) -> list[str]:
    """Return generated C++ lines for packed uint32 words."""
    return [f"{word:#010x}," for word in words]


def _generate_ess_service(  # pragma: no cover
    svc_config: dict[str, Any],
    schema: dict[str, Any],
    gctx: ProtoGeneratorContext,
) -> list[str]:
    """Emit normalized ESS characteristic entries."""
    lines: list[str] = []
    cpp_helper = str(schema.get("cpp_helper", ""))
    cpp_service_class = str(schema.get("cpp_service_class", ""))
    fmt = gctx.format_helper
    sensor_defs = {
        str(item.get("yaml_name", "")): str(item.get("cpp_enum", ""))
        for item in schema.get("sensor_types", [])
    }

    entries: list[tuple[str, str, int, list[str]]] = []
    for entry in _ess_characteristic_entries(svc_config):
        sensor_type = str(entry.get("type", ""))
        cpp_enum = sensor_defs.get(sensor_type)
        obj_id = gctx.resolve_reference(entry.get("data"))
        if not cpp_enum or not obj_id:
            continue
        (
            desc_mask,
            valid_min,
            valid_max,
            measurement_flags_ref,
            sampling_function_ref,
            measurement_period_ref,
            update_interval_ref,
            application_ref,
            uncertainty_ref,
            configuration_ref,
            trigger_setting_ref,
            user_desc,
        ) = _ess_metadata(entry)
        ext_lines: list[str] = []
        if desc_mask & _ESS_DESC_USER_DESCRIPTION:
            ext_lines.append(
                _ess_ext_cfg_line(
                    cpp_service_class, "ESS_EXT_USER_DESCRIPTION", 4
                )
            )
            ext_lines.extend(
                _word_lines(
                    fmt.pack_fixed_string(
                        user_desc, _ESS_USER_DESCRIPTION_BYTES
                    )
                )
            )
        if desc_mask & _ESS_DESC_VALID_RANGE:
            ext_lines.extend(
                [
                    _ess_ext_cfg_line(
                        cpp_service_class, "ESS_EXT_VALID_RANGE", 2
                    ),
                    f"{valid_min:#010x},",
                    f"{valid_max:#010x},",
                ]
            )
        if desc_mask & _ESS_DESC_MEASUREMENT:
            ext_lines.append(
                _ess_ext_cfg_line(cpp_service_class, "ESS_EXT_MEASUREMENT", 6)
            )
            ext_lines.extend(
                [
                    _ess_objid_line(measurement_flags_ref),
                    _ess_objid_line(sampling_function_ref),
                    _ess_objid_line(measurement_period_ref),
                    _ess_objid_line(update_interval_ref),
                    _ess_objid_line(application_ref),
                    _ess_objid_line(uncertainty_ref),
                ]
            )
        if desc_mask & _ESS_DESC_CONFIGURATION:
            ext_lines.extend(
                [
                    _ess_ext_cfg_line(
                        cpp_service_class, "ESS_EXT_CONFIGURATION", 1
                    ),
                    _ess_objid_line(configuration_ref),
                ]
            )
        if desc_mask & _ESS_DESC_TRIGGER_SETTING:
            ext_lines.extend(
                [
                    _ess_ext_cfg_line(
                        cpp_service_class, "ESS_EXT_TRIGGER_SETTING", 1
                    ),
                    _ess_objid_line(trigger_setting_ref),
                ]
            )
        ext_count = sum(1 for line in ext_lines if "cfgIdIOBindEssExt" in line)
        entries.append((cpp_enum, obj_id, ext_count, ext_lines))

    count = len(entries)
    total_size = 3 + sum(3 + len(ext_lines) for _, _, _, ext_lines in entries)
    fmt.append_line(lines, 2, f"{cpp_helper}({total_size}),")
    fmt.append_line(
        lines, 3, f"{cpp_service_class}::cfgIdIOBindEssCfg0({count}),"
    )
    fmt.append_line(lines, 3, f"{cpp_service_class}::cfgIdIOBindEssCfg1(0),")
    fmt.append_line(lines, 3, f"{cpp_service_class}::cfgIdIOBindEssCfg2(0),")
    for cpp_enum, obj_id, ext_count, ext_lines in entries:
        fmt.append_line(
            lines,
            4,
            f"{cpp_service_class}::cfgIdIOBindEssCfgObj({cpp_enum}),",
        )
        fmt.append_line(lines, 4, f"{obj_id.upper()},")
        fmt.append_line(lines, 4, f"{ext_count},")
        for ext_line in ext_lines:
            fmt.append_line(lines, 4, ext_line)
    return lines


def _generate_aios_service(  # noqa: C901  # pragma: no cover
    svc_config: dict[str, Any],
    schema: dict[str, Any],
    gctx: ProtoGeneratorContext,
) -> list[str]:
    lines: list[str] = []
    cpp_helper = str(schema.get("cpp_helper", ""))
    cpp_service_class = str(schema.get("cpp_service_class", ""))
    fmt = gctx.format_helper
    groups = svc_config.get("groups", [])
    aggregate = 1 if bool(svc_config.get("aggregate", False)) else 0

    all_bindings: list[tuple[str, str, list[str]]] = []
    field_map = {
        str(field.get("name", "")): str(field.get("io_type", ""))
        for field in schema.get("group_fields", [])
    }
    for group in groups:
        if not isinstance(group, dict):
            continue
        appended = False
        for field_name, group_type_str in field_map.items():
            group_bindings = group.get(field_name, [])
            if not isinstance(group_bindings, list):
                continue
            for binding in group_bindings:
                resolved = _aios_binding_ref(binding)
                if resolved:
                    all_bindings.append(
                        (
                            group_type_str,
                            resolved,
                            _aios_ext_lines(cpp_service_class, binding, fmt),
                        )
                    )
                    appended = True
        if appended:
            continue
        group_type_str = str(group.get("type", "")).upper()
        group_bindings = group.get("bindings", [])
        if not isinstance(group_bindings, list):
            continue
        for binding in group_bindings:
            resolved = _aios_binding_ref(binding)
            if resolved:
                all_bindings.append(
                    (
                        group_type_str,
                        resolved,
                        _aios_ext_lines(cpp_service_class, binding, fmt),
                    )
                )

    count = len(all_bindings)
    total_size = 3 + sum(
        3 + len(ext_lines) for _, _, ext_lines in all_bindings
    )
    fmt.append_line(lines, 2, f"{cpp_helper}({total_size}),")
    fmt.append_line(
        lines, 3, f"{cpp_service_class}::cfgIdIOBindAiosCfg0({count}),"
    )
    fmt.append_line(
        lines, 3, f"{cpp_service_class}::cfgIdIOBindAiosCfg1({aggregate}),"
    )
    fmt.append_line(lines, 3, f"{cpp_service_class}::cfgIdIOBindAiosCfg2(0),")
    for group_type_str, obj_id, ext_lines in all_bindings:
        fmt.append_line(
            lines,
            4,
            f"{cpp_service_class}::cfgIdIOBindAiosCfgObj("
            f"{cpp_service_class}::{group_type_str}),",
        )
        fmt.append_line(lines, 4, f"{obj_id.upper()},")
        ext_count = sum(
            1 for line in ext_lines if "cfgIdIOBindAiosExt" in line
        )
        fmt.append_line(lines, 4, f"{ext_count},")
        for ext_line in ext_lines:
            fmt.append_line(lines, 4, ext_line)
    return lines


def _generate_ots_service(  # pragma: no cover
    svc_config: dict[str, Any],
    schema: dict[str, Any],
    gctx: ProtoGeneratorContext,
) -> list[str]:
    """Emit the C++ source block for an OTS service binding."""
    cpp_helper = str(schema.get("cpp_helper", ""))
    fmt = gctx.format_helper

    objects = svc_config.get("objects", []) or []
    entries: list[tuple[int, str, str]] = []
    for entry in objects:
        if not isinstance(entry, dict):
            continue
        obj_id = gctx.resolve_reference(entry.get("io"))
        if not obj_id:
            continue
        kind = _OTS_TYPE_VALUES.get(str(entry.get("type", "file")), 0)
        access = _OTS_ACCESS_VALUES.get(str(entry.get("access", "rw")), 2)
        cfg_word = (kind & 0xF) | ((access & 0x3) << 4)
        entries.append((cfg_word, str(entry.get("name", "")), obj_id))

    lines: list[str] = []
    count = len(entries)
    # 3 cfg words + per-object: 1 cfg + 4 name + 1 objid = 6 words
    total_size = 3 + 6 * count
    fmt.append_line(lines, 2, f"{cpp_helper}({total_size}),")
    fmt.append_line(lines, 3, f"{count},  // OTS object count")
    fmt.append_line(lines, 3, "0,  // reserved")
    fmt.append_line(lines, 3, "0,  // reserved")
    for cfg_word, name, obj_id in entries:
        fmt.append_line(lines, 4, f"{cfg_word:#010x},  // OTS cfg")
        name_words = fmt.pack_fixed_string(name, 16)
        fmt.append_words(lines, name_words, level=4)
        fmt.append_line(lines, 4, f"{obj_id.upper()},")
    return lines


def _generate_custom_service(  # noqa: C901  # pragma: no cover
    svc_config: dict[str, Any], gctx: ProtoGeneratorContext
) -> list[str]:
    svc_uuid = svc_config.get("uuid")
    chars = svc_config.get("characteristics", [])
    if svc_uuid is None or not isinstance(chars, list):
        return []

    entries: list[tuple[list[int], int, str]] = []
    for char in chars:
        if not isinstance(char, dict):
            continue
        obj_id = gctx.resolve_reference(char.get("io"))
        char_uuid = char.get("uuid")
        if not obj_id or char_uuid is None:
            continue
        flags = char.get("flags", [])
        if not isinstance(flags, list):
            flags = []
        flag_word = 0
        if "read" in flags:
            flag_word |= 0x01
        if "write" in flags:
            flag_word |= 0x02
        if "notify" in flags:
            flag_word |= 0x04
        entries.append((_uuid_to_words(char_uuid), flag_word, obj_id))

    if not entries:
        return []

    fmt = gctx.format_helper
    total_size = 7 + 6 * len(entries)
    lines = [
        fmt.line(2, f"CProtoNimblePrph::cfgIdIOBindCustom({total_size}),")
    ]
    fmt.append_line(lines, 3, f"{len(entries)},")
    fmt.append_line(lines, 3, "0,")
    fmt.append_line(lines, 3, "0,")
    for word in _uuid_to_words(svc_uuid):
        fmt.append_line(lines, 3, f"0x{word:08x},")
    for uuid_words, flag_word, obj_id in entries:
        fmt.append_line(lines, 3, f"0x{flag_word:08x},")
        for word in uuid_words:
            fmt.append_line(lines, 3, f"0x{word:08x},")
        fmt.append_line(lines, 3, f"{obj_id.upper()},")
    return lines
