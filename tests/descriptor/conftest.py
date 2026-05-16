#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor-local source-free header fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from dawnpy.descriptor.generation.generator import DescriptorGenerator


class _DummyParams(list[str]):
    def __contains__(self, item: object) -> bool:
        if item == "rw":
            return False
        return super().__contains__(item)


_DTYPE_ROWS = [
    (0, "any", "DTYPE_ANY", 0, 0),
    (1, "bool", "DTYPE_BOOL", 1, 1),
    (2, "int8", "DTYPE_INT8", 8, 2),
    (3, "uint8", "DTYPE_UINT8", 8, 3),
    (4, "int16", "DTYPE_INT16", 16, 4),
    (5, "uint16", "DTYPE_UINT16", 16, 5),
    (6, "int32", "DTYPE_INT32", 32, 6),
    (7, "uint32", "DTYPE_UINT32", 32, 7),
    (8, "int64", "DTYPE_INT64", 64, 8),
    (9, "uint64", "DTYPE_UINT64", 64, 9),
    (10, "float", "DTYPE_FLOAT", 32, 10),
    (11, "double", "DTYPE_DOUBLE", 64, 11),
    (12, "char", "DTYPE_CHAR", 8, None),
    (13, "b16", "DTYPE_B16", 16, 10),
    (15, "block", "DTYPE_BLOCK", 0, None),
]

_IO_PARAM_OVERRIDES = {
    "dummy": _DummyParams(["dtype", "rw", "instance"]),
    "adc_fetch": ["timestamp", "instance"],
    "adc_sync": ["timestamp", "instance"],
    "adc_stream": ["timestamp", "instance"],
    "dac": ["timestamp", "instance"],
    "leds": ["timestamp", "instance"],
    "rgb_led": ["timestamp", "instance"],
    "buttons": ["timestamp", "instance"],
    "pwm": ["timestamp", "instance"],
    "gpi": ["notify", "instance"],
    "gpo": ["notify", "instance"],
    "virt": ["dtype", "notify", "instance"],
    "rand": ["dtype", "timestamp", "instance"],
}

_IO_EXTRA = {
    "sensor": {
        "helper_func": "{cpp_class}::objectId{subtype}",
        "subtypes": ["temp", "accel", "gyro", "mag", "press", "humi", "hum"],
    },
    "sensor_producer": {
        "helper_func": "{cpp_class}::objectId{subtype}",
        "subtypes": ["temp", "accel", "gyro", "mag", "baro", "hum", "atemp"],
    },
    "sysinfo": {
        "helper_func": "{cpp_class}::objectId{variant}",
        "params": [],
        "variants": [{"name": "uptime"}, {"name": "cpuload"}],
    },
    "uname": {
        "helper_func": "{cpp_class}::objectId{variant}",
        "params": [],
        "variants": [{"name": "hostname"}],
    },
    "boardctl": {
        "helper_func": "{cpp_class}::objectId{variant}",
        "params": [],
        "variants": [
            {"name": "default"},
            {"name": "reset"},
            {"name": "reset_cause"},
            {"name": "poweroff"},
        ],
    },
}

