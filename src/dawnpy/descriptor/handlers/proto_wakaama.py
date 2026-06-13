# tools/dawnpy/src/dawnpy/descriptor/handlers/proto_wakaama.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for the ``wakaama`` LwM2M PROTO type."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.proto_runtime import _ProtoSerializeContext
from dawnpy.descriptor.encoding.words import append_cfg_item, cfg_id
from dawnpy.descriptor.handlers._allocation import fmt_bindings
from dawnpy.descriptor.support.utils import resolve_reference
from dawnpy.headerdefs import HeaderDefsError, load_header_enum_value_ids

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import ProtocolObject
    from dawnpy.descriptor.generation.proto_base import ProtoGeneratorContext

yaml_type: str = "wakaama"
cpp_class: str = "CProtoWakaama"
nuttx_requirements: tuple[str, ...] = (
    "CONFIG_NETUTILS_WAKAAMA",
    "CONFIG_WAKAAMA_CLIENT_MODE",
)
uses_standard_bindings: bool = False
multi_device: bool = False
cfg_id_helpers: dict[str, tuple[str, str]] = {
    "wakaama_endpoint": ("CProtoWakaama", "cfgIdEndpoint"),
    "wakaama_server_host": ("CProtoWakaama", "cfgIdServerHost"),
    "wakaama_server_port": ("CProtoWakaama", "cfgIdServerPort"),
    "wakaama_local_port": ("CProtoWakaama", "cfgIdLocalPort"),
    "wakaama_lifetime": ("CProtoWakaama", "cfgIdLifetime"),
    "wakaama_iobind": ("CProtoWakaama", "cfgIdIOBind"),
    "wakaama_device_manufacturer": (
        "CProtoWakaama",
        "cfgIdDeviceManufacturer",
    ),
    "wakaama_device_model_number": (
        "CProtoWakaama",
        "cfgIdDeviceModelNumber",
    ),
    "wakaama_device_serial_number": (
        "CProtoWakaama",
        "cfgIdDeviceSerialNumber",
    ),
    "wakaama_device_firmware_version": (
        "CProtoWakaama",
        "cfgIdDeviceFirmwareVersion",
    ),
    "wakaama_device_battery_voltage": (
        "CProtoWakaama",
        "cfgIdDeviceBatteryVoltage",
    ),
    "wakaama_device_battery_level": (
        "CProtoWakaama",
        "cfgIdDeviceBatteryLevel",
    ),
    "wakaama_device_battery_status": (
        "CProtoWakaama",
        "cfgIdDeviceBatteryStatus",
    ),
    "wakaama_server": ("CProtoWakaama", "cfgIdServer"),
}
dtype_names: dict[str, str] = {
    "string": "char",
    "port": "uint16",
    "lifetime": "uint32",
}
enum_value_maps: dict[str, tuple[str, str]] = {
    "wakaama_object": ("CProtoWakaama", "WAKAAMA_OBJECT_"),
    "wakaama_resource": ("CProtoWakaama", "WAKAAMA_RESOURCE_"),
}
defaults: dict[str, int] = {}
fixed_string_bytes: dict[str, int] = {}

_ACCESS = {
    "read": 1,
    "write": 2,
    "rw": 3,
    "execute": 4,
    "exec": 4,
}
_UINT16_MAX = 0xFFFF
_UINT32_MAX = 0xFFFFFFFF
_SERVER_EXT_MAGIC = 0x574B4131
_SERVER_FLAG_COAPS = 1 << 0
_SERVER_FLAG_SECURITY_SHIFT = 8
_SERVER_FLAG_BOOTSTRAP = 1 << 16
_SECURITY_MODES = {
    "psk": 0,
    "none": 3,
}
_SCHEMES = {"coap", "coaps"}
_RESOURCE_DTYPE_RULES = {
    "binary_app_data": {"block"},
    "firmware_package": {"block"},
    "software_package": {"block"},
    "on_off": {"bool"},
    "digital_input_state": {"bool"},
    "digital_output_state": {"bool"},
    "dimmer": {"uint8"},
}
_NUMERIC_RESOURCE_NAMES = {
    "sensor_value",
    "analog_input_current_value",
    "analog_output_current_value",
    "min_measured_value",
    "max_measured_value",
    "min_range_value",
    "max_range_value",
    "x_value",
    "y_value",
    "z_value",
}
_NUMERIC_DTYPES = {
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "float",
    "double",
    "b16",
    "ub16",
}


