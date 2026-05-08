# tools/dawnpy/tests/test_descriptor_objects.py
#
# SPDX-License-Identifier: Apache-2.0
#

from types import SimpleNamespace
from typing import Any

import pytest

from dawnpy.descriptor.definitions.objects import (
    DescriptorDecodeError,
    DescriptorObject,
    IoObject,
    ProgramObject,
    ProtocolObject,
    _is_list_of_dicts,
    decode_objects,
    prepare_spec_instances,
)
from dawnpy.descriptor.definitions.registry import PROG_TYPES

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_descriptor_object_validate():
    assert DescriptorObject("foo").validate() == []


def test_io_object_canonical_subtype():
    spec = {
        "id": "temp1",
        "type": "sensor",
        "subtype": "hum",
        "instance": 1,
        "dtype": "float",
    }
    obj = IoObject.from_spec(spec, strict=True)
    assert obj is not None
    assert obj.subtype == "hum"


@pytest.mark.parametrize(
    "spec,error_message",
    [
        ({"type": "dummy", "instance": 1}, "IO entry is missing id"),
        ({"id": "temp1"}, "IO temp1 is missing type"),
        (
            {"id": "io1", "type": "unknown"},
            "IO io1 invalid: unknown IO type 'unknown'",
        ),
    ],
)
def test_io_object_missing_fields(spec: dict[str, Any], error_message: str):
    with pytest.raises(DescriptorDecodeError) as excinfo:
        IoObject.from_spec(spec, strict=True)
    assert error_message in str(excinfo.value)


def test_io_object_missing_fields_non_strict():
    assert IoObject.from_spec({"type": "dummy"}, strict=False) is None
    assert IoObject.from_spec({"id": "io1"}, strict=False) is None
    assert (
        IoObject.from_spec({"id": "io1", "type": "unknown"}, strict=False)
        is None
    )


