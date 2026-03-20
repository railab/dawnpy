#!/usr/bin/env python3
# tools/dawnpy/tests/test_type_registration.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Unit tests for the dawnpy descriptor TypeRegistration extension API.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from dawnpy.descriptor.definitions.registry import (
    ConfigField,
    IOTypeInfo,
    ProgTypeInfo,
    ProtoTypeInfo,
    TypeRegistration,
    _apply_registration,
    load_registrations_from_path,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")


@pytest.fixture
def mock_builtin_registry(monkeypatch):
    """Stub the lazy built-in registry with fixed unit-test entries."""
    import dawnpy.descriptor.definitions.registry as registry_mod

    def _fake_ensure() -> None:
        registry_mod._DTYPE_MAP_DATA.clear()
        registry_mod._DTYPE_MAP_DATA.update(
            {"uint32": "SObjectId::DTYPE_UINT32"}
        )
        registry_mod._DTYPE_INITVAL_PARAM_MAP_DATA.clear()
        registry_mod._DTYPE_INITVAL_PARAM_MAP_DATA.update({"uint32": 8})
        registry_mod._IO_TYPES_DATA.clear()
        registry_mod._IO_TYPES_DATA.update(
            {
                "dummy": IOTypeInfo(
                    cpp_class="CIODummy",
                    header="dawn/io/dummy.hxx",
                    helper_func="{cpp_class}::objectId",
                    params=["dtype", "instance"],
                )
            }
        )
        registry_mod._PROG_TYPES_DATA.clear()
        registry_mod._PROG_TYPES_DATA.update(
            {
                "sampling": ProgTypeInfo(
                    cpp_class="CProgSampling",
                    header="dawn/prog/sampling.hxx",
                )
            }
        )
        registry_mod._PROTO_TYPES_DATA.clear()
        registry_mod._PROTO_TYPES_DATA.update(
            {
                "shell": ProtoTypeInfo(
                    cpp_class="CProtoShellPretty",
                    header="dawn/proto/shell_pretty.hxx",
                )
            }
        )

    monkeypatch.setattr(registry_mod, "_ensure_registry_loaded", _fake_ensure)


class TestTypeRegistration:
    """Tests for the TypeRegistration dataclass and merge semantics."""

    def test_apply_adds_new_types(self):
        """Custom yaml_types are added to each kind's dict."""
        io: dict = {}
        prog: dict = {}
        proto: dict = {}

        reg = TypeRegistration(
            name="test_pkg",
            io_types={
                "my_io": IOTypeInfo(
                    cpp_class="CIOMyDummy",
                    header="my_io_dummy.hxx",
                    helper_func="{cpp_class}::objectId",
                    params=["instance"],
                ),
            },
            prog_types={
                "my_prog": ProgTypeInfo(
                    cpp_class="CProgMyDummy",
                    header="my_prog_dummy.hxx",
                ),
            },
            proto_types={
                "my_proto": ProtoTypeInfo(
                    cpp_class="CProtoMyDummy",
                    header="my_proto_dummy.hxx",
                ),
            },
        )

        _apply_registration(reg, io, prog, proto)

        assert "my_io" in io
        assert io["my_io"].cpp_class == "CIOMyDummy"
        assert "my_prog" in prog
        assert prog["my_prog"].cpp_class == "CProgMyDummy"
        assert "my_proto" in proto
        assert proto["my_proto"].cpp_class == "CProtoMyDummy"

    def test_apply_overrides_existing_types_with_warning(self, caplog):
        """Re-registering a yaml_type overrides and logs a warning."""
        io = {
            "dummy": IOTypeInfo(
                cpp_class="CIODummy",
                header="dawn/io/dummy.hxx",
                helper_func="{cpp_class}::objectId",
                params=["dtype", "ts", "instance"],
            ),
        }

        reg = TypeRegistration(
            name="override_pkg",
            io_types={
                "dummy": IOTypeInfo(
                    cpp_class="CIOMyDummy",
                    header="my_io_dummy.hxx",
                    helper_func="{cpp_class}::objectId",
                    params=["instance"],
                ),
            },
        )

        with caplog.at_level(logging.WARNING):
            _apply_registration(reg, io, {}, {})

        assert io["dummy"].cpp_class == "CIOMyDummy"
        assert any(
            "override_pkg" in record.getMessage() for record in caplog.records
        )

    def test_apply_does_not_touch_unrelated_kinds(self):
        """An io-only registration leaves prog/proto dicts untouched."""
        io: dict = {}
        prog = {"existing": ProgTypeInfo(cpp_class="CProgX", header="x.hxx")}
        proto: dict = {}

        reg = TypeRegistration(
            name="io_only",
            io_types={
                "my_io": IOTypeInfo(
                    cpp_class="CIOMyDummy",
                    header="my_io_dummy.hxx",
                    helper_func="{cpp_class}::objectId",
                    params=["instance"],
                ),
            },
        )

        _apply_registration(reg, io, prog, proto)

        assert "my_io" in io
        assert list(prog.keys()) == ["existing"]
        assert prog["existing"].cpp_class == "CProgX"
        assert prog["existing"].header == "x.hxx"
        assert proto == {}