@lru_cache(maxsize=2)
def _wakaama_enum_values(enum_key: str) -> dict[str, int]:
    """Return firmware-owned Wakaama enum values."""
    owner, prefix = enum_value_maps[enum_key]
    try:
        return load_header_enum_value_ids(owner, prefix)
    except HeaderDefsError:
        return {}


def allocation_rows(proto: Any) -> list[list[str]]:
    """Return Wakaama object/resource allocation summary rows."""
    config = proto.config
    endpoint = str(config.get("endpoint", "n/a"))
    servers = _server_entries(config)
    server_text = ",".join(
        f"{server.get('host', config.get('server_host', '<default>'))}:"
        f"{server.get('port', server.get('server_port', '<default>'))}"
        for server in servers
    )
    if not server_text:
        server_text = (
            f"{config.get('server_host', 'n/a')}:"
            f"{config.get('server_port', 'n/a')}"
        )
    rows: list[list[str]] = [
        [
            "0",
            "client",
            "n/a",
            "n/a",
            "0",
            (f"endpoint={endpoint}, servers={server_text}, " "ios=none"),
        ]
    ]

    objects = config.get("objects", [])
    if not isinstance(objects, list):
        return rows

    _append_allocation_rows(rows, objects, 1)
    return rows


def _append_allocation_rows(
    rows: list[list[str]],
    objects: list[Any],
    block: int,
) -> int:
    for idx, entry in enumerate(objects):
        if not isinstance(entry, dict):
            continue

        resources = entry.get("resources", [])
        if not isinstance(resources, list):
            resources = []

        object_id = _display_object_id(
            entry, _wakaama_enum_values("wakaama_object")
        )
        instance_id = str(entry.get("instance", 0))
        ios: list[str] = []
        resource_ids: list[str] = []

        for resource in resources:
            if not isinstance(resource, dict):
                continue

            io_id = resolve_reference(resource.get("io"))
            if io_id:
                ios.append(io_id)

            resource_ids.append(
                _display_resource_id(
                    resource,
                    _wakaama_enum_values("wakaama_resource"),
                )
            )

        rows.append(
            [
                str(block),
                f"object.{idx}",
                object_id,
                instance_id,
                str(len(ios)),
                f"resources={','.join(resource_ids) or 'none'}, "
                f"ios={fmt_bindings(ios)}",
            ]
        )
        block += 1

    return block


def config_fields() -> list[ConfigField]:
    """Return the user-facing YAML config schema for ``wakaama``."""
    return [
        ConfigField(
            name="endpoint",
            cpp_helper="CProtoWakaama::cfgIdEndpoint",
            value_type="string",
        ),
        ConfigField(
            name="server_host",
            cpp_helper="CProtoWakaama::cfgIdServerHost",
            value_type="string",
        ),
        ConfigField(
            name="server_port",
            cpp_helper="CProtoWakaama::cfgIdServerPort",
            value_type="uint16",
        ),
        ConfigField(
            name="local_port",
            cpp_helper="CProtoWakaama::cfgIdLocalPort",
            value_type="uint16",
        ),
        ConfigField(
            name="lifetime",
            cpp_helper="CProtoWakaama::cfgIdLifetime",
            value_type="uint32",
        ),
        ConfigField(
            name="queue_mode",
            cpp_helper="CProtoWakaama::cfgIdQueueMode",
            value_type="uint16",
        ),
        ConfigField(name="servers", nested=True),
        ConfigField(name="device", nested=True),
        ConfigField(name="objects", nested=True),
    ]


def validate_object(obj: Any) -> list[str]:
    """Validate the Wakaama config shape."""
    errors: list[str] = []
    _validate_uint_field(
        errors, obj.config, "server_port", "config.server_port", _UINT16_MAX
    )
    _validate_uint_field(
        errors, obj.config, "local_port", "config.local_port", _UINT16_MAX
    )
    _validate_uint_field(
        errors, obj.config, "lifetime", "config.lifetime", _UINT32_MAX
    )
    _validate_uint_field(
        errors, obj.config, "queue_mode", "config.queue_mode", _UINT16_MAX
    )
    _validate_servers(errors, obj.config)

    device = obj.config.get("device")
    if device is not None and not isinstance(device, dict):
        errors.append("config.device must be a mapping")

    objects = obj.config.get("objects")
    if objects is not None and not isinstance(objects, list):
        errors.append("config.objects must be a list")
        return errors

    if not isinstance(objects, list):
        return errors

    for entry_idx, entry in enumerate(objects):
        if not isinstance(entry, dict):
            errors.append(f"config.objects[{entry_idx}] must be a mapping")
            continue

        _validate_wakaama_id(
            errors,
            entry,
            "object",
            "object_id",
            f"config.objects[{entry_idx}]",
        )
        _validate_uint_field(
            errors,
            entry,
            "instance",
            f"config.objects[{entry_idx}].instance",
            _UINT16_MAX,
        )

        resources = entry.get("resources", [])
        if not isinstance(resources, list):
            errors.append(
                f"config.objects[{entry_idx}].resources must be a list"
            )
            continue

        for res_idx, resource in enumerate(resources):
            if not isinstance(resource, dict):
                errors.append(
                    f"config.objects[{entry_idx}].resources[{res_idx}] "
                    "must be a mapping"
                )
                continue

            _validate_wakaama_id(
                errors,
                resource,
                "resource",
                "resource_id",
                f"config.objects[{entry_idx}].resources[{res_idx}]",
            )

            access = str(resource.get("access", "read")).lower()
            if access not in _ACCESS:
                errors.append(
                    f"config.objects[{entry_idx}].resources[{res_idx}]"
                    ".access must be one of read, write, rw, execute"
                )
    return errors


