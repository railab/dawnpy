# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def _wakaama_proto() -> ProtocolObject:
    return ProtocolObject(
        "lwm2m0",
        "wakaama",
        0,
        {
            "endpoint": "ntfc",
            "server_host": "127.0.0.1",
            "server_port": 5683,
            "local_port": 56830,
            "lifetime": 60,
            "device": {
                "manufacturer": "Dawn",
                "model_number": "qemu-intel64",
                "serial_number": "dawn-wakaama",
                "firmware_version": "0.1",
            },
            "objects": [
                {
                    "object": "temperature",
                    "instance": 2,
                    "resources": [
                        {
                            "resource": "sensor_value",
                            "io": {"id": "temp"},
                            "access": "read",
                        }
                    ],
                },
                {
                    "object_id": 33000,
                    "instance": 1,
                    "resources": [
                        {
                            "resource_id": 7,
                            "io": "counter",
                            "access": "rw",
                        }
                    ],
                },
            ],
        },
        [],
    )


def test_wakaama_validate_objects_shape():
    from dawnpy.descriptor.handlers import proto_wakaama

    assert (
        proto_wakaama.validate_object(
            ProtocolObject("lwm2m0", "wakaama", 0, {}, [])
        )
        == []
    )
    assert proto_wakaama.validate_object(
        ProtocolObject("lwm2m0", "wakaama", 0, {"objects": {}}, [])
    ) == ["config.objects must be a list"]
    assert proto_wakaama.validate_object(
        ProtocolObject("lwm2m0", "wakaama", 0, {"device": []}, [])
    ) == ["config.device must be a mapping"]

    assert proto_wakaama.validate_object(
        ProtocolObject(
            "lwm2m0",
            "wakaama",
            0,
            {"objects": [None, {"resources": "bad"}]},
            [],
        )
    ) == [
        "config.objects[0] must be a mapping",
        "config.objects[1].resources must be a list",
    ]

    errors = proto_wakaama.validate_object(
        ProtocolObject(
            "lwm2m0",
            "wakaama",
            0,
            {
                "objects": [
                    {
                        "resources": [
                            1,
                            {"resource": "sensor_value", "access": "bad"},
                        ]
                    },
                ]
            },
            [],
        )
    )

    assert "config.objects[0].resources[0] must be a mapping" in errors
    assert (
        "config.objects[0].resources[1].access must be one of "
        "read, write, rw, execute"
    ) in errors

    assert (
        proto_wakaama.validate_object(
            ProtocolObject(
                "lwm2m0",
                "wakaama",
                0,
                {
                    "objects": [
                        {
                            "resources": [
                                {
                                    "resource": "firmware_update",
                                    "access": "execute",
                                },
                            ]
                        },
                    ]
                },
                [],
            )
        )
        == []
    )


def test_wakaama_validate_numeric_ranges():
    from dawnpy.descriptor.handlers import proto_wakaama

    errors = proto_wakaama.validate_object(
        ProtocolObject(
            "lwm2m0",
            "wakaama",
            0,
            {
                "server_port": "bad",
                "local_port": 65536,
                "lifetime": 4294967296,
                "objects": [
                    {
                        "object_id": 70000,
                        "instance": -1,
                        "resources": [
                            {
                                "resource_id": 65536,
                                "io": "temp",
                            }
                        ],
                    },
                    {
                        "object": "",
                        "object_id": "bad",
                        "resources": [
                            {
                                "resource": "",
                                "resource_id": "bad",
                            }
                        ],
                    },
                    {
                        "object": "70000",
                        "resources": [
                            {
                                "resource": "65536",
                            }
                        ],
                    },
                ],
            },
            [],
        )
    )

    assert "config.server_port must be an integer in range 0..65535" in errors
    assert "config.local_port must be an integer in range 0..65535" in errors
    assert (
        "config.lifetime must be an integer in range 0..4294967295" in errors
    )
    assert (
        "config.objects[0].object_id must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.objects[0].instance must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.objects[0].resources[0].resource_id must be an integer in "
        "range 0..65535"
    ) in errors
    assert (
        "config.objects[1].object_id must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.objects[1].resources[0].resource_id must be an integer in "
        "range 0..65535"
    ) in errors
    assert (
        "config.objects[2].object must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.objects[2].resources[0].resource must be an integer in "
        "range 0..65535"
    ) in errors
    with pytest.raises(ValueError, match="Wakaama uint16 value out of range"):
        proto_wakaama._pack_u16_pair(70000, 1)


