# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.dawn.tooling_context import *


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