def validate_descriptor_context(
    proto_id: str,
    config: dict[str, Any],
    objects: dict[str, Any],
) -> None:
    """Validate Wakaama IO bindings against descriptor IO metadata."""
    errors: list[str] = []
    wakaama_objects = config.get("objects", [])
    if not isinstance(wakaama_objects, list):
        return

    for entry_idx, entry in enumerate(wakaama_objects):
        if not isinstance(entry, dict):
            continue
        resources = entry.get("resources", [])
        if not isinstance(resources, list):
            continue
        for res_idx, resource in enumerate(resources):
            if not isinstance(resource, dict):
                continue
            _validate_resource_context(
                errors,
                proto_id,
                entry_idx,
                res_idx,
                resource,
                objects,
            )

    if errors:
        raise ValueError("; ".join(errors))


def _validate_resource_context(
    errors: list[str],
    proto_id: str,
    entry_idx: int,
    res_idx: int,
    resource: dict[str, Any],
    objects: dict[str, Any],
) -> None:
    io_id = resolve_reference(resource.get("io"))
    if io_id is None:
        return
    io = objects.get(io_id)
    if io is None:
        errors.append(
            f"wakaama protocol '{proto_id}' resource "
            f"objects[{entry_idx}].resources[{res_idx}] references "
            f"unknown IO '{io_id}'"
        )
        return

    access = str(resource.get("access", "read")).lower()
    resource_name = str(resource.get("resource", "")).lower()
    dtype = str(getattr(io, "dtype", "")).lower()
    io_type = str(getattr(io, "io_type", "")).lower()

    expected_dtypes = _RESOURCE_DTYPE_RULES.get(resource_name)
    if expected_dtypes is not None and dtype not in expected_dtypes:
        errors.append(
            f"wakaama protocol '{proto_id}' resource '{resource_name}' "
            f"requires dtype {sorted(expected_dtypes)}, but IO '{io_id}' "
            f"uses '{dtype}'"
        )

    if (
        resource_name in _NUMERIC_RESOURCE_NAMES
        and dtype not in _NUMERIC_DTYPES
    ):
        errors.append(
            f"wakaama protocol '{proto_id}' resource '{resource_name}' "
            f"requires numeric dtype, but IO '{io_id}' uses '{dtype}'"
        )

    if (
        access in ("execute", "exec")
        and io_type != "trigger"
        and dtype != "uint8"
    ):
        errors.append(
            f"wakaama protocol '{proto_id}' execute resource "
            f"objects[{entry_idx}].resources[{res_idx}] must bind to "
            f"trigger IO or uint8 command IO, but IO '{io_id}' is "
            f"type '{io_type}' dtype '{dtype}'"
        )


def _validate_servers(errors: list[str], config: dict[str, Any]) -> None:
    servers = config.get("servers")
    if servers is None:
        return
    if not isinstance(servers, list):
        errors.append("config.servers must be a list")
        return

    for idx, server in enumerate(servers):
        path = f"config.servers[{idx}]"
        if not isinstance(server, dict):
            errors.append(f"{path} must be a mapping")
            continue

        _validate_server_entry(errors, server, path)


def _validate_server_entry(
    errors: list[str], server: dict[str, Any], path: str
) -> None:
    host = server.get("host")
    if host is not None and not isinstance(host, str):
        errors.append(f"{path}.host must be a string")

    _validate_required_server_fields(errors, server, path)
    _validate_server_security(errors, server, path)
    _validate_server_uint_fields(errors, server, path)


