# tools/dawnpy/tests/test_simple_device_client.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for shared simple device client helpers."""

from typing import Any

import dawnpy.cli.simple_device_client as simple_device_client_mod
from dawnpy.cli.simple_device_client import SimpleDeviceClient
from dawnpy.descriptor.client import ClientDescriptor, ClientIo


class _SeekClient:
    def __init__(self, data):
        self._data = data

    def read_io_seek(self, objid: int):
        del objid
        return self._data


class _ClientStub:
    IO_TYPE_READ_ONLY = 1

    def __init__(self) -> None:
        self.connect_result = True
        self.ping_result = True
        self.disconnect_calls = 0
        self.discover_result: dict[int, dict[str, object]] = {}
        self.info_map: dict[int, dict[str, Any]] = {}
        self.read_map: dict[int, bytes | None] = {}
        self.pack_result: bytes | None = b"\x01"
        self.write_result = True
        self.seek_map: dict[int, bytes | None] = {}
        self.writes: list[tuple[int, bytes]] = []
        self.objid_decoder = None

    def connect(self) -> bool:
        return self.connect_result

    def ping(self) -> bool:
        return self.ping_result

    def disconnect(self) -> None:
        self.disconnect_calls += 1

    def discover_all_ios(self) -> dict[int, dict[str, object]]:
        return self.discover_result

    def get_io_info(self, objid: int) -> dict[str, Any] | None:
        return self.info_map.get(objid)

    def read_io(self, objid: int) -> bytes | None:
        return self.read_map.get(objid)

    def pack_data_by_dtype(self, dtype: int, value: int) -> bytes | None:
        del dtype, value
        return self.pack_result

    def write_io(self, objid: int, data: bytes) -> bool:
        self.writes.append((objid, data))
        return self.write_result

    def read_io_seek(self, objid: int) -> bytes | None:
        return self.seek_map.get(objid)


def test_read_seekable_io_requires_connection(capsys):
    """read_seekable_io should reject disconnected access."""
    client = SimpleDeviceClient()
    client.read_seekable_io(0x40A10001)

    captured = capsys.readouterr()
    assert "ERROR: Not connected to device" in captured.out


def test_read_seekable_io_reports_read_failure(capsys):
    """read_seekable_io should report protocol read failures."""
    client = SimpleDeviceClient()
    client.connected = True
    client.client = _SeekClient(None)

    client.read_seekable_io(0x40A10001)

    captured = capsys.readouterr()
    assert "ERROR: Failed to read seekable IO 0x40A10001" in captured.out


def test_read_seekable_io_prints_hexdump(capsys):
    """read_seekable_io should render a hex/ascii dump for the payload."""
    client = SimpleDeviceClient()
    client.connected = True
    client.client = _SeekClient(b"AB")

    client.read_seekable_io(0x40A10001)

    captured = capsys.readouterr()
    assert "IO 0x40A10001 seekable data (2 bytes):" in captured.out
    assert "00000000: 41 42" in captured.out
    assert "AB" in captured.out


def test_connect_disconnect_and_discovery_paths(capsys):
    client = SimpleDeviceClient()
    stub = _ClientStub()
    client.client = stub

    stub.connect_result = False
    assert client.connect() is False
    assert "ERROR: Failed to connect to device" in capsys.readouterr().out

    stub.connect_result = True
    stub.ping_result = False
    assert client.connect() is False
    out = capsys.readouterr().out
    assert "ERROR: Failed to ping device" in out
    assert stub.disconnect_calls == 1

    stub.ping_result = True
    assert client.connect() is True
    assert client.connected is True

    # Cover _ClientStub.read_io_seek helper path.
    stub.seek_map = {0x40A10001: b"\x01"}
    client.read_seekable_io(0x40A10001)

    client.disconnect()
    assert client.connected is False
    assert stub.disconnect_calls == 2

    client.connected = False
    stub.discover_result = {1: {"dtype": 1}}
    assert client.perform_discovery() is True
    assert client.discovered_ios == {1: {"dtype": 1}}