class TestBuiltInRegistryStillWorks:
    """Built-in types must resolve after the extension API is in place."""

    def test_builtin_io_dummy_present(self, mock_builtin_registry):
        from dawnpy.descriptor.definitions.registry import IO_TYPES

        assert "dummy" in IO_TYPES
        assert IO_TYPES["dummy"].cpp_class == "CIODummy"

    def test_builtin_prog_sampling_present(self, mock_builtin_registry):
        from dawnpy.descriptor.definitions.registry import PROG_TYPES

        assert "sampling" in PROG_TYPES

    def test_builtin_proto_shell_present(self, mock_builtin_registry):
        from dawnpy.descriptor.definitions.registry import PROTO_TYPES

        # Built-in shell-pretty proto is exposed under a yaml-friendly name.
        assert any("shell" in t for t in PROTO_TYPES)


class TestTypeRegistrationDataclass:
    """Smoke tests for the dataclass surface itself."""

    def test_default_dicts_are_empty(self):
        reg = TypeRegistration(name="empty")
        assert reg.io_types == {}
        assert reg.prog_types == {}
        assert reg.proto_types == {}

    def test_frozen_cannot_mutate(self):
        reg = TypeRegistration(name="frozen")
        with pytest.raises(dataclasses.FrozenInstanceError):
            reg.name = "renamed"  # type: ignore[misc]


# Source for a tiny TypeRegistration module used by the path-loading tests.

_REG_SRC = """
from dawnpy.descriptor.definitions.registry import (
    IOTypeInfo, ProgTypeInfo, ProtoTypeInfo, TypeRegistration,
)

registration = TypeRegistration(
    name="path_loaded",
    io_types={
        "my_io": IOTypeInfo(
            cpp_class="CIOMyDummy",
            header="my_io_dummy.hxx",
            helper_func="{cpp_class}::objectId",
            params=["instance"],
        ),
    },
)
"""


_REG_LIST_SRC = """
from dawnpy.descriptor.definitions.registry import (
    IOTypeInfo, ProgTypeInfo, TypeRegistration,
)

registrations = [
    TypeRegistration(
        name="path_loaded_a",
        io_types={"a_io": IOTypeInfo(
            cpp_class="CIOA", header="a.hxx",
            helper_func="{cpp_class}::objectId", params=["instance"],
        )},
    ),
    TypeRegistration(
        name="path_loaded_b",
        prog_types={
            "b_prog": ProgTypeInfo(cpp_class="CProgB", header="b.hxx"),
        },
    ),
]
"""


class TestLoadRegistrationsFromPath:
    """Tests for path-based plugin loading (no install required)."""

    def test_loads_single_registration_from_file(self, tmp_path: Path):
        path = tmp_path / "my_types.py"
        path.write_text(_REG_SRC)

        regs = load_registrations_from_path(path)

        assert len(regs) == 1
        assert regs[0].name == "path_loaded"
        assert "my_io" in regs[0].io_types

    def test_loads_iterable_registrations_from_file(self, tmp_path: Path):
        path = tmp_path / "my_types.py"
        path.write_text(_REG_LIST_SRC)

        regs = load_registrations_from_path(path)

        assert [r.name for r in regs] == ["path_loaded_a", "path_loaded_b"]

    def test_loads_from_package_directory(self, tmp_path: Path):
        pkg = tmp_path / "my_types_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(_REG_SRC)

        regs = load_registrations_from_path(pkg)

        assert len(regs) == 1
        assert regs[0].name == "path_loaded"

    def test_missing_path_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_registrations_from_path(tmp_path / "nope.py")

    def test_directory_without_init_raises(self, tmp_path: Path):
        empty = tmp_path / "empty_pkg"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            load_registrations_from_path(empty)

    def test_module_without_attribute_raises(self, tmp_path: Path):
        path = tmp_path / "stubborn.py"
        path.write_text("# no registration here\n")
        with pytest.raises(AttributeError):
            load_registrations_from_path(path)

    def test_non_registration_value_raises(self, tmp_path: Path):
        path = tmp_path / "wrong_type.py"
        path.write_text("registration = 'not a TypeRegistration'\n")
        with pytest.raises(TypeError):
            load_registrations_from_path(path)


