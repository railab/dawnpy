# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_inlined_serializer_registries_bind_yaml_to_cpp_class(monkeypatch):
    # Every IO yaml-token lives in its own handler under handlers/io_*.py;
    # IO_HANDLER_REGISTRY is the single source of truth.
    from dawnpy.descriptor.handlers import IO_HANDLER_REGISTRY

    assert IO_HANDLER_REGISTRY["sensor"].cpp_class == "CIOSensor"
    assert IO_HANDLER_REGISTRY["sensor"].no_fields is True
    assert IO_HANDLER_REGISTRY["descriptor"].pass_through is True
    assert IO_HANDLER_REGISTRY["descriptor"].dtype == "block"
    assert IO_HANDLER_REGISTRY["sysinfo"].variant_dtypes["uptime"] == "uint64"
    assert IO_HANDLER_REGISTRY["dummy"].cpp_class == "CIODummy"
    assert IO_HANDLER_REGISTRY["control"].cpp_class == "CIOControl"
    assert IO_HANDLER_REGISTRY["fileio"].cpp_class == "CIOFile"
    assert IO_HANDLER_REGISTRY["pwm"].cpp_class == "CIOPwm"
    assert IO_HANDLER_REGISTRY["pulsecount"].cpp_class == "CIOPulseCount"
    assert IO_HANDLER_REGISTRY["leds"].cpp_class == "CIOLeds"
    assert IO_HANDLER_REGISTRY["rgb_led"].cpp_class == "CIORgbLed"

    # Every PROG yaml-token lives in its own handler under handlers/prog_*.py.
    import dawnpy.headerdefs as headerdefs_mod
    from dawnpy.descriptor.handlers import PROG_HANDLER_REGISTRY

    monkeypatch.setattr(
        headerdefs_mod,
        "load_header_type_defs",
        lambda: {
            "prog_types": [
                {"yaml_type": name} for name in PROG_HANDLER_REGISTRY
            ]
        },
    )
    prog_yaml_types = {
        item["yaml_type"]
        for item in headerdefs_mod.load_header_type_defs()["prog_types"]
    }
    assert prog_yaml_types == set(PROG_HANDLER_REGISTRY)

    assert PROG_HANDLER_REGISTRY["stats"].cpp_class == "CProgStatsAvg"
    assert PROG_HANDLER_REGISTRY["sampling"].cpp_class == "CProgSampling"
    assert [
        f.name for f in PROG_HANDLER_REGISTRY["movingavg"].config_fields()
    ] == [
        "iobind",
        "window",
    ]

    # Every PROTO type now lives in a per-type handler under handlers/.
    from dawnpy.descriptor.handlers import PROTO_HANDLER_REGISTRY

    assert PROTO_HANDLER_REGISTRY["serial"].cpp_class == "CProtoSerial"
    assert PROTO_HANDLER_REGISTRY["nimble"].cpp_class == "CProtoNimblePrph"
    assert PROTO_HANDLER_REGISTRY["can"].cpp_class == "CProtoCan"
    assert PROTO_HANDLER_REGISTRY["serial"].dtype_names()["string"] == "char"
    assert (
        PROTO_HANDLER_REGISTRY["nxscope_serial"].fixed_string_bytes()[
            "nxscope_name"
        ]
        == 12
    )


def test_auto_handler_registry_error_branches(monkeypatch):
    """Cover handler auto-discovery validation errors."""
    import dawnpy.descriptor.handlers as handlers_mod

    missing = ModuleType("missing")
    monkeypatch.setattr(
        handlers_mod, "_iter_handler_modules", lambda family: [missing]
    )
    with pytest.raises(RuntimeError, match="missing required io handler"):
        handlers_mod._load_io_registry()

    invalid = ModuleType("invalid")
    for attr in handlers_mod._FAMILY_REQUIRED_ATTRS["prog"]:
        setattr(invalid, attr, object())
    invalid.yaml_type = ""
    monkeypatch.setattr(
        handlers_mod, "_iter_handler_modules", lambda family: [invalid]
    )
    with pytest.raises(RuntimeError, match="invalid prog handler yaml_type"):
        handlers_mod._load_prog_registry()

    for family, loader, label in (
        ("io", handlers_mod._load_io_registry, "IO"),
        ("prog", handlers_mod._load_prog_registry, "PROG"),
        ("proto", handlers_mod._load_proto_registry, "PROTO"),
    ):
        first = ModuleType(f"{family}_first")
        second = ModuleType(f"{family}_second")
        for module in (first, second):
            for attr in handlers_mod._FAMILY_REQUIRED_ATTRS[family]:
                setattr(module, attr, object())
            module.yaml_type = "dup"
        monkeypatch.setattr(
            handlers_mod,
            "_iter_handler_modules",
            lambda requested_family, a=first, b=second: [a, b],
        )
        with pytest.raises(RuntimeError, match=f"Duplicate {label} handler"):
            loader()