def test_io_object_validate_errors():
    io_empty = IoObject(
        obj_id="",
        io_type="dummy",
        instance=0,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="uptime",
    )
    assert "id is required" in io_empty.validate()

    io_bad_type = IoObject(
        obj_id="io2",
        io_type="unknown",
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
    assert any("unknown IO type" in err for err in io_bad_type.validate())

    io_negative = IoObject(
        obj_id="io3",
        io_type="dummy",
        instance=-1,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert "instance must be >= 0" in io_negative.validate()

    io_sensor = IoObject(
        obj_id="sensor1",
        io_type="sensor",
        instance=0,
        dtype="float",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert "subtype is required" in io_sensor.validate()

    io_variant_skip = IoObject(
        obj_id="sys1",
        io_type="sysinfo",
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
    assert io_variant_skip.validate() == []

    io_invalid_subtype = IoObject(
        obj_id="sensor2",
        io_type="sensor",
        instance=0,
        dtype="float",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype="invalid",
        variant=None,
    )
    assert any(
        "invalid subtype" in err for err in io_invalid_subtype.validate()
    )


def test_io_object_missing_subtype():
    spec = {
        "id": "temp1",
        "type": "sensor",
        "instance": 1,
        "dtype": "float",
    }
    with pytest.raises(DescriptorDecodeError, match="subtype is required"):
        IoObject.from_spec(spec, strict=True)


def test_io_object_invalid_variant():
    spec = {
        "id": "sys1",
        "type": "sysinfo",
        "instance": 1,
        "dtype": "uint32",
        "variant": "unknown",
    }
    with pytest.raises(DescriptorDecodeError, match="invalid variant"):
        IoObject.from_spec(spec, strict=True)


def test_decode_objects_rejects_unknown_virt_owner(monkeypatch):
    prog_types = dict(PROG_TYPES)
    prog_types["futureprog"] = SimpleNamespace(header="future.hxx")
    monkeypatch.setattr(
        "dawnpy.descriptor.definitions.objects.PROG_TYPES", prog_types
    )

    spec = {
        "ios": [
            {"id": "src1", "type": "dummy", "dtype": "uint32"},
            {"id": "virt1", "type": "virt", "dtype": "uint32"},
        ],
        "programs": [
            {
                "id": "prog1",
                "type": "futureprog",
                "config": {"inputs": ["src1"], "outputs": ["virt1"]},
            }
        ],
    }

    with pytest.raises(
        DescriptorDecodeError,
        match="futureprog may not own output-side virt shape 'virt1'",
    ):
        decode_objects(spec, strict=True)


def test_decode_objects_accepts_selector_virt_target():
    spec = {
        "ios": [
            {"id": "ctrl1", "type": "virt", "dtype": "uint32"},
            {"id": "data1", "type": "virt", "dtype": "uint32"},
            {"id": "virt1", "type": "virt", "dtype": "uint32"},
        ],
        "programs": [
            {
                "id": "sel1",
                "type": "selector",
                "config": {
                    "control": "ctrl1",
                    "data": ["data1"],
                    "target": "virt1",
                },
            }
        ],
    }

    objects = decode_objects(spec, strict=True)
    assert any(
        isinstance(obj, ProgramObject) and obj.obj_id == "sel1"
        for obj in objects
    )


def test_program_object_missing_fields():
    with pytest.raises(
        DescriptorDecodeError, match="Program entry is missing id"
    ):
        ProgramObject.from_spec({}, strict=True)

    with pytest.raises(
        DescriptorDecodeError, match="Program prog is missing type"
    ):
        ProgramObject.from_spec({"id": "prog"}, strict=True)


def test_program_object_returns_none_when_not_strict():
    assert ProgramObject.from_spec({}, strict=False) is None
    assert ProgramObject.from_spec({"id": "prog"}, strict=False) is None
    assert (
        ProgramObject.from_spec(
            {"id": "prog", "type": "unknown"}, strict=False
        )
        is None
    )


def test_program_object_validate_errors():
    prog_missing_id = ProgramObject("", "statsmin", 1, [], [], None, {})
    assert "id is required" in prog_missing_id.validate()
    prog_bad_type = ProgramObject("prog2", "unknown", 1, [], [], None, {})
    assert any(
        "unknown program type" in err for err in prog_bad_type.validate()
    )

    with pytest.raises(DescriptorDecodeError, match="Program prog invalid"):
        ProgramObject.from_spec(
            {"id": "prog", "type": "stats", "instance": -1, "config": {}},
            strict=True,
        )


def test_program_object_validate_negative_instance():
    prog = ProgramObject("prog1", "statsmin", -1, [], [], None, {})
    assert "instance must be >= 0" in prog.validate()


@pytest.mark.parametrize(
    "config,error_message",
    [
        (
            {"inputs": ["io.in"], "outputs": []},
            "adjust requires exactly 1 output",
        ),
        (
            {"inputs": [], "outputs": ["io.out"]},
            "adjust requires exactly 1 input",
        ),
        (
            {"inputs": ["io.in1", "io.in2"], "outputs": ["io.out"]},
            "adjust requires exactly 1 input",
        ),
        (
            {"inputs": ["io.in"], "outputs": ["io.out1", "io.out2"]},
            "adjust requires exactly 1 output",
        ),
    ],
)
def test_program_object_adjust_binding_validation(
    config: dict[str, Any], error_message: str
):
    with pytest.raises(DescriptorDecodeError, match=error_message):
        ProgramObject.from_spec(
            {"id": "adjust1", "type": "adjust", "config": config},
            strict=True,
        )


def test_program_object_adjust_binding_validation_non_strict():
    assert (
        ProgramObject.from_spec(
            {
                "id": "adjust1",
                "type": "adjust",
                "config": {"inputs": ["io.in"], "outputs": []},
            },
            strict=False,
        )
        is None
    )


def test_program_object_adjust_valid_single_binding():
    obj = ProgramObject.from_spec(
        {
            "id": "adjust1",
            "type": "adjust",
            "config": {"inputs": ["io.in"], "outputs": ["io.out"]},
        },
        strict=True,
    )
    assert obj is not None
    assert obj.inputs == ["io.in"]
    assert obj.outputs == ["io.out"]


def test_decode_objects_rejects_bitpack_char_input():
    spec = {
        "ios": [
            {"id": "src", "type": "virt", "dtype": "char"},
            {"id": "dst", "type": "virt", "dtype": "uint32"},
        ],
        "programs": [
            {
                "id": "pack1",
                "type": "bitpack",
                "config": {
                    "inputs": [{"io": "src", "bit": 0}],
                    "output": "dst",
                },
            }
        ],
    }

    with pytest.raises(
        DescriptorDecodeError,
        match="bitpack input 'src' uses unsupported dtype 'char'",
    ):
        decode_objects(spec, strict=True)


def test_decode_objects_rejects_bitsplit_block_output():
    spec = {
        "ios": [
            {"id": "src", "type": "virt", "dtype": "uint32"},
            {"id": "dst", "type": "virt", "dtype": "block"},
        ],
        "programs": [
            {
                "id": "split1",
                "type": "bitsplit",
                "config": {
                    "inputs": ["src"],
                    "outputs": ["dst"],
                    "bits": [0],
                },
            }
        ],
    }

    with pytest.raises(
        DescriptorDecodeError,
        match="bitsplit output 'dst' uses unsupported dtype 'block'",
    ):
        decode_objects(spec, strict=True)


def test_decode_objects_accepts_bitpack_bitsplit_bitwise_dtypes():
    spec = {
        "ios": [
            {"id": "src", "type": "virt", "dtype": "uint8"},
            {"id": "mid", "type": "virt", "dtype": "uint64"},
            {"id": "dst", "type": "virt", "dtype": "bool"},
        ],
        "programs": [
            {
                "id": "pack1",
                "type": "bitpack",
                "config": {
                    "inputs": [{"io": "src", "bit": 0}],
                    "output": "mid",
                },
            },
            {
                "id": "split1",
                "type": "bitsplit",
                "config": {
                    "inputs": ["mid"],
                    "outputs": ["dst"],
                    "bits": [0],
                },
            },
        ],
    }

    objects = decode_objects(spec, strict=True)
    assert any(
        isinstance(obj, ProgramObject) and obj.obj_id == "pack1"
        for obj in objects
    )
    assert any(
        isinstance(obj, ProgramObject) and obj.obj_id == "split1"
        for obj in objects
    )


def test_decode_objects_validates_vecpack_vecsplit_dtype_mismatch():
    spec = {
        "ios": [
            {"id": "u32", "type": "virt", "dtype": "uint32"},
            {"id": "flt", "type": "virt", "dtype": "float"},
            {"id": "out", "type": "virt", "dtype": "uint32"},
        ],
        "programs": [
            {
                "id": "pack1",
                "type": "vecpack",
                "config": {"inputs": ["u32", "flt"], "output": "out"},
            },
            {
                "id": "split1",
                "type": "vecsplit",
                "config": {"source": "out", "outputs": ["u32", "flt"]},
            },
        ],
    }

    with pytest.raises(
        DescriptorDecodeError,
        match="vecpack input 'flt' dtype 'float' does not match output",
    ):
        decode_objects(spec, strict=True)


def test_program_handler_ref_and_shape_policies_cover_edge_paths():
    from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY

    src_bad = IoObject(
        "src_bad", "dummy", 0, "char", [], {}, False, False, False, None, None
    )
    src_ok = IoObject(
        "src_ok", "dummy", 0, "uint32", [], {}, False, False, False, None, None
    )
    out_bad = IoObject(
        "out_bad", "virt", 0, "block", [], {}, False, False, False, None, None
    )
    io_map = {io.obj_id: io for io in (src_bad, src_ok, out_bad)}

    bitpack = ProgramObject(
        "pack",
        "bitpack",
        0,
        [],
        [],
        None,
        {
            "inputs": [{}, [], {"io": "missing"}, {"io": "src_bad"}],
            "output": "out_bad",
        },
    )
    assert PROG_HANDLER_REGISTRY["bitpack"].validate_object_refs(
        bitpack, io_map
    ) == [
        "Program pack invalid: bitpack input 'src_bad' uses unsupported "
        "dtype 'char'",
        "Program pack invalid: bitpack output 'out_bad' uses unsupported "
        "dtype 'block'",
    ]

    bitsplit = ProgramObject(
        "split",
        "bitsplit",
        0,
        [],
        [],
        None,
        {"sources": ["missing", "src_bad"], "outputs": ["missing", "out_bad"]},
    )
    assert PROG_HANDLER_REGISTRY["bitsplit"].validate_object_refs(
        bitsplit, io_map
    ) == [
        "Program split invalid: bitsplit input 'src_bad' uses unsupported "
        "dtype 'char'",
        "Program split invalid: bitsplit output 'out_bad' uses unsupported "
        "dtype 'block'",
    ]

    vecpack = ProgramObject(
        "vpack",
        "vecpack",
        0,
        [],
        [],
        None,
        {"inputs": ["src_ok", "out_bad"], "output": "src_ok"},
    )
    assert PROG_HANDLER_REGISTRY["vecpack"].validate_object_refs(
        vecpack, io_map
    ) == [
        "Program vpack invalid: vecpack input 'out_bad' dtype 'block' "
        "does not match output 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["vecpack"].validate_object_refs(
            ProgramObject(
                "vpack_missing",
                "vecpack",
                0,
                [],
                [],
                None,
                {"inputs": ["missing"], "output": "src_ok"},
            ),
            io_map,
        )
        == []
    )
    assert PROG_HANDLER_REGISTRY["vecpack"].output_shape_owned_virt_targets(
        vecpack
    ) == {"src_ok"}

    vecsplit = ProgramObject(
        "vsplit",
        "vecsplit",
        0,
        [],
        [],
        None,
        {"source": "src_ok", "outputs": ["src_ok", "out_bad"]},
    )
    assert PROG_HANDLER_REGISTRY["vecsplit"].validate_object_refs(
        vecsplit, io_map
    ) == [
        "Program vsplit invalid: vecsplit output 'out_bad' dtype 'block' "
        "does not match source 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["vecsplit"].validate_object_refs(
            ProgramObject(
                "vsplit_missing",
                "vecsplit",
                0,
                [],
                [],
                None,
                {"source": "src_ok", "outputs": ["missing"]},
            ),
            io_map,
        )
        == []
    )
    assert PROG_HANDLER_REGISTRY["vecsplit"].output_shape_owned_virt_targets(
        vecsplit
    ) == {"src_ok", "out_bad"}

    manytoone = ProgramObject(
        "m2o",
        "manytoone",
        0,
        [],
        [],
        None,
        {"inputs": ["src_ok", "out_bad"], "output": "src_ok"},
    )
    assert PROG_HANDLER_REGISTRY["manytoone"].validate_object_refs(
        manytoone, io_map
    ) == [
        "Program m2o invalid: manytoone input 'out_bad' dtype 'block' "
        "does not match output 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["manytoone"].validate_object_refs(
            ProgramObject(
                "m2o_missing",
                "manytoone",
                0,
                [],
                [],
                None,
                {"inputs": ["missing"], "output": "src_ok"},
            ),
            io_map,
        )
        == []
    )

    onetomany = ProgramObject(
        "o2m",
        "onetomany",
        0,
        [],
        [],
        None,
        {"input": "src_ok", "outputs": ["src_ok", "out_bad"]},
    )
    assert PROG_HANDLER_REGISTRY["onetomany"].validate_object_refs(
        onetomany, io_map
    ) == [
        "Program o2m invalid: onetomany output 'out_bad' dtype 'block' "
        "does not match input 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["onetomany"].validate_object_refs(
            ProgramObject(
                "o2m_missing",
                "onetomany",
                0,
                [],
                [],
                None,
                {"input": "src_ok", "outputs": ["missing"]},
            ),
            io_map,
        )
        == []
    )

    iomux = ProgramObject(
        "mux",
        "iomux",
        0,
        [],
        [],
        None,
        {"inputs": ["src_ok", "out_bad"], "output": "src_ok"},
    )
    assert PROG_HANDLER_REGISTRY["iomux"].validate_object_refs(
        iomux, io_map
    ) == [
        "Program mux invalid: iomux input 'out_bad' dtype 'block' "
        "does not match output 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["iomux"].validate_object_refs(
            ProgramObject(
                "mux_missing",
                "iomux",
                0,
                [],
                [],
                None,
                {"inputs": ["missing"], "output": "src_ok"},
            ),
            io_map,
        )
        == []
    )

    iodemux = ProgramObject(
        "demux",
        "iodemux",
        0,
        [],
        [],
        None,
        {"input": "src_ok", "outputs": ["src_ok", "out_bad"]},
    )
    assert PROG_HANDLER_REGISTRY["iodemux"].validate_object_refs(
        iodemux, io_map
    ) == [
        "Program demux invalid: iodemux output 'out_bad' dtype 'block' "
        "does not match input 'src_ok' dtype 'uint32'"
    ]
    assert (
        PROG_HANDLER_REGISTRY["iodemux"].validate_object_refs(
            ProgramObject(
                "demux_missing",
                "iodemux",
                0,
                [],
                [],
                None,
                {"input": "src_ok", "outputs": ["missing"]},
            ),
            io_map,
        )
        == []
    )

    buffer = ProgramObject(
        "buf",
        "buffer",
        0,
        [],
        [],
        None,
        {"iobind": [[], {"src": "src_ok", "out": "o", "sel": "s"}]},
    )
    assert PROG_HANDLER_REGISTRY["buffer"].output_shape_owned_virt_targets(
        buffer
    ) == {"o", "s"}
    assert (
        PROG_HANDLER_REGISTRY["buffer"].output_shape_owned_virt_targets(
            ProgramObject("buf", "buffer", 0, [], [], None, {"iobind": {}})
        )
        == set()
    )

    gateway = ProgramObject(
        "gw",
        "gateway",
        0,
        [],
        [],
        None,
        {"iobind": [[], {"io1": "a", "io2": "b"}]},
    )
    assert PROG_HANDLER_REGISTRY["gateway"].output_shape_owned_virt_targets(
        gateway
    ) == {"a", "b"}
    assert (
        PROG_HANDLER_REGISTRY["gateway"].output_shape_owned_virt_targets(
            ProgramObject("gw", "gateway", 0, [], [], None, {"iobind": {}})
        )
        == set()
    )

    assert PROG_HANDLER_REGISTRY["selector"].output_shape_owned_virt_targets(
        ProgramObject("sel", "selector", 0, [], [], None, {"target": ["dst"]})
    ) == {"dst"}
    assert PROG_HANDLER_REGISTRY["manytoone"].output_shape_owned_virt_targets(
        ProgramObject("m2o", "manytoone", 0, [], [], None, {"output": ["dst"]})
    ) == {"dst"}
    assert PROG_HANDLER_REGISTRY["manytoone"].output_shape_owned_virt_targets(
        ProgramObject("m2o", "manytoone", 0, [], [], None, {"output": "dst"})
    ) == {"dst"}
    assert PROG_HANDLER_REGISTRY["onetomany"].output_shape_owned_virt_targets(
        ProgramObject(
            "o2m", "onetomany", 0, [], [], None, {"outputs": ["a", "b"]}
        )
    ) == {"a", "b"}
    assert PROG_HANDLER_REGISTRY["iomux"].output_shape_owned_virt_targets(
        ProgramObject("mux", "iomux", 0, [], [], None, {"output": "dst"})
    ) == {"dst"}
    assert PROG_HANDLER_REGISTRY["iomux"].output_shape_owned_virt_targets(
        ProgramObject("mux", "iomux", 0, [], [], None, {"output": ["dst"]})
    ) == {"dst"}
    assert PROG_HANDLER_REGISTRY["iodemux"].output_shape_owned_virt_targets(
        ProgramObject(
            "demux", "iodemux", 0, [], [], None, {"outputs": ["a", "b"]}
        )
    ) == {"a", "b"}
    assert (
        PROG_HANDLER_REGISTRY["adjust"].emit_iobind_cpp(
            [],
            ProgramObject("adj", "adjust", 0, [], [], None, {}),
            0,
            SimpleNamespace(append_line=lambda *args: None),
            "CProgAdjust",
        )
        is False
    )
    assert (
        PROG_HANDLER_REGISTRY["switch"].output_shape_owned_virt_targets(
            ProgramObject("sw", "switch", 0, [], [], None, {"target": []})
        )
        == set()
    )
    assert PROG_HANDLER_REGISTRY["switch"].output_shape_owned_virt_targets(
        ProgramObject("sw", "switch", 0, [], [], None, {"target": ["dst"]})
    ) == {"dst"}


