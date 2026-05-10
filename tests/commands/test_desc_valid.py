# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_validate_command_success():
    """Test validate command with valid configuration."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        # Create defconfig
        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "[OK] Validation passed!" in result.output


def test_validate_command_missing_descriptor():
    """Test validate command with missing descriptor.cxx."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create defconfig but not descriptor.cxx
        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert "descriptor.cxx not found" in result.output


def test_validate_command_missing_defconfig():
    """Test validate command with missing defconfig."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx but not defconfig
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert "defconfig not found" in result.output


def test_validate_command_quiet():
    """Test validate command with --quiet flag."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create valid configuration
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_IO_DUMMY=y\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path), "--quiet"])

        assert result.exit_code == 0
        # Should have minimal output in quiet mode
        assert (
            "Validation passed" not in result.output
            or result.output.strip() == ""
        )


def test_validate_command_invalid_config():
    """Test validate command with invalid configuration."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create descriptor.cxx with IO that needs config
        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        # Create defconfig without the required config
        defconfig = config_path / "defconfig"
        defconfig.write_text("# CONFIG_DAWN_IO_DUMMY is not set\n")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        # Should indicate validation failed
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_fails_for_disabled_dtype_in_yaml():
    """Test validate command fails when descriptor.yaml uses disabled dtype."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor = config_path / "descriptor.cxx"
        descriptor.write_text('#include "dawn/io/dummy.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text(
            "CONFIG_DAWN_IO_DUMMY=y\n" "# CONFIG_DAWN_DTYPE_FLOAT is not set\n"
        )

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "ios:\n"
            "  - id: io1\n"
            "    type: dummy\n"
            "    instance: 0\n"
            "    dtype: float\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Validation passed" not in result.output
        assert "CONFIG_DAWN_DTYPE_FLOAT" in result.output


def test_validate_command_detects_can_overlap_in_yaml(monkeypatch):
    """Validate should fail when descriptor.yaml has CAN ID block overlap."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "  - &io2\n"
            "    id: io2\n"
            "    type: dummy\n"
            "    instance: 2\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 0\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 256\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
            "            - *io2\n"
            "        - type: write\n"
            "          can_id_start: 257\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        fake_descriptor = SimpleNamespace(
            load_can_descriptor=lambda _: object(),
            iter_conflict_keys=lambda _: [
                (0x101, "read[0]"),
                (0x101, "write[1]"),
            ],
        )
        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: fake_descriptor,
        )
        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "CAN overlap conflicts:" in result.output
        assert "0x101" in result.output
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_invalid_descriptor_yaml_reports_error():
    """Validate should report YAML parsing/runtime descriptor load errors."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text("protocols: [bad yaml")

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Invalid descriptor.yaml" in result.output
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_can_mapping_failure_reports_error(monkeypatch):
    """Validate should report CAN mapping errors gracefully."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 0\n"
            "      objects: []\n"
        )

        def _raise_can_mapping(_):
            raise ValueError("broken can mapping")

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: SimpleNamespace(
                load_can_descriptor=_raise_can_mapping,
                iter_conflict_keys=lambda _: [],
            ),
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert (
            "CAN mapping validation failed: broken can mapping"
            in result.output
        )
        assert "[OK] Validation passed!" not in result.output


def test_validate_command_prints_can_allocation_table():
    """Validate should always print CAN allocation details when CAN exists."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: 256\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 16\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Protocol allocation summary:" in result.output
        assert "- can_main (can)" in result.output
        assert "block" in result.output
        assert "kind" in result.output
        assert "start" in result.output
        assert "end" in result.output
        assert "count" in result.output
        assert "details" in result.output
        assert "0x110" in result.output
        assert "ios=io1" in result.output


def test_validate_command_skips_can_allocation_with_kconfig():
    """Validate should skip CAN allocation when Kconfig expressions exist."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/can/can.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_CAN=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "vars:\n"
            "  can_id:\n"
            "    kconfig: CONFIG_SIM_CAN_NODEID\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: can_main\n"
            "    type: can\n"
            "    instance: 1\n"
            "    config:\n"
            "      node_id: ${can_id}\n"
            "      objects:\n"
            "        - type: read\n"
            "          can_id_start: 16\n"
            "          count: 1\n"
            "          bindings:\n"
            "            - *io1\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Variables:" in result.output
        assert "can_id: kconfig=CONFIG_SIM_CAN_NODEID" in result.output
        assert "can_main (can)" in result.output
        assert (
            "node=CONFIG_SIM_CAN_NODEID (assumed 0 for validation)"
            in result.output
        )
        assert "CAN runtime validation skipped" not in result.output


def test_validate_command_prints_serial_allocation_table():
    """Validate should print allocation summary for non-CAN protocols too."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        descriptor_cxx = config_path / "descriptor.cxx"
        descriptor_cxx.write_text('#include "dawn/proto/serial/simple.hxx"\n')

        defconfig = config_path / "defconfig"
        defconfig.write_text("CONFIG_DAWN_PROTO_SERIAL=y\n")

        yaml_path = config_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - &io1\n"
            "    id: io1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "protocols:\n"
            "  - id: serial_main\n"
            "    type: serial\n"
            "    instance: 1\n"
            "    bindings:\n"
            "      - *io1\n"
            "    config:\n"
            "      path: /dev/ttyS1\n"
            "      baudrate: 115200\n"
        )

        result = runner.invoke(cmd_desc_valid, [str(config_path)])

        assert result.exit_code == 0
        assert "Protocol allocation summary:" in result.output
        assert "- serial_main (serial)" in result.output
        assert "bind-index" in result.output
        assert "path=/dev/ttyS1" in result.output
        assert "baudrate=115200" in result.output
        assert "ios=io1" in result.output
