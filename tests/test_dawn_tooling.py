# tools/dawnpy/tests/test_dawn_tooling.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the Dawn CLI support modules."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from dawnpy.config import DawnRC
from dawnpy.dawn import output
from dawnpy.dawn.build_dir import (
    generate_build_dir_name,
    is_build_configured,
    sanitize_build_component,
)
from dawnpy.dawn.cmake import build_cmake, configure_cmake
from dawnpy.dawn.kconfig import build_kconfig_env, set_kconfig_value
from dawnpy.dawn.workflows import (
    BatchRequest,
    BuildRequest,
    KconfigSweepRequest,
    _maybe_configure,
    _merge_cmake_flags,
    _merge_env_vars,
    _parse_batch_line,
    _resolve_descriptor_yaml_from_config,
    _run_build_only,
    _run_configure_build,
    _validate_generated_config,
    parse_batch_config_file,
    parse_cmake_defines,
    parse_env_vars,
    run_batch_request,
    run_build_request,
    run_kconfig_request,
)


def _completed(
    stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"], returncode=0, stdout=stdout, stderr=stderr
    )


def _fake_project(project_root: Path) -> object:
    from dawnpy.dawn.project import Project

    return Project(
        project_root=project_root,
        dawn_root=project_root,
        nuttx_dir=project_root / "external" / "nuttx",
        nuttx_apps_dir=project_root / "external" / "apps",
        is_oot=False,
        dawnrc=DawnRC(path=None, data={}),
    )


def test_constants_and_output(capsys: pytest.CaptureFixture[str]) -> None:
    output.print_header("Title")
    output.print_success("ok")
    output.print_error("bad")
    output.print_warning("warn")
    output.print_info("info")
    output.print_verbose("detail", True)
    output.print_verbose("skip", False)

    captured = capsys.readouterr()
    assert "Title" in captured.out
    assert "ok" in captured.out
    assert "warn" in captured.out
    assert "info" in captured.out
    assert "detail" in captured.out
    assert "bad" in captured.err


def test_build_dir_helpers(tmp_path: Path) -> None:
    name = generate_build_dir_name("boards/sim/sim/sim/configs/tests")
    assert name == "build-sim-sim-tests"
    oot = generate_build_dir_name(
        "boards/sim/sim/sim/configs/tests",
        project_root=tmp_path / "oot",
        dawn_root=tmp_path / "dawn",
    )
    assert oot.startswith("build-sim-sim-tests-oot-")
    other = generate_build_dir_name("boards/arch/board/config")
    assert other == "build-arch-board-config"
    assert sanitize_build_component("CONFIG_SIM@NODE") == "config-sim-node"
    assert sanitize_build_component("alpha-beta.gamma") == "alpha-beta.gamma"

    assert is_build_configured(tmp_path) is False
    cache = tmp_path / "CMakeCache.txt"
    cache.write_text("ok", encoding="utf-8")
    assert is_build_configured(tmp_path) is True


def test_configure_cmake_missing_nuttx(tmp_path: Path) -> None:
    assert (
        configure_cmake(
            tmp_path / "build",
            "boards/sim/config",
            tmp_path,
        )
        is False
    )


def test_configure_cmake_success_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    nuttx_dir = project_root / "external" / "nuttx"
    nuttx_dir.mkdir(parents=True)

    config_path = project_root / "boards" / "sim" / "config"
    config_path.mkdir(parents=True)
    (config_path / "defconfig").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout="warning: ok")
    )
    assert (
        configure_cmake(
            project_root / "build",
            str(config_path.relative_to(project_root)),
            project_root,
            env_vars=None,
            cmake_flags=None,
            verbose=False,
        )
        is True
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _completed(stdout="warning: test", stderr="err"),
    )
    assert (
        configure_cmake(
            project_root / "build2",
            str(config_path.relative_to(project_root)),
            project_root,
            env_vars={"CC": "gcc"},
            cmake_flags=["-DTEST=1"],
            verbose=True,
        )
        is True
    )


