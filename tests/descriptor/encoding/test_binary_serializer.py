# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_generate_descriptor_binary_dynamic_desc_like():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "dynamic.yaml"
        yaml_path.write_text(
            "metadata:\n"
            "  version: '0.2'\n"
            "  user_string: dynslot1\n"
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 0\n"
            "  - id: descriptor1\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 1\n"
            "  - id: descselector0\n"
            "    type: descselector\n"
            "    dtype: uint32\n"
            "  - id: dummy0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 77\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - descriptor0\n"
            "      - descriptor1\n"
            "      - descselector0\n"
            "      - dummy0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        binary = _generate_descriptor_binary(yaml_path, None)
        words = list(struct.unpack(f"<{len(binary) // 4}I", binary))

        assert words[0] == 0x0D0A0302
        assert words[1] == 6  # metadata + 4 IO + 1 protocol
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(binary) == 0
        assert 77 in words


def test_generate_descriptor_binary_pwm_freq_config(mock_header_cfg_id):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pwm0",
        io_type="pwm",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0, "freq": 1000},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pwm"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    freq_cfg = cfg_id(
        1, io_cls, dtype, False, 1, header_cfg_id("CIOPwm", "cfgIdFreq")
    )
    assert freq_cfg in words
    assert words[words.index(freq_cfg) + 1] == 1000

    freq_only = IoObject(
        obj_id="pwm_all",
        io_type="pwm",
        instance=1,
        dtype="uint32",
        tags=[],
        config={"device": 0, "freq": 500},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    freq_only_words: list[int] = []
    _serialize_io_object(freq_only_words, freq_only, {}, decoder)
    assert freq_cfg in freq_only_words


def test_generate_descriptor_binary_pwm_without_freq_has_no_type_config(
    mock_header_cfg_id,
):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pwm0",
        io_type="pwm",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pwm"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    freq_cfg = cfg_id(
        1, io_cls, dtype, True, 1, header_cfg_id("CIOPwm", "cfgIdFreq")
    )
    assert freq_cfg not in words


def test_generate_descriptor_binary_pulsecount_timing_config(
    mock_header_cfg_id,
):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pulsecount0",
        io_type="pulsecount",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0, "high_ns": 1000, "low_ns": 2000},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pulsecount"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    high_cfg = cfg_id(
        1,
        io_cls,
        dtype,
        False,
        1,
        header_cfg_id("CIOPulseCount", "cfgIdHighNs"),
    )
    low_cfg = cfg_id(
        1,
        io_cls,
        dtype,
        False,
        1,
        header_cfg_id("CIOPulseCount", "cfgIdLowNs"),
    )
    assert high_cfg in words
    assert words[words.index(high_cfg) + 1] == 1000
    assert low_cfg in words
    assert words[words.index(low_cfg) + 1] == 2000


def test_generate_descriptor_binary_pulsecount_without_timing_has_no_type_config(
    mock_header_cfg_id,
):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="pulsecount0",
        io_type="pulsecount",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"device": 0},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    words: list[int] = []

    _serialize_io_object(words, obj, {}, decoder)

    io_cls = next(
        cls for cls, name in decoder.io_classes.items() if name == "pulsecount"
    )
    dtype = next(
        dtype_id
        for dtype_id, info in decoder.dtype_info.items()
        if info["type"] == "uint32"
    )
    high_cfg = cfg_id(
        1,
        io_cls,
        dtype,
        True,
        1,
        header_cfg_id("CIOPulseCount", "cfgIdHighNs"),
    )
    low_cfg = cfg_id(
        1,
        io_cls,
        dtype,
        True,
        1,
        header_cfg_id("CIOPulseCount", "cfgIdLowNs"),
    )
    assert high_cfg not in words
    assert low_cfg not in words