def _validate_required_server_fields(
    errors: list[str], server: dict[str, Any], path: str
) -> None:
    required_fields = ["port"]
    if bool(server.get("bootstrap", False)):
        required_fields.append("holdoff")
    else:
        required_fields.extend(["lifetime", "short_server_id"])

    for required in required_fields:
        if required not in server and (
            required != "port" or "server_port" not in server
        ):
            errors.append(f"{path}.{required} is required")


def _validate_server_security(
    errors: list[str], server: dict[str, Any], path: str
) -> None:
    scheme = str(server.get("scheme", "coap")).lower()
    if "scheme" in server and scheme not in _SCHEMES:
        errors.append(f"{path}.scheme must be one of coap, coaps")

    security_mode = str(server.get("security_mode", "none")).lower()
    if "security_mode" in server and security_mode not in _SECURITY_MODES:
        errors.append(f"{path}.security_mode must be one of none, psk")

    if security_mode != "psk":
        return

    if scheme != "coaps":
        errors.append(f"{path}.security_mode psk requires scheme coaps")
    if not isinstance(server.get("psk_identity"), str):
        errors.append(f"{path}.psk_identity must be a string")
    psk_key = server.get("psk_key")
    if not isinstance(psk_key, str) or not _is_hex_string(psk_key):
        errors.append(f"{path}.psk_key must be an even-length hex string")


def _validate_server_uint_fields(
    errors: list[str], server: dict[str, Any], path: str
) -> None:
    _validate_uint_field(errors, server, "port", f"{path}.port", _UINT16_MAX)
    _validate_uint_field(
        errors,
        server,
        "server_port",
        f"{path}.server_port",
        _UINT16_MAX,
    )
    _validate_uint_field(
        errors, server, "lifetime", f"{path}.lifetime", _UINT32_MAX
    )
    _validate_uint_field(
        errors,
        server,
        "short_server_id",
        f"{path}.short_server_id",
        _UINT16_MAX,
    )
    _validate_uint_field(
        errors,
        server,
        "security_instance",
        f"{path}.security_instance",
        _UINT16_MAX,
    )
    _validate_uint_field(
        errors,
        server,
        "server_instance",
        f"{path}.server_instance",
        _UINT16_MAX,
    )
    _validate_uint_field(
        errors, server, "holdoff", f"{path}.holdoff", _UINT32_MAX
    )
    _validate_uint_field(
        errors,
        server,
        "bootstrap_timeout",
        f"{path}.bootstrap_timeout",
        _UINT32_MAX,
    )


def _validate_uint_field(
    errors: list[str],
    config: dict[str, Any],
    key: str,
    path: str,
    max_value: int,
) -> None:
    if key not in config:
        return
    _validate_uint_value(errors, config[key], path, max_value)


def _validate_wakaama_id(
    errors: list[str],
    entry: dict[str, Any],
    symbolic_key: str,
    numeric_key: str,
    path: str,
) -> None:
    if symbolic_key in entry:
        raw_value = entry[symbolic_key]
        if raw_value in (None, ""):
            if numeric_key in entry:
                _validate_uint_field(
                    errors,
                    entry,
                    numeric_key,
                    f"{path}.{numeric_key}",
                    _UINT16_MAX,
                )
            return
        if _is_int_like(raw_value):
            _validate_uint_value(
                errors,
                raw_value,
                f"{path}.{symbolic_key}",
                _UINT16_MAX,
            )
        return

    _validate_uint_field(
        errors, entry, numeric_key, f"{path}.{numeric_key}", _UINT16_MAX
    )


def _validate_uint_value(
    errors: list[str], value: Any, path: str, max_value: int
) -> None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{path} must be an integer in range 0..{max_value}")
        return

    if parsed < 0 or parsed > max_value:
        errors.append(f"{path} must be an integer in range 0..{max_value}")


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _is_hex_string(value: str) -> bool:
    if len(value) == 0 or len(value) % 2 != 0:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def encode_binary(ctx: _ProtoSerializeContext) -> None:
    """Encode endpoint/server settings and resource bindings."""
    _append_string(ctx, "endpoint", "wakaama_endpoint", 1)
    _append_u16(ctx, "local_port", "wakaama_local_port", 4)
    if _server_entries(ctx.config):
        for server_words in _server_word_blocks(ctx.config, ctx.fmt):
            append_cfg_item(
                ctx.items,
                cfg_id(
                    2,
                    ctx.cls,
                    0,
                    False,
                    len(server_words),
                    ctx.cfg_id("wakaama_server", 11),
                ),
                server_words,
            )
    else:
        _append_string(ctx, "server_host", "wakaama_server_host", 2)
        _append_u16(ctx, "server_port", "wakaama_server_port", 3)
        _append_u32(ctx, "lifetime", "wakaama_lifetime", 5)
    _append_device_string(
        ctx, "manufacturer", "wakaama_device_manufacturer", 7
    )
    _append_device_string(
        ctx, "model_number", "wakaama_device_model_number", 8
    )
    _append_device_string(
        ctx, "serial_number", "wakaama_device_serial_number", 9
    )
    _append_device_string(
        ctx, "firmware_version", "wakaama_device_firmware_version", 10
    )
    for _key, _cfg_key, _cfg_default in _device_iobind_fields():
        _append_device_iobind(ctx, _key, _cfg_key, _cfg_default)

    for iobind_words in _iobind_word_blocks(ctx):
        append_cfg_item(
            ctx.items,
            cfg_id(
                2,
                ctx.cls,
                0,
                False,
                len(iobind_words),
                ctx.cfg_id("wakaama_iobind", 6),
            ),
            iobind_words,
        )


