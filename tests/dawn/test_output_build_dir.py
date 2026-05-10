# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.dawn.tooling_context import *


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