class TestConfigField:
    """ConfigField default values + dict-to-ConfigField coercion."""

    def test_minimal_field(self):
        cf = ConfigField(
            name="init_value",
            cpp_helper="CIOMyDummy::cfgIdInitval",
            value_type="int",
        )
        assert cf.name == "init_value"
        assert cf.cpp_helper == "CIOMyDummy::cfgIdInitval"
        assert cf.value_type == "int"
        assert cf.value_format == ""
        assert cf.enum_values == {}
        assert cf.params == []
        assert cf.nested is False

    def test_full_shape(self):
        cf = ConfigField(
            name="freq",
            cpp_helper="CIOMy::cfgIdFreq",
            value_type="uint32",
            value_format="hex",
            params=["dtype"],
            default_params=[1],
            string_fixed_bytes=12,
            string_array_size="bytes",
            enum_values={"low": "FREQ_LOW", "high": "FREQ_HIGH"},
        )
        assert cf.value_format == "hex"
        assert cf.enum_values == {"low": "FREQ_LOW", "high": "FREQ_HIGH"}
        assert cf.params == ["dtype"]
        assert cf.default_params == [1]
        assert cf.string_fixed_bytes == 12
        assert cf.string_array_size == "bytes"


class TestTypeInfoConfigFields:
    """config_fields kwarg accepts ConfigField entries."""

    def test_io_type_info_normalizes_configfield(self):
        info = IOTypeInfo(
            cpp_class="CIOMy",
            header="my.hxx",
            helper_func="{cpp_class}::objectId",
            params=["instance"],
            config_fields=[
                ConfigField(
                    name="init_value",
                    cpp_helper="CIOMy::cfgIdInitval",
                    value_type="uint32",
                )
            ],
        )
        assert len(info.config_fields) == 1
        assert info.config_fields[0].cpp_helper == "CIOMy::cfgIdInitval"

    def test_io_type_info_rejects_garbage_entries(self):
        with pytest.raises(TypeError):
            IOTypeInfo(
                cpp_class="X",
                header="x.hxx",
                helper_func="x",
                params=[],
                config_fields=[  # type: ignore[list-item]
                    "this is not a field",
                ],
            )

    def test_proto_type_info_uses_standard_bindings_default_true(self):
        info = ProtoTypeInfo(cpp_class="CProtoMy", header="my.hxx")
        assert info.uses_standard_bindings is True

    def test_proto_type_info_uses_standard_bindings_explicit_false(self):
        info = ProtoTypeInfo(
            cpp_class="CProtoMy",
            header="my.hxx",
            uses_standard_bindings=False,
        )
        assert info.uses_standard_bindings is False


class TestConfigLoaderMerge:
    """ConfigLoader.get_*_config_fields merges user-registered fields."""

    def test_io_user_fields_appended(self):
        from dawnpy.descriptor.definitions import registry as _types
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        # Register a one-off user IO type.
        old_io = dict(_types.IO_TYPES)
        try:
            _types.IO_TYPES["__test_io__"] = IOTypeInfo(
                cpp_class="CIOTest",
                header="t.hxx",
                helper_func="{cpp_class}::objectId",
                params=["instance"],
                config_fields=[
                    ConfigField(
                        name="my_field",
                        cpp_helper="CIOTest::cfgIdMine",
                        value_type="uint32",
                    )
                ],
            )

            fields = loader.get_io_config_fields("__test_io__")
            user_only = [f for f in fields if f.name == "my_field"]
            assert len(user_only) == 1
        finally:
            _types.IO_TYPES.clear()
            _types.IO_TYPES.update(old_io)

    def test_proto_user_schema_synthesized_when_no_builtin(self):
        from dawnpy.descriptor.definitions import registry as _types
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        old_proto = dict(_types.PROTO_TYPES)
        try:
            _types.PROTO_TYPES["__test_proto__"] = ProtoTypeInfo(
                cpp_class="CProtoTest",
                header="t.hxx",
                uses_standard_bindings=False,
                config_fields=[
                    ConfigField(
                        name="port",
                        cpp_helper="CProtoTest::cfgIdPort",
                        value_type="uint16",
                    )
                ],
            )
            schema = loader.get_proto_config_schema("__test_proto__")
            assert schema is not None
            assert schema.uses_standard_bindings is False
            assert schema.fields[0].name == "port"
        finally:
            _types.PROTO_TYPES.clear()
            _types.PROTO_TYPES.update(old_proto)

    def test_unknown_proto_returns_none(self):
        from dawnpy.descriptor.definitions.loader import ConfigLoader

        loader = ConfigLoader()
        assert loader.get_proto_config_schema("__never_registered__") is None


