# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.dawn.tooling_context import *


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
    dawn_root = _fake_dawn_root(tmp_path / "dawn")
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
        dawn_root=str(dawn_root),
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