_IO_CLASS_ALIASES = {
    "rgb_led": "rgbled",
    "descselector": "desc_selector",
    "fileio": "file",
    "gpi": "gpi_single",
    "gpo": "gpo_single",
    "systime": "system_systemtime",
    "uuid": "system_uuid",
}
_SENSOR_SUFFIXES = {
    "temp": "temperature",
    "accel": "accelerometer",
    "gyro": "gyroscope",
    "mag": "magneticfield",
    "baro": "barometer",
    "hum": "humidity",
}
_PROG_OBJECT_CLASS_NAMES = {
    "bitpack": "bit_pack",
    "bitsplit": "bit_split",
    "iirfilter": "iir_filter",
    "iodemux": "io_demux",
    "iomux": "io_mux",
    "manytoone": "many_to_one",
    "movingavg": "moving_avg",
    "onetomany": "one_to_many",
    "stats": "stats",
    "statsavg": "stats",
    "statsmin": "stat_min",
    "statsrms": "stat_rms",
    "vecpack": "vec_pack",
    "vecsplit": "vec_split",
}
_PROG_CLASS_NAMES = {
    **_PROG_OBJECT_CLASS_NAMES,
    "statsavg": "statsavg",
}
_PROTO_EXTRA_CLASS_NAMES = {"nimble": ["nimble_peripheral"]}
_PROTO_HEADERS = {
    "can": "dawn/proto/can/can.hxx",
    "modbus_rtu": "dawn/proto/modbus/rtu.hxx",
    "modbus_tcp": "dawn/proto/modbus/tcp.hxx",
    "nimble": "dawn/proto/nimble/prph.hxx",
    "nxscope_dummy": "dawn/proto/nxscope/dummy.hxx",
    "nxscope_serial": "dawn/proto/nxscope/serial.hxx",
    "nxscope_udp": "dawn/proto/nxscope/udp.hxx",
    "serial": "dawn/proto/serial/simple.hxx",
    "shell": "dawn/proto/shell/pretty.hxx",
    "wakaama": "dawn/proto/wakaama/wakaama.hxx",
}


