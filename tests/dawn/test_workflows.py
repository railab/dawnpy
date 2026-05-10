# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.dawn.tooling_context import *


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
        dawn_root = _fake_dawn_root(tmp_path / "dawn")
        run_build_request(
            BuildRequest(
                build_dir=build_dir,
                confpath=confpath,
                generator=generator,
                env_vars=env_vars,
                cmake_defines=cmake_defines,
                kconfig_overrides=kconfig_overrides,
                jobs=jobs,
                dawn_root=str(dawn_root),
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
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.Project.resolve",
        lambda *a, **k: _fake_project(tmp_path),
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
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.Project.resolve",
        lambda *a, **k: _fake_project(workspace),
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
    monkeypatch.setattr(
        "dawnpy.dawn.workflows.Project.resolve",
        lambda *a, **k: _fake_project(workspace),
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
