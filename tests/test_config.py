# tools/dawnpy/tests/test_config.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for `.dawnrc` discovery and path resolution."""

from pathlib import Path

from dawnpy.config import DawnRC, load_dawnrc, write_dawnrc


def test_dawnrc_resolves_relative_paths(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    project = workspace / "myproj"
    project.mkdir(parents=True)

    write_dawnrc(
        workspace / ".dawnrc",
        {
            "paths": {
                "dawn_root": "./dawn-src",
                "nuttx_dir": "./vendor/nuttx",
            },
            "project": {
                "types_from": "dawnpy_types.py",
            },
        },
    )

    rc = load_dawnrc(project)

    assert rc.root_dir == workspace
    assert rc.get_path("paths", "dawn_root") == workspace / "dawn-src"
    assert rc.get_path("paths", "nuttx_dir") == workspace / "vendor" / "nuttx"
    assert rc.implicit_types_from() == [workspace / "dawnpy_types.py"]


def test_dawnrc_uses_global_fallback(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)

    write_dawnrc(
        home / ".config" / "dawn" / "dawnrc",
        {"paths": {"dawn_root": "/opt/dawn"}},
    )

    rc = load_dawnrc(tmp_path / "outside")

    assert rc.get_path("paths", "dawn_root") == Path("/opt/dawn")


def test_dawnrc_get_returns_default_when_section_is_not_dict() -> None:
    rc = DawnRC(path=None, data={"paths": "scalar-not-dict"})
    assert rc.get("paths", "dawn_root", default="x") == "x"


def test_dawnrc_get_path_resolves_without_root_dir(tmp_path: Path) -> None:
    rc = DawnRC(path=None, data={"paths": {"dawn_root": "rel/path"}})
    assert rc.get_path("paths", "dawn_root") == Path("rel/path").resolve()


def test_dawnrc_resolve_path_prefers_cli_over_env(
    tmp_path: Path, monkeypatch
) -> None:
    rc = DawnRC(path=None, data={"paths": {"dawn_root": "rc-value"}})
    monkeypatch.setenv("DAWN_ROOT", str(tmp_path / "env-value"))
    assert (
        rc.resolve_path(
            cli_value="cli-value",
            env_var="DAWN_ROOT",
            section="paths",
            key="dawn_root",
        )
        == Path("cli-value").resolve()
    )


def test_dawnrc_resolve_path_uses_env_over_rc(
    tmp_path: Path, monkeypatch
) -> None:
    rc = DawnRC(path=None, data={"paths": {"dawn_root": "rc-value"}})
    monkeypatch.setenv("DAWN_ROOT", str(tmp_path / "env-value"))
    assert (
        rc.resolve_path(
            env_var="DAWN_ROOT",
            section="paths",
            key="dawn_root",
        )
        == (tmp_path / "env-value").resolve()
    )


def test_dawnrc_resolve_path_returns_none_without_default() -> None:
    rc = DawnRC(path=None, data={})
    assert (
        rc.resolve_path(section="paths", key="dawn_root", default=None) is None
    )


def test_dawnrc_implicit_types_from_skips_empty_entries(
    tmp_path: Path,
) -> None:
    rc = DawnRC(
        path=tmp_path / ".dawnrc",
        data={"project": {"types_from": ["", "x.py", None]}},
    )
    assert rc.implicit_types_from() == [(tmp_path / "x.py").resolve()]


def test_dawnrc_implicit_types_from_empty_returns_empty_list() -> None:
    rc = DawnRC(path=None, data={"project": {"types_from": ""}})
    assert rc.implicit_types_from() == []
