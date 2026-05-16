# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def _cfg_item_data(words: list[int]) -> list[list[int]]:
    items: list[list[int]] = []
    idx = 2
    for _ in range(words[1]):
        cfgid = words[idx]
        size = (cfgid >> 5) & 0x3FF
        idx += 1
        items.append(words[idx : idx + size])
        idx += size
    return items


def test_serialize_proto_shell_path_prompt_and_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {"dummy0": 0x11111111}
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="shell0",
        proto_type="shell",
        instance=0,
        config={"path": "/dev/ttyS0", "prompt": "dawn> "},
        bindings=["dummy0"],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["shell0"] != 0


def test_serialize_proto_can_with_objects():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="can0",
        proto_type="can",
        instance=0,
        config={
            "device": 1,
            "node_id": 0x21,
            "objects": [
                1,
                {
                    "type": "read",
                    "flags": 2,
                    "can_id_start": 0x80,
                    "bindings": [{"id": "io0"}, {"ref": "io1"}],
                },
                {"bindings": ["io0"]},
            ],
        },
        bindings=[],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["can0"] != 0
    assert len(words) > 0


def test_serialize_proto_modbus_with_registers_and_fallback_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_with_regs: list[int] = []
    proto_with_regs = ProtocolObject(
        obj_id="mb0",
        proto_type="modbus_rtu",
        instance=0,
        config={
            "path": "/tmp/ttySIM0",
            "baudrate": 115200,
            "registers": [
                1,
                {
                    "type": "holding",
                    "config": 1,
                    "start": 100,
                    "bindings": [{"id": "io0"}, {"ref": "io1"}],
                },
                {"bindings": ["io0"]},
            ],
        },
        bindings=[],
    )
    serialize_proto_object(words_with_regs, proto_with_regs, obj_ids, decoder)
    assert obj_ids["mb0"] != 0
    assert len(words_with_regs) > 0

    words_fallback: list[int] = []
    proto_fallback = ProtocolObject(
        obj_id="mb1",
        proto_type="modbus_rtu",
        instance=1,
        config={"path": "/tmp/ttySIM1"},
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_fallback, proto_fallback, obj_ids, decoder)
    assert obj_ids["mb1"] != 0
    assert len(words_fallback) > 0

    words_tcp: list[int] = []
    proto_tcp = ProtocolObject(
        obj_id="mbtcp0",
        proto_type="modbus_tcp",
        instance=0,
        config={
            "port": 502,
            "registers": [
                {
                    "type": "holding",
                    "config": 1,
                    "start": 100,
                    "bindings": ["io0"],
                },
            ],
        },
        bindings=[],
    )
    serialize_proto_object(words_tcp, proto_tcp, obj_ids, decoder)
    assert obj_ids["mbtcp0"] != 0
    assert 502 in words_tcp


def test_serialize_proto_nxscope_serial_and_dummy():
    def cfg_item_ids(words: list[int]) -> list[int]:
        item_ids: list[int] = []
        idx = 2
        for _ in range(words[1]):
            cfgid = words[idx]
            item_ids.append(cfgid & 0x1F)
            idx += 1 + ((cfgid >> 5) & 0x3FF)
        return item_ids

    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_serial: list[int] = []
    proto_serial = ProtocolObject(
        obj_id="nxs0",
        proto_type="nxscope_serial",
        instance=0,
        config={
            "iobind2": [
                {"id": "io0", "name": "a"},
                "io1",
                {"name": "missing"},
                1,
            ],
            "path": "/tmp/ttySIM0",
            "baudrate": 115200,
        },
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_serial, proto_serial, obj_ids, decoder)
    assert obj_ids["nxs0"] != 0
    assert len(words_serial) > 0
    assert 1 not in cfg_item_ids(words_serial)
    assert 2 in cfg_item_ids(words_serial)

    words_serial_unnamed: list[int] = []
    proto_serial_unnamed = ProtocolObject(
        obj_id="nxs1",
        proto_type="nxscope_serial",
        instance=1,
        config={"bindings": ["io0"]},
        bindings=["io0"],
    )
    serialize_proto_object(
        words_serial_unnamed, proto_serial_unnamed, obj_ids, decoder
    )
    assert 1 in cfg_item_ids(words_serial_unnamed)
    assert 2 not in cfg_item_ids(words_serial_unnamed)

    words_serial_bad_bindings: list[int] = []
    proto_serial_bad_bindings = ProtocolObject(
        obj_id="nxs2",
        proto_type="nxscope_serial",
        instance=2,
        config={"bindings": "io0"},
        bindings=[],
    )
    serialize_proto_object(
        words_serial_bad_bindings,
        proto_serial_bad_bindings,
        obj_ids,
        decoder,
    )
    assert cfg_item_ids(words_serial_bad_bindings) == []

    words_dummy: list[int] = []
    proto_dummy = ProtocolObject(
        obj_id="nxd0",
        proto_type="nxscope_dummy",
        instance=0,
        config={"iobind2": [{"id": "io0", "name": "d"}]},
        bindings=[],
    )
    serialize_proto_object(words_dummy, proto_dummy, obj_ids, decoder)
    assert obj_ids["nxd0"] != 0
    assert len(words_dummy) > 0

    words_udp: list[int] = []
    proto_udp = ProtocolObject(
        obj_id="nxu0",
        proto_type="nxscope_udp",
        instance=0,
        config={
            "iobind2": [{"id": "io0", "name": "u"}],
            "port": 50000,
        },
        bindings=["io0"],
    )
    serialize_proto_object(words_udp, proto_udp, obj_ids, decoder)
    assert obj_ids["nxu0"] != 0
    assert len(words_udp) > 0


