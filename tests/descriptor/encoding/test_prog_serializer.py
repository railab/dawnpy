# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_prog_yaml_driven_branches_and_errors(monkeypatch):
    decoder = ObjectIdDecoder()
    obj_ids = {
        "src0": 0x1001,
        "src1": 0x1002,
        "virt0": 0x2001,
        "virt1": 0x2002,
        "o0": 0x3001,
        "sel0": 0x3002,
        "stat0": 0x3003,
        "t0": 0x4001,
    }
    words: list[int] = []

    # Prog policy now lives in handlers/prog_*.py; no YAML monkey-patch
    # needed.
    sampling = ProgramObject(
        obj_id="p_sampling",
        prog_type="sampling",
        instance=0,
        inputs=["src0", "src1"],
        outputs=["virt0", "virt1"],
        reset=None,
        config={"interval": 5},
    )
    serialize_prog_object(words, sampling, obj_ids, decoder)

    adjust = ProgramObject(
        obj_id="p_adjust",
        prog_type="adjust",
        instance=1,
        inputs=["src0"],
        outputs=["virt0"],
        reset=None,
        config={"params": {"offset": 2, "scale": 3}},
    )
    serialize_prog_object(words, adjust, obj_ids, decoder)

    gateway = ProgramObject(
        obj_id="p_gateway",
        prog_type="gateway",
        instance=2,
        inputs=[],
        outputs=[],
        reset=None,
        config={"iobind": [0, {"x": 1}, {"io1": "src0", "io2": "virt0"}]},
    )
    serialize_prog_object(words, gateway, obj_ids, decoder)

    buffer = ProgramObject(
        obj_id="p_buffer",
        prog_type="buffer",
        instance=3,
        inputs=[],
        outputs=[],
        reset=None,
        config={
            "iobind": [
                0,
                {"x": 1},
                {
                    "src": "src0",
                    "out": "o0",
                    "sel": "sel0",
                    "stat": "stat0",
                },
            ],
            "chunk_size": 32,
        },
    )
    serialize_prog_object(words, buffer, obj_ids, decoder)
    assert 32 in words

    default_buffer_words: list[int] = []
    default_buffer = ProgramObject(
        obj_id="p_buffer_default",
        prog_type="buffer",
        instance=5,
        inputs=[],
        outputs=[],
        reset=None,
        config={},
    )
    serialize_prog_object(
        default_buffer_words, default_buffer, dict(obj_ids), decoder
    )
    from dawnpy.descriptor.encoding.words import cfg_id

    buffer_cls = next(
        cls for cls, name in decoder.prog_classes.items() if name == "buffer"
    )
    chunk_cfg = cfg_id(3, buffer_cls, 0, False, 1, 4)
    chunk_idx = default_buffer_words.index(chunk_cfg)
    assert default_buffer_words[chunk_idx + 1] == 1

    sequencer = ProgramObject(
        obj_id="p_seq",
        prog_type="sequencer",
        instance=4,
        inputs=[],
        outputs=[],
        reset=None,
        config={
            "targets": ["x", "t0"],
            "states": [0, {"x": 1}, {"value": 7, "dwell_us": 10}],
            "start_index": 1,
        },
    )
    serialize_prog_object(words, sequencer, obj_ids, decoder)
    assert obj_ids["p_seq"] != 0
    adjust_objid = obj_ids["p_adjust"]
    adjust_idx = words.index(adjust_objid)
    assert words[adjust_idx + 1] == 2

    # When neither the handlers nor PROG_TYPES has an entry for a prog
    # type, the serializer cannot resolve the C++ class and bails out.
    monkeypatch.setattr(prog_serializer_mod, "PROG_HANDLER_REGISTRY", {})
    monkeypatch.setattr(prog_serializer_mod, "PROG_TYPES", {})
    with pytest.raises(
        click.ClickException, match="Unable to resolve PROG class"
    ):
        serialize_prog_object([], sampling, dict(obj_ids), decoder)

    # When the resolved class name is not in the decoder map, the serializer
    # raises an "Unknown PROG class" error.
    monkeypatch.setattr(
        prog_serializer_mod,
        "header_object_class_name",
        lambda owner, method: "missing_prog_class",
    )
    monkeypatch.setattr(
        prog_serializer_mod,
        "PROG_HANDLER_REGISTRY",
        {"sampling": SimpleNamespace(cpp_class="CProgSampling")},
    )
    with pytest.raises(click.ClickException, match="Unknown PROG class"):
        serialize_prog_object([], sampling, {}, decoder)


