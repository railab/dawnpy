# tools/dawnpy/tests/test_simple_protocol.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for shared simple protocol helpers."""

from unittest.mock import patch

from dawnpy.simple_protocol import SimpleProtocolBase


def test_create_objid_decoder_uses_default_decoder():
    """The default decoder factory should use ObjectIdDecoder."""
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)

    with patch("dawnpy.simple_protocol.ObjectIdDecoder") as mock_decoder:
        result = protocol._create_objid_decoder()

    mock_decoder.assert_called_once_with()
    assert result is mock_decoder.return_value


def test_init_success_and_failure_paths(monkeypatch, capsys):
    monkeypatch.setattr(
        SimpleProtocolBase,
        "_create_objid_decoder",
        lambda self: {"cfg": "ok"},
    )
    ok = SimpleProtocolBase(verbose=True)
    assert ok.verbose is True
    assert isinstance(ok.objid_decoder, dict)
    assert ok.io_list == []
    assert ok.io_info == {}

    def _boom(self):  # pragma: no cover - used via monkeypatch
        raise RuntimeError("boom")

    monkeypatch.setattr(SimpleProtocolBase, "_create_objid_decoder", _boom)
    bad = SimpleProtocolBase()
    assert bad.objid_decoder is None
    assert (
        "Could not initialize ObjectIdDecoder: boom" in capsys.readouterr().out
    )


def test_decode_object_id_without_decoder_and_on_decode_error():
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)
    protocol.objid_decoder = None
    assert protocol.decode_object_id(0xAA) == "0x000000AA"

    protocol.objid_decoder = type(
        "Decoder",
        (),
        {
            "decode": lambda self, _objid: (_ for _ in ()).throw(ValueError()),
            "format_compact": lambda self, decoded: str(decoded),
        },
    )()
    assert protocol.decode_object_id(0xBB) == "0x000000BB"


def test_decode_object_id_with_decoder_success():
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {
            "decode": lambda self, objid: {"objid": objid},
            "format_compact": (
                lambda self, decoded: f"decoded-{decoded['objid']}"
            ),
        },
    )()
    assert protocol.decode_object_id(0x10) == "decoded-16"


def test_pack_data_by_dtype_returns_none_for_unsupported_format():
    """Unsupported dtype names should return None."""
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {7: {"type": "custom"}}},
    )()

    assert protocol.pack_data_by_dtype(7, 1) is None


def test_pack_data_by_dtype_edge_cases():
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)
    protocol.objid_decoder = None
    assert protocol.pack_data_by_dtype(1, 1) is None

    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {1: {"type": "invalid"}, 2: {"type": "char"}}},
    )()
    assert protocol.pack_data_by_dtype(1, 1) is None
    assert protocol.pack_data_by_dtype(2, "ab") == b"ab"
    assert protocol.pack_data_by_dtype(2, b"\x01\x02") == b"\x01\x02"
    assert protocol.pack_data_by_dtype(2, 7) is None

    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {3: {"type": "uint8"}, 4: {"type": "int8"}}},
    )()
    assert protocol.pack_data_by_dtype(3, 1, 2) is None
    assert protocol.pack_data_by_dtype(4, 300) is None


def test_base_log_and_err_print(capsys):
    protocol = SimpleProtocolBase.__new__(SimpleProtocolBase)
    protocol.verbose = False
    protocol._log("hidden")
    assert capsys.readouterr().out == ""

    protocol.verbose = True
    protocol._log("shown")
    protocol._err("errline")
    out = capsys.readouterr().out
    assert "shown" in out
    assert "errline" in out