def test_run_build_request_adds_explicit_oot_cmake_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    oot_root = tmp_path / "oot"
    (oot_root / "boards" / "sim" / "configs" / "demo").mkdir(parents=True)
    cmake_file = oot_root / "external" / "dawn_oot.cmake"
    cmake_file.parent.mkdir(parents=True)
    cmake_file.write_text("# oot\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_configure(
        build_dir,
        confpath,
        project_root,
        generator,
        env_vars,
        cmake_flags,
        verbose,
        dawn_root=None,
        boards_search_root=None,
        nuttx_dir=None,
    ):
        captured["env_vars"] = env_vars
        captured["cmake_flags"] = cmake_flags
        return True

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", fake_configure
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )

    request = BuildRequest(
        build_dir=str(tmp_path / "build"),
        confpath=str(oot_root / "boards" / "sim" / "configs" / "demo"),
        generator="Ninja",
        env_vars=(),
        cmake_defines=(),
        kconfig_overrides=(),
        jobs=None,
        dawn_root=None,
        nuttx_dir=None,
        nuttx_apps_dir=None,
        config_only=True,
        build_only=False,
        verbose=False,
    )

    run_build_request(request)

    assert captured["env_vars"]["DAWN_OOT_ROOT"] == str(oot_root)
    assert f"-DDAWN_OOT_CMAKE_FILE={cmake_file}" in captured["cmake_flags"]


def test_configure_cmake_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    nuttx_dir = project_root / "external" / "nuttx"
    nuttx_dir.mkdir(parents=True)

    def run_fail(*args, **kwargs):  # pragma: no cover
        err = subprocess.CalledProcessError(1, args[0])
        err.stdout = "error: failed"  # pragma: no cover
        err.stderr = "boom"  # pragma: no cover
        raise err  # pragma: no cover

    monkeypatch.setattr(subprocess, "run", run_fail)
    assert (
        configure_cmake(
            project_root / "build",
            "missing",
            project_root,
            verbose=True,
        )
        is False
    )


def test_build_cmake_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    build_dir = project_root / "build"
    build_dir.mkdir(parents=True)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _completed(stdout="warning: ok", stderr=""),
    )
    assert (
        build_cmake(build_dir, project_root, jobs=None, verbose=False) is True
    )

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout="ok", stderr="")
    )
    assert build_cmake(build_dir, project_root, jobs=2, verbose=True) is True

    def run_fail(*args, **kwargs):
        err = subprocess.CalledProcessError(1, args[0])
        err.stdout = "error: nope"
        err.stderr = "boom"
        raise err

    monkeypatch.setattr(subprocess, "run", run_fail)
    assert (
        build_cmake(build_dir, project_root, jobs=None, verbose=False) is False
    )

    missing = tmp_path / "missing"
    assert (
        build_cmake(missing, project_root, jobs=None, verbose=False) is False
    )


