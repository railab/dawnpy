# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_serialize_io_control_trigger_and_config_paths():
    decoder = ObjectIdDecoder()

    dummy_obj = IoObject(
        obj_id="dummy0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 5},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    control_obj = IoObject(
        obj_id="control0",
        io_type="control",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"targets": ["dummy0"], "allowed": ["stop", "start"]},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    trigger_obj = IoObject(
        obj_id="trigger0",
        io_type="trigger",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "targets": ["dummy0"],
            "allowed": ["reset", "trigger1", "trigger2", "trigger3"],
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    config_obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 5},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    obj_ids: dict[str, int] = {}
    words: list[int] = []

    _serialize_io_object(words, dummy_obj, obj_ids, decoder)
    _serialize_io_object(words, control_obj, obj_ids, decoder)
    _serialize_io_object(words, trigger_obj, obj_ids, decoder)
    _serialize_io_object(words, config_obj, obj_ids, decoder)

    assert "control0" in obj_ids
    assert "trigger0" in obj_ids
    assert "config0" in obj_ids


def test_serialize_io_config_raises_when_dummy_class_missing():
    decoder = ObjectIdDecoder()
    decoder.io_classes = {
        cls_id: name
        for cls_id, name in decoder.io_classes.items()
        if name != "dummy"
    }

    obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 5},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    with pytest.raises(click.ClickException, match="Unknown IO class 'dummy'"):
        _serialize_io_object([], obj, {"dummy0": 0x12345678}, decoder)


def test_io_config_generic_helper_edge_branches():
    """Cover generic ConfigField helper branches for config IO."""
    assert (
        io_config_mod._cpp_helper_call(
            ConfigField(name="x"), SimpleNamespace(), 0
        )
        is None
    )
    assert (
        io_config_mod._cpp_helper_call(
            ConfigField(
                name="x",
                cpp_helper="CExample::cfg",
                params=["custom"],
                default_params=[False],
            ),
            SimpleNamespace(initval_param=7, rw=True),
            0,
        )
        == "CExample::cfg(false),"
    )
    assert (
        io_config_mod._choose_config_field(
            [
                ConfigField(name="a", cpp_helper="CExample::a"),
                ConfigField(name="b", cpp_helper="CExample::b"),
            ],
            {"a": 1, "b": 2},
            "",
        )
        is None
    )


def test_io_config_binary_handles_non_dict_reference_config():
    """Cover malformed anchored-reference config without target coupling."""
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="config0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": [],
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    _serialize_io_object([], obj, {"dummy0": 0x12345678}, decoder)


def test_io_config_binary_default_param_branch():
    """Cover generic binary cfg-id params that use ConfigField defaults."""
    decoder = ObjectIdDecoder()
    io_dtype_map = {
        str(info["type"]).lower(): dtype_id
        for dtype_id, info in decoder.dtype_info.items()
    }
    io_cls_map = {
        name.lower(): cls_id for cls_id, name in decoder.io_classes.items()
    }
    ctx = io_config_mod._IOSerializeContext(
        obj=IoObject(
            obj_id="config0",
            io_type="config",
            instance=0,
            dtype="uint32",
            tags=[],
            config={},
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        ),
        io_cls=io_cls_map["config"],
        dtype=io_dtype_map["uint32"],
        dtype_name="uint32",
        config={},
        obj_ids={},
        items=[],
        decoder=decoder,
        io_dtype_map=io_dtype_map,
        io_cls_map=io_cls_map,
    )
    field = ConfigField(
        name="init_value",
        cpp_helper="CIODummy::cfgIdInitval",
        params=["custom"],
        default_params=[False],
    )
    value = io_config_mod._binary_cfg_id(
        ctx,
        field,
        {
            "id": "dummy0",
            "type": "dummy",
            "dtype": "uint32",
            "config": {"init_value": 1},
        },
    )
    assert isinstance(value, int)


