#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared test guards for standalone dawnpy unit tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest


class _DummyParams(list[str]):
    def __contains__(self, item: object) -> bool:
        if item == "rw":
            return False
        return super().__contains__(item)


def minimal_dtype_header_defs() -> dict[str, object]:
    """Dtype constants needed by descriptor registry/generator tests."""
    return {
        "dtype": [
            {
                "value": 0,
                "type": "any",
                "name": "DTYPE_ANY",
                "size": 0,
                "initval_param": 0,
            },
            {
                "value": 1,
                "type": "bool",
                "name": "DTYPE_BOOL",
                "size": 1,
                "initval_param": 1,
            },
            {
                "value": 2,
                "type": "int8",
                "name": "DTYPE_INT8",
                "size": 8,
                "initval_param": 2,
            },
            {
                "value": 3,
                "type": "uint8",
                "name": "DTYPE_UINT8",
                "size": 8,
                "initval_param": 3,
            },
            {
                "value": 4,
                "type": "int16",
                "name": "DTYPE_INT16",
                "size": 16,
                "initval_param": 4,
            },
            {
                "value": 5,
                "type": "uint16",
                "name": "DTYPE_UINT16",
                "size": 16,
                "initval_param": 5,
            },
            {
                "value": 6,
                "type": "int32",
                "name": "DTYPE_INT32",
                "size": 32,
                "initval_param": 6,
            },
            {
                "value": 7,
                "type": "uint32",
                "name": "DTYPE_UINT32",
                "size": 32,
                "initval_param": 7,
            },
            {
                "value": 8,
                "type": "int64",
                "name": "DTYPE_INT64",
                "size": 64,
                "initval_param": 8,
            },
            {
                "value": 9,
                "type": "uint64",
                "name": "DTYPE_UINT64",
                "size": 64,
                "initval_param": 9,
            },
            {
                "value": 10,
                "type": "float",
                "name": "DTYPE_FLOAT",
                "size": 32,
                "initval_param": 10,
            },
            {
                "value": 11,
                "type": "double",
                "name": "DTYPE_DOUBLE",
                "size": 64,
                "initval_param": 11,
            },
            {
                "value": 12,
                "type": "char",
                "name": "DTYPE_CHAR",
                "size": 8,
            },
            {
                "value": 13,
                "type": "b16",
                "name": "DTYPE_B16",
                "size": 16,
                "initval_param": 10,
            },
            {
                "value": 15,
                "type": "block",
                "name": "DTYPE_BLOCK",
                "size": 0,
            },
        ],
    }


def minimal_header_defs() -> dict[str, object]:
    """Small ObjectId definition set used by tests that need a decoder."""
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
        "io_classes": {
            1: "dummy",
            2: "descriptor",
            3: "desc_selector",
            4: "capabilities_legacy",
            5: "sensor",
            6: "sysinfo",
            7: "uname",
            8: "boardctl",
            9: "gpi",
            10: "gpo",
            11: "virt",
            12: "timestamp",
            13: "pwm",
            14: "encoder_legacy",
            15: "encoder_index_legacy",
            16: "dac",
            17: "rand",
            18: "config",
            19: "adc_fetch",
            20: "adc_sync",
            21: "adc_stream",
            22: "leds",
            23: "buttons",
            24: "control",
            25: "trigger",
            26: "gpi_single",
            27: "gpo_single",
            28: "system_uptime",
            29: "system_cpuload",
            30: "system_hostname",
            31: "system_resetcause",
            32: "sensor_humidity",
            33: "dummy_notify",
            34: "file",
            35: "system_systemtime",
            36: "system_uuid",
            37: "sensor_temperature",
            85: "capabilities",
            86: "encoder",
            87: "encoder_index",
            88: "system_reset",
            89: "system_poweroff",
        },
        "prog_classes": {
            1: "dummy",
            2: "stats",
            3: "stat_min",
            4: "sampling",
            5: "bit_split",
            6: "toggle_legacy",
            7: "counter",
            8: "switch",
            9: "expression",
            10: "selector",
            11: "bit_pack",
            12: "configwriter_legacy",
            13: "latest",
            14: "redirect",
            15: "stat_rms",
            16: "moving_avg",
            17: "iir_filter",
            18: "many_to_one",
            19: "one_to_many",
            20: "configwriter",
            21: "io_demux",
            22: "adjust",
            23: "vec_pack",
            24: "vec_split",
            25: "bitsplit",
            26: "bitpack",
            27: "toggle",
            28: "counter",
            29: "switch",
            30: "expression",
            31: "selector",
            32: "configwriter",
            33: "gateway",
            34: "statscount",
            35: "statsmax",
            36: "statssum",
            37: "statsavg",
            38: "threshold",
            39: "thresholdvalue",
            40: "buffer",
            41: "sequencer",
            42: "io_mux",
        },
        "proto_classes": {
            1: "serial",
            2: "can",
            3: "nxscope_udp_legacy",
            4: "modbus_rtu",
            5: "modbus_tcp_legacy",
            6: "nimble",
            7: "nimble_peripheral",
            8: "dummy",
            9: "shell",
            10: "nxscope_dummy",
            11: "nxscope_serial",
            12: "udp",
            13: "nxscope_udp",
            14: "ipc",
            19: "modbus_tcp",
        },
    }