def test_serialize_proto_nimble_services():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "bat0": 0x10000001,
        "di0": 0x10000002,
        "do0": 0x10000003,
        "ai0": 0x10000004,
        "t0": 0x10000005,
        "h0": 0x10000006,
        "p0": 0x10000007,
        "g0": 0x10000008,
        "fio0": 0x10000009,
        "fio1": 0x1000000A,
    }
    words: list[int] = []
    proto = ProtocolObject(
        obj_id="nim0",
        proto_type="nimble",
        instance=0,
        config={
            "gap_name": "thingy53",
            "services": {
                "dis": {"enabled": True},
                "bas": {"battery_level": {"id": "bat0"}},
                "aios": {
                    "groups": [
                        {
                            "digital_inputs": ["di0"],
                            "digital_outputs": ["do0"],
                        },
                        {"analog_inputs": ["ai0"]},
                        {"digital_inputs": "bad"},
                        1,
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t0"}},
                        {"type": "humidity", "data": {"id": "h0"}},
                        {"type": "pressure", "data": {"id": "p0"}},
                        {"type": "gas_resistance", "data": {"id": "g0"}},
                    ]
                },
                "imds": {
                    "temperature": {
                        "data": {"id": "t0"},
                        "metadata": {"user_description": "imds temp"},
                    },
                    "humidity": {"id": "h0"},
                    "pressure": {"id": "p0"},
                    "gas_resistance": {"id": "g0"},
                },
                "ots": {
                    "objects": [
                        {
                            "name": "ro",
                            "type": "file",
                            "access": "read",
                            "io": "fio0",
                        },
                        {
                            "type": "file",
                            "on_complete": "delete",
                            "io": {"id": "fio1"},
                        },
                        # Skipped: not a dict.
                        "bad-entry",
                        # Skipped: io is missing.
                        {"name": "no-io"},
                        # Skipped: io does not resolve.
                        {"name": "bad-io", "io": "missing"},
                    ]
                },
            },
        },
        bindings=[],
    )
    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["nim0"] != 0
    assert len(words) > 0

    words_bad_services: list[int] = []
    proto_bad_services = ProtocolObject(
        obj_id="nim1",
        proto_type="nimble",
        instance=1,
        config={"gap_name": "x", "services": []},
        bindings=[],
    )
    serialize_proto_object(
        words_bad_services, proto_bad_services, obj_ids, decoder
    )
    assert obj_ids["nim1"] != 0

    words_malformed_ess: list[int] = []
    proto_malformed_ess = ProtocolObject(
        obj_id="nim2",
        proto_type="nimble",
        instance=2,
        config={
            "services": {
                "ess": {
                    "characteristics": [
                        "bad",
                        {
                            "type": "temperature",
                            "data": {"id": "t0"},
                            "metadata": "bad",
                        },
                    ]
                }
            }
        },
        bindings=[],
    )
    serialize_proto_object(
        words_malformed_ess, proto_malformed_ess, obj_ids, decoder
    )
    assert obj_ids["nim2"] != 0

    words_bad_ess_shape: list[int] = []
    proto_bad_ess_shape = ProtocolObject(
        obj_id="nim3",
        proto_type="nimble",
        instance=3,
        config={"services": {"ess": {"characteristics": "bad"}}},
        bindings=[],
    )
    serialize_proto_object(
        words_bad_ess_shape, proto_bad_ess_shape, obj_ids, decoder
    )
    assert obj_ids["nim3"] != 0