def test_kconfig_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    build_dir = project_root / "build"
    build_dir.mkdir(parents=True)

    apps_dir = project_root / "external" / "apps"
    nuttx_dir = project_root / "external" / "nuttx"
    boards_common = project_root / "boards" / "common"
    apps_dir.mkdir(parents=True)
    nuttx_dir.mkdir(parents=True)
    boards_common.mkdir(parents=True)

    project = _fake_project(project_root)
    env = build_kconfig_env(build_dir, project)
    assert env["APPSDIR"] == str(apps_dir)
    assert env["SRCTREE"] == str(nuttx_dir)

    assert set_kconfig_value(build_dir, project, "CONFIG_X", "1") is False

    config_path = build_dir / ".config"
    config_path.write_text("x", encoding="utf-8")

    def which_missing(name: str) -> str | None:
        return None if name == "setconfig" else "/bin/tool"

    monkeypatch.setattr("shutil.which", which_missing)
    assert set_kconfig_value(build_dir, project, "CONFIG_X", "1") is False

    def which_missing_old(name: str) -> str | None:
        if name == "setconfig":
            return "/bin/setconfig"
        if name == "olddefconfig":
            return None
        return "/bin/tool"

    monkeypatch.setattr("shutil.which", which_missing_old)
    assert set_kconfig_value(build_dir, project, "CONFIG_X", "1") is False
    assert which_missing_old("other") == "/bin/tool"

    def which_ok(name: str) -> str | None:
        return f"/bin/{name}"

    monkeypatch.setattr("shutil.which", which_ok)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout="ok")
    )
    assert (
        set_kconfig_value(build_dir, project, "CONFIG_X", "1", verbose=True)
        is True
    )

    call_count = {"count": 0}

    def run_olddef_fail(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return _completed()
        err = subprocess.CalledProcessError(1, args[0])
        err.stderr = "boom"
        raise err

    monkeypatch.setattr(subprocess, "run", run_olddef_fail)
    assert set_kconfig_value(build_dir, project, "CONFIG_X", "1") is False

    def run_fail(*args, **kwargs):
        err = subprocess.CalledProcessError(1, args[0])
        err.stderr = "boom"
        raise err

    monkeypatch.setattr(subprocess, "run", run_fail)
    assert set_kconfig_value(build_dir, project, "CONFIG_X", "1") is False


def test_workflow_parsers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[str] = []

    def warn(msg: str) -> None:
        warnings.append(msg)

    monkeypatch.setattr("dawnpy.dawn.workflows.print_warning", warn)

    env = parse_env_vars(("CC=gcc", "INVALID"))
    assert env["CC"] == "gcc"
    assert warnings
    assert parse_cmake_defines(("TEST=1",)) == ["-DTEST=1"]

    config_file = tmp_path / "configs.txt"
    config_file.write_text(
        "boards/sim/configs/tests -e CC=gcc -D TEST=1 -x\n",
        encoding="utf-8",
    )
    configs = parse_batch_config_file(str(config_file))
    assert configs[0].path == "boards/sim/configs/tests"

    bad_config = tmp_path / "bad.txt"
    bad_config.write_text('"unterminated\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_batch_config_file(str(bad_config))

    empty_config = tmp_path / "empty.txt"
    empty_config.write_text("\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_batch_config_file(str(empty_config))

    parsed = _parse_batch_line("boards/sim/configs/tests", 1)
    assert parsed is not None

    merged = _merge_env_vars({"CC": "gcc"}, ["CXX=g++", "BAD"])
    assert merged["CC"] == "gcc"
    assert merged["CXX"] == "g++"

    flags = _merge_cmake_flags(["-DTEST=1"], ["OTHER=1"])
    assert flags == ["-DTEST=1", "-DOTHER=1"]

    empty_parts = tmp_path / "empty_parts.txt"
    empty_parts.write_text("boards/sim/configs/tests\n", encoding="utf-8")
    monkeypatch.setattr("dawnpy.dawn.workflows.shlex.split", lambda line: [])
    with pytest.raises(SystemExit):
        parse_batch_config_file(str(empty_parts))

    def open_boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", open_boom)
    with pytest.raises(SystemExit):
        parse_batch_config_file(str(config_file))


def test_run_build_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run_build(
        build_dir: str,
        confpath: str | None,
        generator: str,
        env_vars: tuple[str, ...],
        cmake_defines: tuple[str, ...],
        kconfig_overrides: tuple[str, ...],
        jobs: int | None,
        *,
        config_only: bool,
        build_only: bool,
        verbose: bool,
    ) -> None:
        run_build_request(
            BuildRequest(
                build_dir=build_dir,
                confpath=confpath,
                generator=generator,
                env_vars=env_vars,
                cmake_defines=cmake_defines,
                kconfig_overrides=kconfig_overrides,
                jobs=jobs,
                dawn_root=None,
                nuttx_dir=None,
                nuttx_apps_dir=None,
                config_only=config_only,
                build_only=build_only,
                verbose=verbose,
            )
        )

    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text("ok", encoding="utf-8")
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", lambda *a, **k: True
    )

    run_build(
        str(build_dir),
        None,
        "Ninja",
        (),
        (),
        (),
        None,
        config_only=False,
        build_only=False,
        verbose=False,
    )

    with pytest.raises(SystemExit):
        run_build(
            str(build_dir),
            None,
            "Ninja",
            (),
            (),
            (),
            None,
            config_only=True,
            build_only=True,
            verbose=False,
        )

    run_build(
        str(build_dir),
        "boards/sim/configs/tests",
        "Ninja",
        ("CC=gcc",),
        ("TEST=1",),
        (),
        None,
        config_only=True,
        build_only=False,
        verbose=False,
    )

    run_build(
        str(build_dir),
        "boards/sim/configs/tests",
        "Ninja",
        (),
        (),
        (),
        None,
        config_only=False,
        build_only=True,
        verbose=False,
    )

    with pytest.raises(SystemExit):
        run_build(
            str(build_dir),
            None,
            "Ninja",
            (),
            (),
            (),
            None,
            config_only=True,
            build_only=False,
            verbose=False,
        )

    missing = tmp_path / "missing"
    with pytest.raises(SystemExit):
        run_build(
            str(missing),
            None,
            "Ninja",
            (),
            (),
            (),
            None,
            config_only=False,
            build_only=False,
            verbose=False,
        )

    unconfigured = tmp_path / "unconfigured"
    unconfigured.mkdir()
    with pytest.raises(SystemExit):
        run_build(
            str(unconfigured),
            None,
            "Ninja",
            (),
            (),
            (),
            None,
            config_only=False,
            build_only=False,
            verbose=False,
        )

    missing_cache = tmp_path / "missing-cache"
    missing_cache.mkdir()
    with pytest.raises(SystemExit):
        _run_build_only(
            missing_cache, None, _fake_project(tmp_path), None, False
        )

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: False
    )
    with pytest.raises(SystemExit):
        _run_build_only(build_dir, None, _fake_project(tmp_path), None, False)
    fake_project = _fake_project(tmp_path)

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", lambda *a, **k: False
    )
    with pytest.raises(SystemExit):
        _run_configure_build(
            build_dir,
            "boards/sim/configs/tests",
            fake_project,
            "Ninja",
            {},
            [],
            (),
            None,
            False,
            False,
        )

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: False
    )
    with pytest.raises(SystemExit):
        _run_configure_build(
            build_dir,
            "boards/sim/configs/tests",
            fake_project,
            "Ninja",
            {},
            [],
            (),
            None,
            False,
            False,
        )

    assert _maybe_configure(
        build_dir, None, fake_project, "Ninja", {}, [], False
    )


