# tools/dawnpy/tests/test_descriptor_vars.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor variable resolution."""

import ast

import pytest

from dawnpy.descriptor.client import load_client_descriptor
from dawnpy.descriptor.support import vars as vars_mod

pytestmark = pytest.mark.usefixtures("source_free_headers")


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


def test_include_block_exports_only_declared_outputs(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "blinky_common.yaml").write_text("""
outputs:
  - id: led
    ref: led1
  - id: control
    ref: ctrl_blinky
ios:
  - id: led1
    type: leds
    dtype: uint32
    config:
      device: 0
  - id: ctrl_blinky
    type: control
    config:
      targets:
        - blinky_seq1
      allowed:
        - start
        - stop
programs:
  - id: blinky_seq1
    type: sequencer
    config:
      targets:
        - led1
      states:
        - value: 0
          dwell_us: 1000
        - value: 1
          dwell_us: 1000
""")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
includes:
  - id: blinky
    path: blocks/blinky_common.yaml
protocols:
  - id: shell1
    type: shell
    bindings:
      - "@blinky.led"
      - "@blinky.control"
""")

    spec = vars_mod.load_yaml_with_vars(str(yaml_path))

    assert [io["id"] for io in spec["ios"]] == ["led", "control"]
    assert spec["programs"][0]["id"] == "blinky__blinky_seq1"
    assert spec["programs"][0]["config"]["targets"] == ["led"]
    assert spec["protocols"][0]["bindings"] == ["led", "control"]


def test_include_block_inputs_bind_outer_objects(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "serial_proto.yaml").write_text("""
inputs:
  - led
  - control
protocols:
  - id: serial1
    type: serial
    bindings:
      - "@INPUTS.led"
      - "@INPUTS.control"
    config:
      path: /dev/ttyS0
      baudrate: 115200
""")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
ios:
  - id: led1
    type: leds
    dtype: uint32
    config:
      device: 0
  - id: ctrl_blinky
    type: control
    config:
      targets: []
      allowed: [start]
includes:
  - id: serial_proto
    path: blocks/serial_proto.yaml
    inputs:
      led: led1
      control: ctrl_blinky
""")

    spec = vars_mod.load_yaml_with_vars(str(yaml_path))

    assert spec["protocols"][0]["id"] == "serial_proto__serial1"
    assert spec["protocols"][0]["bindings"] == ["led1", "ctrl_blinky"]


def test_include_block_unknown_output_raises(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "block.yaml").write_text("""
outputs:
  - id: led
    ref: led1
ios:
  - id: led1
    type: dummy
    dtype: uint32
""")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
includes:
  - id: demo
    path: blocks/block.yaml
protocols:
  - id: shell1
    type: shell
    bindings:
      - "@demo.hidden"
""")

    with pytest.raises(ValueError, match="unknown include output reference"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_include_block_missing_input_raises(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "block.yaml").write_text("""
inputs:
  - led
protocols:
  - id: shell1
    type: shell
    bindings:
      - "@INPUTS.led"