def test_wakaama_allocation_rows_invalid_shapes():
    rows = _wakaama_allocation_rows({"endpoint": "x", "objects": {}})
    assert rows == [
        [
            "0",
            "client",
            "n/a",
            "n/a",
            "0",
            "endpoint=x, servers=n/a:n/a, ios=none",
        ]
    ]

    rows = _wakaama_allocation_rows(
        {
            "objects": [
                1,
                {"object": "temperature", "resources": "bad"},
                {"object": "temperature", "resources": [1]},
            ]
        }
    )

    assert rows[1] == [
        "1",
        "object.1",
        "0",
        "0",
        "0",
        "resources=none, ios=none",
    ]
    assert rows[2] == [
        "2",
        "object.2",
        "0",
        "0",
        "0",
        "resources=none, ios=none",
    ]


def test_wakaama_allocation_rows_unresolved_symbols(monkeypatch):
    from dawnpy.descriptor.handlers import proto_wakaama

    def _raise(*_args):
        raise HeaderDefsError("missing")

    proto_wakaama._wakaama_enum_values.cache_clear()
    monkeypatch.setattr(proto_wakaama, "load_header_enum_value_ids", _raise)
    rows = _wakaama_allocation_rows(
        {
            "objects": [
                {
                    "object": "temperature",
                    "resources": [{"resource": "sensor_value", "io": "temp"}],
                }
            ]
        }
    )

    assert rows[1] == [
        "1",
        "object.0",
        "temperature",
        "0",
        "1",
        "resources=sensor_value, ios=temp",
    ]
    proto_wakaama._wakaama_enum_values.cache_clear()