class TestDemoPluginFile:
    """The demo's dawnpy_types.py must load and apply cleanly."""

    def test_iter_registrations_collects_typeregistration_entries(
        self, monkeypatch
    ):
        from dawnpy.descriptor.definitions import registry as types_mod

        reg = TypeRegistration(name="ep-single")
        reg_iter = TypeRegistration(name="ep-iter")

        class _FakeEntry:
            def __init__(self, name: str, value):
                self.name = name
                self.value = "fake.module"
                self._value = value

            def load(self):
                return self._value

        fake_eps = [
            _FakeEntry("descriptor_types", reg),
            _FakeEntry("descriptor_types", [reg_iter, "not-a-registration"]),
            _FakeEntry("ignored", reg),
        ]

        monkeypatch.setattr(types_mod, "entry_points", lambda group: fake_eps)
        out = types_mod._iter_registrations()
        names = {r.name for r in out}
        assert {"ep-single", "ep-iter"}.issubset(names)

    def test_apply_registration_to_module_mutates_live_dicts(
        self, monkeypatch
    ):
        from dawnpy.descriptor.definitions import registry as types_mod

        slot_io = "__test_apply_io__"
        slot_prog = "__test_apply_prog__"
        monkeypatch.delitem(types_mod.IO_TYPES, slot_io, raising=False)
        monkeypatch.delitem(types_mod.PROG_TYPES, slot_prog, raising=False)

        reg = TypeRegistration(
            name="apply-live",
            io_types={
                slot_io: IOTypeInfo(
                    cpp_class="X",
                    header="x.hxx",
                    helper_func="x_helper",
                    params=[],
                )
            },
            prog_types={
                slot_prog: ProgTypeInfo(cpp_class="Y", header="y.hxx")
            },
        )
        types_mod.apply_registration_to_module(reg)
        try:
            assert slot_io in types_mod.IO_TYPES
            assert slot_prog in types_mod.PROG_TYPES
        finally:
            types_mod.IO_TYPES.pop(slot_io, None)
            types_mod.PROG_TYPES.pop(slot_prog, None)

    def test_registration_file_loads_all_type_kinds(self, tmp_path: Path):
        demo_file = tmp_path / "dawnpy_types.py"
        demo_file.write_text(
            """
from dawnpy.descriptor.definitions.registry import (
    IOTypeInfo,
    ProgTypeInfo,
    ProtoTypeInfo,
    TypeRegistration,
)

registration = TypeRegistration(
    name="dawn-oot-demo",
    io_types={
        "my_io_dummy": IOTypeInfo(
            cpp_class="CIOMyDummy",
            header="my_io_dummy.hxx",
            helper_func="{cpp_class}::objectId",
            params=["instance"],
        ),
    },
    prog_types={
        "my_prog_dummy": ProgTypeInfo(
            cpp_class="CProgMyDummy",
            header="my_prog_dummy.hxx",
        ),
    },
    proto_types={
        "my_proto_dummy": ProtoTypeInfo(
            cpp_class="CProtoMyDummy",
            header="my_proto_dummy.hxx",
        ),
    },
)
""",
            encoding="utf-8",
        )

        regs = load_registrations_from_path(demo_file)
        assert len(regs) == 1
        reg = regs[0]
        assert reg.name == "dawn-oot-demo"
        assert "my_io_dummy" in reg.io_types
        assert "my_prog_dummy" in reg.prog_types
        assert "my_proto_dummy" in reg.proto_types