def minimal_type_defs() -> dict[str, list[dict[str, object]]]:
    """Representative type definitions for registry-focused unit tests."""
    from dawnpy.descriptor.handlers import (
        IO_HANDLER_REGISTRY,
        PROG_HANDLER_REGISTRY,
        PROTO_HANDLER_REGISTRY,
    )

    io_param_overrides = {
        "dummy": _DummyParams(["dtype", "rw", "instance"]),
        "adc_fetch": ["timestamp", "instance"],
        "adc_sync": ["timestamp", "instance"],
        "adc_stream": ["timestamp", "instance"],
        "dac": ["timestamp", "instance"],
        "leds": ["timestamp", "instance"],
        "buttons": ["timestamp", "instance"],
        "pwm": ["timestamp", "instance"],
        "gpi": ["notify", "instance"],
        "gpo": ["notify", "instance"],
        "virt": ["dtype", "notify", "instance"],
        "rand": ["dtype", "timestamp", "instance"],
    }
    io_extra: dict[str, dict[str, object]] = {
        "sensor": {
            "helper_func": "{cpp_class}::objectId{subtype}",
            "subtypes": [
                "temp",
                "accel",
                "gyro",
                "mag",
                "press",
                "humi",
                "hum",
            ],
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
            "variants": [{"name": "default"}, {"name": "reset_cause"}],
        },
    }

    io_types: list[dict[str, object]] = []
    for yaml_type, handler in IO_HANDLER_REGISTRY.items():
        extra = io_extra.get(yaml_type, {})
        io_types.append(
            {
                "yaml_type": yaml_type,
                "cpp_class": handler.cpp_class,
                "header": f"dawn/io/{yaml_type}.hxx",
                "helper_func": extra.get(
                    "helper_func", "{cpp_class}::objectId"
                ),
                "params": extra.get(
                    "params",
                    io_param_overrides.get(yaml_type, ["dtype", "instance"]),
                ),
                **{
                    key: value
                    for key, value in extra.items()
                    if key not in ("helper_func", "params")
                },
            }
        )

    proto_header_overrides = {
        "serial": "dawn/proto/serial/simple.hxx",
        "can": "dawn/proto/can/can.hxx",
        "modbus_rtu": "dawn/proto/modbus/rtu.hxx",
        "modbus_tcp": "dawn/proto/modbus/tcp.hxx",
        "shell": "dawn/proto/shell/pretty.hxx",
        "nimble": "dawn/proto/nimble/prph.hxx",
        "nxscope_dummy": "dawn/proto/nxscope/dummy.hxx",
        "nxscope_serial": "dawn/proto/nxscope/serial.hxx",
        "nxscope_udp": "dawn/proto/nxscope/udp.hxx",
    }
    prog_overrides = {
        # The legacy YAML token still resolves through the process program
        # metadata in the generated Dawn definitions.
        "stats": {
            "cpp_class": "CProgProcess",
            "header": "dawn/prog/process.hxx",
        },
    }
    return {
        "io_types": io_types,
        "prog_types": [
            {
                "yaml_type": key,
                "cpp_class": prog_overrides.get(key, {}).get(
                    "cpp_class", handler.cpp_class
                ),
                "header": prog_overrides.get(key, {}).get(
                    "header", f"dawn/prog/{key}.hxx"
                ),
            }
            for key, handler in PROG_HANDLER_REGISTRY.items()
        ],
        "proto_types": [
            {
                "yaml_type": key,
                "cpp_class": handler.cpp_class,
                "header": proto_header_overrides.get(
                    key, f"dawn/proto/{key}.hxx"
                ),
            }
            for key, handler in PROTO_HANDLER_REGISTRY.items()
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


def minimal_header_bundle(
    *,
    groups=None,
    lookups=None,
):
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
    def _entry(name: str, include: str, kval: str) -> dict[str, str]:
        return {"name": name, "include": include, "kval": kval}

    return {
        "ios": [
            _entry("CIODummy", "dawn/io/dummy.hxx", "CONFIG_DAWN_IO_DUMMY"),
            _entry("CIOVirt", "dawn/io/virt.hxx", "CONFIG_DAWN_IO_VIRT"),
            _entry("CIOSensor", "dawn/io/sensor.hxx", "CONFIG_DAWN_IO_SENSOR"),
            _entry("CIOGpi", "dawn/io/gpi.hxx", "CONFIG_DAWN_IO_GPI"),
            _entry("CIOGpo", "dawn/io/gpo.hxx", "CONFIG_DAWN_IO_GPO"),
            _entry(
                "CIOCapabilities",
                "dawn/io/capabilities.hxx",
                "CONFIG_DAWN_IO_CAPABILITIES",
            ),
            _entry("CIOPwm", "dawn/io/pwm.hxx", "CONFIG_DAWN_IO_PWM"),
        ],
        "programs": [
            _entry(
                "CProgProcess",
                "dawn/prog/process.hxx",
                "CONFIG_DAWN_PROG_PROCESS",
            ),
            _entry(
                "CProgSampling",
                "dawn/prog/sampling.hxx",
                "CONFIG_DAWN_PROG_SAMPLING",
            ),
            _entry(
                "CProgAdjust",
                "dawn/prog/adjust.hxx",
                "CONFIG_DAWN_PROG_ADJUST",
            ),
        ],
        "protocols": [
            _entry(
                "CProtoCan",
                "dawn/proto/can/can.hxx",
                "CONFIG_DAWN_PROTO_CAN",
            ),
            _entry(
                "CProtoSerial",
                "dawn/proto/serial/simple.hxx",
                "CONFIG_DAWN_PROTO_SERIAL",
            ),
            _entry(
                "CProtoDummy",
                "dawn/proto/dummy.hxx",
                "CONFIG_DAWN_PROTO_DUMMY",
            ),
        ],
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
    if owner == "CProtoCan" and enum_prefix == "CAN_TYPE_":
        return {
            "read": "READ",
            "write": "WRITE",
            "uint8": "UINT8",
            "uint16": "UINT16",
            "uint32": "UINT32",
        }
    if owner == "CProtoModbusRegs" and enum_prefix == "MODBUS_TYPE_":
        return {
            "holding": "HOLDING",
            "input": "INPUT",
            "coil": "COIL",
            "uint16": "UINT16",
            "float": "FLOAT",
        }
    if owner == "CIOControl" and enum_prefix == "CTRL_ALLOW_":
        return {"start": "START", "stop": "STOP"}
    if owner == "CIOTrigger" and enum_prefix == "TRIG_ALLOW_":
        return {"rising": "RISING", "falling": "FALLING"}
    return {}


def minimal_enum_value_ids(owner: str, enum_prefix: str) -> dict[str, int]:
    return {
        value: idx
        for idx, value in enumerate(minimal_enum_map(owner, enum_prefix))
    }


def minimal_object_class_name(owner: str, method: str) -> str:
    if method != "objectId":
        return ""
    class_names = {
        "CIODummy": "dummy",
        "CIODescriptor": "descriptor",
        "CIODescSelector": "desc_selector",
        "CIOCapabilities": "capabilities",
        "CIOSensor": "sensor",
        "CIOSysinfo": "sysinfo",
        "CIOUname": "uname",
        "CIOBoardctl": "boardctl",
        "CIOGpi": "gpi",
        "CIOGpo": "gpo",
        "CIOVirt": "virt",
        "CIOTimestamp": "timestamp",
        "CIOSystime": "systime",
        "CIOUuid": "uuid",
        "CIOFile": "fileio",
        "CIOPwm": "pwm",
        "CIOEncoder": "encoder",
        "CIOEncoderIndex": "encoder_index",
        "CIODac": "dac",
        "CIORand": "rand",
        "CIOConfig": "config",
        "CIOAdcFetch": "adc_fetch",
        "CIOAdcSync": "adc_sync",
        "CIOAdcStream": "adc_stream",
        "CIOLeds": "leds",
        "CIOButtons": "buttons",
        "CIOControl": "control",
        "CIOTrigger": "trigger",
        "CProgDummy": "dummy",
        "CProgProcess": "stats",
        "CProgStatsAvg": "stats",
        "CProgStatsCount": "statscount",
        "CProgStatsMax": "statsmax",
        "CProgStatsSum": "statssum",
        "CProgStatsMin": "stat_min",
        "CProgSampling": "sampling",
        "CProgBitSplit": "bit_split",
        "CProgBitPack": "bit_pack",
        "CProgToggle": "toggle",
        "CProgCounter": "counter",
        "CProgSwitch": "switch",
        "CProgExpression": "expression",
        "CProgSelector": "selector",
        "CProgConfigWriter": "configwriter",
        "CProgGateway": "gateway",
        "CProgThreshold": "threshold",
        "CProgThresholdValue": "thresholdvalue",
        "CProgBuffer": "buffer",
        "CProgSequencer": "sequencer",
        "CProgLatest": "latest",
        "CProgRedirect": "redirect",
        "CProgStatsRms": "stat_rms",
        "CProgMovingAverage": "moving_avg",
        "CProgIIRFilter": "iir_filter",
        "CProgManyToOne": "many_to_one",
        "CProgOneToMany": "one_to_many",
        "CProgIOMux": "io_mux",
        "CProgIODemux": "io_demux",
        "CProgAdjust": "adjust",
        "CProgVecPack": "vec_pack",
        "CProgVecSplit": "vec_split",
        "CProtoSerial": "serial",
        "CProtoCan": "can",
        "CProtoNxscopeUdp": "nxscope_udp",
        "CProtoModbusRtu": "modbus_rtu",
        "CProtoModbusTcp": "modbus_tcp",
        "CProtoNimblePrph": "nimble",
        "CProtoDummy": "dummy",
        "CProtoShellPretty": "shell",
        "CProtoNxscopeDummy": "nxscope_dummy",
        "CProtoNxscopeSerial": "nxscope_serial",
        "CProtoUdp": "udp",
        "CProtoIpc": "ipc",
    }
    if owner not in class_names:
        from dawnpy.headerdefs import HeaderDefsError

        raise HeaderDefsError(f"Unknown test owner {owner}")
    return class_names[owner]


def blocked_repo_root_lookup() -> None:
    pytest.fail(
        "Unit tests must not discover or read Dawn sources. "
        "Mock the relevant dawnpy.headerdefs loader in the test instead."
    )


@pytest.fixture(autouse=True)
def block_dawn_source_reads(monkeypatch, request):
    """Prevent tests from accidentally reading the real Dawn checkout."""
    if request.node.path.name == "test_headerdefs.py":
        yield
        return

    import dawnpy.headerdefs._paths as headerdefs_paths

    monkeypatch.setattr(
        headerdefs_paths, "_repo_root_from_here", blocked_repo_root_lookup
    )

    import dawnpy.descriptor.definitions.registry as registry

    registry.reset_type_registry()
    yield
    registry.reset_type_registry()


@pytest.fixture
def source_free_headers(monkeypatch):
    """Install source-free descriptor headers for tests that need them."""
    import dawnpy.headerdefs.bundle as header_bundle
    from dawnpy.descriptor.handlers import proto_nimble

    monkeypatch.setattr(
        header_bundle,
        "load_header_bundle",
        minimal_header_definition_set,
    )
    proto_nimble._nimble_service_defs.cache_clear()
    monkeypatch.setattr(
        proto_nimble,
        "load_header_nimble_service_defs",
        minimal_nimble_service_defs,
    )
    yield minimal_header_definition_set()
    proto_nimble._nimble_service_defs.cache_clear()