def generate_cpp(
    macro_name: str, obj: "ProtocolObject", gctx: "ProtoGeneratorContext"
) -> list[str]:
    """Emit Wakaama protocol config, including resource bindings."""
    lines: list[str] = []
    config = obj.config
    fmt = gctx.format_helper
    scalar_fields = _cpp_scalar_fields(config)
    device_fields = _cpp_device_fields()
    server_blocks = _server_cpp_word_blocks(config, fmt)
    iobind_blocks = _iobind_cpp_word_blocks(config, gctx)
    device_iobinds = _device_iobind_cpp_entries(config, gctx)

    config_count = _cpp_config_count(
        config,
        scalar_fields,
        device_fields,
        len(server_blocks),
        len(iobind_blocks),
    ) + len(device_iobinds)
    fmt.append_line(lines, 1, f"{macro_name}, {config_count},")
    _append_cpp_scalar_configs(lines, fmt, config, scalar_fields)
    _append_cpp_device_configs(lines, fmt, config, device_fields)
    _append_cpp_device_iobinds(lines, fmt, device_iobinds)
    _append_cpp_int_blocks(
        lines, fmt, "CProtoWakaama::cfgIdServer", server_blocks
    )
    _append_cpp_iobind_blocks(lines, fmt, iobind_blocks)

    return lines


def _cpp_scalar_fields(config: dict[str, Any]) -> list[tuple[str, str, str]]:
    scalar_fields = [
        ("endpoint", "CProtoWakaama::cfgIdEndpoint", "string"),
        ("local_port", "CProtoWakaama::cfgIdLocalPort", "number"),
        ("queue_mode", "CProtoWakaama::cfgIdQueueMode", "number"),
    ]
    if not _server_entries(config):
        scalar_fields.extend(
            [
                ("server_host", "CProtoWakaama::cfgIdServerHost", "string"),
                ("server_port", "CProtoWakaama::cfgIdServerPort", "number"),
                ("lifetime", "CProtoWakaama::cfgIdLifetime", "number"),
            ]
        )
    return scalar_fields


def _cpp_device_fields() -> list[tuple[str, str]]:
    return [
        (
            "manufacturer",
            "CProtoWakaama::cfgIdDeviceManufacturer",
        ),
        (
            "model_number",
            "CProtoWakaama::cfgIdDeviceModelNumber",
        ),
        (
            "serial_number",
            "CProtoWakaama::cfgIdDeviceSerialNumber",
        ),
        (
            "firmware_version",
            "CProtoWakaama::cfgIdDeviceFirmwareVersion",
        ),
    ]


def _device_iobind_fields() -> list[tuple[str, str, int]]:
    """Device-object resources backed by an IO reference in the device: block.

    Each entry is (config key, cfgId helper / cfg helper key, binary cfg id).
    """
    return [
        ("battery_voltage", "wakaama_device_battery_voltage", 12),
        ("battery_level", "wakaama_device_battery_level", 13),
        ("battery_status", "wakaama_device_battery_status", 14),
    ]


def _device_iobind_cpp_entries(
    config: dict[str, Any], gctx: "ProtoGeneratorContext"
) -> list[tuple[str, str]]:
    """Resolve device IO-bind references to (cfgId helper, io-id symbol)."""
    helpers = {
        "battery_voltage": "CProtoWakaama::cfgIdDeviceBatteryVoltage",
        "battery_level": "CProtoWakaama::cfgIdDeviceBatteryLevel",
        "battery_status": "CProtoWakaama::cfgIdDeviceBatteryStatus",
    }
    entries: list[tuple[str, str]] = []
    for key, _cfg_key, _cfg_default in _device_iobind_fields():
        ref = _device_config_value(config, key)
        if ref is None:
            continue
        io_id = gctx.resolve_reference(ref)
        if not io_id:
            continue
        entries.append((helpers[key], io_id.upper()))
    return entries