def test_run_build_request_resolves_relative_build_dir_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dawn_root = tmp_path / "dawn-src"
    (dawn_root / "boards" / "sim" / "sim" / "sim" / "configs" / "demo").mkdir(
        parents=True
    )
    (dawn_root / "dawn").mkdir()
    (dawn_root / "Documentation").mkdir()
    (dawn_root / "external" / "nuttx").mkdir(parents=True)
    invocation_dir = tmp_path / "myproj"
    invocation_dir.mkdir()

    captured: dict[str, Path] = {}

    def fake_configure(build_dir, *args, **kwargs):
        captured["build_dir"] = build_dir
        return True

    monkeypatch.chdir(invocation_dir)
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", fake_configure
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )

    run_build_request(
        BuildRequest(
            build_dir="build",
            confpath=str(
                dawn_root
                / "boards"
                / "sim"
                / "sim"
                / "sim"
                / "configs"
                / "demo"
            ),
            generator="Ninja",
            env_vars=(),
            cmake_defines=(),
            kconfig_overrides=(),
            jobs=None,
            dawn_root=None,
            nuttx_dir=None,
            nuttx_apps_dir=None,
            config_only=True,
            build_only=False,
            verbose=False,
        )
    )

    assert captured["build_dir"] == (invocation_dir / "build").resolve()


def test_validate_generated_config_resolves_yaml_descriptor(
    tmp_path: Path,
) -> None:
    project = _fake_project(tmp_path)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    yaml_path = tmp_path / "descriptors" / "demo.yaml"
    yaml_path.parent.mkdir()
    yaml_path.write_text(
        "ios:\n"
        "  - id: pwm1\n"
        "    type: pwm\n"
        "    instance: 0\n"
        "    dtype: uint32\n",
        encoding="utf-8",
    )
    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n"
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="
        '"../../../descriptors/demo.yaml"\n'
        "CONFIG_DAWN_IO_PWM=y\n"
        "CONFIG_DAWN_DTYPE_UINT32=y\n"
        "CONFIG_PWM=y\n",
        encoding="utf-8",
    )

    assert _validate_generated_config(build_dir, project) is False

    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n"
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="
        '"../../../descriptors/demo.yaml"\n'
        "CONFIG_DAWN_IO_PWM=y\n"
        "CONFIG_DAWN_DTYPE_UINT32=y\n"
        "CONFIG_PWM=y\n"
        "CONFIG_PWM_MULTICHAN=y\n",
        encoding="utf-8",
    )

    assert _validate_generated_config(build_dir, project) is True