def test_wakaama_generate_cpp_standard_and_custom_objects(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    gctx = generator._protocol_config_generator().ctx
    lines = proto_wakaama.generate_cpp("WAKAAMA0", _wakaama_proto(), gctx)
    text = "\n".join(lines)

    assert lines[0].strip() == "WAKAAMA0, 11,"
    assert "CProtoWakaama::cfgIdEndpoint" in text
    assert "CProtoWakaama::cfgIdServerHost" in text
    assert "CProtoWakaama::cfgIdServerPort" in text
    assert "CProtoWakaama::cfgIdLocalPort" in text
    assert "CProtoWakaama::cfgIdLifetime" in text
    assert "CProtoWakaama::cfgIdDeviceManufacturer" in text
    assert "CProtoWakaama::cfgIdDeviceModelNumber" in text
    assert "CProtoWakaama::cfgIdDeviceSerialNumber" in text
    assert "CProtoWakaama::cfgIdDeviceFirmwareVersion" in text
    assert "CProtoWakaama::cfgIdIOBind(3)" in text
    assert "CProtoWakaama::WAKAAMA_OBJECT_TEMPERATURE" in text
    assert "CProtoWakaama::WAKAAMA_RESOURCE_SENSOR_VALUE" in text
    assert "TEMP," in text
    assert "COUNTER," in text
    assert "0x000180e8" in text
    assert "0x00030007" in text


def test_wakaama_generate_cpp_queue_mode(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    gctx = generator._protocol_config_generator().ctx
    proto = _wakaama_proto()
    proto.config["queue_mode"] = True
    lines = proto_wakaama.generate_cpp("WAKAAMA0", proto, gctx)

    qm = [i for i, ln in enumerate(lines) if "cfgIdQueueMode()" in ln]
    assert qm, "queue_mode config item not emitted"
    # A YAML bool must serialize to the integer 1, not Python's "True".
    assert lines[qm[0] + 1].strip() == "1,"


def test_wakaama_generate_cpp_device_battery(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    gctx = generator._protocol_config_generator().ctx
    proto = ProtocolObject(
        "lwm2m0",
        "wakaama",
        0,
        {
            "endpoint": "ntfc",
            "server_host": "127.0.0.1",
            "server_port": 5683,
            "local_port": 56830,
            "lifetime": 60,
            "device": {
                "manufacturer": "Dawn",
                # valid -> emitted
                "battery_voltage": {"id": "battvolt"},
                # present but unresolvable -> skipped (if not io_id)
                "battery_level": {"missing_id": 1},
                # battery_status absent -> skipped (if ref is None)
            },
        },
        [],
    )
    lines = proto_wakaama.generate_cpp("WAKAAMA0", proto, gctx)
    text = "\n".join(lines)

    assert "CProtoWakaama::cfgIdDeviceBatteryVoltage" in text
    assert "BATTVOLT," in text
    assert "cfgIdDeviceBatteryLevel" not in text
    assert "cfgIdDeviceBatteryStatus" not in text


def test_wakaama_generate_cpp_multi_server(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    proto = _wakaama_proto()
    proto.config.pop("server_host")
    proto.config.pop("server_port")
    proto.config["servers"] = [
        {"port": 5683, "lifetime": 60, "short_server_id": 123},
        {
            "host": "192.0.2.1",
            "port": 5684,
            "lifetime": 120,
            "short_server_id": 124,
            "security_instance": 4,
            "server_instance": 5,
        },
    ]

    gctx = generator._protocol_config_generator().ctx
    lines = proto_wakaama.generate_cpp("WAKAAMA0", proto, gctx)
    text = "\n".join(lines)

    assert lines[0].strip() == "WAKAAMA0, 10,"
    assert "CProtoWakaama::cfgIdServer(3)" in text
    assert "CProtoWakaama::cfgIdServer(7)" in text
    assert "CProtoWakaama::cfgIdServerHost" not in text
    assert "CProtoWakaama::cfgIdServerPort" not in text
    assert "0x00000000" in text
    assert "0x007b1633" in text
    assert "0x00040005" in text
    assert "0x007c1634" in text


def test_wakaama_generate_cpp_secure_bootstrap_server(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    proto = _wakaama_proto()
    proto.config.pop("server_host")
    proto.config.pop("server_port")
    proto.config["servers"] = [
        {
            "host": "192.0.2.2",
            "port": 5684,
            "scheme": "coaps",
            "security_mode": "psk",
            "psk_identity": "client",
            "psk_key": "01020304",
            "bootstrap": True,
            "holdoff": 5,
            "bootstrap_timeout": 30,
            "security_instance": 2,
        },
    ]

    gctx = generator._protocol_config_generator().ctx
    lines = proto_wakaama.generate_cpp("WAKAAMA0", proto, gctx)
    text = "\n".join(lines)

    assert "CProtoWakaama::cfgIdServer(22)" in text
    assert "0x574b4131" in text
    assert "0x00010001" in text
    assert "0x00000005" in text
    assert "0x0000001e" in text


def test_wakaama_validate_server_entries():
    from dawnpy.descriptor.handlers import proto_wakaama

    assert proto_wakaama.validate_object(
        ProtocolObject("lwm2m0", "wakaama", 0, {"servers": {}}, [])
    ) == ["config.servers must be a list"]

    assert (
        proto_wakaama.allocation_rows(
            ProtocolObject("lwm2m0", "wakaama", 0, {"servers": {}}, [])
        )[0][5]
        == "endpoint=n/a, servers=n/a:n/a, ios=none"
    )

    errors = proto_wakaama.validate_object(
        ProtocolObject(
            "lwm2m0",
            "wakaama",
            0,
            {
                "servers": [
                    "bad",
                    {"port": 5683, "short_server_id": 123},
                    {
                        "host": 1,
                        "port": 65536,
                        "server_port": -1,
                        "lifetime": 4294967296,
                        "short_server_id": 65536,
                        "security_instance": -1,
                        "server_instance": 65536,
                    },
                ],
            },
            [],
        )
    )

    assert "config.servers[0] must be a mapping" in errors
    assert "config.servers[1].lifetime is required" in errors
    assert "config.servers[2].host must be a string" in errors
    assert (
        "config.servers[2].port must be an integer in range 0..65535" in errors
    )
    assert (
        "config.servers[2].server_port must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.servers[2].lifetime must be an integer in range 0..4294967295"
        in errors
    )
    assert (
        "config.servers[2].short_server_id must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.servers[2].security_instance must be an integer in range 0..65535"
        in errors
    )
    assert (
        "config.servers[2].server_instance must be an integer in range 0..65535"
        in errors
    )


def test_wakaama_validate_secure_and_bootstrap_servers():
    from dawnpy.descriptor.handlers import proto_wakaama

    assert (
        proto_wakaama.validate_object(
            ProtocolObject(
                "lwm2m0",
                "wakaama",
                0,
                {
                    "servers": [
                        {
                            "port": 5684,
                            "scheme": "coaps",
                            "security_mode": "psk",
                            "psk_identity": "client",
                            "psk_key": "01020304",
                            "lifetime": 60,
                            "short_server_id": 123,
                        }
                    ]
                },
                [],
            )
        )
        == []
    )

    errors = proto_wakaama.validate_object(
        ProtocolObject(
            "lwm2m0",
            "wakaama",
            0,
            {
                "servers": [
                    {
                        "port": 5684,
                        "lifetime": 60,
                        "short_server_id": 123,
                        "scheme": "bad",
                        "security_mode": "cert",
                    },
                    {
                        "port": 5684,
                        "lifetime": 60,
                        "short_server_id": 123,
                        "security_mode": "psk",
                        "psk_identity": 1,
                        "psk_key": "abc",
                    },
                    {
                        "port": 5685,
                        "bootstrap": True,
                        "holdoff": 4294967296,
                        "bootstrap_timeout": -1,
                    },
                    {"port": 5685, "bootstrap": True},
                ],
            },
            [],
        )
    )

    assert "config.servers[0].scheme must be one of coap, coaps" in errors
    assert "config.servers[0].security_mode must be one of none, psk" in errors
    assert (
        "config.servers[1].security_mode psk requires scheme coaps" in errors
    )
    assert "config.servers[1].psk_identity must be a string" in errors
    assert (
        "config.servers[1].psk_key must be an even-length hex string" in errors
    )
    assert (
        "config.servers[2].holdoff must be an integer in range 0..4294967295"
        in errors
    )
    assert (
        "config.servers[2].bootstrap_timeout must be an integer in range "
        "0..4294967295"
    ) in errors
    assert "config.servers[3].holdoff is required" in errors


def test_wakaama_validate_descriptor_context_handles_malformed_entries():
    from dawnpy.descriptor.handlers import proto_wakaama

    proto_wakaama.validate_descriptor_context("lwm2m0", {"objects": {}}, {})

    config = {
        "objects": [
            "malformed",
            {"resources": "malformed"},
            {"resources": ["malformed", {"resource": "on_off"}]},
            {"resources": [{"resource": "on_off", "io": "missing"}]},
        ]
    }

    with pytest.raises(ValueError) as excinfo:
        proto_wakaama.validate_descriptor_context("lwm2m0", config, {})

    assert "references unknown IO 'missing'" in str(excinfo.value)


def test_wakaama_validate_descriptor_context_checks_io_shapes():
    from dawnpy.descriptor.handlers import proto_wakaama

    config = {
        "objects": [
            {
                "object": "binary_app_data_container",
                "resources": [
                    {
                        "resource": "binary_app_data",
                        "io": "counter",
                        "access": "rw",
                    },
                    {
                        "resource": "on_off",
                        "io": "counter",
                        "access": "rw",
                    },
                    {
                        "resource": "sensor_value",
                        "io": "flag",
                        "access": "read",
                    },
                    {
                        "resource": "firmware_update",
                        "io": "flag",
                        "access": "execute",
                    },
                    {
                        "resource": "firmware_update",
                        "io": "trigger",
                        "access": "execute",
                    },
                ],
            }
        ]
    }
    objects = {
        "counter": SimpleNamespace(dtype="uint32", io_type="dummy"),
        "flag": SimpleNamespace(dtype="bool", io_type="dummy"),
        "trigger": SimpleNamespace(dtype="uint32", io_type="trigger"),
    }

    with pytest.raises(ValueError) as excinfo:
        proto_wakaama.validate_descriptor_context("lwm2m0", config, objects)

    message = str(excinfo.value)
    assert "resource 'binary_app_data' requires dtype ['block']" in message
    assert "resource 'on_off' requires dtype ['bool']" in message
    assert "resource 'sensor_value' requires numeric dtype" in message
    assert "execute resource objects[0].resources[3]" in message
    assert "objects[0].resources[4]" not in message


def test_wakaama_generate_cpp_ignores_malformed_objects(generator):
    from dawnpy.descriptor.handlers import proto_wakaama

    gctx = generator._protocol_config_generator().ctx

    no_objects = ProtocolObject("lwm2m0", "wakaama", 0, {"objects": {}}, [])
    assert proto_wakaama.generate_cpp("WAKAAMA0", no_objects, gctx) == [
        "  WAKAAMA0, 0,"
    ]

    malformed = ProtocolObject(
        "lwm2m1",
        "wakaama",
        1,
        {
            "objects": [
                {"object_id": 42, "resources": "bad"},
                {
                    "object": "temperature",
                    "resources": [
                        1,
                        {"resource_id": 8},
                    ],
                },
            ]
        },
        [],
    )
    assert proto_wakaama.generate_cpp("WAKAAMA1", malformed, gctx) == [
        "  WAKAAMA1, 0,"
    ]

    fallback_ids = ProtocolObject(
        "lwm2m2",
        "wakaama",
        2,
        {
            "objects": [
                {
                    "object": "",
                    "object_id": 33000,
                    "resources": [
                        {
                            "resource": "",
                            "resource_id": 7,
                            "io": "counter",
                        }
                    ],
                }
            ]
        },
        [],
    )
    text = "\n".join(
        proto_wakaama.generate_cpp("WAKAAMA2", fallback_ids, gctx)
    )
    assert "0x000080e8" in text
    assert "0x00010007" in text


def test_wakaama_enum_values_header_failure(monkeypatch):
    from dawnpy.descriptor.handlers import proto_wakaama

    def _raise(*_args):
        raise HeaderDefsError("missing")

    proto_wakaama._wakaama_enum_values.cache_clear()
    monkeypatch.setattr(proto_wakaama, "load_header_enum_value_ids", _raise)
    assert proto_wakaama._wakaama_enum_values("wakaama_object") == {}
    proto_wakaama._wakaama_enum_values.cache_clear()