class _ProtocolHarness(SimpleProtocolBase):
    def __init__(self):
        self.verbose = False
        self.io_list = []
        self.io_info = {}
        self._frames = []
        self._info_map = {}
        self._read_map = {}
        self._read_calls = []
        self.logged = []
        self.errors = []
        self.objid_decoder = None

    def send_frame(self, cmd: int, payload: bytes = b"") -> bool:
        self.logged.append(("send", cmd, payload))
        return True

    def receive_frame(self):
        if self._frames:
            return self._frames.pop(0)
        return None

    def read_io_seek_chunk(self, objid: int, offset: int):
        del objid
        if self._frames:
            return self._frames.pop(0)
        return None

    def get_io_info(self, objid: int):
        return self._info_map.get(objid)

    def read_io(self, objid: int):
        self._read_calls.append(objid)
        return self._read_map.get(objid)

    def decode_object_id(self, objid: int) -> str:
        return f"id-{objid:08X}"

    def _log(self, message: str) -> None:
        self.logged.append(message)

    def _err(self, message: str) -> None:
        self.errors.append(message)


def test_ping_with_messages_success_and_failure():
    """Shared ping helper should handle success and failure responses."""
    protocol = _ProtocolHarness()
    protocol._frames = [(protocol.CMD_PONG, b"")]

    assert (
        protocol._ping_with_messages(
            start_message="start",
            success_message="ok",
            failure_message="fail",
        )
        is True
    )
    assert "start" in protocol.logged
    assert "ok" in protocol.logged

    protocol = _ProtocolHarness()

    assert (
        protocol._ping_with_messages(
            start_message="start",
            success_message="ok",
            failure_message="fail",
        )
        is False
    )
    assert protocol.errors == ["fail"]

    protocol = _ProtocolHarness()

    def _send_false(cmd: int, payload: bytes = b"") -> bool:
        del cmd, payload
        return False

    protocol.send_frame = _send_false  # type: ignore[assignment]
    assert (
        protocol._ping_with_messages(
            start_message="start",
            success_message="ok",
            failure_message="fail",
        )
        is False
    )


def test_parse_io_list_payload_truncates_and_logs_ids():
    """LIST_IOS parsing should stop at truncated payloads."""
    protocol = _ProtocolHarness()
    payload = b"\x02\x00" + (1).to_bytes(4, "little")

    result = protocol._parse_io_list_payload(payload, log_decoded_ids=True)

    assert result == [1]
    assert protocol.io_list == [1]
    assert "Found 2 IO objects" in protocol.logged
    assert "  IO 0: id-00000001" in protocol.logged


def test_build_io_info_logs_unknown_detailed_type():
    """GET_INFO parsing should support detailed unknown IO type strings."""
    protocol = _ProtocolHarness()

    result = protocol._build_io_info(
        0x1234,
        bytes([0x99, 3, 7]),
        detailed_unknown=True,
        log_details=True,
    )

    assert result["io_type_str"] == "Unknown(0x99)"
    assert protocol.io_info[0x1234] == result
    assert "id-00001234" in protocol.logged[-1]


def test_read_io_seek_all_handles_none_and_empty_chunks():
    """Shared seek reader should stop on missing or empty chunks."""
    protocol = _ProtocolHarness()

    assert protocol._read_io_seek_all(1) is None

    protocol = _ProtocolHarness()
    protocol._frames = [(4, b"ab")]

    assert protocol._read_io_seek_all(1) is None

    protocol = _ProtocolHarness()
    protocol._frames = [(4, b"ab"), (4, b"")]

    assert (
        protocol._read_io_seek_all(1, empty_chunk_error="empty at {offset}")
        is None
    )
    assert protocol.errors == ["empty at 2"]


def test_read_io_seek_all_reassembles_multiple_chunks():
    """Shared seek reader should reassemble data until total size is met."""
    protocol = _ProtocolHarness()
    protocol._frames = [(4, b"ab"), (4, b"cd")]

    assert protocol._read_io_seek_all(1) == b"abcd"


