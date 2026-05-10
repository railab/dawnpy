# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_nxscope_allocation_rows_resolves_iobind2():
    config = {
        "iobind2": [
            "io1",
            {"id": "io2"},
            {"io": "io3"},
            {"ref": "io4"},
            123,
        ],
        "path": "/dev/tty",
        "baudrate": 9600,
    }
    rows = _nxscope_allocation_rows(config, ["io1"])
    assert any("names=5" in row[-1] for row in rows)
    assert any("path=/dev/tty" in row[-1] for row in rows)


def test_nxscope_allocation_rows_uses_names_fallback():
    config = {"names": ["a", "b", "c"]}
    rows = _nxscope_allocation_rows(config, [])
    assert any("names=3" in row[-1] for row in rows)


def test_can_allocation_rows_indexed_and_empty_group():
    """CAN allocation helper reserves indexed IDs only for bindings."""
    rows = _can_allocation_rows(
        {
            "node_id": 256,
            "objects": [
                {
                    "type": "read_indexed",
                    "can_id_start": 5,
                    "count": 0,
                    "bindings": [],
                },
                {
                    "type": "write_indexed",
                    "can_id_start": 6,
                    "count": 2,
                    "bindings": [],
                },
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert rows[0][4] == "0"
    assert "ios=none" in rows[0][5]
    assert rows[1][2] == "n/a"
    assert rows[1][3] == "n/a"
    assert rows[1][4] == "0"
    assert "ios=none" in rows[1][5]


def test_can_allocation_rows_ignores_user_count():
    rows = _can_allocation_rows(
        {
            "node_id": 0,
            "objects": [
                {
                    "type": "read",
                    "can_id_start": 16,
                    "count": "CONFIG_COUNT",
                    "bindings": [],
                }
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert "CONFIG_COUNT" not in rows[0][5]


def test_can_allocation_rows_with_kconfig_start():
    rows = _can_allocation_rows(
        {
            "node_id": 0,
            "objects": [
                {
                    "type": "read",
                    "can_id_start": "CONFIG_START",
                    "count": 1,
                    "bindings": [],
                }
            ],
        }
    )
    assert rows[0][2] == "n/a"
    assert "note=can_id_start=CONFIG_START assumed 0" in rows[0][5]


def test_modbus_allocation_rows_with_registers():
    """Modbus allocation helper builds ranges from register blocks."""
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": 100,
                    "count": 3,
                    "bindings": [],
                },
            ]
        }
    )
    assert rows == [
        ["0", "holding", "100", "102", "3", "start=100, config=0, ios=none"]
    ]


def test_modbus_allocation_rows_with_kconfig_start():
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": "CONFIG_BASE",
                    "count": 1,
                    "bindings": [],
                },
            ]
        }
    )
    assert rows[0][2] == "0"
    assert "note=start=CONFIG_BASE assumed 0" in rows[0][5]


def test_modbus_allocation_rows_with_kconfig_count():
    rows = _modbus_allocation_rows(
        {
            "registers": [
                {
                    "type": "holding",
                    "start": 10,
                    "count": "CONFIG_COUNT",
                    "bindings": [],
                },
            ]
        }
    )
    assert "note=count=CONFIG_COUNT assumed 0" in rows[0][5]


def test_serial_nxscope_shell_allocation_rows():
    """Protocol-specific rows include config details for non-CAN protocols."""
    serial_rows = _serial_allocation_rows(
        {"path": "/dev/ttyS2", "baudrate": 230400},
        ["io1", "io2"],
    )
    assert (
        serial_rows[0][5] == "path=/dev/ttyS2, baudrate=230400, ios=io1, io2"
    )

    nxscope_rows = _nxscope_allocation_rows(
        {
            "iobind2": [
                {"id": "io1", "name": "a"},
                {"id": "io2", "name": "b"},
            ],
            "path": "/dev/ttyS1",
            "baudrate": 115200,
        },
        [],
    )
    assert (
        nxscope_rows[0][5]
        == "names=2, path=/dev/ttyS1, baudrate=115200, ios=io1, io2"
    )

    shell_rows = _shell_allocation_rows(
        {"prompt": "dawn>"},
        ["io1"],
    )
    assert shell_rows[0][5] == "prompt=dawn>, ios=io1"


def test_bindings_allocation_rows_with_custom_details():
    """Bindings row helper supports details text."""
    rows = _bindings_allocation_rows(["io1"], details="custom")
    assert rows == [["0", "bind-index", "1", "1", "1", "custom, ios=io1"]]


