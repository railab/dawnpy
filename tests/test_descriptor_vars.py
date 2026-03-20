# tools/dawnpy/tests/test_descriptor_vars.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor variable resolution."""

import ast

import pytest

from dawnpy.descriptor.client import load_client_descriptor
from dawnpy.descriptor.support import vars as vars_mod


def test_vars_kconfig_expression(tmp_path):
    yaml_content = """
vars:
  can_offset:
    kconfig: CONFIG_SIM_CAN_NODEID
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${can_offset}
    objects:
    - type: read
      can_id_start: ${can_offset} + 0x20
      count: 1
      bindings: []
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text("CONFIG_SIM_CAN_NODEID=0x40\n")

    desc = load_client_descriptor(
        str(yaml_path), kconfig_path=str(kconfig_path)
    )
    proto = desc.get_protocol("can")
    assert proto is not None
    assert proto.config["node_id"] == 0x40
    assert proto.config["objects"][0]["can_id_start"] == 0x60


def test_vars_default_used_when_kconfig_missing(tmp_path):
    yaml_content = """
vars:
  can_offset:
    kconfig: CONFIG_SIM_CAN_NODEID
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${can_offset}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text("# empty\n")

    desc = load_client_descriptor(
        str(yaml_path), kconfig_path=str(kconfig_path)
    )
    proto = desc.get_protocol("can")
    assert proto is not None
    assert proto.config["node_id"] == "CONFIG_SIM_CAN_NODEID"


def test_vars_kconfig_override(tmp_path):
    yaml_content = """
vars:
  can_offset:
    kconfig: CONFIG_SIM_CAN_NODEID
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${can_offset}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    desc = load_client_descriptor(
        str(yaml_path),
        kconfig_overrides={"CONFIG_SIM_CAN_NODEID": 0x55},
    )
    proto = desc.get_protocol("can")
    assert proto is not None
    assert proto.config["node_id"] == 0x55


def test_vars_unknown_reference_raises(tmp_path):
    yaml_content = """
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${missing}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    with pytest.raises(ValueError, match="Unknown variable"):
        load_client_descriptor(str(yaml_path))


def test_vars_modbus_registers(tmp_path):
    yaml_content = """
vars:
  reg_base:
    kconfig: CONFIG_SIM_MODBUS_BASE
protocols:
- id: modbus_main
  type: modbus_rtu
  instance: 1
  config:
    registers:
    - type: holding
      notify: 1
      start: ${reg_base} + 4
      count: 2
      bindings: []
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text("CONFIG_SIM_MODBUS_BASE=0x200\n")

    desc = load_client_descriptor(
        str(yaml_path), kconfig_path=str(kconfig_path)
    )
    proto = desc.get_protocol("modbus_rtu")
    assert proto is not None
    registers = proto.config["registers"]
    assert registers[0]["start"] == 0x204


def test_generator_keeps_kconfig_symbol(tmp_path):
    yaml_content = """
vars:
  can_offset:
    kconfig: CONFIG_SIM_CAN_NODEID
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${can_offset}
    objects:
    - type: read
      can_id_start: ${can_offset} + 0x20
      count: 1
      bindings: []
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    from dawnpy.descriptor.generation.generator import DescriptorGenerator

    generator = DescriptorGenerator()
    output = generator.generate(str(yaml_path))
    assert "CONFIG_SIM_CAN_NODEID" in output
    assert "CONFIG_SIM_CAN_NODEID + 0x20" in output


def test_load_yaml_with_vars_non_dict(tmp_path):
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("- 1\n- 2\n")
    assert vars_mod.load_yaml_with_vars(str(yaml_path)) == {}


def test_no_vars_no_refs(tmp_path):
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("metadata:\n  version: '1.0'\n")
    spec = vars_mod.load_yaml_with_vars(str(yaml_path))
    assert spec["metadata"]["version"] == "1.0"