def test_descriptor_backed_discovery(monkeypatch):
    """Descriptor mode should avoid CMD_LIST_IOS and read descriptor IOs."""
    client = SimpleDeviceClient(descriptor_path="config")
    stub = _ClientStub()
    stub.info_map = {
        0x40120003: {
            "io_type": 3,
            "io_type_str": "IO_READ_WRITE",
            "dimension": 1,
            "dtype": 2,
        }
    }
    stub.read_map = {0x40120003: b"\x2a"}
    client.client = stub

    descriptor = ClientDescriptor(
        ios={
            "adc0": ClientIo(
                io_id="adc0",
                io_type="adc_fetch",
                instance=3,
                dtype="uint16",
                tags=["sample"],
                config={},
                timestamp=False,
                notify=False,
                rw=True,
                subtype=None,
                variant=None,
            )
        },
        programs=[],
        protocols=[],
    )

    class _Resolver:
        def io_objid(self, io):
            assert io.io_id == "adc0"
            return 0x40120003

    monkeypatch.setattr(
        simple_device_client_mod,
        "find_descriptor_path",
        lambda path: f"{path}/descriptor.yaml",
    )
    loaded_paths: list[str] = []

    def _load(path):
        loaded_paths.append(path)
        return descriptor

    monkeypatch.setattr(
        simple_device_client_mod, "load_client_descriptor", _load
    )
    monkeypatch.setattr(
        simple_device_client_mod, "ObjectIdResolver", _Resolver
    )

    assert client.discover_ios() == {
        0x40120003: {
            "source": "descriptor",
            "io_id": "adc0",
            "io_type_str": "IO_READ_WRITE",
            "io_type": 3,
            "dimension": 1,
            "dtype": 2,
            "dtype_name": "uint16",
            "rw": True,
            "tags": ["sample"],
            "data": "2a",
            "data_bytes": [42],
        }
    }
    assert loaded_paths == ["config/descriptor.yaml"]
    assert client.known_objids() == [0x40120003]


def test_descriptor_discovery_covers_fallback_paths(monkeypatch):
    """Descriptor discovery should tolerate unresolved and info-less IOs."""
    client = SimpleDeviceClient(descriptor_path="descriptor.yaml")
    client.client = _ClientStub()

    descriptor = ClientDescriptor(
        ios={
            "skip": ClientIo(
                io_id="skip",
                io_type="unknown",
                instance=0,
                dtype="uint8",
                tags=[],
                config={},
                timestamp=False,
                notify=False,
                rw=False,
                subtype=None,
                variant=None,
            ),
            "keep": ClientIo(
                io_id="keep",
                io_type="dummy",
                instance=1,
                dtype="uint8",
                tags=[],
                config={},
                timestamp=False,
                notify=False,
                rw=False,
                subtype=None,
                variant=None,
            ),
        },
        programs=[],
        protocols=[],
    )

    class _Resolver:
        def io_objid(self, io):
            if io.io_id == "skip":
                return None
            return 0x40050001

    monkeypatch.setattr(
        simple_device_client_mod,
        "load_client_descriptor",
        lambda path: descriptor,
    )
    monkeypatch.setattr(
        simple_device_client_mod, "ObjectIdResolver", _Resolver
    )

    assert client.known_objids() == [0x40050001]
    assert client.discovered_ios[0x40050001]["dtype"] == 5

    no_descriptor = SimpleDeviceClient()
    assert no_descriptor.known_objids() == []


def test_perform_discovery_returns_false_when_connect_fails(monkeypatch):
    client = SimpleDeviceClient()
    monkeypatch.setattr(client, "connect", lambda: False)
    assert client.perform_discovery() is False


def test_read_io_value_branches(monkeypatch, capsys):
    client = SimpleDeviceClient()
    stub = _ClientStub()
    client.client = stub
    objid = 0x1234

    client.read_io_value(objid)
    assert "ERROR: Not connected to device" in capsys.readouterr().out

    client.connected = True
    block_objid = (SimpleDeviceClient.DTYPE_BLOCK << 16) | 1
    seen: list[int] = []
    monkeypatch.setattr(client, "read_seekable_io", lambda x: seen.append(x))
    client.read_io_value(block_objid)
    assert seen == [block_objid]

    stub.info_map = {}
    client.read_io_value(objid)
    assert "ERROR: Failed to get IO info" in capsys.readouterr().out

    stub.info_map = {objid: {"dtype": 2}}
    stub.read_map = {objid: None}
    client.read_io_value(objid)
    assert "ERROR: Failed to read data" in capsys.readouterr().out

    calls: list[tuple[int, bytes, int]] = []
    monkeypatch.setattr(
        client,
        "format_value",
        lambda o, d, t, include_objid=True: calls.append((o, d, t)),
    )
    stub.read_map = {objid: b"\xaa"}
    client.read_io_value(objid)
    assert calls == [(objid, b"\xaa", 2)]