def _append_cpp_device_iobinds(
    lines: list[str], fmt: Any, entries: list[tuple[str, str]]
) -> None:
    for helper, io_id in entries:
        fmt.append_line(lines, 2, f"{helper}(),")
        fmt.append_line(lines, 3, f"{io_id},")


def _cpp_config_count(
    config: dict[str, Any],
    scalar_fields: list[tuple[str, str, str]],
    device_fields: list[tuple[str, str]],
    server_count: int,
    iobind_count: int,
) -> int:
    config_count = sum(1 for key, _, _ in scalar_fields if key in config)
    config_count += sum(
        1
        for key, _ in device_fields
        if _device_config_value(config, key) is not None
    )
    config_count += server_count
    config_count += iobind_count
    return config_count


def _append_cpp_scalar_configs(
    lines: list[str],
    fmt: Any,
    config: dict[str, Any],
    scalar_fields: list[tuple[str, str, str]],
) -> None:
    for key, helper, kind in scalar_fields:
        if key not in config:
            continue
        if kind == "string":
            packed = fmt.pack_string(str(config[key]))
            fmt.append_line(lines, 2, f"{helper}({len(packed)}),")
            fmt.append_words(lines, packed, level=3)
        else:
            value = config[key]
            if isinstance(value, bool):
                value = int(value)
            fmt.append_line(lines, 2, f"{helper}(),")
            fmt.append_line(lines, 3, f"{fmt.format_numeric(value)},")


def _append_cpp_device_configs(
    lines: list[str],
    fmt: Any,
    config: dict[str, Any],
    device_fields: list[tuple[str, str]],
) -> None:
    for key, helper in device_fields:
        value = _device_config_value(config, key)
        if value is None:
            continue
        packed = fmt.pack_string(str(value))
        fmt.append_line(lines, 2, f"{helper}({len(packed)}),")
        fmt.append_words(lines, packed, level=3)


def _append_cpp_int_blocks(
    lines: list[str], fmt: Any, helper: str, blocks: list[list[int]]
) -> None:
    for server_words in blocks:
        fmt.append_line(lines, 2, f"{helper}({len(server_words)}),")
        for word in server_words:
            fmt.append_line(lines, 3, f"0x{word:08x},")


def _append_cpp_iobind_blocks(
    lines: list[str], fmt: Any, iobind_blocks: list[list[int | str]]
) -> None:
    for iobind_words in iobind_blocks:
        fmt.append_line(
            lines, 2, f"CProtoWakaama::cfgIdIOBind({len(iobind_words)}),"
        )
        for iobind_word in iobind_words:
            if isinstance(iobind_word, str):
                fmt.append_line(lines, 3, f"{iobind_word},")
            else:
                fmt.append_line(lines, 3, f"0x{iobind_word:08x},")


def _server_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    servers = config.get("servers", [])
    if not isinstance(servers, list):
        return []
    return [server for server in servers if isinstance(server, dict)]


def _server_word_blocks(config: dict[str, Any], fmt: Any) -> list[list[int]]:
    blocks: list[list[int]] = []
    for idx, server in enumerate(_server_entries(config)):
        security_instance = int(server.get("security_instance", idx))
        server_instance = int(server.get("server_instance", idx))
        bootstrap = bool(server.get("bootstrap", False))
        short_server_id = int(
            server.get("short_server_id", 0 if bootstrap else 0)
        )
        port = int(
            server["port"] if "port" in server else server["server_port"]
        )
        lifetime = int(server.get("lifetime", 0))
        words = [
            _pack_u16_pair_ints(security_instance, server_instance),
            _pack_u16_pair_ints(short_server_id, port),
            lifetime,
        ]
        if _server_needs_extended_block(server):
            scheme = str(server.get("scheme", "coap")).lower()
            security_mode = str(server.get("security_mode", "none")).lower()
            flags = (
                _SECURITY_MODES[security_mode] << _SERVER_FLAG_SECURITY_SHIFT
            )
            if scheme == "coaps":
                flags |= _SERVER_FLAG_COAPS
            if bootstrap:
                flags |= _SERVER_FLAG_BOOTSTRAP

            identity_words = fmt.pack_string(
                str(server.get("psk_identity", ""))
            )
            key_words = fmt.pack_string(str(server.get("psk_key", "")))
            host_value = server.get("host")
            host_words = (
                fmt.pack_string(str(host_value))
                if host_value is not None
                else []
            )
            words.extend(
                [
                    _SERVER_EXT_MAGIC,
                    flags,
                    int(server.get("holdoff", 0)),
                    int(server.get("bootstrap_timeout", 0)),
                    len(identity_words),
                    len(key_words),
                    len(host_words),
                    *identity_words,
                    *key_words,
                    *host_words,
                ]
            )
        else:
            host = server.get("host")
            if host is not None:
                words.extend(fmt.pack_string(str(host)))
        blocks.append(words)
    return blocks