def test_resolve_descriptor_yaml_config_edge_cases(tmp_path: Path) -> None:
    project = _fake_project(tmp_path)
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    assert _resolve_descriptor_yaml_from_config(build_dir, project) is None
    assert _validate_generated_config(build_dir, project) is True

    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_CXX=y\n",
        encoding="utf-8",
    )
    assert _resolve_descriptor_yaml_from_config(build_dir, project) is None
    assert _validate_generated_config(build_dir, project) is True

    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n",
        encoding="utf-8",
    )
    assert _resolve_descriptor_yaml_from_config(build_dir, project) is None

    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n"
        'CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="missing.yaml"\n',
        encoding="utf-8",
    )
    assert _resolve_descriptor_yaml_from_config(build_dir, project) == (
        tmp_path / "missing.yaml"
    )


def test_validate_generated_config_oot_resolution(tmp_path: Path) -> None:
    from dawnpy.dawn.project import Project

    dawn_root = tmp_path / "dawn"
    oot_root = tmp_path / "oot"
    yaml_path = oot_root / "descriptors" / "demo.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text("ios: []\n", encoding="utf-8")
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n"
        'CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="descriptors/demo.yaml"\n',
        encoding="utf-8",
    )
    project = Project(
        project_root=oot_root,
        dawn_root=dawn_root,
        nuttx_dir=dawn_root / "external" / "nuttx",
        nuttx_apps_dir=dawn_root / "external" / "apps",
        is_oot=True,
        dawnrc=DawnRC(path=None, data={}),
    )

    assert (
        _resolve_descriptor_yaml_from_config(build_dir, project) == yaml_path
    )