def test_generate_descriptor_binary_with_program_object():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "prog.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: in0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 11\n"
            "  - id: out0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "programs:\n"
            "  - id: p0\n"
            "    type: statsmin\n"
            "    config:\n"
            "      inputs:\n"
            "        - in0\n"
            "      outputs:\n"
            "        - out0\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - in0\n"
            "      - out0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        binary = _generate_descriptor_binary(yaml_path, None)
        words = list(struct.unpack(f"<{len(binary) // 4}I", binary))

        assert words[0] == 0x0D0A0302
        assert words[1] == 4  # 2 IO + 1 PROG + 1 protocol
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(binary) == 0
        assert any((word >> 30) == 3 for word in words)


def test_binary_command_deterministic_output_for_same_input():
    """Characterization: binary CLI output is stable for identical YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "stable.yaml"
        out1 = Path(tmpdir) / "out1.bin"
        out2 = Path(tmpdir) / "out2.bin"
        yaml_path.write_text(
            "metadata:\n"
            "  version: '1.2'\n"
            "  user_string: stable\n"
            "ios:\n"
            "  - id: io0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 5\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n"
            "    bindings:\n"
            "      - io0\n",
            encoding="utf-8",
        )

        result1 = runner.invoke(
            cmd_desc_bin, [str(yaml_path), "-o", str(out1)]
        )
        result2 = runner.invoke(
            cmd_desc_bin, [str(yaml_path), "-o", str(out2)]
        )

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert "Generated binary" in result1.output
        assert "Generated binary" in result2.output

        bin1 = out1.read_bytes()
        bin2 = out2.read_bytes()
        assert bin1 == bin2

        words = list(struct.unpack(f"<{len(bin1) // 4}I", bin1))
        assert words[0] == 0x0D0A0302
        assert words[-2] == 0x02030A0D
        assert nuttx_crc32(bin1) == 0


def test_binary_command_rejects_unsupported_io_type():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "bad.yaml"
        out_path = Path(tmpdir) / "bad.bin"
        yaml_path.write_text(
            "ios:\n"
            "  - id: io0\n"
            "    type: unknown_io\n"
            "    dtype: uint32\n"
            "protocols: []\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            cmd_desc_bin,
            [str(yaml_path), "-o", str(out_path)],
        )

        assert result.exit_code != 0
        assert result.exception is not None
        assert "unknown io type" in str(result.exception).lower()


def test_io_class_and_dtype_mapping_branches():
    assert _io_class_name(_mk_io("sensor", subtype="temp")) == (
        "sensor_temperature"
    )
    assert _io_class_name(_mk_io("sensor")) is None
    assert _io_class_name(_mk_io("sysinfo", variant="uptime")) == (
        "system_uptime"
    )
    assert _io_class_name(_mk_io("sysinfo")) is None
    assert _io_class_name(_mk_io("uname", variant="hostname")) == (
        "system_hostname"
    )
    assert _io_class_name(_mk_io("uname", variant="other")) is None
    assert _io_class_name(_mk_io("boardctl", variant="poweroff")) == (
        "system_poweroff"
    )
    assert _io_class_name(_mk_io("boardctl", variant="x")) is None

    assert _io_dtype_name(_mk_io("sysinfo", variant="uptime")) == "uint64"
    assert _io_dtype_name(_mk_io("uname", variant="hostname")) == "char"
    assert _io_dtype_name(_mk_io("boardctl", variant="reset")) == "int32"
    assert _io_dtype_name(_mk_io("boardctl", variant="unknown")) == "uint32"


def test_coerce_u32_words_for_dtype_branches():
    assert _coerce_u32_words_for_dtype(1.5, "float")
    assert len(_coerce_u32_words_for_dtype(1.5, "double")) == 2
    assert len(_coerce_u32_words_for_dtype(-1, "int64")) == 2
    assert len(_coerce_u32_words_for_dtype(1, "uint64")) == 2
    assert _coerce_u32_words_for_dtype(-2, "int32")[0] == 0xFFFFFFFE
    assert _coerce_u32_words_for_dtype(True, "bool")[0] == 1
    with pytest.raises(
        click.ClickException,
        match="Unsupported dtype",
    ):
        _coerce_u32_words_for_dtype(1, "block")


def test_binary_command_success_and_default_output():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "ok.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 0\n"
            "  - id: descriptor1\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      device: 1\n"
            "  - id: descselector0\n"
            "    type: descselector\n"
            "    dtype: uint32\n"
            "  - id: capabilities0\n"
            "    type: capabilities\n"
            "    dtype: block\n"
            "protocols:\n"
            "  - id: serial0\n"
            "    type: serial\n"
            "    bindings:\n"
            "      - descriptor0\n"
            "      - descriptor1\n"
            "      - descselector0\n"
            "      - capabilities0\n"
            "    config:\n"
            "      path: /tmp/ttySIM0\n"
            "      baudrate: 115200\n",
            encoding="utf-8",
        )

        result = runner.invoke(cmd_desc_bin, [str(yaml_path)])
        assert result.exit_code == 0
        assert "Generated binary" in result.output
        assert (Path(tmpdir) / "descriptor.bin").exists()


def test_binary_command_proto_dummy_and_prog_stats_supported():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        proto_dummy_yaml = Path(tmpdir) / "proto_dummy.yaml"
        proto_dummy_yaml.write_text(
            "ios:\n"
            "  - id: descriptor0\n"
            "    type: descriptor\n"
            "    dtype: uint32\n"
            "protocols:\n"
            "  - id: dummy0\n"
            "    type: dummy\n",
            encoding="utf-8",
        )
        result_proto_dummy = runner.invoke(
            cmd_desc_bin, [str(proto_dummy_yaml)]
        )
        assert result_proto_dummy.exit_code == 0
        assert "Generated binary" in result_proto_dummy.output

        proto_bad_yaml = Path(tmpdir) / "proto_bad.yaml"
        proto_bad_yaml.write_text(
            "protocols:\n" "  - id: p0\n" "    type: unknown_protocol\n",
            encoding="utf-8",
        )
        result_proto_bad = runner.invoke(cmd_desc_bin, [str(proto_bad_yaml)])
        assert result_proto_bad.exit_code != 0
        assert (
            "unknown protocol type" in str(result_proto_bad.exception).lower()
        )

        prog_ok_yaml = Path(tmpdir) / "prog_stats_ok.yaml"
        prog_ok_yaml.write_text(
            "programs:\n"
            "  - id: p0\n"
            "    type: stats\n"
            "    config: {}\n",
            encoding="utf-8",
        )
        result_prog_ok = runner.invoke(cmd_desc_bin, [str(prog_ok_yaml)])
        assert result_prog_ok.exit_code == 0
        assert "Generated binary" in result_prog_ok.output

        prog_bad_yaml = Path(tmpdir) / "prog_bad.yaml"
        prog_bad_yaml.write_text(
            "programs:\n"
            "  - id: p1\n"
            "    type: unknown_program\n"
            "    config: {}\n",
            encoding="utf-8",
        )
        result_prog_bad = runner.invoke(cmd_desc_bin, [str(prog_bad_yaml)])
        assert result_prog_bad.exit_code != 0
        assert result_prog_bad.exception is not None
        assert "unknown program type" in str(result_prog_bad.exception).lower()


def test_serialize_error_paths_for_unknown_mappings():
    decoder = ObjectIdDecoder()
    io = _mk_io("sensor")
    with pytest.raises(
        click.ClickException,
        match="Unable to resolve IO class",
    ):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], io, {}, decoder)

    decoder.io_classes = {}
    with pytest.raises(click.ClickException, match="Unknown IO class"):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], _mk_io("dummy"), {}, decoder)

    decoder = ObjectIdDecoder()
    bad_dtype_io = _mk_io("dummy", dtype="notype")
    with pytest.raises(click.ClickException, match="Unknown IO dtype"):
        from dawnpy.descriptor.encoding.binary_serializer import (
            _serialize_io_object,
        )

        _serialize_io_object([], bad_dtype_io, {}, decoder)

    decoder = ObjectIdDecoder()
    proto = ProtocolObject(
        obj_id="p0", proto_type="serial", instance=0, config={}, bindings=["x"]
    )
    with pytest.raises(KeyError, match="x"):
        from dawnpy.descriptor.encoding.proto_serializer import (
            serialize_proto_object,
        )

        serialize_proto_object([], proto, {}, decoder)

    unknown_io = IoObject(
        obj_id="io_unknown",
        io_type="system_uptime",
        instance=0,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    with pytest.raises(click.ClickException, match="supports IO types"):
        _serialize_io_object([], unknown_io, {}, ObjectIdDecoder())


def test_serialize_metadata_non_dict_and_dummy_dim_branch():
    words: list[int] = []
    assert _serialize_metadata(words, {"metadata": []}) == 0

    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="dummy0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"dim": 3},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    out: list[int] = []
    _serialize_io_object(out, obj, {}, decoder)
    assert 3 in out


def test_serialize_metadata_no_idle_quit_only():
    words: list[int] = []

    assert (
        _serialize_metadata(words, {"metadata": {"no_idle_quit": True}}) == 1
    )

    assert words == [
        1,  # CDescriptor::objectId(1)
        1,
        (3 << 16) | (1 << 5) | 3,
        1,
    ]


def test_serialize_proto_unknown_class_raises():
    decoder = ObjectIdDecoder()
    decoder.proto_classes = {}
    proto = ProtocolObject(
        obj_id="serial0",
        proto_type="serial",
        instance=0,
        config={},
        bindings=[],
    )
    with pytest.raises(click.ClickException, match="Unknown protocol class"):
        serialize_proto_object([], proto, {}, decoder)


def test_generate_descriptor_binary_unknown_object_raises(monkeypatch):
    class _Unknown:
        pass

    monkeypatch.setattr(
        binary_serializer_mod, "load_yaml_with_vars", lambda *a, **k: {}
    )
    monkeypatch.setattr(
        binary_serializer_mod,
        "decode_objects",
        lambda *a, **k: [_Unknown()],
    )
    with pytest.raises(click.ClickException, match="supports IO/PROG/PROTO"):
        _generate_descriptor_binary(Path("/tmp/x.yaml"), None)


def test_generate_descriptor_binaries_single_slot():
    """Single-descriptor YAML returns slot 0 only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "single.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: dummy0\n"
            "    type: dummy\n"
            "    dtype: uint32\n"
            "    config:\n"
            "      init_value: 42\n",
            encoding="utf-8",
        )
        binaries = _generate_descriptor_binaries(yaml_path, None)

        assert len(binaries) == 1
        assert 0 in binaries
        assert nuttx_crc32(binaries[0]) == 0
        words = list(struct.unpack(f"<{len(binaries[0]) // 4}I", binaries[0]))
        assert words[0] == 0x0D0A0302