def test_serialize_proto_udp_and_ipc():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
        "io1": 0x10000002,
    }

    words_udp: list[int] = []
    proto_udp = ProtocolObject(
        obj_id="udp0",
        proto_type="udp",
        instance=0,
        config={"port": 3344},
        bindings=["io0", "io1"],
    )
    serialize_proto_object(words_udp, proto_udp, obj_ids, decoder)
    assert obj_ids["udp0"] != 0
    assert len(words_udp) > 0

    words_ipc: list[int] = []
    proto_ipc = ProtocolObject(
        obj_id="ipc0",
        proto_type="ipc",
        instance=0,
        config={"rx_path": "/var/pipe/rx", "tx_path": "/var/pipe/tx"},
        bindings=["io0"],
    )
    serialize_proto_object(words_ipc, proto_ipc, obj_ids, decoder)
    assert obj_ids["ipc0"] != 0
    assert len(words_ipc) > 0


def test_serialize_proto_dummy_with_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "io0": 0x10000001,
    }

    words_dummy: list[int] = []
    proto_dummy = ProtocolObject(
        obj_id="dummy0",
        proto_type="dummy",
        instance=0,
        config={},
        bindings=["io0"],
    )
    serialize_proto_object(words_dummy, proto_dummy, obj_ids, decoder)
    assert obj_ids["dummy0"] != 0
    assert len(words_dummy) > 0


def test_default_enum_key_helper_branches():
    assert default_enum_key({"a": 1, "b": 2}, "x") == "a"
    assert default_enum_key({}, "x") == "x"


def test_serialize_proto_error_branches(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=[]
    )

    # The handler registry drives class resolution; remove "serial" from
    # both the handler registry and the PROTO_TYPES fallback to force the
    # failure path.
    monkeypatch.setattr(
        proto_serializer_mod,
        "PROTO_HANDLER_REGISTRY",
        {
            k: v
            for k, v in proto_serializer_mod.PROTO_HANDLER_REGISTRY.items()
            if k != "serial"
        },
    )
    monkeypatch.setattr(
        proto_serializer_mod,
        "PROTO_TYPES",
        {
            k: v
            for k, v in proto_serializer_mod.PROTO_TYPES.items()
            if k != "serial"
        },
    )
    with pytest.raises(click.ClickException, match="supports protocol type"):
        serialize_proto_object([], proto, {}, decoder)

    # Restore PROTO_TYPES; force handler-declared dtype lookup failures.
    monkeypatch.undo()
    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", lambda d, name: None
    )
    with pytest.raises(click.ClickException, match="protocol field 'string'"):
        serialize_proto_object([], proto, {}, decoder)

    def _dtype_missing_int(dec, name):
        if name == "char":
            return 14
        return None

    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", _dtype_missing_int
    )
    with pytest.raises(click.ClickException, match="protocol field 'int'"):
        serialize_proto_object([], proto, {}, decoder)

    # Custom (non-built-in) proto type cannot be resolved.
    custom_proto = ProtocolObject(
        obj_id="custom0",
        proto_type="custom_proto",
        instance=0,
        config={},
        bindings=[],
    )
    monkeypatch.setattr(
        proto_serializer_mod, "dtype_id_by_name", lambda d, n: 7
    )
    with pytest.raises(click.ClickException, match="supports protocol type"):
        serialize_proto_object([], custom_proto, {}, decoder)

    # UDP port dtype lookup failure names the handler-declared field.
    monkeypatch.setattr(
        proto_serializer_mod,
        "dtype_id_by_name",
        lambda dec, name: None if name == "uint16" else 7,
    )
    with pytest.raises(
        click.ClickException, match="protocol field 'udp_port'"
    ):
        serialize_proto_object(
            [],
            ProtocolObject(
                obj_id="udp0",
                proto_type="udp",
                instance=0,
                config={"port": 1},
                bindings=[],
            ),
            {},
            decoder,
        )


def test_serialize_proto_wakaama_standard_and_custom_objects():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "temp": 0x10000001,
        "counter": 0x10000002,
        "numeric": 0x10000003,
    }
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="lwm2m0",
        proto_type="wakaama",
        instance=0,
        config={
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
                {
                    "object": 33000,
                    "instance": 0,
                    "resources": [
                        {
                            "resource": 7,
                            "io": "numeric",
                            "access": "rw",
                        }
                    ],
                },
            ],
        },
        bindings=[],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    data_items = _cfg_item_data(words)

    assert obj_ids["lwm2m0"] != 0
    assert words[1] == 12
    assert [0x00020000, 0x00010000, 0x10000001] in data_items
    assert [0x000180E8, 0x00030007, 0x10000002] in data_items
    assert [0x000080E8, 0x00030007, 0x10000003] in data_items