def test_modbus_handler_context_helpers_cover_width_paths():
    from dawnpy.descriptor.handlers.proto_modbus_rtu import (
        _modbus_address_space,
        _modbus_binding_registers,
    )

    wide = IoObject(
        "wide", "dummy", 0, "uint64", [], {}, False, False, False, None, None
    )
    medium = IoObject(
        "medium",
        "dummy",
        0,
        "uint32",
        [],
        {},
        False,
        False,
        False,
        None,
        None,
    )
    narrow = IoObject(
        "narrow", "dummy", 0, "uint16", [], {}, False, False, False, None, None
    )
    objects = {obj.obj_id: obj for obj in (wide, medium, narrow)}

    assert _modbus_address_space("discrete") == "discrete"
    assert _modbus_address_space("holding") == "holding"
    assert _modbus_address_space("input") == "input"
    assert _modbus_binding_registers("coil", "wide", objects) == 1
    assert _modbus_binding_registers("holding", "missing", objects) == 1
    assert _modbus_binding_registers("holding", "wide", objects) == 4
    assert _modbus_binding_registers("holding", "medium", objects) == 2
    assert _modbus_binding_registers("holding", "narrow", objects) == 1


def test_protocol_object_validation_and_subclasses():
    with pytest.raises(
        DescriptorDecodeError, match="Protocol entry is missing id"
    ):
        ProtocolObject.from_spec({"type": "shell"}, strict=True)

    with pytest.raises(
        DescriptorDecodeError, match="Protocol proto is missing type"
    ):
        ProtocolObject.from_spec({"id": "proto"}, strict=True)

    assert ProtocolObject.from_spec({"type": "shell"}, strict=False) is None
    assert ProtocolObject.from_spec({"id": "proto"}, strict=False) is None

    serial = ProtocolObject.from_spec(
        {
            "id": "proto",
            "type": "serial",
            "config": {"bindings": ["io1", {"id": "io2"}]},
        },
        strict=True,
    )
    assert serial is not None
    assert serial.bindings == ["io1", "io2"]

    serial_bad_bindings = ProtocolObject.from_spec(
        {
            "id": "proto",
            "type": "serial",
            "config": {"bindings": "io1"},
        },
        strict=True,
    )
    assert serial_bad_bindings is not None
    assert serial_bad_bindings.bindings == []

    assert (
        ProtocolObject.from_spec(
            {
                "id": "proto",
                "type": "serial",
                "config": "bad",
                "bindings": ["io1"],
            },
            strict=False,
        )
        is None
    )

    modbus = ProtocolObject.from_spec(
        {
            "id": "modbus",
            "type": "modbus_rtu",
            "config": {
                "registers": [
                    {"type": "holding", "bindings": ["io1"]},
                    {"type": "coil", "bindings": [{"id": "io2"}]},
                ]
            },
        },
        strict=True,
    )
    assert modbus is not None
    assert modbus.bindings == ["io1", "io2"]

    assert (
        ProtocolObject.from_spec(
            {
                "id": "can",
                "type": "can",
                "bindings": ["io1"],
                "config": {"objects": "bad"},
            },
            strict=False,
        )
        is None
    )

    assert (
        ProtocolObject.from_spec(
            {
                "id": "modbus",
                "type": "modbus_rtu",
                "bindings": ["io1"],
                "config": {"registers": "bad"},
            },
            strict=False,
        )
        is None
    )

    proto = ProtocolObject("p1", "shell", 0, "not-a-map", [])
    assert "config must be a mapping" in proto.validate()

    can = ProtocolObject("p2", "can", 0, {"objects": "bad"}, [])
    assert "config.objects must be a list of mappings" in can.validate()

    modbus = ProtocolObject("p3", "modbus_rtu", 0, {"registers": "bad"}, [])
    assert "config.registers must be a list of mappings" in modbus.validate()

    nimble = ProtocolObject("p4", "nimble", 0, {"services": []}, [])
    assert "config.services must be a mapping" in nimble.validate()

    with pytest.raises(DescriptorDecodeError, match="Protocol proto invalid"):
        ProtocolObject.from_spec(
            {
                "id": "proto",
                "type": "unknown",
                "instance": 1,
                "config": {},
                "bindings": [],
            },
            strict=True,
        )
    assert (
        ProtocolObject.from_spec(
            {
                "id": "proto",
                "type": "unknown",
                "instance": 1,
                "config": {},
                "bindings": [],
            },
            strict=False,
        )
        is None
    )