def test_write_io_value_branches(monkeypatch, capsys):
    client = SimpleDeviceClient()
    stub = _ClientStub()
    client.client = stub
    objid = 0x55

    client.write_io_value(objid, 1)
    assert "ERROR: Not connected to device" in capsys.readouterr().out

    client.connected = True
    client.write_io_value(objid, 1)
    assert "ERROR: Failed to get IO info" in capsys.readouterr().out

    stub.info_map = {objid: {"io_type": stub.IO_TYPE_READ_ONLY, "dtype": 1}}
    client.write_io_value(objid, 1)
    assert "ERROR: IO is read-only, cannot write" in capsys.readouterr().out

    stub.info_map = {objid: {"io_type": 0, "dtype": 1}}
    stub.pack_result = None
    client.write_io_value(objid, 1)
    assert "ERROR: Could not pack data for dtype 1" in capsys.readouterr().out

    stub.pack_result = b"\x01"
    stub.write_result = False
    client.write_io_value(objid, 1)
    assert "ERROR: Write failed" in capsys.readouterr().out

    formatted: list[tuple[int, bytes, int]] = []
    monkeypatch.setattr(
        client,
        "format_value",
        lambda o, d, t, include_objid=True: formatted.append((o, d, t)),
    )
    stub.write_result = True
    stub.read_map = {objid: b"\x10"}
    client.write_io_value(objid, 1)
    assert formatted == [(objid, b"\x10", 1)]

    # Successful write with no readback should stay silent.
    stub.read_map = {objid: None}
    client.write_io_value(objid, 1)


def test_write_io_raw_branches(monkeypatch, capsys):
    client = SimpleDeviceClient()
    stub = _ClientStub()
    client.client = stub
    objid = 0x99

    client.write_io_raw(objid, b"\x01")
    assert "ERROR: Not connected to device" in capsys.readouterr().out

    client.connected = True
    client.write_io_raw(objid, b"\x01")
    assert "ERROR: Failed to get IO info" in capsys.readouterr().out

    stub.info_map = {objid: {"io_type": stub.IO_TYPE_READ_ONLY, "dtype": 1}}
    client.write_io_raw(objid, b"\x01")
    assert "ERROR: IO is read-only, cannot write" in capsys.readouterr().out

    stub.info_map = {objid: {"io_type": 0, "dtype": 1}}
    stub.write_result = False
    client.write_io_raw(objid, b"\x01")
    assert "ERROR: Write failed" in capsys.readouterr().out

    formatted: list[tuple[int, bytes, int]] = []
    monkeypatch.setattr(
        client,
        "format_value",
        lambda o, d, t, include_objid=True: formatted.append((o, d, t)),
    )
    stub.write_result = True
    stub.read_map = {objid: b"\xcc"}
    client.write_io_raw(objid, b"\xab")
    assert formatted == [(objid, b"\xcc", 1)]

    stub.read_map = {objid: None}
    client.write_io_raw(objid, b"\xab")


def test_parse_hex_bytes_and_format_value(monkeypatch, capsys):
    assert SimpleDeviceClient.parse_hex_bytes("0x01ff") == b"\x01\xff"
    assert SimpleDeviceClient.parse_hex_bytes("AA_bb") == b"\xaa\xbb"
    assert SimpleDeviceClient.parse_hex_bytes("") is None
    assert SimpleDeviceClient.parse_hex_bytes("123") is None
    assert SimpleDeviceClient.parse_hex_bytes("zz") is None

    client = SimpleDeviceClient()
    client.client = _ClientStub()
    client.debug = True

    monkeypatch.setattr(
        simple_device_client_mod,
        "decode_value",
        lambda *args, **kwargs: ["line1", "line2"],
    )
    client.format_value(0x12, b"\x01", 1)
    out = capsys.readouterr().out
    assert "line1" in out and "line2" in out


def test_print_hexdump_multiline(capsys):
    data = bytes(range(20))
    SimpleDeviceClient._print_hexdump(data)
    out = capsys.readouterr().out
    assert "00000000:" in out
    assert "00000010:" in out


def test_parse_object_id_returns_int_or_none(capsys):
    client = SimpleDeviceClient()
    assert client.parse_object_id("0x40A10001") == 0x40A10001
    assert client.parse_object_id("not-a-hex") is None
    err = capsys.readouterr().out
    assert "Invalid object ID format" in err


def test_parse_object_ids_handles_csv_and_errors(capsys):
    client = SimpleDeviceClient()
    assert client.parse_object_ids("0x1, 0x2, 0x3") == [0x1, 0x2, 0x3]
    assert client.parse_object_ids("0x1,not-hex") is None
    err = capsys.readouterr().out
    assert "Invalid object ID format" in err
