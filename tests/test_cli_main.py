#
# SPDX-License-Identifier: Apache-2.0
#

"""CLI entrypoint regressions."""

from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from dawnpy.cli.environment import Environment
from dawnpy.cli.main import cli_on_close, main
from dawnpy.descriptor.definitions.type_info import TypeRegistration


def test_top_level_help_does_not_touch_repo_registry(
    monkeypatch, tmp_path
) -> None:
    """``dawnpy --help`` must work before a Dawn repo is available."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAWN_ROOT", raising=False)
    monkeypatch.setattr(
        "dawnpy.descriptor.definitions.registry._ensure_registry_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("registry loaded")),
    )

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output


def test_init_help_does_not_touch_repo_registry(monkeypatch, tmp_path) -> None:
    """``dawnpy init --help`` must work before bootstrap."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAWN_ROOT", raising=False)
    monkeypatch.setattr(
        "dawnpy.descriptor.definitions.registry._ensure_registry_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("registry loaded")),
    )

    result = runner.invoke(main, ["init", "--help"])

    assert result.exit_code == 0
    assert "Bootstrap a Dawn workspace or inline install." in result.output


def test_main_applies_unique_types_from_paths(monkeypatch, tmp_path) -> None:
    """CLI callback de-duplicates explicit and implicit registration paths."""
    runner = CliRunner()
    reg_file = tmp_path / "types.py"
    reg_file.write_text("# stub\n", encoding="utf-8")
    seen: list[str] = []

    monkeypatch.setattr(
        "dawnpy.cli.main.load_dawnrc",
        lambda: SimpleNamespace(implicit_types_from=lambda: [reg_file]),
    )
    monkeypatch.setattr(
        "dawnpy.cli.main.load_registrations_from_path",
        lambda path: [TypeRegistration(name=Path(path).stem)],
    )
    monkeypatch.setattr(
        "dawnpy.cli.main.apply_registration_to_module",
        lambda reg: seen.append(reg.name),
    )

    result = runner.invoke(
        main,
        [
            "--types-from",
            str(reg_file),
            "init",
            str(tmp_path / "ws"),
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert seen == ["types"]


def test_cli_on_close_returns_true() -> None:
    """Close hook is a no-op success path."""
    assert cli_on_close.__wrapped__(Environment()) is True