def test_protocol_object_validate_errors():
    proto_bad = ProtocolObject("p1", "unknown", -1, "bad", [])
    errors = proto_bad.validate()
    assert any("unknown protocol type" in err for err in errors)
    assert any("instance must be >= 0" in err for err in errors)
    assert any("config must be a mapping" in err for err in errors)


def test_protocol_bindings_fallback_with_iobind2():
    spec = {
        "id": "nx1",
        "type": "nxscope_dummy",
        "instance": 1,
        "bindings": [],
        "config": {
            "iobind2": [
                "io1",
                {"id": "io2"},
                {"io": "io3"},
                {"ref": "io4"},
            ]
        },
    }
    obj = ProtocolObject.from_spec(spec, strict=True)
    assert obj.bindings == ["io1", "io2", "io3", "io4"]


def test_special_protocol_validates_super_errors():
    assert ProtocolObject("", "can", 0, {}, []).validate() == [
        "id is required"
    ]
    assert ProtocolObject("", "modbus_rtu", 0, {}, []).validate() == [
        "id is required"
    ]
    assert ProtocolObject("", "nimble", 0, {}, []).validate() == [
        "id is required"
    ]


def test_decode_objects_collections():
    spec = {
        "ios": [
            {"id": "io1", "type": "dummy", "instance": 1, "dtype": "uint32"}
        ],
        "programs": [
            {
                "id": "prog1",
                "type": "statsmin",
                "instance": 1,
                "config": {"inputs": ["io1"], "outputs": []},
            }
        ],
        "protocols": [
            {
                "id": "proto1",
                "type": "shell",
                "instance": 1,
                "config": {},
                "bindings": [],
            }
        ],
    }
    objs = decode_objects(spec)
    assert any(isinstance(obj, IoObject) for obj in objs)
    assert any(isinstance(obj, ProgramObject) for obj in objs)
    assert any(isinstance(obj, ProtocolObject) for obj in objs)