def test_io_config_binary_uses_config_io_rw_grant(mock_header_cfg_id):
    """ConfigIO target cfg-id RW comes from the resolved ConfigIO grant."""
    decoder = ObjectIdDecoder()
    io_dtype_map = {
        str(info["type"]).lower(): dtype_id
        for dtype_id, info in decoder.dtype_info.items()
    }
    io_cls_map = {
        name.lower(): cls_id for cls_id, name in decoder.io_classes.items()
    }
    ctx = io_config_mod._IOSerializeContext(
        obj=IoObject(
            obj_id="config0",
            io_type="config",
            instance=0,
            dtype="uint32",
            tags=[],
            config={},
            timestamp=False,
            notify=False,
            rw=False,
            subtype=None,
            variant=None,
        ),
        io_cls=io_cls_map["config"],
        dtype=io_dtype_map["uint32"],
        dtype_name="uint32",
        config={},
        obj_ids={},
        items=[],
        decoder=decoder,
        io_dtype_map=io_dtype_map,
        io_cls_map=io_cls_map,
        config_rw_grants={("pwm0", "freq"): True},
    )
    field = ConfigField(
        name="freq",
        cpp_helper="CIOPwm::cfgIdFreq",
        value_type="int",
    )

    value = io_config_mod._binary_cfg_id(
        ctx,
        field,
        {
            "id": "pwm0",
            "type": "pwm",
            "dtype": "uint32",
            "config": {"freq": 1000},
        },
    )

    assert value == cfg_id(
        1,
        io_cls_map["pwm"],
        io_dtype_map["uint32"],
        True,
        1,
        header_cfg_id("CIOPwm", "cfgIdFreq"),
    )


def test_serialize_io_extended_supported_types():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []

    dummy_notify = IoObject(
        obj_id="dn0",
        io_type="dummy_notify",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "dim": 2,
            "init_value": [1, 2],
            "interval_us": 1000,
            "notify_on_write": True,
        },
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )
    timestamp = IoObject(
        obj_id="ts0",
        io_type="timestamp",
        instance=0,
        dtype="uint64",
        tags=[],
        config={"interval_us": 5000},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    fileio = IoObject(
        obj_id="f0",
        io_type="fileio",
        instance=0,
        dtype="block",
        tags=[],
        config={"path": "/tmp/test.bin", "perm": 2},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    gpi = IoObject(
        obj_id="gpi0",
        io_type="gpi",
        instance=0,
        dtype="bool",
        tags=[],
        config={"device": 1},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, dummy_notify, obj_ids, decoder)
    _serialize_io_object(words, timestamp, obj_ids, decoder)
    _serialize_io_object(words, fileio, obj_ids, decoder)
    _serialize_io_object(words, gpi, obj_ids, decoder)
    assert obj_ids["dn0"] != 0
    assert obj_ids["ts0"] != 0
    assert obj_ids["f0"] != 0
    assert obj_ids["gpi0"] != 0


def test_serialize_io_encoder_emits_posmax():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    encoder = IoObject(
        obj_id="enc0",
        io_type="encoder",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"posmax": 4096},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    encoder_index = IoObject(
        obj_id="enc_idx0",
        io_type="encoder_index",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"posmax": 8192},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, encoder, obj_ids, decoder)
    _serialize_io_object(words, encoder_index, obj_ids, decoder)

    assert obj_ids["enc0"] != 0
    assert obj_ids["enc_idx0"] != 0
    assert 4096 in words
    assert 8192 in words


def test_serialize_io_notify_unknown_dtype_raises(monkeypatch):
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="dn0",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"notify": {"type": "stream", "priority": 1, "batch": 2}},
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )

    monkeypatch.setattr(
        binary_serializer_mod,
        "dtype_id_by_name",
        lambda _decoder, _name: None,
    )
    with pytest.raises(click.ClickException, match="notify cfg"):
        _serialize_io_object([], obj, {}, decoder)


def test_serialize_io_notify_config_serializes_values():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    obj = IoObject(
        obj_id="dn1",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"notify": {"type": "stream", "priority": 7, "batch": 3}},
        timestamp=False,
        notify=True,
        rw=True,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, obj, obj_ids, decoder)
    assert obj_ids["dn1"] != 0
    assert 7 in words
    assert 3 in words