""")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
includes:
  - id: demo
    path: blocks/block.yaml
""")

    with pytest.raises(ValueError, match="missing block inputs"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_include_block_cycle_raises(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "a.yaml").write_text("""
includes:
  - id: b
    path: b.yaml
""")
    (block_dir / "b.yaml").write_text("""
includes:
  - id: a
    path: a.yaml
""")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
includes:
  - id: a
    path: blocks/a.yaml
""")

    with pytest.raises(ValueError, match="Descriptor include cycle detected"):
        vars_mod.load_yaml_with_vars(str(yaml_path))


def test_include_helper_expansion_and_errors(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "common.yaml").write_text("""
outputs:
  exported: led1
ios:
  - id: led1
    type: dummy
    dtype: uint32
""")
    (block_dir / "nested.yaml").write_text("""
includes:
  - id: common
    path: common.yaml
outputs:
  - id: forwarded
    ref: "@common.exported"
""")

    direct = vars_mod._expand_yaml_includes(
        {"ios": []},
        tmp_path / "descriptor.yaml",
        kconfig_path=None,
        resolve_kconfig_values=True,
        kconfig_overrides=None,
        include_stack=(),
    )
    assert direct["ios"] == []

    direct_none = vars_mod._expand_single_descriptor_includes(
        {"includes": None},
        tmp_path / "descriptor.yaml",
        kconfig_path=None,
        resolve_kconfig_values=True,
        kconfig_overrides=None,
        include_stack=(),
    )
    assert direct_none["includes"] is None

    multi = vars_mod._expand_yaml_includes(
        {"descriptor0": {"ios": []}, "note": "keep-me"},
        tmp_path / "descriptor.yaml",
        kconfig_path=None,
        resolve_kconfig_values=True,
        kconfig_overrides=None,
        include_stack=(),
    )
    assert multi["note"] == "keep-me"
    assert multi["descriptor0"]["ios"] == []

    expanded = vars_mod._expand_single_descriptor_includes(
        {
            "includes": [{"id": "nested", "path": "blocks/nested.yaml"}],
            "outputs": [{"id": "top", "ref": "@nested.forwarded"}],
        },
        tmp_path / "descriptor.yaml",
        kconfig_path=None,
        resolve_kconfig_values=True,
        kconfig_overrides=None,
        include_stack=(),
    )
    assert expanded["outputs"][0]["ref"] == "forwarded"

    with pytest.raises(ValueError, match="includes must be a list"):
        vars_mod._expand_single_descriptor_includes(
            {"includes": {}},
            tmp_path / "descriptor.yaml",
            kconfig_path=None,
            resolve_kconfig_values=True,
            kconfig_overrides=None,
            include_stack=(),
        )

    with pytest.raises(ValueError, match="duplicate include id"):
        vars_mod._expand_single_descriptor_includes(
            {
                "includes": [
                    {"id": "dup", "path": "blocks/common.yaml"},
                    {"id": "dup", "path": "blocks/common.yaml"},
                ]
            },
            tmp_path / "descriptor.yaml",
            kconfig_path=None,
            resolve_kconfig_values=True,
            kconfig_overrides=None,
            include_stack=(),
        )

    with pytest.raises(ValueError, match="unknown include output reference"):
        vars_mod._expand_single_descriptor_includes(
            {
                "includes": [
                    {"id": "common", "path": "blocks/common.yaml"},
                    {
                        "id": "nested",
                        "path": "blocks/common.yaml",
                        "inputs": {"bad": "@common.missing"},
                    },
                ]
            },
            tmp_path / "descriptor.yaml",
            kconfig_path=None,
            resolve_kconfig_values=True,
            kconfig_overrides=None,
            include_stack=(),
        )


def test_include_helper_instantiation_edges(tmp_path):
    include_file = tmp_path / "block.yaml"
    include_file.write_text("outputs: []\n")

    with pytest.raises(ValueError, match="include id 'bad-id' is invalid"):
        vars_mod._instantiate_include_block(
            {"ios": [], "programs": [], "protocols": []},
            namespace="bad-id",
            provided_inputs={},
            include_file=include_file,
        )

    with pytest.raises(ValueError, match="unknown block inputs"):
        vars_mod._instantiate_include_block(
            {"inputs": [], "ios": [], "programs": [], "protocols": []},
            namespace="demo",
            provided_inputs={"extra": "io1"},
            include_file=include_file,
        )

    with pytest.raises(ValueError, match="unresolved block input reference"):
        vars_mod._instantiate_include_block(
            {
                "inputs": ["led"],
                "protocols": [
                    {
                        "id": "shell1",
                        "type": "shell",
                        "bindings": ["@INPUTS.missing"],
                    }
                ],
            },
            namespace="demo",
            provided_inputs={"led": "led1"},
            include_file=include_file,
        )

    with pytest.raises(ValueError, match="unknown include output reference"):
        vars_mod._instantiate_include_block(
            {
                "outputs": [{"id": "x", "ref": "@child.missing"}],
                "ios": [],
                "programs": [],
                "protocols": [],
            },
            namespace="demo",
            provided_inputs={},
            include_file=include_file,
        )

    with pytest.raises(ValueError, match="unknown include output reference"):
        vars_mod._instantiate_include_block(
            {
                "ios": [],
                "programs": [],
                "protocols": [
                    {
                        "id": "shell1",
                        "type": "shell",
                        "bindings": ["@child.missing"],
                    }
                ],
            },
            namespace="demo",
            provided_inputs={},
            include_file=include_file,
        )

    with pytest.raises(ValueError, match="exported more than once"):
        vars_mod._instantiate_include_block(
            {
                "outputs": [
                    {"id": "a", "ref": "shared"},
                    {"id": "b", "ref": "shared"},
                ],
                "ios": [{"id": "shared", "type": "dummy", "dtype": "uint32"}],
                "programs": [],
                "protocols": [],
            },
            namespace="demo",
            provided_inputs={},
            include_file=include_file,
        )


def test_blinky_style_include_stack_promotes_public_ids(tmp_path):
    block_dir = tmp_path / "blocks"
    block_dir.mkdir()
    (block_dir / "common.yaml").write_text("""
inputs:
  - led
outputs:
  - id: led1
    ref: "@INPUTS.led"
  - id: ctrl_blinky
    ref: ctrl_blinky
  - id: trig_blinky
    ref: trig_blinky
ios:
  - id: ctrl_blinky
    type: control
    config:
      targets:
        - blinky_seq1
      allowed:
        - start
  - id: trig_blinky
    type: trigger
    config:
      targets:
        - blinky_seq1
      allowed:
        - reset
programs:
  - id: blinky_seq1
    type: sequencer
    config:
      targets:
        - "@INPUTS.led"
      states:
        - value: 0
          dwell_us: 1
""")

    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("""
ios:
  - id: led1
    type: dummy
    dtype: uint32
includes:
  - id: blinky
    path: blocks/common.yaml
    inputs:
      led: led1
protocols:
  - id: shell1
    type: shell
    bindings:
      - "@blinky.led1"
      - "@blinky.ctrl_blinky"
      - "@blinky.trig_blinky"
""")

    spec = vars_mod.load_yaml_with_vars(str(yaml_path))

    assert any(
        entry.get("id") == "ctrl_blinky" for entry in spec.get("ios", [])
    )
    assert any(
        entry.get("id") == "trig_blinky" for entry in spec.get("ios", [])
    )
    assert any(
        entry.get("id") == "blinky__blinky_seq1"
        for entry in spec.get("programs", [])
    )
    assert spec["protocols"][0]["bindings"] == [
        "led1",
        "ctrl_blinky",
        "trig_blinky",
    ]


def test_include_helper_parsers_and_walkers(tmp_path):
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text("metadata: {}\n")

    with pytest.raises(ValueError, match="must be a mapping"):
        vars_mod._parse_include_entry([], yaml_path, 0)
    with pytest.raises(ValueError, match="missing id"):
        vars_mod._parse_include_entry({}, yaml_path, 0)
    with pytest.raises(ValueError, match="missing path"):
        vars_mod._parse_include_entry({"id": "x"}, yaml_path, 0)
    with pytest.raises(ValueError, match="must be a mapping"):
        vars_mod._parse_include_entry(
            {"id": "x", "path": "missing.yaml", "inputs": []},
            yaml_path,
            0,
        )
    existing = tmp_path / "existing.yaml"
    existing.write_text("metadata: {}\n")
    include_id, include_file, include_inputs = vars_mod._parse_include_entry(
        {"id": "x", "path": "existing.yaml", "inputs": None},
        yaml_path,
        0,
    )
    assert include_id == "x"
    assert include_file == existing.resolve()
    assert include_inputs == {}
    with pytest.raises(ValueError, match="not found"):
        vars_mod._parse_include_entry(
            {"id": "x", "path": "missing.yaml"}, yaml_path, 0
        )

    block = tmp_path / "block.yaml"
    block.write_text("metadata: {}\n")
    assert vars_mod._parse_block_inputs(None, block) == []
    assert vars_mod._parse_block_inputs(["a", {"id": "b"}], block) == [
        "a",
        "b",
    ]
    with pytest.raises(ValueError, match="inputs must be a list"):
        vars_mod._parse_block_inputs({}, block)
    with pytest.raises(ValueError, match="must be a string or mapping"):
        vars_mod._parse_block_inputs([1], block)
    with pytest.raises(ValueError, match="is missing id"):
        vars_mod._parse_block_inputs([{}], block)

    assert vars_mod._parse_block_outputs(None, block) == {}
    assert vars_mod._parse_block_outputs({"x": "io1"}, block) == {"x": "io1"}
    assert vars_mod._parse_block_outputs(
        [{"id": "x", "ref": "io1"}], block
    ) == {"x": "io1"}
    with pytest.raises(ValueError, match="outputs must be a list or mapping"):
        vars_mod._parse_block_outputs(1, block)
    with pytest.raises(ValueError, match="must be a mapping"):
        vars_mod._parse_block_outputs([1], block)
    with pytest.raises(ValueError, match="is missing id"):
        vars_mod._parse_block_outputs([{"ref": "io1"}], block)
    with pytest.raises(ValueError, match="is missing ref"):
        vars_mod._parse_block_outputs([{"id": "x"}], block)
    with pytest.raises(ValueError, match="duplicates id 'x'"):
        vars_mod._parse_block_outputs(
            [{"id": "x", "ref": "io1"}, {"id": "x", "ref": "io2"}],
            block,
        )

    assert vars_mod._normalize_interface_ref("io1", block) == "io1"
    with pytest.raises(ValueError, match="interface reference is invalid"):
        vars_mod._normalize_interface_ref({}, block)

    assert vars_mod._list_section(None, "ios") == []
    with pytest.raises(ValueError, match="must be a list"):
        vars_mod._list_section({}, "ios")

    assert vars_mod._substitute_exact_strings({"x": ["a"]}, {"a": "b"}) == {
        "x": ["b"]
    }
    assert vars_mod._substitute_exact_strings("a", {"a": "b"}) == "b"
    assert vars_mod._substitute_exact_strings(1, {"a": "b"}) == 1

    assert (
        vars_mod._find_first_input_token({"x": ["@INPUTS.foo"]})
        == "@INPUTS.foo"
    )
    assert (
        vars_mod._find_first_named_output_token(["@demo.out"]) == "@demo.out"
    )
    assert vars_mod._find_first_named_output_token(["@INPUTS.foo"]) is None

    assert vars_mod._collect_object_ids(
        {
            "ios": [{"id": "io1"}, {}],
            "programs": [{"id": "prog1"}],
            "protocols": [],
        }
    ) == ["io1", "prog1"]
    with pytest.raises(ValueError, match="duplicate object id"):
        vars_mod._ensure_unique_object_ids(
            {"ios": [{"id": "io1"}, {"id": "io1"}]},
            yaml_path,
        )