def test_generate_descriptor_binaries_two_slots():
    """Multi-descriptor YAML returns one binary per slot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "multi.yaml"
        yaml_path.write_text(
            "descriptor0:\n"
            "  ios:\n"
            "    - id: dummy0\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 10\n"
            "descriptor1:\n"
            "  ios:\n"
            "    - id: dummy1\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 20\n",
            encoding="utf-8",
        )
        binaries = _generate_descriptor_binaries(yaml_path, None)

        assert len(binaries) == 2
        assert 0 in binaries
        assert 1 in binaries

        # Both slots have valid CRC.
        assert nuttx_crc32(binaries[0]) == 0
        assert nuttx_crc32(binaries[1]) == 0

        # Slot 0 has init_value 10, slot 1 has init_value 20.
        words0 = list(struct.unpack(f"<{len(binaries[0]) // 4}I", binaries[0]))
        words1 = list(struct.unpack(f"<{len(binaries[1]) // 4}I", binaries[1]))
        assert 10 in words0
        assert 20 in words1
        assert 10 not in words1
        assert 20 not in words0


def test_generate_descriptor_binaries_three_slots():
    """Three contiguous descriptor slots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "three.yaml"
        parts = []
        for i in range(3):
            parts.append(
                f"descriptor{i}:\n"
                f"  ios:\n"
                f"    - id: dummy{i}\n"
                f"      type: dummy\n"
                f"      dtype: uint32\n"
                f"      config:\n"
                f"        init_value: {i * 10}\n"
            )
        yaml_path.write_text("".join(parts), encoding="utf-8")

        binaries = _generate_descriptor_binaries(yaml_path, None)
        assert len(binaries) == 3
        for i in range(3):
            assert i in binaries
            assert nuttx_crc32(binaries[i]) == 0


