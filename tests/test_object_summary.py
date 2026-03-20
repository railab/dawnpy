# tools/dawnpy/tests/test_object_summary.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for object summary utilities."""

from dawnpy.descriptor.client import (
    ClientDescriptor,
    ClientIo,
    ClientProgram,
    ClientProto,
)
from dawnpy.descriptor.definitions.summary import (
    ObjectIdResolver,
    build_io_table,
    build_program_table,
    build_protocol_table,
)


def _io_class_id(resolver: ObjectIdResolver, name: str) -> int:
    for class_id, class_name in resolver.decoder.io_classes.items():
        if class_name == name:
            return class_id
    raise AssertionError(f"Missing IO class {name}")


def _dtype_id(resolver: ObjectIdResolver, name: str) -> int:
    for dtype_id, info in resolver.decoder.dtype_info.items():
        if info["type"] == name:
            return dtype_id
    raise AssertionError(f"Missing dtype {name}")


def test_object_id_resolver_io_and_program_proto():
    resolver = ObjectIdResolver()
    dummy = ClientIo(
        io_id="dummy1",
        io_type="dummy",
        instance=1,
        dtype="bool",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    objid = resolver.io_objid(dummy)
    expected = resolver.decoder.encode(
        1,
        _io_class_id(resolver, "dummy"),
        _dtype_id(resolver, "bool"),
        0,
        1,
    )
    assert objid == expected

    uptime = ClientIo(
        io_id="uptime1",
        io_type="sysinfo",
        instance=1,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="uptime",
    )
    uptime_id = resolver.io_objid(uptime)
    decoded = resolver.decoder.decode(uptime_id)
    assert decoded.dtype_name == "uint64"

    reset = ClientIo(
        io_id="reset1",
        io_type="boardctl",
        instance=5,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="reset",
    )
    reset_id = resolver.io_objid(reset)
    decoded = resolver.decoder.decode(reset_id)
    assert decoded.priv == 0

    uptime_default_inst = ClientIo(
        io_id="uptime_default",
        io_type="sysinfo",
        instance=0,
        dtype="float",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="uptime",
    )
    uptime_default_id = resolver.io_objid(uptime_default_inst)
    decoded = resolver.decoder.decode(uptime_default_id)
    assert decoded.priv == 1

    systime = ClientIo(
        io_id="systime1",
        io_type="systime",
        instance=0,
        dtype="uint64",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    systime_id = resolver.io_objid(systime)
    decoded = resolver.decoder.decode(systime_id)
    assert decoded.priv == 1
    assert decoded.flags == 0

    prog = ClientProgram(
        prog_id="stats1",
        prog_type="statsmin",
        instance=2,
        inputs=["dummy1"],
        outputs=["dummy1"],
        config={},
    )
    prog_id = resolver.program_objid(prog)
    assert prog_id is not None

    proto = ClientProto(
        proto_id="shell1",
        proto_type="shell",
        instance=1,
        config={},
        bindings=["dummy1"],
    )
    proto_id = resolver.protocol_objid(proto)
    assert proto_id is not None

    custom_prog = ClientProgram(
        prog_id="prog2",
        prog_type="custom",
        instance=1,
        inputs=[],
        outputs=[],
        config={},
    )
    assert resolver.program_objid(custom_prog) is None

    empty_prog = ClientProgram(
        prog_id="prog3",
        prog_type="",
        instance=1,
        inputs=[],
        outputs=[],
        config={},
    )
    assert resolver.program_objid(empty_prog) is None

    empty_proto = ClientProto(
        proto_id="proto2",
        proto_type="",
        instance=1,
        config={},
        bindings=[],
    )
    assert resolver.protocol_objid(empty_proto) is None

    unknown_proto = ClientProto(
        proto_id="proto3",
        proto_type="missing_proto_class",
        instance=1,
        config={},
        bindings=[],
    )
    assert resolver.protocol_objid(unknown_proto) is None


def test_object_id_resolver_io_branches():
    resolver = ObjectIdResolver()

    sensor_missing = ClientIo(
        io_id="sensor1",
        io_type="sensor",
        instance=1,
        dtype="uint16",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert resolver.io_objid(sensor_missing) is None

    sysinfo_missing = ClientIo(
        io_id="sys1",
        io_type="sysinfo",
        instance=1,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert resolver.io_objid(sysinfo_missing) is None

    uname_bad = ClientIo(
        io_id="uname1",
        io_type="uname",
        instance=1,
        dtype="string",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="domain",
    )
    assert resolver.io_objid(uname_bad) is None

    boardctl_bad = ClientIo(
        io_id="board1",
        io_type="boardctl",
        instance=1,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="unknown",
    )
    assert resolver.io_objid(boardctl_bad) is None

    gpo = ClientIo(
        io_id="gpo1",
        io_type="gpo",
        instance=2,
        dtype="uint16",
        tags=[],
        config={},
        timestamp=True,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    gpo_id = resolver.io_objid(gpo)
    decoded = resolver.decoder.decode(gpo_id)
    assert decoded.dtype_name == "uint32"

    gpi = ClientIo(
        io_id="gpi1",
        io_type="gpi",
        instance=1,
        dtype="uint16",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert resolver.io_objid(gpi) is not None

    uuid = ClientIo(
        io_id="uuid1",
        io_type="uuid",
        instance=1,
        dtype="uint64",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert resolver.io_objid(uuid) is not None

    systime = ClientIo(
        io_id="systime1",
        io_type="systime",
        instance=1,
        dtype="uint64",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    assert resolver.io_objid(systime) is not None

    sensor = ClientIo(
        io_id="sensor1",
        io_type="sensor",
        instance=1,
        dtype="uint16",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype="temp",
        variant=None,
    )
    assert resolver.io_objid(sensor) is not None

    sysinfo = ClientIo(
        io_id="sysload",
        io_type="sysinfo",
        instance=1,
        dtype="int32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="cpuload",
    )
    assert resolver.io_objid(sysinfo) is not None

    uname = ClientIo(
        io_id="host1",
        io_type="uname",
        instance=1,
        dtype="string",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="hostname",
    )
    uname_id = resolver.io_objid(uname)
    decoded = resolver.decoder.decode(uname_id)
    assert decoded.dtype_name == "char"

    board_reset_cause = ClientIo(
        io_id="resetcause",
        io_type="boardctl",
        instance=1,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="reset_cause",
    )
    assert resolver.io_objid(board_reset_cause) is not None

    board_poweroff = ClientIo(
        io_id="poweroff",
        io_type="boardctl",
        instance=1,
        dtype="bool",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant="poweroff",
    )
    assert resolver.io_objid(board_poweroff) is not None

    adc = ClientIo(
        io_id="adc1",
        io_type="adc_fetch",
        instance=1,
        dtype="uint16",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    adc_id = resolver.io_objid(adc)
    decoded = resolver.decoder.decode(adc_id)
    assert decoded.dtype_name == "int32"

    fileio = ClientIo(
        io_id="file1",
        io_type="fileio",
        instance=1,
        dtype="block",
        tags=[],
        config={"path": "/data/test.bin", "perm": 2},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    fileio_id = resolver.io_objid(fileio)
    expected = resolver.decoder.encode(
        1,
        _io_class_id(resolver, "file"),
        _dtype_id(resolver, "block"),
        0,
        1,
    )
    assert fileio_id == expected

    descselector = ClientIo(
        io_id="descselector0",
        io_type="descselector",
        instance=0,
        dtype="uint32",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    descselector_id = resolver.io_objid(descselector)
    expected = resolver.decoder.encode(
        1,
        _io_class_id(resolver, "desc_selector"),
        _dtype_id(resolver, "uint32"),
        0,
        0,
    )
    assert descselector_id == expected


def test_build_object_tables_with_methods():
    resolver = ObjectIdResolver()
    io = ClientIo(
        io_id="io1",
        io_type="dummy",
        instance=1,
        dtype="uint8",
        tags=["fast"],
        config={},
        timestamp=True,
        notify=False,
        rw=True,
        subtype=None,
        variant=None,
    )
    prog = ClientProgram(
        prog_id="stats1",
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

    headers, rows = build_io_table(
        desc,
        resolver=resolver,
        methods_lookup=lambda _io_id: "read",
    )
    assert "objid" in headers
    assert rows[0][1] == "io1"
    assert "read" in rows[0]

    prog_headers, prog_rows = build_program_table(desc, resolver=resolver)
    assert prog_headers[0] == "objid"
    assert "inputs=1" in prog_rows[0][-1]

    proto_headers, proto_rows = build_protocol_table(desc, resolver=resolver)
    assert proto_headers[0] == "objid"
    assert "bindings=1" in proto_rows[0][-1]

    nimble = ClientProto(
        proto_id="ble1",
        proto_type="nimble",
        instance=1,
        config={},
        bindings=[],
    )
    desc = ClientDescriptor(
        ios={"io1": io},
        programs=[],
        protocols=[nimble],
    )
    proto_headers, proto_rows = build_protocol_table(desc, resolver=resolver)
    assert proto_rows[0][0].startswith("0x")

    unknown = ClientIo(
        io_id="unknown1",
        io_type="unknown",
        instance=1,
        dtype="uint8",
        tags=[],
        config={},
        timestamp=False,
        notify=False,
        rw=False,
        subtype=None,
        variant=None,
    )
    desc = ClientDescriptor(
        ios={"unknown1": unknown},
        programs=[],
        protocols=[],
    )
    headers, rows = build_io_table(desc, resolver=resolver)
    assert rows[0][0] == "n/a"