def test_nimble_allocation_rows_services():
    """Nimble summary should include service rows with bound IO details."""
    rows = _nimble_allocation_rows(
        {
            "gap_name": "thingy",
            "services": {
                "dis": {"enabled": True},
                "bas": {"battery_level": {"id": "bat1"}},
                "aios": {
                    "groups": [
                        {
                            "digital_inputs": [
                                {
                                    "data": {"id": "in1"},
                                    "metadata": {"user_description": "input"},
                                }
                            ],
                            "analog_outputs": [{"id": "out1"}],
                        }
                    ]
                },
                "ess": {
                    "characteristics": [
                        {"type": "temperature", "data": {"id": "t1"}},
                        {"type": "humidity", "data": {"id": "h1"}},
                    ]
                },
                "imds": {"pressure": {"id": "p1"}},
            },
        }
    )
    assert rows[0] == [
        "0",
        "gap",
        "n/a",
        "n/a",
        "0",
        "gap_name=thingy, ios=none",
    ]
    assert rows[1][1] == "dis"
    assert rows[1][5] == "enabled=true, ios=none"
    assert rows[2][1] == "bas"
    assert rows[2][5] == "ios=bat1"
    assert rows[3][1] == "aios.group0"
    assert rows[3][4] == "2"
    assert rows[3][5] == "ios=in1, out1"
    assert rows[4][1] == "ess"
    assert rows[4][5] == "ios=t1, h1"
    assert rows[5][1] == "imds"
    assert rows[5][5] == "ios=p1"


def test_nimble_allocation_rows_with_invalid_services_shape():
    """Nimble summary should keep gap row when services config is invalid."""
    rows = _nimble_allocation_rows({"gap_name": "x", "services": []})
    assert rows == [["0", "gap", "n/a", "n/a", "0", "gap_name=x, ios=none"]]


def test_nimble_allocation_rows_skips_invalid_group_and_sensor_shapes():
    """Nimble summary skips malformed aios/ess/imds configs."""
    rows = _nimble_allocation_rows(
        {
            "gap_name": "x",
            "services": {
                "aios": {"groups": ["bad_group"]},
                "ess": {"characteristics": ["bad_ess"]},
                "imds": "bad_imds",
            },
        }
    )
    # malformed entries are skipped; dis defaults to disabled row
    assert rows == [
        ["0", "gap", "n/a", "n/a", "0", "gap_name=x, ios=none"],
        ["1", "dis", "n/a", "n/a", "0", "enabled=false, ios=none"],
        ["2", "bas", "n/a", "n/a", "0", "ios=none"],
        ["3", "ess", "n/a", "n/a", "0", "ios=none"],
    ]


def test_fmt_bindings_empty_and_list():
    """Binding formatter supports empty and populated lists."""
    assert _fmt_bindings([]) == "none"
    assert _fmt_bindings(["io1", "io2"]) == "io1, io2"


def test_print_table_wrap_and_empty_cell(capsys):
    """Table renderer should wrap long cells and handle empty cells."""
    headers = ["block", "kind", "start", "end", "count", "details"]
    rows = [
        [
            "0",
            "read",
            "0x1",
            "0x1",
            "1",
            "this is a very long details text that must wrap "
            "into multiple lines for readability",
        ],
        ["1", "write", "0x2", "0x2", "1", ""],
    ]
    _print_table(headers, rows)
    out = capsys.readouterr().out
    assert "block | kind" in out
    assert "this is a very long details text" in out
    # rich's MARKDOWN box with show_lines emits a separator between every row
    assert out.count("|--") >= 2


def test_print_protocol_allocation_summaries_unknown_and_empty(capsys):
    """Summary handles unknown protocol and empty descriptors."""
    empty = ClientDescriptor(ios={}, programs=[], protocols=[])
    print_protocol_allocation_summaries(empty, {})
    out = capsys.readouterr().out
    assert out == ""

    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="x1",
                proto_type="unknown_proto",
                instance=1,
                config={},
                bindings=[],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "x1 (unknown_proto)" in out
    assert "unsupported protocol" in out