def test_encode_limit_word_dtype_paths():
    from dawnpy.descriptor.encoding.binary_serializer import (
        _encode_limit_word,
        _limit_value_words,
    )

    assert _encode_limit_word(7, "uint32") == 7
    # Negative int8 -> two's complement bit pattern.
    assert (
        _encode_limit_word(-3, "int8")
        == struct.unpack("<I", struct.pack("<i", -3))[0]
    )
    # Float -> IEEE-754 bit pattern.
    expected_float = struct.unpack("<I", struct.pack("<f", 0.25))[0]
    assert _encode_limit_word(0.25, "float") == expected_float
    # List input expands to per-element words.
    assert _limit_value_words([1, 2, 3], "uint32") == [1, 2, 3]
    # Scalar wraps in single-element list.
    assert _limit_value_words(5, "uint32") == [5]


def test_encode_limit_word_unsupported_dtype_raises():
    from dawnpy.descriptor.encoding.binary_serializer import _encode_limit_word

    with pytest.raises(click.ClickException, match="limits not supported"):
        _encode_limit_word(0, "block")


def test_serialize_io_limits_uint32_emits_three_items(mock_header_cfg_id):
    from dawnpy.descriptor.encoding.binary_serializer import (
        _append_limits_items,
    )

    items: list[tuple[int, list[int]]] = []
    _append_limits_items(
        items,
        {"min": 0, "max": 10, "step": 1},
        "uint32",
        dtype_id=8,  # arbitrary id; cfg_id only masks low bits
    )
    assert len(items) == 3
    cfg_min = mock_header_cfg_id("CIOCommon", "cfgIdLimitMin")
    cfg_max = mock_header_cfg_id("CIOCommon", "cfgIdLimitMax")
    cfg_step = mock_header_cfg_id("CIOCommon", "cfgIdLimitStep")
    assert (items[0][0] & 0x1F) == cfg_min
    assert (items[1][0] & 0x1F) == cfg_max
    assert (items[2][0] & 0x1F) == cfg_step
    assert items[0][1] == [0]
    assert items[1][1] == [10]
    assert items[2][1] == [1]


def test_serialize_io_limits_partial_block():
    from dawnpy.descriptor.encoding.binary_serializer import (
        _append_limits_items,
    )

    items: list[tuple[int, list[int]]] = []
    _append_limits_items(items, {"min": 0, "max": 10}, "uint32", dtype_id=8)
    # No step => only two items emitted.
    assert len(items) == 2

    items_skipped: list[tuple[int, list[int]]] = []
    _append_limits_items(items_skipped, "not-a-dict", "uint32", dtype_id=8)
    assert items_skipped == []


def test_serialize_io_limits_full_object_path():
    decoder = ObjectIdDecoder()
    obj_ids: dict[str, int] = {}
    words: list[int] = []
    obj = IoObject(
        obj_id="lim1",
        io_type="dummy",
        instance=0,
        dtype="int8",
        tags=[],
        config={"limits": {"min": -5, "max": 5, "step": 1}},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )

    _serialize_io_object(words, obj, obj_ids, decoder)
    assert obj_ids["lim1"] != 0
    # Negative min must be encoded as two's complement uint32.
    expected_min = struct.unpack("<I", struct.pack("<i", -5))[0]
    assert expected_min in words
    assert 5 in words


def test_descriptor_generator_limits_emits_helpers():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import (
        IoConfigGenerator,
        _limits_item_count,
    )
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    obj = IoObject(
        obj_id="lim2",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"limits": {"min": 0, "max": 10, "step": [1]}},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    assert _limits_item_count({"min": 0, "max": 10}) == 2
    assert _limits_item_count("invalid") == 0

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: {},
        config_rw_grants=lambda: {},
    )
    lines = gen.generate_io_config("DUMMY_MACRO", obj)
    body = "\n".join(lines)
    # The leading count line must include three cfg items for the limits
    # block, even though it is one YAML key.
    assert "DUMMY_MACRO, 3," in lines[0]
    assert "CIOCommon::cfgIdLimitMin" in body
    assert "CIOCommon::cfgIdLimitMax" in body
    assert "CIOCommon::cfgIdLimitStep" in body


