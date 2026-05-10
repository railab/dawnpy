# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_capabilities_decode_helpers():
    blob = _make_capabilities_blob_v2()
    decoded = _decode_capabilities_blob(blob)
    assert decoded["version"] == 2
    assert decoded["layout_id"] == 0
    assert decoded["payload_len"] == 504
    assert decoded["desc_slots"] == 2
    assert decoded["desc_slot_size"] == 4096
    assert decoded["max_io_cls"] == 0x1FF
    assert decoded["io_enabled"] == list(_CAPS_IO_BITS)
    assert decoded["prog_enabled"] == list(_CAPS_PROG_BITS)
    assert decoded["proto_enabled"] == list(_CAPS_PROTO_BITS)


def test_capabilities_decode_helper_errors():
    assert parse_hex_file_text("00000000: 01 02 03 |...|") == bytes(
        [0x01, 0x02, 0x03]
    )

    with pytest.raises(click.ClickException, match="Hex file is empty"):
        parse_hex_file_text("   \n\t")

    with pytest.raises(click.ClickException, match="even number"):
        parse_hex_file_text("A")

    with pytest.raises(click.ClickException, match="too short"):
        _decode_capabilities_blob(b"\x02")

    bad_version = bytearray(_make_capabilities_blob_v2())
    bad_version[0] = 1
    with pytest.raises(click.ClickException, match="Unsupported.*version"):
        _decode_capabilities_blob(bytes(bad_version))

    bad_layout = bytearray(_make_capabilities_blob_v2())
    bad_layout[1] = 7
    with pytest.raises(click.ClickException, match="Unsupported.*layout"):
        _decode_capabilities_blob(bytes(bad_layout))

    bad_len = bytearray(_make_capabilities_blob_v2())
    bad_len[2:4] = (503).to_bytes(2, "little")
    with pytest.raises(
        click.ClickException, match="Unsupported.*payload length"
    ):
        _decode_capabilities_blob(bytes(bad_len))

    bad_reserved = bytearray(_make_capabilities_blob_v2())
    bad_reserved[4:8] = (1).to_bytes(4, "little")
    with pytest.raises(click.ClickException, match="reserved field"):
        _decode_capabilities_blob(bytes(bad_reserved))

    bad_actual = _make_capabilities_blob_v2()[:-1]
    with pytest.raises(click.ClickException, match="payload size mismatch"):
        _decode_capabilities_blob(bad_actual)

    bad_class_limit = bytearray(_make_capabilities_blob_v2())
    struct.pack_into(
        "<I", bad_class_limit, 8 + 192 + (8 * 4), max(_CAPS_IO_BITS) - 1
    )
    with pytest.raises(click.ClickException, match="above advertised max"):
        _decode_capabilities_blob(bytes(bad_class_limit))


def test_capabilities_decode_uses_inlined_layout():
    """Inlined layout constants drive _decode_capabilities_blob end-to-end."""
    blob = _make_capabilities_blob_v2()
    decoded = _decode_capabilities_blob(blob)
    assert decoded["version"] == 2
    assert decoded["layout_id"] == 0
    assert decoded["desc_slots"] == 2
    assert decoded["dtype_bits_lo"] != 0


def test_enabled_flag_names_skips_invalid_entries():
    names = enabled_flag_names(
        0b11,
        [
            {"bit": -1, "name": "bad"},
            {"bit": 0, "name": ""},
            {"bit": 1, "name": "ok"},
        ],
    )
    assert names == ["ok"]


def test_capabilities_decode_command_file():
    runner = CliRunner()
    blob = _make_capabilities_blob_v2()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "cap.bin"
        path.write_bytes(blob)
        hex_path = Path(tmpdir) / "cap.hex"
        hex_path.write_text(blob.hex(), encoding="utf-8")
        shell_hex_path = Path(tmpdir) / "cap_shell.hex"
        shell_hex_path.write_text(_to_shell_hexdump(blob), encoding="utf-8")
        bad_hex_path = Path(tmpdir) / "cap_bad.hex"
        bad_hex_path.write_text("GG", encoding="utf-8")

        result = runner.invoke(cmd_desc_decode_caps, [str(path)])
        assert result.exit_code == 0
        assert (
            "Capabilities Blob: version=2 layout=0 payload=504B"
            in result.output
        )
        assert "Descriptor: slots=2 slot_size=4096" in result.output
        assert "Build flags: os_nuttx, desc_dynamic" in result.output
        assert "IO classes enabled" in result.output
        assert "dummy" in result.output
        assert "bitpack" in result.output
        assert "bit_split" in result.output
        assert "can" in result.output
        assert "modbus_rtu" in result.output

        result_hex_file = runner.invoke(
            cmd_desc_decode_caps,
            [str(path), "--hex-file", str(hex_path)],
        )
        assert result_hex_file.exit_code == 0
        assert "PROTO classes enabled" in result_hex_file.output

        result_shell_hex_file = runner.invoke(
            cmd_desc_decode_caps,
            [
                str(path),
                "--hex-file",
                str(shell_hex_path),
            ],
        )
        assert result_shell_hex_file.exit_code == 0
        assert "Capabilities Blob: version=2 layout=0 payload=504B" in (
            result_shell_hex_file.output
        )

        result_bad_hex = runner.invoke(
            cmd_desc_decode_caps,
            [
                str(path),
                "--hex-file",
                str(bad_hex_path),
            ],
        )
        assert result_bad_hex.exit_code != 0
        assert "Invalid hex file content" in result_bad_hex.output

    result_bad = runner.invoke(
        cmd_desc_decode_caps, ["/nonexistent/path/cap.bin"]
    )
    assert result_bad.exit_code != 0
    assert "Input file not found" in result_bad.output