def test_print_object_summary_tables(capsys):
    io = ClientIo(
        io_id="io1",
        io_type="dummy",
        instance=1,
        dtype="uint8",
        tags=["tag1"],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    prog = ClientProgram(
        prog_id="prog1",
        prog_type="statsmin",
        instance=1,
        inputs=["io1"],
        outputs=["io1"],
        config={},
    )
    proto = ClientProto(
        proto_id="can1",
        proto_type="can",
        instance=1,
        config={},
        bindings=["io1"],
    )
    desc = ClientDescriptor(
        ios={"io1": io},
        programs=[prog],
        protocols=[proto],
    )

    _print_object_summary(desc)
    out = capsys.readouterr().out
    assert "Object summary:" in out
    assert "IO objects:" in out
    assert "Program objects:" in out
    assert "Protocol objects:" in out
    assert "0x" in out


def test_print_protocol_allocation_summaries_modbus_fallback(capsys):
    """Modbus without registers falls back to binding index table."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="mb1",
                proto_type="modbus_rtu",
                instance=1,
                config={},
                bindings=["io1", "io2"],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "mb1 (modbus_rtu)" in out
    assert "bind-index" in out
    assert "registers=0" in out
    assert "ios=io1, io2" in out


def test_print_protocol_allocation_summaries_nxscope_and_shell(capsys):
    """Summary should print per-protocol details for nxscope and shell."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="nx1",
                proto_type="nxscope_serial",
                instance=1,
                config={"names": ["x", "y", "z"], "baudrate": 115200},
                bindings=["io1"],
            ),
            ClientProto(
                proto_id="sh1",
                proto_type="shell",
                instance=1,
                config={"prompt": "sh>"},
                bindings=["io2"],
            ),
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "nx1 (nxscope_serial)" in out
    assert "names=3" in out
    assert "baudrate=115200" in out
    assert "ios=io1" in out
    assert "sh1 (shell)" in out
    assert "prompt=sh>" in out
    assert "ios=io2" in out


def test_print_protocol_allocation_summaries_nimble(capsys):
    """Summary should print nimble services and IO bindings."""
    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="ble1",
                proto_type="nimble",
                instance=1,
                config={
                    "gap_name": "dev",
                    "services": {
                        "dis": {"enabled": True},
                        "bas": {"battery_level": {"id": "bat"}},
                    },
                },
                bindings=[],
            )
        ],
    )
    print_protocol_allocation_summaries(desc, {})
    out = capsys.readouterr().out
    assert "ble1 (nimble)" in out
    assert "gap_name=dev" in out
    assert "enabled=true" in out
    assert "ios=bat" in out


def test_fmt_hex_none_and_value():
    """Hex formatter handles both populated and empty IDs."""
    assert _fmt_hex(None) == "n/a"
    assert _fmt_hex(255) == "0xFF"


def test_fmt_value_and_parse_helpers(capsys):
    assert _fmt_value(None) == "n/a"
    assert _fmt_value(10) == "10"
    assert _fmt_value(10, hex_format=True) == "0xA"
    assert try_parse_int("CONFIG_X") is None
    assert try_parse_int("0x10") == 16

    _print_vars_summary(
        {
            "k1": {"kconfig": "CONFIG_X", "type": "int"},
            "v1": {"value": 5},
            "v2": {"value": "abc", "type": "string"},
            "raw": 7,
            "unknown": {"foo": "bar"},
        }
    )
    out = capsys.readouterr().out
    assert "Variables:" in out
    assert "k1: kconfig=CONFIG_X" in out
    assert "v1: value=5" in out
    assert "v2: value=abc, type=string" in out
    assert "raw: value=7" in out
    assert "unknown: value=?" in out

    _print_can_kconfig_note({"node_id": "CONFIG_NODE"})
    out = capsys.readouterr().out
    assert "node=CONFIG_NODE (assumed 0 for validation)" in out


def test_proto_unresolved_kconfig_helpers():
    assert _proto_has_unresolved_kconfig({"node_id": "CONFIG_X"}, ["node_id"])
    assert not _proto_has_unresolved_kconfig({"node_id": 1}, ["node_id"])
    assert _proto_has_unresolved_kconfig(
        {"objects": [{"can_id_start": "CONFIG_Y"}]}, ["objects"]
    )

    desc = ClientDescriptor(
        ios={},
        programs=[],
        protocols=[
            ClientProto(
                proto_id="can1",
                proto_type="can",
                instance=1,
                config={"node_id": "CONFIG_X", "objects": []},
                bindings=[],
            )
        ],
    )
    assert _can_has_unresolved_kconfig(desc)

    empty = ClientDescriptor(ios={}, programs=[], protocols=[])
    assert _can_has_unresolved_kconfig(empty) is False


def test_try_parse_int_variants():
    assert try_parse_int(True) is None
    assert try_parse_int(3) == 3
    assert try_parse_int("0x2") == 2
    assert try_parse_int("CONFIG_Z") is None
    assert try_parse_int([]) is None


def test_proto_has_unresolved_kconfig_list_items():
    assert (
        _proto_has_unresolved_kconfig({"objects": ["bad"]}, ["objects"])
        is False
    )