def test_serialize_proto_wakaama_multi_server():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="lwm2m0",
        proto_type="wakaama",
        instance=0,
        config={
            "endpoint": "ntfc",
            "local_port": 56830,
            "lifetime": 60,
            "servers": [
                {"port": 5683, "lifetime": 60, "short_server_id": 123},
                {
                    "host": "192.0.2.1",
                    "port": 5684,
                    "lifetime": 120,
                    "short_server_id": 124,
                    "security_instance": 4,
                    "server_instance": 5,
                },
            ],
        },
        bindings=[],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    data_items = _cfg_item_data(words)

    assert words[1] == 4
    assert [0x00000000, 0x007B1633, 0x0000003C] in data_items
    assert any(
        item[:3] == [0x00040005, 0x007C1634, 0x00000078] for item in data_items
    )


def test_serialize_proto_wakaama_secure_bootstrap_server():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []

    proto = ProtocolObject(
        obj_id="lwm2m0",
        proto_type="wakaama",
        instance=0,
        config={
            "endpoint": "ntfc",
            "local_port": 56830,
            "servers": [
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
            ],
        },
        bindings=[],
    )

    serialize_proto_object(words, proto, obj_ids, decoder)
    data_items = _cfg_item_data(words)

    assert words[1] == 3
    assert any(
        item[:10]
        == [
            0x00020000,
            0x00001634,
            0x00000000,
            0x574B4131,
            0x00010001,
            0x00000005,
            0x0000001E,
            0x00000004,
            0x00000004,
            0x00000004,
        ]
        for item in data_items
    )


def test_serialize_proto_wakaama_ignores_malformed_objects():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}

    bad_objects: list[int] = []
    serialize_proto_object(
        bad_objects,
        ProtocolObject(
            obj_id="lwm2m0",
            proto_type="wakaama",
            instance=0,
            config={"objects": {}},
            bindings=[],
        ),
        obj_ids,
        decoder,
    )
    assert bad_objects[1] == 0

    malformed: list[int] = []
    serialize_proto_object(
        malformed,
        ProtocolObject(
            obj_id="lwm2m1",
            proto_type="wakaama",
            instance=1,
            config={
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
            bindings=[],
        ),
        obj_ids,
        decoder,
    )
    assert malformed[1] == 0


def test_serialize_proto_non_dict_cfg_sections(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=[]
    )
    serialize_proto_object([], proto, {}, decoder)


def test_serialize_proto_nimble_non_dict_maps():
    decoder = ObjectIdDecoder()
    obj_ids = {"io0": 0x10000001}
    proto = ProtocolObject(
        obj_id="nimx",
        proto_type="nimble",
        instance=0,
        config={
            "services": {"aios": {"groups": [{"digital_inputs": "bad"}]}},
        },
        bindings=[],
    )
    serialize_proto_object([], proto, obj_ids, decoder)


def test_serialize_proto_nimble_service_enum_paths(monkeypatch):
    decoder = ObjectIdDecoder()
    obj_ids = {"di0": 0x10000001, "ai0": 0x10000002, "t0": 0x10000003}
    proto = ProtocolObject(
        obj_id="nimsvc",
        proto_type="nimble",
        instance=0,
        config={
            "services": {
                "aios": {
                    "groups": [
                        {"digital_inputs": ["di0", "ai0"]},
                        {"digital_inputs": "bad"},
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t0"}}
                    ]
                },
                "imds": {"temperature": {"id": "t0"}},
            }
        },
        bindings=[],
    )

    def _enum_map(owner, _prefix):
        if owner == "CProtoNimblePrphAios":
            return {"digital_inputs": 1}
        return {"temperature": 2}

    monkeypatch.setattr(
        proto_serializer_mod, "header_enum_value_ids", _enum_map
    )
    words: list[int] = []
    serialize_proto_object(words, proto, obj_ids, decoder)
    assert obj_ids["nimsvc"] != 0
    assert len(words) > 0


def test_serialize_proto_defensive_header_enum_failure(monkeypatch):
    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="s1",
        proto_type="can",
        instance=0,
        config={},
        bindings=[],
    )

    # When headerdefs raises for an enum prefix, the safe-resolver returns {}
    # and serialization proceeds without crashing.
    def _raise(*_a):
        raise proto_serializer_mod.HeaderDefsError("missing")

    monkeypatch.setattr(proto_serializer_mod, "header_enum_value_ids", _raise)
    serialize_proto_object([], proto, {}, decoder)
