# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.descriptor.cmd_descriptor_context import *


def test_generate_command_success():
    """Test generate command with valid YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create descriptor.yaml
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios:\n"
            "  - id: dummy1\n"
            "    type: dummy\n"
            "    instance: 1\n"
            "    dtype: bool\n"
            "programs: []\n"
            "protocols: []\n"
        )

        # Output path
        output_path = tmpdir_path / "descriptor.cxx"

        result = runner.invoke(
            cmd_desc_gen,
            [str(yaml_path), "-o", str(output_path)],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Generated:" in result.output
        assert "CRC policy:" in result.output


def test_generate_command_default_output():
    """Test generate command with default output path."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create descriptor.yaml
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols: []\n"
        )

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])

        assert result.exit_code == 0
        # Should generate descriptor.cxx in same directory as YAML
        default_output = tmpdir_path / "descriptor.cxx"
        assert default_output.exists()
        assert "Generated:" in result.output
        assert "CRC policy:" in result.output
        assert "descriptor.cxx not found" not in result.output
        assert (
            "Descriptor generated, but validation failed." not in result.output
        )


def test_generate_command_keeps_crc_placeholder():
    """Generate keeps C++ checksum placeholder (firmware-filled policy)."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text(
            "metadata:\n  version: '1.0'\n"
            "ios: []\n"
            "programs: []\n"
            "protocols: []\n"
        )

        output_path = tmpdir_path / "descriptor.cxx"
        result = runner.invoke(
            cmd_desc_gen,
            [str(yaml_path), "-o", str(output_path)],
        )
        assert result.exit_code == 0
        text = output_path.read_text(encoding="utf-8")
        assert "0xdeadbeef" in text.lower()


def test_generate_command_invalid_yaml():
    """Test generate command with invalid YAML."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create invalid YAML
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("invalid: [yaml without proper structure")

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])

        # Should show error message (exit code may be 0 even on error)
        assert "Error" in result.output or "error" in result.output


def test_generate_command_debug_mode():
    """Test generate command with --debug flag raises exceptions."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create invalid YAML that will cause an error
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("invalid: [yaml")

        result = runner.invoke(cmd_desc_gen, ["--debug", str(yaml_path)])

        # In debug mode, exceptions should be raised (non-zero exit code)
        assert result.exit_code != 0


def test_generate_command_reports_validation_failure_with_defconfig(
    monkeypatch,
):
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_path = tmpdir_path / "descriptor.yaml"
        yaml_path.write_text("ios: []\nprograms: []\nprotocols: []\n")
        (tmpdir_path / "defconfig").write_text("CONFIG_TEST=y\n")

        monkeypatch.setattr(
            cmd_desc_gen_mod,
            "generate_descriptor",
            lambda yaml_path, output_path, kconfig_path=None: None,
        )
        monkeypatch.setattr(
            cmd_desc_gen_mod,
            "validate_config",
            lambda config_path, quiet, verbose: False,
        )

        result = runner.invoke(cmd_desc_gen, [str(yaml_path)])
        assert result.exit_code == 0
        assert "Descriptor generated, but validation failed." in result.output


def test_fill_crc32_footer_invalid_inputs():
    with pytest.raises(ValueError, match="too small"):
        fill_crc32_footer(b"\x00\x01\x02")

    bad_footer = struct.pack("<II", 0x0D0A0302, 1) + struct.pack(
        "<II", 0x11111111, 0x00000000
    )
    with pytest.raises(ValueError, match="footer marker mismatch"):
        fill_crc32_footer(bad_footer)


def test_fill_crc32_footer_nuttx_crc_property():
    base = struct.pack("<II", 0x0D0A0302, 1) + struct.pack(
        "<II", 0x02030A0D, 0
    )
    out = fill_crc32_footer(base)
    assert nuttx_crc32(out) == 0