def _server_needs_extended_block(server: dict[str, Any]) -> bool:
    return any(
        key in server
        for key in (
            "scheme",
            "security_mode",
            "psk_identity",
            "psk_key",
            "bootstrap",
            "holdoff",
            "bootstrap_timeout",
        )
    )


def _server_cpp_word_blocks(
    config: dict[str, Any], fmt: Any
) -> list[list[int]]:
    return _server_word_blocks(config, fmt)


def _append_string(
    ctx: _ProtoSerializeContext,
    key: str,
    cfg_key: str,
    cfg_default: int,
) -> None:
    if key not in ctx.config:
        return
    packed = ctx.fmt.pack_string(str(ctx.config[key]))
    append_cfg_item(
        ctx.items,
        cfg_id(
            2,
            ctx.cls,
            ctx.dtype_id("string"),
            False,
            len(packed),
            ctx.cfg_id(cfg_key, cfg_default),
        ),
        packed,
    )


def _device_config_value(config: dict[str, Any], key: str) -> Any | None:
    device = config.get("device")
    if not isinstance(device, dict):
        return None
    value = device.get(key)
    return value if value is not None else None


def _append_device_string(
    ctx: _ProtoSerializeContext,
    key: str,
    cfg_key: str,
    cfg_default: int,
) -> None:
    value = _device_config_value(ctx.config, key)
    if value is None:
        return
    packed = ctx.fmt.pack_string(str(value))
    append_cfg_item(
        ctx.items,
        cfg_id(
            2,
            ctx.cls,
            ctx.dtype_id("string"),
            False,
            len(packed),
            ctx.cfg_id(cfg_key, cfg_default),
        ),
        packed,
    )


def _append_device_iobind(
    ctx: _ProtoSerializeContext,
    key: str,
    cfg_key: str,
    cfg_default: int,
) -> None:
    """Encode a device-object resource bound to a descriptor IO."""
    ref = _device_config_value(ctx.config, key)
    if ref is None:
        return
    io_id = resolve_reference(ref)
    if not io_id:
        return
    word = ctx.obj_ids[io_id] if io_id in ctx.obj_ids else 0
    append_cfg_item(
        ctx.items,
        cfg_id(2, ctx.cls, 0, False, 1, ctx.cfg_id(cfg_key, cfg_default)),
        [word],
    )


def _append_u16(
    ctx: _ProtoSerializeContext,
    key: str,
    cfg_key: str,
    cfg_default: int,
) -> None:
    if key not in ctx.config:
        return
    append_cfg_item(
        ctx.items,
        cfg_id(
            2,
            ctx.cls,
            ctx.dtype_id("port"),
            False,
            1,
            ctx.cfg_id(cfg_key, cfg_default),
        ),
        [int(ctx.config[key])],
    )


def _append_u32(
    ctx: _ProtoSerializeContext,
    key: str,
    cfg_key: str,
    cfg_default: int,
) -> None:
    if key not in ctx.config:
        return
    append_cfg_item(
        ctx.items,
        cfg_id(
            2,
            ctx.cls,
            ctx.dtype_id("lifetime"),
            False,
            1,
            ctx.cfg_id(cfg_key, cfg_default),
        ),
        [int(ctx.config[key])],
    )


def _iobind_word_blocks(
    ctx: _ProtoSerializeContext,
) -> list[list[int]]:
    blocks: list[list[int]] = []
    objects = ctx.config.get("objects", [])
    if not isinstance(objects, list):
        return blocks

    for entry in objects:
        if isinstance(entry, dict):
            words = _object_entry_words(ctx, entry)
            if words:
                blocks.append(words)

    return blocks


def _iobind_cpp_word_blocks(
    config: dict[str, Any],
    gctx: "ProtoGeneratorContext",
) -> list[list[int | str]]:
    blocks: list[list[int | str]] = []
    objects = config.get("objects", [])
    if not isinstance(objects, list):
        return blocks

    for entry in objects:
        if isinstance(entry, dict):
            words = _object_entry_cpp_words(gctx, entry)
            if words:
                blocks.append(words)

    return blocks