def test_select_kconfig_path_sources(tmp_path, monkeypatch):
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("vars: {}\n")

    direct = tmp_path / "direct.config"
    direct.write_text("CONFIG_FOO=1\n")
    assert vars_mod._select_kconfig_path(str(yaml_path), str(direct)) == str(
        direct
    )

    env_path = tmp_path / "env.config"
    env_path.write_text("CONFIG_FOO=1\n")
    monkeypatch.setenv("KCONFIG_CONFIG", str(env_path))
    assert vars_mod._select_kconfig_path(str(yaml_path), None) == str(env_path)
    monkeypatch.delenv("KCONFIG_CONFIG", raising=False)

    dot_config = tmp_path / ".config"
    dot_config.write_text("CONFIG_FOO=1\n")
    assert vars_mod._select_kconfig_path(str(yaml_path), None) == str(
        dot_config
    )
    dot_config.unlink()

    defconfig = tmp_path / "defconfig"
    defconfig.write_text("CONFIG_FOO=1\n")
    assert vars_mod._select_kconfig_path(str(yaml_path), None) == str(
        defconfig
    )
    defconfig.unlink()

    assert vars_mod._select_kconfig_path(str(yaml_path), None) is None


def test_kconfig_value_parsing_and_coercion(tmp_path):
    yaml_content = """
vars:
  flag:
    kconfig: CONFIG_FLAG
    type: bool
  name:
    kconfig: CONFIG_NAME
    type: string
  size:
    kconfig: CONFIG_SIZE
    type: int
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${size}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text(
        'CONFIG_FLAG=y\nCONFIG_NAME="dev"\nCONFIG_SIZE=0x20\n'
    )

    spec = vars_mod.load_yaml_with_vars(
        str(yaml_path), kconfig_path=str(kconfig_path)
    )
    assert spec["protocols"][0]["config"]["node_id"] == 0x20
    assert spec["vars"]["flag"]["kconfig"] == "CONFIG_FLAG"
    assert spec["vars"]["name"]["kconfig"] == "CONFIG_NAME"


def test_kconfig_value_parsing_helpers(tmp_path):
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text(
        "# comment\nCONFIG_NUM=123\nCONFIG_HEX=0x10\n"
        'CONFIG_BOOL=y\nCONFIG_STR="abc"\nCONFIG_RAW=foo\n'
        "FOO=1\nNOEQUAL\n"
    )
    values = vars_mod._load_kconfig_values(str(kconfig_path))
    assert values["CONFIG_NUM"] == 123
    assert values["CONFIG_HEX"] == 0x10
    assert values["CONFIG_BOOL"] is True
    assert values["CONFIG_STR"] == "abc"
    assert values["CONFIG_RAW"] == "foo"


def test_kconfig_value_parsing_helpers_with_include(tmp_path):
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text('#include "defconfig.dawn"\nCONFIG_NUM=123\n')
    include_path = tmp_path / "defconfig.dawn"
    include_path.write_text('CONFIG_STR="abc"\nCONFIG_BOOL=y\n')

    values = vars_mod._load_kconfig_values(str(kconfig_path))

    assert values["CONFIG_NUM"] == 123
    assert values["CONFIG_STR"] == "abc"
    assert values["CONFIG_BOOL"] is True


def test_kconfig_value_parsing_helpers_with_blank_line_and_cycle(tmp_path):
    kconfig_path = tmp_path / "defconfig"
    kconfig_path.write_text('#include "defconfig.dawn"\n\nCONFIG_NUM=123\n')
    include_path = tmp_path / "defconfig.dawn"
    include_path.write_text('#include "defconfig"\nCONFIG_BOOL=y\n')

    values = vars_mod._load_kconfig_values(str(kconfig_path))

    assert values["CONFIG_NUM"] == 123
    assert values["CONFIG_BOOL"] is True


def test_string_substitution_no_eval(tmp_path):
    yaml_content = """
vars:
  name:
    value: demo
protocols:
- id: serial
  type: serial
  instance: 1
  config:
    path: /dev/${name}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    spec = vars_mod.load_yaml_with_vars(str(yaml_path))
    assert spec["protocols"][0]["config"]["path"] == "/dev/demo"