def test_exchange_helpers_build_payloads():
    """Shared exchange helpers should build the expected payloads."""
    protocol = _ProtocolHarness()
    protocol._frames = [(1, b"x"), (2, b"y"), (3, b"z")]

    assert protocol._exchange(9, b"ab") == (1, b"x")
    assert protocol.logged[0] == ("send", 9, b"ab")

    assert protocol._exchange_objid(10, 0x1234) == (2, b"y")
    assert protocol.logged[1] == ("send", 10, (0x1234).to_bytes(4, "little"))

    assert protocol._exchange_write(11, 0x34, b"cd") == (3, b"z")
    assert protocol.logged[2] == (
        "send",
        11,
        (0x34).to_bytes(4, "little") + b"cd",
    )

    def _send_false(cmd: int, payload: bytes = b"") -> bool:
        del cmd, payload
        return False

    protocol.send_frame = _send_false  # type: ignore[assignment]
    assert protocol._exchange(9, b"ab") is None


def test_collect_io_snapshot_handles_skips_and_missing_data():
    """Snapshot collection should handle missing info and empty reads."""
    protocol = _ProtocolHarness()
    protocol.io_list = [1, 2, 3]
    protocol._info_map = {
        2: {"io_type": protocol.IO_TYPE_WRITE_ONLY},
        3: {"io_type": protocol.IO_TYPE_READ_ONLY},
    }
    protocol._read_map = {3: None}

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=True,
        set_none_for_failed_read=True,
    )

    assert 1 not in result
    assert result[2]["data"] is None
    assert result[3]["data"] is None


def test_collect_io_snapshot_metadata_only_mode():
    """Snapshot collection should skip all GET_IO calls in metadata mode."""
    protocol = _ProtocolHarness()
    protocol.io_list = [9]
    protocol._info_map = {9: {"io_type": protocol.IO_TYPE_READ_ONLY}}
    protocol._read_map = {9: b"\x01"}

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=True,
        set_none_for_failed_read=True,
        read_values=False,
    )

    assert result[9]["data"] is None
    assert protocol._read_calls == []


def test_collect_io_snapshot_fetch_info_false_uses_fallback():
    protocol = _ProtocolHarness()
    protocol.io_list = [0x11]
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"decode": lambda self, _objid: type("D", (), {"dtype": 7})()},
    )()
    result = protocol._collect_io_snapshot(
        set_none_for_write_only=False,
        set_none_for_failed_read=False,
        fetch_info=False,
        read_values=False,
    )
    assert result[0x11]["dtype"] == 7


def test_fallback_io_info_handles_decode_exception():
    protocol = _ProtocolHarness()
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {
            "decode": lambda self, _objid: (_ for _ in ()).throw(
                RuntimeError("x")
            )
        },
    )()
    info = protocol._fallback_io_info_from_objid(0x22)
    assert info["dtype"] == 0


def test_collect_io_snapshot_stores_read_data_and_callback():
    """Snapshot collection should store read bytes and invoke callback."""
    protocol = _ProtocolHarness()
    protocol.io_list = [5]
    protocol._info_map = {5: {"io_type": protocol.IO_TYPE_READ_ONLY}}
    protocol._read_map = {5: b"\x01\x02"}
    seen = []

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=False,
        set_none_for_failed_read=False,
        on_data=lambda info, data: seen.append((info["data"], data)),
    )

    assert result[5]["data"] == "0102"
    assert result[5]["data_bytes"] == [1, 2]
    assert seen == [("0102", b"\x01\x02")]


def test_collect_io_snapshot_skips_block_dtype_reads():
    """Snapshot collection should skip GET_IO reads for block dtype."""
    protocol = _ProtocolHarness()
    protocol.io_list = [7]
    protocol._info_map = {
        7: {
            "io_type": protocol.IO_TYPE_READ_ONLY,
            "dtype": 15,
        }
    }
    protocol._read_map = {7: b"\xaa\xbb"}
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {15: {"type": "block"}}},
    )()

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=True,
        set_none_for_failed_read=True,
    )

    assert result[7]["data"] is None
    assert protocol._read_calls == []


def test_collect_io_snapshot_block_dtype_guard_non_int_dtype():
    """Snapshot collection should keep reading when dtype is non-integer."""
    protocol = _ProtocolHarness()
    protocol.io_list = [8]
    protocol._info_map = {
        8: {
            "io_type": protocol.IO_TYPE_READ_ONLY,
            "dtype": "block",
        }
    }
    protocol._read_map = {8: b"\x12\x34"}
    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {15: {"type": "block"}}},
    )()

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=True,
        set_none_for_failed_read=True,
    )

    assert result[8]["data"] == "1234"
    assert protocol._read_calls == [8]