def test_generate_descriptor_binary_backwards_compat_multi():
    """generate_descriptor_binary on multi-descriptor returns slot 0 only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "multi.yaml"
        yaml_path.write_text(
            "descriptor0:\n"
            "  ios:\n"
            "    - id: dummy0\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 33\n"
            "descriptor1:\n"
            "  ios:\n"
            "    - id: dummy1\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 44\n",
            encoding="utf-8",
        )
        binary = _generate_descriptor_binary(yaml_path, None)
        assert nuttx_crc32(binary) == 0
        words = list(struct.unpack(f"<{len(binary) // 4}I", binary))
        assert 33 in words
        assert 44 not in words


def test_binary_command_multi_slot_output():
    """CLI produces slot0/slot1 files for multi-descriptor YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "multi.yaml"
        yaml_path.write_text(
            "descriptor0:\n"
            "  ios:\n"
            "    - id: d0\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 5\n"
            "descriptor1:\n"
            "  ios:\n"
            "    - id: d1\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "      config:\n"
            "        init_value: 7\n",
            encoding="utf-8",
        )

        out_base = Path(tmpdir) / "desc.bin"
        result = runner.invoke(
            cmd_desc_bin, [str(yaml_path), "-o", str(out_base)]
        )

        assert result.exit_code == 0
        assert "slot 0" in result.output
        assert "slot 1" in result.output

        slot0_path = Path(tmpdir) / "desc_slot0.bin"
        slot1_path = Path(tmpdir) / "desc_slot1.bin"
        assert slot0_path.exists()
        assert slot1_path.exists()

        assert nuttx_crc32(slot0_path.read_bytes()) == 0
        assert nuttx_crc32(slot1_path.read_bytes()) == 0