def test_simple_prog_handlers_encode_binary():
    """Cover simple auto-discovered PROG handler binary paths."""
    decoder = ObjectIdDecoder()
    obj_ids = {"src0": 0x1001, "virt0": 0x2001}

    cases = [
        ("dummy", {}),
        ("latest", {}),
        ("redirect", {}),
        ("statsavg", {}),
        ("statscount", {}),
        ("statsmax", {}),
        ("statsrms", {}),
        ("statssum", {}),
        ("movingavg", {"window": 4}),
        ("iirfilter", {"alpha_num": 1, "alpha_den": 8}),
        ("threshold", {"mode": 1, "low": 2, "high": 3}),
        ("thresholdvalue", {"mode": 1, "low": 2, "high": 3}),
    ]
    for index, (prog_type, config) in enumerate(cases):
        words: list[int] = []
        obj = ProgramObject(
            obj_id=f"p_{prog_type}",
            prog_type=prog_type,
            instance=index,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config=config,
        )
        serialize_prog_object(words, obj, dict(obj_ids), decoder)
        assert words[1] >= 1

    # Exercise the "field not present" branch in shared uint32 emission.
    serialize_prog_object(
        [],
        ProgramObject(
            obj_id="p_movingavg_empty",
            prog_type="movingavg",
            instance=99,
            inputs=["src0"],
            outputs=["virt0"],
            reset=None,
            config={},
        ),
        dict(obj_ids),
        decoder,
    )


def test_prog_iobind_binary_interleaves_multiple_binds():
    decoder = ObjectIdDecoder()
    obj_ids = {
        "src0": 0x1001,
        "src1": 0x1002,
        "virt0": 0x2001,
        "virt1": 0x2002,
    }
    words: list[int] = []
    obj = ProgramObject(
        obj_id="p_bitsplit",
        prog_type="bitsplit",
        instance=0,
        inputs=["src0", "src1"],
        outputs=["virt0", "virt1"],
        reset=None,
        config={"bits": [0, 1]},
    )

    serialize_prog_object(words, obj, dict(obj_ids), decoder)

    assert words[3:7] == [0x1001, 0x2001, 0x1002, 0x2002]


def test_prog_iobind_binary_rejects_mismatched_bindings():
    decoder = ObjectIdDecoder()
    obj_ids = {"src0": 0x1001, "src1": 0x1002, "virt0": 0x2001}
    obj = ProgramObject(
        obj_id="p_mismatch",
        prog_type="statsmin",
        instance=0,
        inputs=["src0"],
        outputs=["virt0"],
        reset=None,
        config={"sources": ["src0", "src1"], "outputs": ["virt0"]},
    )

    with pytest.raises(ValueError, match="has 2 sources and 1 outputs"):
        serialize_prog_object([], obj, obj_ids, decoder)


def test_prog_serializer_falls_back_to_registered_type(monkeypatch):
    """Cover OOT-style PROG_TYPES fallback when no built-in handler exists."""
    decoder = ObjectIdDecoder()
    monkeypatch.setattr(prog_serializer_mod, "PROG_HANDLER_REGISTRY", {})
    monkeypatch.setattr(
        prog_serializer_mod,
        "PROG_TYPES",
        {"oot_sampling": SimpleNamespace(cpp_class="CProgSampling")},
    )
    words: list[int] = []
    serialize_prog_object(
        words,
        ProgramObject(
            obj_id="oot",
            prog_type="oot_sampling",
            instance=0,
            inputs=[],
            outputs=[],
            reset=None,
            config={},
        ),
        {},
        decoder,
    )
    assert words[1] == 0