def test_run_build_only_fails_on_generated_config_validation(
    tmp_path: Path,
) -> None:
    project = _fake_project(tmp_path)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text("ok", encoding="utf-8")
    yaml_path = tmp_path / "descriptor.yaml"
    yaml_path.write_text(
        "protocols:\n" "  - id: udp1\n" "    type: udp\n" "    bindings: []\n",
        encoding="utf-8",
    )
    (build_dir / ".config").write_text(
        "CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML=y\n"
        'CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH="descriptor.yaml"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        _run_build_only(build_dir, None, project, None, False)


def test_run_batch_and_kconfig_workflows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run_batch(
        config_file: str,
        generator: str,
        env_vars: tuple[str, ...],
        cmake_defines: tuple[str, ...],
        jobs: int | None,
        build_root: str,
        *,
        continue_on_error: bool,
        config_only: bool,
        verbose: bool,
    ) -> None:
        run_batch_request(
            BatchRequest(
                config_file=config_file,
                generator=generator,
                env_vars=env_vars,
                cmake_defines=cmake_defines,
                jobs=jobs,
                build_root=build_root,
                continue_on_error=continue_on_error,
                config_only=config_only,
                verbose=verbose,
            )
        )

    def run_kconfig(
        confpath: str,
        kconfig_symbol: str,
        values: str,
        generator: str,
        env_vars: tuple[str, ...],
        cmake_defines: tuple[str, ...],
        jobs: int | None,
        build_root: str,
        *,
        continue_on_error: bool,
        config_only: bool,
        verbose: bool,
    ) -> None:
        run_kconfig_request(
            KconfigSweepRequest(
                confpath=confpath,
                kconfig_symbol=kconfig_symbol,
                values=values,
                generator=generator,
                env_vars=env_vars,
                cmake_defines=cmake_defines,
                jobs=jobs,
                build_root=build_root,
                continue_on_error=continue_on_error,
                config_only=config_only,
                verbose=verbose,
            )
        )

    build_root = tmp_path / "build"
    build_root.mkdir()

    config_file = tmp_path / "configs.txt"
    config_file.write_text(
        "boards/sim/configs/tests\nboards/sim/configs/shell\n",
        encoding="utf-8",
    )

    batch_calls = {"count": 0}

    def configure_toggle(*args, **kwargs):
        batch_calls["count"] += 1
        return batch_calls["count"] > 1

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", configure_toggle
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )

    with pytest.raises(SystemExit):
        run_batch(
            str(config_file),
            "Ninja",
            ("CC=gcc",),
            ("TEST=1",),
            None,
            "build",
            continue_on_error=True,
            config_only=False,
            verbose=False,
        )

    run_batch(
        str(config_file),
        "Ninja",
        (),
        (),
        None,
        "build",
        continue_on_error=False,
        config_only=False,
        verbose=False,
    )

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", lambda *a, **k: False
    )
    with pytest.raises(SystemExit):
        run_batch(
            str(config_file),
            "Ninja",
            (),
            (),
            None,
            "build",
            continue_on_error=False,
            config_only=False,
            verbose=False,
        )

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )
    run_batch(
        str(config_file),
        "Ninja",
        (),
        (),
        None,
        "newbuild",
        continue_on_error=False,
        config_only=True,
        verbose=False,
    )

    kconfig_confpath = "boards/sim/configs/tests"

    monkeypatch.setattr(
        "dawnpy.dawn.workflows._normalize_confpath",
        lambda confpath, base_dir: confpath,
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.Project.resolve",
        lambda *a, **k: _fake_project(tmp_path),
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows._run_kconfig_value",
        lambda *a, **k: (True, None),
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        run_kconfig(
            kconfig_confpath,
            "CONFIG_X",
            "",
            "Ninja",
            (),
            (),
            None,
            "build",
            continue_on_error=False,
            config_only=False,
            verbose=False,
        )

    run_kconfig(
        kconfig_confpath,
        "CONFIG_X",
        "1,2",
        "Ninja",
        ("CC=gcc",),
        ("D=1",),
        None,
        str(tmp_path / "kbuild-abs"),
        continue_on_error=True,
        config_only=True,
        verbose=True,
    )


def test_run_batch_request_build_root_relative_to_invocation_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_dir = workspace / "tools"
    config_dir.mkdir()
    config_file = config_dir / "configs.txt"
    config_file.write_text("boards/sim/configs/tests\n", encoding="utf-8")

    captured: dict[str, Path] = {}

    monkeypatch.chdir(workspace)

    def capture_configure(build_path, *args, **kwargs):
        captured["build_path"] = build_path
        return True

    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake", capture_configure
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )

    run_batch_request(
        BatchRequest(
            config_file=str(config_file.relative_to(workspace)),
            generator="Ninja",
            env_vars=(),
            cmake_defines=(),
            jobs=None,
            build_root="tools/build",
            continue_on_error=False,
            config_only=True,
            verbose=False,
        )
    )

    assert captured["build_path"] == (
        workspace / "tools" / "build" / "build-sim-sim-tests"
    )


def test_run_batch_request_accepts_absolute_build_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_file = workspace / "configs.txt"
    config_file.write_text("boards/sim/configs/tests\n", encoding="utf-8")

    captured: dict[str, Path] = {}

    monkeypatch.chdir(workspace)
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.configure_cmake",
        lambda build_path, *a, **k: captured.setdefault(
            "build_path", build_path
        )
        and True
        or True,
    )
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.build_cmake", lambda *a, **k: True
    )

    abs_build_root = tmp_path / "abs-build"

    run_batch_request(
        BatchRequest(
            config_file=str(config_file),
            generator="Ninja",
            env_vars=(),
            cmake_defines=(),
            jobs=None,
            build_root=str(abs_build_root),
            continue_on_error=False,
            config_only=True,
            verbose=False,
        )
    )

    assert "build_path" in captured
    assert captured["build_path"].is_relative_to(abs_build_root.resolve())


def test_normalize_confpath_returns_absolute_when_file_exists(
    tmp_path: Path,
) -> None:
    from dawnpy.dawn.workflows import _normalize_confpath

    confpath = tmp_path / "boards" / "sim" / "configs" / "tests"
    confpath.mkdir(parents=True)
    (confpath / "defconfig").write_text("", encoding="utf-8")

    rel = "boards/sim/configs/tests"
    assert _normalize_confpath(rel, tmp_path) == str(confpath.resolve())
    assert _normalize_confpath("nonexistent/path", tmp_path) == (
        "nonexistent/path"
    )