def _unique(items: Iterable[str | None]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _numbered(names: Iterable[str | None]) -> dict[int, str]:
    return dict(enumerate(_unique(names), start=1))


def _sensor_class(subtype: str) -> str:
    return f"sensor_{_SENSOR_SUFFIXES.get(subtype, subtype)}"


def _sensor_producer_class(subtype: str) -> str:
    return f"sensor_producer_{_SENSOR_SUFFIXES.get(subtype, subtype)}"


def _io_variant_class(io_type: str, variant: object) -> str | None:
    variant_name = str(variant)
    if io_type == "sysinfo":
        return f"system_{variant_name}"
    if io_type == "uname" and variant_name == "hostname":
        return "system_hostname"
    if io_type == "boardctl":
        return {
            "reset": "system_reset",
            "reset_cause": "system_resetcause",
            "poweroff": "system_poweroff",
        }.get(variant_name)


def _io_class_names(
    type_defs: dict[str, list[dict[str, object]]],
) -> list[str]:
    names: list[str | None] = []
    for entry in type_defs["io_types"]:
        yaml_type = str(entry["yaml_type"])
        names.append(_IO_CLASS_ALIASES.get(yaml_type, yaml_type))
        if yaml_type == "sensor_producer":
            names.extend(
                _sensor_producer_class(str(subtype))
                for subtype in entry.get("subtypes", [])
            )
        else:
            names.extend(
                _sensor_class(str(subtype))
                for subtype in entry.get("subtypes", [])
            )
        names.extend(
            _io_variant_class(yaml_type, variant.get("name"))
            for variant in entry.get("variants", [])
            if isinstance(variant, dict)
        )
    return _unique(names)


def _prog_class_names(
    type_defs: dict[str, list[dict[str, object]]],
) -> list[str]:
    names: list[str | None] = []
    for entry in type_defs["prog_types"]:
        yaml_type = str(entry["yaml_type"])
        names.append(_PROG_CLASS_NAMES.get(yaml_type, yaml_type))
        names.append(yaml_type)
    return _unique(names)


def _proto_class_names(
    type_defs: dict[str, list[dict[str, object]]],
) -> list[str]:
    names: list[str | None] = []
    for entry in type_defs["proto_types"]:
        yaml_type = str(entry["yaml_type"])
        names.append(yaml_type)
        names.extend(_PROTO_EXTRA_CLASS_NAMES.get(yaml_type, []))
    return _unique(names)


def minimal_dtype_header_defs() -> dict[str, object]:
    """Dtype constants needed by descriptor registry/generator tests."""
    dtype = []
    for value, yaml_type, name, size, initval_param in _DTYPE_ROWS:
        entry = {"value": value, "type": yaml_type, "name": name, "size": size}
        if initval_param is not None:
            entry["initval_param"] = initval_param
        dtype.append(entry)
    return {"dtype": dtype}


def minimal_header_defs() -> dict[str, object]:
    """Small ObjectId definition set used by tests that need a decoder."""
    type_defs = minimal_type_defs()
    return {
        "bit_fields": {
            "priv": {"shift": 0, "width": 14, "max": 0x3FFF},
            "flags": {"shift": 14, "width": 2, "max": 0x3},
            "dtype": {"shift": 16, "width": 4, "max": 0xF},
            "ext": {"shift": 20, "width": 1, "max": 0x1},
            "cls": {"shift": 21, "width": 9, "max": 0x1FF},
            "type": {"shift": 30, "width": 2, "max": 0x3},
        },
        "object_types": {0: "ANY", 1: "IO", 2: "PROTO", 3: "PROG"},
        **minimal_dtype_header_defs(),
        "io_classes": _numbered(_io_class_names(type_defs)),
        "prog_classes": _numbered(_prog_class_names(type_defs)),
        "proto_classes": _numbered(_proto_class_names(type_defs)),
    }


def _prog_type_entry(yaml_type: str, cpp_class: str) -> dict[str, object]:
    if yaml_type == "stats":
        cpp_class = "CProgProcess"
        header = "dawn/prog/process.hxx"
    else:
        header = f"dawn/prog/{yaml_type}.hxx"
    return {
        "yaml_type": yaml_type,
        "cpp_class": cpp_class,
        "header": header,
        "object_class_name": _PROG_OBJECT_CLASS_NAMES.get(
            yaml_type, yaml_type
        ),
    }


def minimal_type_defs() -> dict[str, list[dict[str, object]]]:
    """Representative type definitions built from handler registrations."""
    from dawnpy.descriptor.handlers import (
        IO_HANDLER_REGISTRY,
        PROG_HANDLER_REGISTRY,
        PROTO_HANDLER_REGISTRY,
    )

    return {
        "io_types": [
            {
                "yaml_type": yaml_type,
                "cpp_class": handler.cpp_class,
                "header": f"dawn/io/{yaml_type}.hxx",
                "helper_func": _IO_EXTRA.get(yaml_type, {}).get(
                    "helper_func", "{cpp_class}::objectId"
                ),
                "params": _IO_EXTRA.get(yaml_type, {}).get(
                    "params",
                    _IO_PARAM_OVERRIDES.get(yaml_type, ["dtype", "instance"]),
                ),
                **{
                    key: value
                    for key, value in _IO_EXTRA.get(yaml_type, {}).items()
                    if key not in ("helper_func", "params")
                },
            }
            for yaml_type, handler in IO_HANDLER_REGISTRY.items()
        ],
        "prog_types": [
            _prog_type_entry(yaml_type, handler.cpp_class)
            for yaml_type, handler in PROG_HANDLER_REGISTRY.items()
        ],
        "proto_types": [
            {
                "yaml_type": yaml_type,
                "cpp_class": handler.cpp_class,
                "header": _PROTO_HEADERS.get(
                    yaml_type, f"dawn/proto/{yaml_type}.hxx"
                ),
            }
            for yaml_type, handler in PROTO_HANDLER_REGISTRY.items()
        ],
    }


def minimal_header_groups():
    from dawnpy.headerdefs.bundle import HeaderDefinitionGroups

    return HeaderDefinitionGroups(
        header_defs=minimal_header_defs(),
        type_defs=minimal_type_defs(),
        metadata_defs=minimal_metadata_defs(),
        component_defs=minimal_component_defs(),
    )


def minimal_header_lookups(
    *,
    enum_map_loader: Callable[[str, str], dict[str, str]] | None = None,
    cfg_id_loader: Callable[[str, str], int] | None = None,
    enum_value_ids_loader: Callable[[str, str], dict[str, int]] | None = None,
    object_class_name_loader: Callable[[str, str], str] | None = None,
):
    from dawnpy.headerdefs.bundle import HeaderLookupFunctions

    return HeaderLookupFunctions(
        enum_map_loader=enum_map_loader or minimal_enum_map,
        cfg_id_loader=cfg_id_loader or minimal_cfg_id,
        enum_value_ids_loader=enum_value_ids_loader or minimal_enum_value_ids,
        object_class_name_loader=object_class_name_loader
        or minimal_object_class_name,
    )


def minimal_header_bundle(*, groups=None, lookups=None):
    from dawnpy.headerdefs.bundle import HeaderBundle

    return HeaderBundle(
        groups if groups is not None else minimal_header_groups(),
        lookups if lookups is not None else minimal_header_lookups(),
    )


def minimal_header_definition_set():
    return minimal_header_bundle()


def minimal_metadata_defs() -> list[dict[str, str]]:
    return [
        {
            "name": "version",
            "cpp_helper": "CDescriptor::cfgIdVersion",
            "value_type": "version",
        },
        {
            "name": "user_string",
            "cpp_helper": "CDescriptor::cfgIdString",
            "value_type": "string",
        },
    ]


def minimal_component_defs() -> dict[str, list[dict[str, str]]]:
    rows = {
        "ios": [
            ("CIODummy", "dawn/io/dummy.hxx", "CONFIG_DAWN_IO_DUMMY"),
            ("CIOVirt", "dawn/io/virt.hxx", "CONFIG_DAWN_IO_VIRT"),
            ("CIOSensor", "dawn/io/sensor.hxx", "CONFIG_DAWN_IO_SENSOR"),
            ("CIOGpi", "dawn/io/gpi.hxx", "CONFIG_DAWN_IO_GPI"),
            ("CIOGpo", "dawn/io/gpo.hxx", "CONFIG_DAWN_IO_GPO"),
            (
                "CIOCapabilities",
                "dawn/io/capabilities.hxx",
                "CONFIG_DAWN_IO_CAPABILITIES",
            ),
            ("CIOPwm", "dawn/io/pwm.hxx", "CONFIG_DAWN_IO_PWM"),
            ("CIORgbLed", "dawn/io/rgbled.hxx", "CONFIG_DAWN_IO_RGB_LED"),
        ],
        "programs": [
            (
                "CProgProcess",
                "dawn/prog/process.hxx",
                "CONFIG_DAWN_PROG_PROCESS",
            ),
            (
                "CProgSampling",
                "dawn/prog/sampling.hxx",
                "CONFIG_DAWN_PROG_SAMPLING",
            ),
            ("CProgAdjust", "dawn/prog/adjust.hxx", "CONFIG_DAWN_PROG_ADJUST"),
        ],
        "protocols": [
            ("CProtoCan", "dawn/proto/can/can.hxx", "CONFIG_DAWN_PROTO_CAN"),
            (
                "CProtoSerial",
                "dawn/proto/serial/simple.hxx",
                "CONFIG_DAWN_PROTO_SERIAL",
            ),
            (
                "CProtoDummy",
                "dawn/proto/dummy.hxx",
                "CONFIG_DAWN_PROTO_DUMMY",
            ),
        ],
    }
    return {
        section: [
            {"name": name, "include": include, "kval": kval}
            for name, include, kval in entries
        ]
        for section, entries in rows.items()
    }


def minimal_nimble_service_defs() -> dict[str, dict[str, object]]:
    return {
        "dis": {"name": "dis", "enabled_only": True},
        "bas": {"name": "bas", "fields": [{"name": "battery_level"}]},
        "aios": {
            "name": "aios",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindAios",
            "cpp_service_class": "CProtoNimblePrphAios",
            "header": "dawn/proto/nimble/prph_aios.hxx",
            "has_groups": True,
            "group_fields": [
                {
                    "name": "digital_inputs",
                    "io_type": "PRPH_AIOS_TYPE_DIGITAL",
                },
                {
                    "name": "digital_outputs",
                    "io_type": "PRPH_AIOS_TYPE_DIGITAL",
                },
                {"name": "analog_inputs", "io_type": "PRPH_AIOS_TYPE_ANALOG"},
                {"name": "analog_outputs", "io_type": "PRPH_AIOS_TYPE_ANALOG"},
            ],
        },
        "ess": {
            "name": "ess",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindEss",
            "cpp_service_class": "CProtoNimblePrphEss",
            "header": "dawn/proto/nimble/prph_ess.hxx",
            "sensor_types": [
                {
                    "yaml_name": "temperature",
                    "cpp_enum": "CProtoNimblePrphEss::PRPH_ESS_TYPE_TEMP",
                }
            ],
        },
        "imds": {
            "name": "imds",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindImds",
            "cpp_service_class": "CProtoNimblePrphImds",
            "header": "dawn/proto/nimble/prph_imds.hxx",
            "sensor_types": [
                {
                    "yaml_name": "temperature",
                    "cpp_enum": "CProtoNimblePrphImds::PRPH_IMDS_TYPE_TEMP",
                },
                {
                    "yaml_name": "humidity",
                    "cpp_enum": (
                        "CProtoNimblePrphImds::PRPH_IMDS_TYPE_HUMIDITY"
                    ),
                },
            ],
        },
        "ots": {
            "name": "ots",
            "cpp_helper": "CProtoNimblePrph::cfgIdIOBindOts",
            "cpp_service_class": "CProtoNimblePrphOts",
            "header": "dawn/proto/nimble/prph_ots.hxx",
            "object_types": {"file": 0, "descriptor": 1, "capabilities": 2},
            "object_access": {"read": 0, "write": 1, "rw": 2},
        },
    }


def minimal_cfg_id(owner: str, method: str) -> int:
    explicit = {
        ("CIOCommon", "cfgIdDevno"): 1,
        ("CIOCommon", "cfgIdNotify"): 2,
        ("CIOCommon", "cfgIdLimitMin"): 3,
        ("CIOCommon", "cfgIdLimitMax"): 4,
        ("CIOCommon", "cfgIdLimitStep"): 5,
        ("CIOPwm", "cfgIdFreq"): 6,
        ("CProtoNxscopeDummy", "cfgIdIOBind"): 1,
        ("CProtoNxscopeDummy", "cfgIdIOBind2"): 2,
        ("CProtoNxscopeSerial", "cfgIdPath"): 3,
        ("CProtoNxscopeSerial", "cfgIdBaud"): 4,
    }
    if (owner, method) in explicit:
        return explicit[(owner, method)]
    return (sum(ord(ch) for ch in f"{owner}.{method}") % 31) + 1


def minimal_enum_map(owner: str, enum_prefix: str) -> dict[str, str]:
    explicit = {
        ("CProtoCan", "CAN_TYPE_"): {
            "read": "READ",
            "write": "WRITE",
            "uint8": "UINT8",
            "uint16": "UINT16",
            "uint32": "UINT32",
        },
        ("CProtoModbusRegs", "MODBUS_TYPE_"): {
            "holding": "HOLDING",
            "input": "INPUT",
            "coil": "COIL",
            "uint16": "UINT16",
            "float": "FLOAT",
        },
        ("CProtoWakaama", "WAKAAMA_OBJECT_"): {
            "temperature": "TEMPERATURE",
            "humidity": "HUMIDITY",
            "pressure": "PRESSURE",
            "light": "LIGHT",
            "actuation": "ACTUATION",
            "binary_app_data_container": "BINARY_APP_DATA_CONTAINER",
            "device": "DEVICE",
            "connectivity_monitoring": "CONNECTIVITY_MONITORING",
            "firmware_update": "FIRMWARE_UPDATE",
            "software_management": "SOFTWARE_MANAGEMENT",
            "cellular_connectivity": "CELLULAR_CONNECTIVITY",
            "digital_input": "DIGITAL_INPUT",
            "digital_output": "DIGITAL_OUTPUT",
            "analog_input": "ANALOG_INPUT",
            "analog_output": "ANALOG_OUTPUT",
            "generic_sensor": "GENERIC_SENSOR",
            "illuminance": "ILLUMINANCE",
            "light_control": "LIGHT_CONTROL",
            "accelerometer": "ACCELEROMETER",
            "magnetometer": "MAGNETOMETER",
            "barometer": "BAROMETER",
            "voltage": "VOLTAGE",
            "current": "CURRENT",
            "gyrometer": "GYROMETER",
        },
        ("CProtoWakaama", "WAKAAMA_RESOURCE_"): {
            "sensor_value": "SENSOR_VALUE",
            "units": "UNITS",
            "min_measured_value": "MIN_MEASURED_VALUE",
            "max_measured_value": "MAX_MEASURED_VALUE",
            "on_off": "ON_OFF",
            "dimmer": "DIMMER",
            "binary_app_data": "BINARY_APP_DATA",
            "firmware_package": "FIRMWARE_PACKAGE",
            "firmware_state": "FIRMWARE_STATE",
            "firmware_update_result": "FIRMWARE_UPDATE_RESULT",
            "digital_input_state": "DIGITAL_INPUT_STATE",
            "digital_output_state": "DIGITAL_OUTPUT_STATE",
            "analog_input_current_value": "ANALOG_INPUT_CURRENT_VALUE",
            "analog_output_current_value": "ANALOG_OUTPUT_CURRENT_VALUE",
            "sensor_units": "SENSOR_UNITS",
            "min_range_value": "MIN_RANGE_VALUE",
            "max_range_value": "MAX_RANGE_VALUE",
            "application_type": "APPLICATION_TYPE",
        },
        ("CIOControl", "CTRL_ALLOW_"): {"start": "START", "stop": "STOP"},
        ("CIOTrigger", "TRIG_ALLOW_"): {
            "rising": "RISING",
            "falling": "FALLING",
        },
    }
    return explicit.get((owner, enum_prefix), {})


def minimal_enum_value_ids(owner: str, enum_prefix: str) -> dict[str, int]:
    return {
        value: idx
        for idx, value in enumerate(minimal_enum_map(owner, enum_prefix))
    }


def minimal_object_class_name(owner: str, method: str) -> str:
    del method
    for family in ("io_types", "prog_types", "proto_types"):
        for entry in minimal_type_defs()[family]:
            if entry["cpp_class"] == owner:
                return str(entry.get("object_class_name", entry["yaml_type"]))
    from dawnpy.headerdefs import HeaderDefsError

    raise HeaderDefsError(f"Unknown test owner {owner}")


@pytest.fixture
def source_free_headers(monkeypatch):
    """Install source-free descriptor headers for descriptor tests."""
    import dawnpy.headerdefs.bundle as header_bundle
    from dawnpy.descriptor.handlers import proto_nimble, proto_wakaama

    monkeypatch.setattr(
        header_bundle,
        "load_header_bundle",
        minimal_header_definition_set,
    )
    proto_nimble._nimble_service_defs.cache_clear()
    proto_wakaama._wakaama_enum_values.cache_clear()
    monkeypatch.setattr(
        proto_nimble,
        "load_header_nimble_service_defs",
        minimal_nimble_service_defs,
    )
    yield minimal_header_definition_set()
    proto_nimble._nimble_service_defs.cache_clear()
    proto_wakaama._wakaama_enum_values.cache_clear()


@pytest.fixture
def generator():
    return DescriptorGenerator()