def test_collect_io_snapshot_skips_block_dtype_from_objid_decode():
    """Snapshot collection should skip reads when objid decodes as block."""
    protocol = _ProtocolHarness()
    protocol.io_list = [0x406F0000]
    protocol._info_map = {
        0x406F0000: {
            "io_type": protocol.IO_TYPE_READ_ONLY,
            "dtype": 7,
        }
    }
    protocol._read_map = {0x406F0000: b"\xfe\xed"}

    class _Decoded:
        dtype_name = "block"

    protocol.objid_decoder = type(
        "Decoder",
        (),
        {"dtype_info": {}, "decode": lambda self, _objid: _Decoded()},
    )()

    result = protocol._collect_io_snapshot(
        set_none_for_write_only=True,
        set_none_for_failed_read=True,
    )

    assert result[0x406F0000]["data"] is None
    assert protocol._read_calls == []


def test_build_frame_includes_header_payload_and_crc():
    """Shared frame builder should produce a valid encoded frame."""
    protocol = _ProtocolHarness()

    frame, crc = protocol._build_frame(0x10, b"\x01\x02")

    assert frame[0] == protocol.FRAME_SYNC
    assert frame[1:3] == b"\x02\x00"
    assert frame[3] == 0x10
    assert frame[4:6] == b"\x01\x02"
    assert frame[6:8] == crc.to_bytes(2, "little")


def test_parse_frame_bytes_validates_and_decodes_frame():
    """Shared frame parser should decode a valid frame."""
    protocol = _ProtocolHarness()
    frame, _ = protocol._build_frame(0x20, b"\xaa")

    result = protocol._parse_frame_bytes(
        frame,
        short_frame_message="short {length}",
        invalid_sync_message="bad {sync}",
        length_mismatch_message="len {expected} {actual}",
        log_message_factory=lambda length: f"len={length}",
    )

    assert result == (0x20, b"\xaa")
    assert "len=1" in protocol.logged


def test_parse_frame_bytes_rejects_invalid_inputs():
    """Shared frame parser should reject malformed frames."""
    protocol = _ProtocolHarness()

    assert (
        protocol._parse_frame_bytes(
            b"\xaa",
            short_frame_message="short {length}",
            invalid_sync_message="bad {sync}",
            length_mismatch_message="len {expected} {actual}",
            log_message_factory=lambda length: str(length),
        )
        is None
    )
    assert protocol.errors[-1] == "short 1"

    protocol = _ProtocolHarness()
    frame, _ = protocol._build_frame(0x20, b"\xaa")
    bad_sync = bytes([0x00]) + frame[1:]
    assert (
        protocol._parse_frame_bytes(
            bad_sync,
            short_frame_message="short {length}",
            invalid_sync_message="bad {sync}",
            length_mismatch_message="len {expected} {actual}",
            log_message_factory=lambda length: str(length),
        )
        is None
    )
    assert protocol.errors[-1] == "bad 0"

    protocol = _ProtocolHarness()
    assert (
        protocol._parse_frame_bytes(
            frame[:-1],
            short_frame_message="short {length}",
            invalid_sync_message="bad {sync}",
            length_mismatch_message="len {expected} {actual}",
            log_message_factory=lambda length: str(length),
        )
        is None
    )
    assert protocol.errors[-1] == "len 7 6"

    protocol = _ProtocolHarness()
    bad_crc = frame[:-2] + b"\x00\x00"
    assert (
        protocol._parse_frame_bytes(
            bad_crc,
            short_frame_message="short {length}",
            invalid_sync_message="bad {sync}",
            length_mismatch_message="len {expected} {actual}",
            log_message_factory=lambda length: str(length),
        )
        is None
    )
    assert "CRC mismatch:" in protocol.errors[-1]