def test_var_errors(tmp_path):
    yaml_content = """
vars:
  badtype:
    value: 1
    type: nonsense
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="Unsupported var type"):
        vars_mod.load_yaml_with_vars(str(yaml_path))

    yaml_content = """
vars:
  badint:
    value: nope
    type: int
"""
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="invalid literal"):
        vars_mod.load_yaml_with_vars(str(yaml_path))

    yaml_content = """
vars:
  badbool:
    value: maybe
    type: bool
"""
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="Cannot convert"):
        vars_mod.load_yaml_with_vars(str(yaml_path))

    yaml_content = """
vars:
  missing:
    kconfig: CONFIG_MISSING
"""
    yaml_path.write_text(yaml_content)
    spec = vars_mod.load_yaml_with_vars(str(yaml_path))
    assert spec["vars"]["missing"]["kconfig"] == "CONFIG_MISSING"

    yaml_content = """
vars:
  bad_default:
    kconfig: CONFIG_BAD
    default: 1
"""
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="should not define default"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_vars_scalar_default_and_missing(tmp_path):
    yaml_content = """
vars:
  scalar: 5
  fallback:
    default: 7
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${scalar}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    spec = vars_mod.load_yaml_with_vars(str(yaml_path))
    assert spec["protocols"][0]["config"]["node_id"] == 5
    assert spec["vars"]["fallback"]["default"] == 7

    yaml_content = """
vars:
  missing: {}
"""
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="has no value or default"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_type_conversions(tmp_path):
    yaml_content = """
vars:
  int_from_bool:
    value: true
    type: int
  bool_from_int:
    value: 2
    type: bool
  bool_true:
    value: "yes"
    type: bool
  bool_false:
    value: "0"
    type: bool
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${int_from_bool}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    spec = vars_mod.load_yaml_with_vars(str(yaml_path))
    assert spec["protocols"][0]["config"]["node_id"] == 1

    with pytest.raises(ValueError, match="Cannot convert"):
        vars_mod._coerce_type([], "int")

    assert vars_mod._coerce_type(2, "bool") is True
    assert vars_mod._coerce_type("yes", "bool") is True
    assert vars_mod._coerce_type("0", "bool") is False


def test_unknown_variable_in_substitution(tmp_path):
    yaml_content = """
vars:
  known: 1
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${unknown}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)
    with pytest.raises(ValueError, match="Unknown variable"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_resolve_kconfig_symbol_direct(tmp_path):
    yaml_content = """
vars:
  node:
    kconfig: CONFIG_NODE_ID
protocols:
- id: can_main
  type: can
  instance: 1
  config:
    node_id: ${node}
"""
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(yaml_content)

    spec = vars_mod.load_yaml_with_vars(
        str(yaml_path), resolve_kconfig_values=False
    )
    assert spec["protocols"][0]["config"]["node_id"] == "CONFIG_NODE_ID"


def test_eval_ast_operators():
    assert vars_mod._eval_expression("1 + 2") == 3
    assert vars_mod._eval_expression("5 - 2") == 3
    assert vars_mod._eval_expression("3 * 2") == 6
    assert vars_mod._eval_expression("8 // 2") == 4
    assert vars_mod._eval_expression("7 % 4") == 3
    assert vars_mod._eval_expression("1 << 3") == 8
    assert vars_mod._eval_expression("8 >> 2") == 2
    assert vars_mod._eval_expression("1 | 2") == 3
    assert vars_mod._eval_expression("3 & 1") == 1
    assert vars_mod._eval_expression("3 ^ 1") == 2
    assert vars_mod._eval_expression("+4") == 4
    assert vars_mod._eval_expression("-4") == -4
    assert vars_mod._eval_expression("1 ** 2") is None
    assert vars_mod._eval_expression("1 + x") is None

    with pytest.raises(ValueError):
        vars_mod._eval_ast(ast.parse("1 ** 2", mode="eval"))
    with pytest.raises(ValueError):
        vars_mod._eval_ast(ast.parse("~1", mode="eval"))