def test_binary_command_multi_slot_default_names():
    """Multi-slot without -o uses descriptor_slotN.bin default names."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "multi.yaml"
        yaml_path.write_text(
            "descriptor0:\n"
            "  ios:\n"
            "    - id: d0\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "descriptor1:\n"
            "  ios:\n"
            "    - id: d1\n"
            "      type: dummy\n"
            "      dtype: uint32\n",
            encoding="utf-8",
        )

        result = runner.invoke(cmd_desc_bin, [str(yaml_path)])

        assert result.exit_code == 0
        assert (Path(tmpdir) / "descriptor_slot0.bin").exists()
        assert (Path(tmpdir) / "descriptor_slot1.bin").exists()


def test_generate_descriptor_binaries_gap_stops():
    """Non-contiguous descriptor indices: gap stops enumeration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "gap.yaml"
        yaml_path.write_text(
            "descriptor0:\n"
            "  ios:\n"
            "    - id: d0\n"
            "      type: dummy\n"
            "      dtype: uint32\n"
            "descriptor2:\n"
            "  ios:\n"
            "    - id: d2\n"
            "      type: dummy\n"
            "      dtype: uint32\n",
            encoding="utf-8",
        )
        binaries = _generate_descriptor_binaries(yaml_path, None)

        # Only slot 0 — gap at descriptor1 stops enumeration.
        assert len(binaries) == 1
        assert 0 in binaries
        assert 1 not in binaries