def test_descriptor_generator_io_config_limits_uint32():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target = IoObject(
        obj_id="dummy_lim",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 4},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio = IoObject(
        obj_id="cfgio_lim",
        io_type="config",
        instance=1,
        dtype="uint32",
        tags=[],
        config={
            "objid_ref": "dummy_lim",
            "limits": {"min": 0, "max": 10, "step": 2},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {"dummy_lim": target, "cfgio_lim": cfgio}

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )
    lines = gen.generate_io_config("CFGIO_LIM", cfgio)
    body = "\n".join(lines)
    # 2 (cfgIdCfg + cfgIdAlloc) + 3 (limits) cfg items.
    assert "CFGIO_LIM, 5," in lines[0]
    assert "CIOCommon::cfgIdLimitMin" in body
    assert "CIOCommon::cfgIdLimitMax" in body
    assert "CIOCommon::cfgIdLimitStep" in body
    assert "CIOConfig::cfgIdCfg()" in body
    assert "DUMMY_LIM" in body


def test_descriptor_generator_io_config_limits_partial():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target = IoObject(
        obj_id="dummy_p",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={"init_value": 0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio = IoObject(
        obj_id="cfg_p",
        io_type="config",
        instance=4,
        dtype="uint32",
        tags=[],
        # No 'step' key -> partial-limits path in generate_cpp.
        config={"objid_ref": "dummy_p", "limits": {"min": 0, "max": 10}},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {"dummy_p": target, "cfg_p": cfgio}
    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )
    body = "\n".join(gen.generate_io_config("CFG_P", cfgio))
    assert "cfgIdLimitMin" in body
    assert "cfgIdLimitMax" in body
    assert "cfgIdLimitStep" not in body


def test_descriptor_generator_io_config_limits_signed_and_float():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    target_i = IoObject(
        obj_id="dummy_i",
        io_type="dummy",
        instance=0,
        dtype="int8",
        tags=[],
        config={"init_value": 0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio_i = IoObject(
        obj_id="cfg_i",
        io_type="config",
        instance=2,
        dtype="int8",
        tags=[],
        config={
            "objid_ref": "dummy_i",
            "limits": {"min": -5, "max": [5], "step": 1},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    target_f = IoObject(
        obj_id="dummy_f",
        io_type="dummy",
        instance=0,
        dtype="float",
        tags=[],
        config={"init_value": 0.0},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    cfgio_f = IoObject(
        obj_id="cfg_f",
        io_type="config",
        instance=3,
        dtype="float",
        tags=[],
        config={
            "objid_ref": "dummy_f",
            "limits": {"min": 0.0, "max": 1.0, "step": 0.25},
        },
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )

    objects = {
        "dummy_i": target_i,
        "cfg_i": cfgio_i,
        "dummy_f": target_f,
        "cfg_f": cfgio_f,
    }
    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: objects,
        config_rw_grants=lambda: {},
    )

    body_i = "\n".join(gen.generate_io_config("CFG_I", cfgio_i))
    # Negative integer literal must be cast through uint32_t.
    assert "(uint32_t)-5" in body_i

    body_f = "\n".join(gen.generate_io_config("CFG_F", cfgio_f))
    # Float literals are emitted as hex bit patterns (0.25 -> 0x3e800000).
    assert "0x3e800000" in body_f


def test_descriptor_generator_limits_partial_and_non_dict():
    from dawnpy.descriptor.definitions.loader import ConfigLoader
    from dawnpy.descriptor.generation.io_codegen import IoConfigGenerator
    from dawnpy.descriptor.support.formatting import DescriptorFormatHelper

    gen = IoConfigGenerator(
        config_loader=ConfigLoader(),
        format_helper=DescriptorFormatHelper(),
        objects=lambda: {},
        config_rw_grants=lambda: {},
    )

    # Non-dict limits value: emitter must short-circuit silently.
    out: list[str] = []
    gen._append_limits_lines(out, "not-a-dict", "uint32")
    assert out == []

    # Missing one of the keys: emitter skips it without erroring.
    out = []
    gen._append_limits_lines(out, {"min": 0, "max": 10}, "uint32")
    body = "\n".join(out)
    assert "cfgIdLimitMin" in body
    assert "cfgIdLimitMax" in body
    assert "cfgIdLimitStep" not in body


def test_io_class_name_resolution_via_headerdefs():
    # Sensor without subtype cannot resolve a method.
    assert _io_class_name(_mk_io("sensor")) is None
    # Sensor temp resolves through CIOSensor::objectIdTemp.
    assert _io_class_name(_mk_io("sensor", subtype="temp")) == (
        "sensor_temperature"
    )
    assert _io_class_name(_mk_io("sensor_producer", subtype="temp")) == (
        "sensor_producer_temperature"
    )
    # System IOs resolve via CIOSysinfo / CIOUname / CIOBoardctl variants.
    assert _io_class_name(_mk_io("sysinfo", variant="uptime")) == (
        "system_uptime"
    )
    assert _io_class_name(_mk_io("uname", variant="hostname")) == (
        "system_hostname"
    )
    assert _io_class_name(_mk_io("boardctl", variant="reset")) == (
        "system_reset"
    )
    # Standard objectId path resolves dummy via headerdefs.
    assert _io_class_name(_mk_io("dummy")) == "dummy"


def test_io_helper_branch_edges():
    from dawnpy.descriptor.encoding.words import (
        dtype_id_by_name,
        mask_from_allowed,
    )

    decoder = ObjectIdDecoder()
    assert dtype_id_by_name(decoder, "not-a-type") is None
    assert mask_from_allowed([], {"x": 1}) is None
    assert mask_from_allowed(["x"], []) == 0
    assert mask_from_allowed(["x", "y"], {"x": 0}) == 1


def test_serialize_io_error_branches(monkeypatch):
    """Cover the dtype-lookup error branches in binary.py + io_config."""
    from dawnpy.descriptor.encoding import io_serialization as io_runtime_mod

    decoder = ObjectIdDecoder()
    io = IoObject(
        obj_id="cfg0",
        io_type="config",
        instance=0,
        dtype="uint32",
        tags=[],
        config={
            "device": 1,
            "objid_ref": {
                "id": "dummy0",
                "type": "dummy",
                "dtype": "uint32",
                "config": {"init_value": 1},
            },
            "objcfg_ref": "init_value",
        },
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    obj_ids = {"dummy0": 0x12345678}

    # Branch 1: device-cfg dtype lookup fails inside binary.py.
    with pytest.MonkeyPatch.context() as scoped_patch:
        scoped_patch.setattr(
            binary_serializer_mod,
            "dtype_id_by_name",
            lambda *a, **kw: None,
        )
        with pytest.raises(click.ClickException, match="device cfg"):
            _serialize_io_object([], io, dict(obj_ids), decoder)

    # Branch 2: config-reference dtype lookup fails inside io_config
    # handler (the first resolve_dtype call inside io_config.encode_binary).
    calls = {"n": 0}

    def _none_on_nth(want_n: int):
        def _wrapped(*a, **kw):
            calls["n"] += 1
            if calls["n"] == want_n:
                return None
            return 7

        return _wrapped

    calls["n"] = 0
    monkeypatch.setattr(io_runtime_mod, "dtype_id_by_name", _none_on_nth(1))
    with pytest.raises(click.ClickException, match="config reference$"):
        _serialize_io_object([], io, dict(obj_ids), decoder)

    calls["n"] = 0
    monkeypatch.setattr(io_runtime_mod, "dtype_id_by_name", _none_on_nth(2))
    with pytest.raises(click.ClickException, match="reference cfgid"):
        _serialize_io_object([], io, dict(obj_ids), decoder)


def test_serialize_io_dummy_baseline():
    decoder = ObjectIdDecoder()
    obj = IoObject(
        obj_id="d0",
        io_type="dummy",
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
    words: list[int] = []
    _serialize_io_object(words, obj, {}, decoder)
    assert words