def _object_entry_cpp_words(
    gctx: "ProtoGeneratorContext",
    entry: dict[str, Any],
) -> list[int | str]:
    object_id = _object_id_cpp(entry)
    instance_id = int(entry.get("instance", 0))
    out: list[int | str] = []
    resources = entry.get("resources", [])
    if not isinstance(resources, list):
        return out

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        resource_id = _resource_id_cpp(resource)
        access = _ACCESS[str(resource.get("access", "read")).lower()]
        io_id = gctx.resolve_reference(resource.get("io"))
        if not io_id:
            continue
        out.extend(
            [
                _pack_u16_pair(instance_id, object_id),
                _pack_u16_pair(access, resource_id),
                io_id.upper(),
            ]
        )

    return out


def _object_entry_words(
    ctx: _ProtoSerializeContext,
    entry: dict[str, Any],
) -> list[int]:
    object_id = _object_id(entry, ctx.enum_map("wakaama_object"))
    instance_id = int(entry.get("instance", 0))
    out: list[int] = []
    resources = entry.get("resources", [])
    if not isinstance(resources, list):
        return out

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        resource_id = _resource_id(resource, ctx.enum_map("wakaama_resource"))
        access = _ACCESS[str(resource.get("access", "read")).lower()]
        io_id = resolve_reference(resource.get("io"))
        if not io_id:
            continue
        objid = ctx.obj_ids[io_id]
        out.extend(
            [
                _pack_u16_pair_ints(instance_id, object_id),
                _pack_u16_pair_ints(access, resource_id),
                objid,
            ]
        )

    return out


def _object_id(entry: dict[str, Any], values: dict[str, int]) -> int:
    raw_obj = entry.get("object")
    if raw_obj is not None:
        raw = str(raw_obj).lower()
        if raw in values:
            return values[raw]
        return int(raw_obj)
    return int(entry.get("object_id", entry.get("object", 0)))


def _resource_id(entry: dict[str, Any], values: dict[str, int]) -> int:
    raw_res = entry.get("resource")
    if raw_res is not None:
        raw = str(raw_res).lower()
        if raw in values:
            return values[raw]
        return int(raw_res)
    return int(entry.get("resource_id", entry.get("resource", 0)))


def _display_object_id(entry: dict[str, Any], values: dict[str, int]) -> str:
    return _display_wakaama_id(entry, values, "object", "object_id")


def _display_resource_id(entry: dict[str, Any], values: dict[str, int]) -> str:
    return _display_wakaama_id(entry, values, "resource", "resource_id")


def _display_wakaama_id(
    entry: dict[str, Any],
    values: dict[str, int],
    symbolic_key: str,
    numeric_key: str,
) -> str:
    raw_value = entry.get(symbolic_key)
    if raw_value is not None:
        raw = str(raw_value).lower()
        if raw in values:
            return str(values[raw])
        try:
            return str(int(raw_value))
        except (TypeError, ValueError):
            return str(raw_value)

    return str(entry.get(numeric_key, 0))


def _object_id_cpp(entry: dict[str, Any]) -> int | str:
    raw_obj = entry.get("object")
    if raw_obj is not None:
        raw = str(raw_obj).lower()
        if raw:
            try:
                return int(raw_obj)
            except ValueError:
                return f"CProtoWakaama::WAKAAMA_OBJECT_{raw.upper()}"
        return int(entry.get("object_id", 0))
    return int(entry.get("object_id", entry.get("object", 0)))


def _resource_id_cpp(entry: dict[str, Any]) -> int | str:
    raw_res = entry.get("resource")
    if raw_res is not None:
        raw = str(raw_res).lower()
        if raw:
            try:
                return int(raw_res)
            except ValueError:
                return f"CProtoWakaama::WAKAAMA_RESOURCE_{raw.upper()}"
        return int(entry.get("resource_id", 0))
    return int(entry.get("resource_id", entry.get("resource", 0)))


def _pack_u16_pair(high: int | str, low: int | str) -> int | str:
    if isinstance(high, int) and isinstance(low, int):
        return _pack_u16_pair_ints(high, low)
    return f"(({high} & 0xffff) << 16) | ({low} & 0xffff)"


def _pack_u16_pair_ints(high: int, low: int) -> int:
    return (_checked_u16(high) << 16) | _checked_u16(low)


def _checked_u16(value: int) -> int:
    if value < 0 or value > _UINT16_MAX:
        raise ValueError(f"Wakaama uint16 value out of range: {value}")
    return value