def test_prepare_spec_instances_assigns_missing_values():
    spec = {
        "ios": [
            {"id": "io1", "type": "dummy"},
            {"id": "io2", "type": "dummy"},
            {"id": "io3", "type": "virt"},
        ],
        "programs": [
            {"id": "prog1", "type": "statsmin", "config": {}},
            {"id": "prog2", "type": "statsmin", "config": {}},
        ],
        "protocols": [
            {"id": "proto1", "type": "shell", "config": {}},
            {"id": "proto2", "type": "shell", "config": {}},
        ],
    }

    prepare_spec_instances(spec)

    assert [item["instance"] for item in spec["ios"]] == [0, 1, 0]
    assert [item["instance"] for item in spec["programs"]] == [0, 1]
    assert [item["instance"] for item in spec["protocols"]] == [0, 1]


def test_prepare_spec_instances_preserves_explicit_values():
    spec = {
        "ios": [
            {"id": "io1", "type": "dummy"},
            {"id": "io2", "type": "dummy", "instance": 4},
            {"id": "io3", "type": "dummy"},
            {"id": "io4", "type": "virt", "instance": 2},
            {"id": "io5", "type": "virt"},
        ]
    }

    prepare_spec_instances(spec)

    assert [item["instance"] for item in spec["ios"]] == [0, 4, 5, 2, 3]


def test_private_helpers():
    assert IoObject.normalize_subtype("HUM") == "hum"
    assert IoObject.normalize_subtype(None) is None
    with pytest.raises(DescriptorDecodeError):
        IoObject.normalize_tags({"foo": "bar"})
    assert IoObject.normalize_tags("solo") == ["solo"]
    assert _is_list_of_dicts("bad") is False
    assert _is_list_of_dicts([{"id": "io1"}]) is True
    assert _is_list_of_dicts(["io1", {"id": "io2"}]) is False


def test_resolve_proto_bindings_non_list():
    assert (
        ProtocolObject.resolve_bindings(
            "nxscope_dummy", [], {"iobind2": "bad"}
        )
        == []
    )
