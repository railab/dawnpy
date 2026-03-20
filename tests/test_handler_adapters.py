# tools/dawnpy/tests/test_handler_adapters.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor handler adapter defaults."""

from types import ModuleType, SimpleNamespace

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.handlers._base import (
    IOHandlerAdapter,
    ProgHandlerAdapter,
    ProtoHandlerAdapter,
)


def _module(name: str, **values: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in values.items():
        setattr(module, key, value)
    return module


def test_io_handler_adapter_custom_and_default_paths() -> None:
    module = _module(
        "io_handler_test",
        yaml_type="dummy",
        cpp_class="CIODummy",
        no_fields=True,
        pass_through=False,
        dtype="uint16",
        variant_dtypes={"fast": "uint32"},
        config_fields=lambda: [],
        encode_binary=lambda ctx: None,
        object_class_name=lambda obj: obj.value,
        summary_class_name=lambda obj: obj.value,
        summary_dtype_name=lambda obj: "float",
        summary_instance=lambda obj: 7,
        summary_flags=lambda obj: 3,
    )
    adapter = IOHandlerAdapter(module)

    assert adapter.no_fields
    assert not adapter.pass_through
    assert adapter.object_class_name(SimpleNamespace(value=None)) is None
    assert adapter.object_class_name(SimpleNamespace(value=123)) == "123"
    assert adapter.summary_class_name(SimpleNamespace(value=None)) is None
    assert adapter.summary_class_name(SimpleNamespace(value="abc")) == "abc"
    assert adapter.summary_dtype_name(SimpleNamespace()) == "float"
    assert adapter.summary_instance(SimpleNamespace()) == 7
    assert adapter.summary_flags(SimpleNamespace()) == 3

    default_module = _module(
        "io_handler_default_test",
        yaml_type="dummy",
        cpp_class="CIODummy",
        no_fields=False,
        pass_through=False,
        dtype="uint16",
        variant_dtypes={"fast": "uint32"},
        config_fields=lambda: [],
        encode_binary=lambda ctx: None,
    )
    default_adapter = IOHandlerAdapter(default_module)

    assert (
        default_adapter.summary_dtype_name(
            SimpleNamespace(variant=None, dtype="bool")
        )
        == "uint16"
    )
    assert (
        default_adapter.summary_instance(
            SimpleNamespace(io_type="sysinfo", instance=5)
        )
        == 1
    )
    assert (
        default_adapter.summary_flags(
            SimpleNamespace(io_type="systime", instance=3, timestamp=False)
        )
        == 3
    )


def test_prog_handler_adapter_custom_and_default_paths() -> None:
    custom_module = _module(
        "prog_handler_custom_test",
        yaml_type="dummy",
        cpp_class="CProgDummy",
        config_fields=lambda: [],
        encode_binary=lambda items, obj, prog_cls, obj_ids, decoder: None,
        object_class_name=lambda obj: "custom",
        validate_object=lambda obj: ["err"],
    )
    custom_adapter = ProgHandlerAdapter(custom_module)

    assert custom_adapter.object_class_name(SimpleNamespace()) == "custom"
    assert custom_adapter.validate_object(SimpleNamespace()) == ["err"]

    default_module = _module(
        "prog_handler_default_test",
        yaml_type="dummy",
        cpp_class="__missing__",
        config_fields=lambda: [],
        encode_binary=lambda items, obj, prog_cls, obj_ids, decoder: None,
    )
    default_adapter = ProgHandlerAdapter(default_module)
    obj = SimpleNamespace(prog_type="dummy", inputs=[], outputs=[], config={})

    assert default_adapter.object_class_name(obj) == "dummy"
    assert (
        default_adapter.config_reference_cpp_line(
            obj,
            "field",
            SimpleNamespace(
                get_prog_type_fields=lambda prog_type: [
                    ConfigField(name="field", cpp_helper="CProg::cfgIdField")
                ]
            ),
        )
        == "CProg::cfgIdField(),"
    )
    assert (
        default_adapter.config_reference_cpp_line(
            obj,
            "missing",
            SimpleNamespace(get_prog_type_fields=lambda prog_type: []),
        )
        is None
    )
    assert (
        default_adapter.output_shape_owned_virt_targets(
            SimpleNamespace(config={"outputs": "bad"}, outputs=[])
        )
        == set()
    )
    assert not default_adapter.emit_iobind_cpp([], obj, 0, None, "CProg")

    no_shape_module = _module(
        "prog_handler_no_shape_test",
        yaml_type="dummy",
        cpp_class="CProgDummy",
        owns_output_shape=False,
        config_fields=lambda: [],
        encode_binary=lambda items, obj, prog_cls, obj_ids, decoder: None,
    )
    assert (
        ProgHandlerAdapter(no_shape_module).output_shape_owned_virt_targets(
            obj
        )
        == set()
    )


def test_proto_handler_adapter_custom_and_default_paths() -> None:
    custom_module = _module(
        "proto_handler_custom_test",
        yaml_type="dummy",
        cpp_class="CProtoDummy",
        uses_standard_bindings=True,
        config_fields=lambda: [],
        encode_binary=lambda ctx: None,
        object_class_name=lambda obj: "custom",
    )
    custom_adapter = ProtoHandlerAdapter(custom_module)

    assert custom_adapter.object_class_name(SimpleNamespace()) == "custom"

    default_module = _module(
        "proto_handler_default_test",
        yaml_type="dummy",
        cpp_class="__missing__",
        uses_standard_bindings=False,
        config_fields=lambda: [],
        encode_binary=lambda ctx: None,
    )
    default_adapter = ProtoHandlerAdapter(default_module)

    assert (
        default_adapter.object_class_name(SimpleNamespace(proto_type="dummy"))
        == "dummy"
    )
    assert default_adapter.allocation_rows(SimpleNamespace()) == [
        ["0", "n/a", "n/a", "n/a", "0", "unsupported protocol"]
    ]
