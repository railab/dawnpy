# tools/dawnpy/tests/test_cmd_init.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for `dawnpy init`."""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
from typing import TYPE_CHECKING
from urllib.error import HTTPError

import click
import pytest
from click.testing import CliRunner

import dawnpy.dawn.workspace_init as workspace_init_mod
from dawnpy.commands.cmd_init import cmd_init
from dawnpy.config import load_dawnrc
from dawnpy.dawn.workspace_init import _github_repo_path

if TYPE_CHECKING:
    from pathlib import Path


def test_github_repo_path_strips_git_suffix() -> None:
    assert (
        _github_repo_path("https://github.com/railab/dawn.git")
        == "railab/dawn"
    )
    assert _github_repo_path("https://github.com/railab/dawn") == "railab/dawn"


def test_init_workspace_bootstraps_sources_only(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_fetch_tree(
        *, source: str, url: str, ref: str, dest_dir: Path
    ) -> None:
        (dest_dir / "dawn").mkdir(parents=True, exist_ok=True)

    def fake_clone_git(url: str, ref: str, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workspace_init_mod, "_fetch_tree", fake_fetch_tree)
    monkeypatch.setattr(workspace_init_mod, "_clone_git", fake_clone_git)
    monkeypatch.setattr(
        workspace_init_mod,
        "_resolve_default_branch",
        lambda repo_url: "master",
    )

    runner = CliRunner()
    result = runner.invoke(cmd_init, [str(tmp_path / "ws")])

    assert result.exit_code == 0
    assert (tmp_path / "ws" / ".dawnrc").exists() is False
    assert (tmp_path / "ws" / "dawn-src").is_dir()
    assert (
        tmp_path / "ws" / "dawn-src" / "external" / "apps" / "external"
    ).is_symlink()


def test_init_can_write_global_dawnrc(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    def fake_fetch_tree(
        *, source: str, url: str, ref: str, dest_dir: Path
    ) -> None:
        (dest_dir / "dawn").mkdir(parents=True, exist_ok=True)

    def fake_clone_git(url: str, ref: str, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workspace_init_mod, "_fetch_tree", fake_fetch_tree)
    monkeypatch.setattr(workspace_init_mod, "_clone_git", fake_clone_git)
    monkeypatch.setattr(
        workspace_init_mod,
        "_resolve_default_branch",
        lambda repo_url: "master",
    )

    runner = CliRunner()
    result = runner.invoke(
        cmd_init,
        [str(tmp_path / "ws"), "--write-global-dawnrc"],
    )

    assert result.exit_code == 0
    rc = load_dawnrc(tmp_path / "outside")
    assert rc.path == home / ".config" / "dawn" / "dawnrc"
    assert rc.get_path("paths", "dawn_root") == tmp_path / "ws" / "dawn-src"
    assert (
        rc.get_path("paths", "nuttx_dir")
        == tmp_path / "ws" / "dawn-src" / "external" / "nuttx"
    )


def test_create_dawn_apps_symlink(tmp_path: Path) -> None:
    dawn_root = tmp_path / "dawn-src"
    apps_dir = dawn_root / "external" / "apps"
    (dawn_root / "dawn").mkdir(parents=True)
    apps_dir.mkdir(parents=True)

    workspace_init_mod._create_dawn_apps_symlink(dawn_root, apps_dir)

    link = apps_dir / "external"
    assert link.is_symlink()
    assert link.resolve() == (dawn_root / "dawn").resolve()


def test_init_git_source_resolves_latest_to_default_branch(
    tmp_path: Path, monkeypatch
) -> None:
    seen: dict[str, object] = {}

    def fake_fetch_tree(
        *, source: str, url: str, ref: str, dest_dir: Path
    ) -> None:
        seen["source"] = source
        seen["ref"] = ref
        (dest_dir / "dawn").mkdir(parents=True, exist_ok=True)

    def fake_clone_git(url: str, ref: str, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workspace_init_mod, "_fetch_tree", fake_fetch_tree)
    monkeypatch.setattr(workspace_init_mod, "_clone_git", fake_clone_git)
    monkeypatch.setattr(
        workspace_init_mod, "_resolve_default_branch", lambda repo_url: "main"
    )

    runner = CliRunner()
    result = runner.invoke(
        cmd_init,
        [str(tmp_path / "ws"), "--dawn-source", "git"],
    )

    assert result.exit_code == 0
    assert seen["source"] == "git"
    assert seen["ref"] == "main"


def test_resolve_default_branch_uses_git_ls_remote(
    monkeypatch,
) -> None:
    class Result:
        stdout = "ref: refs/heads/master\tHEAD\n123\tHEAD\n"

    monkeypatch.setattr(
        workspace_init_mod.subprocess, "run", lambda *args, **kwargs: Result()
    )

    assert (
        workspace_init_mod._resolve_default_branch(
            "https://github.com/railab/dawn.git"
        )
        == "master"
    )


class _FakeUrlResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def _patch_urlopen(monkeypatch, payload: bytes) -> None:
    def fake_urlopen(url):
        return _FakeUrlResponse(payload)

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlopen", fake_urlopen
    )


def test_resolve_latest_release_tag_returns_tag(monkeypatch) -> None:
    _patch_urlopen(
        monkeypatch, json.dumps({"tag_name": "v9.9.9"}).encode("utf-8")
    )
    assert (
        workspace_init_mod._resolve_latest_release_tag(
            "https://github.com/railab/dawn"
        )
        == "v9.9.9"
    )


def _raise_http_error(url: str, code: int, msg: str) -> None:
    fp = io.BytesIO(b"")
    try:
        raise HTTPError(url, code, msg, {}, fp)
    finally:
        fp.close()


@pytest.mark.filterwarnings("ignore::ResourceWarning")
def test_resolve_latest_release_tag_404(monkeypatch) -> None:
    def fake_urlopen(url):
        _raise_http_error(url, 404, "not found")

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlopen", fake_urlopen
    )
    with pytest.raises(click.ClickException, match="has no GitHub latest"):
        workspace_init_mod._resolve_latest_release_tag(
            "https://github.com/railab/dawn"
        )


@pytest.mark.filterwarnings("ignore::ResourceWarning")
def test_resolve_latest_release_tag_other_http_error(monkeypatch) -> None:
    def fake_urlopen(url):
        _raise_http_error(url, 500, "server error")

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlopen", fake_urlopen
    )
    with pytest.raises(click.ClickException, match="HTTP 500"):
        workspace_init_mod._resolve_latest_release_tag(
            "https://github.com/railab/dawn"
        )


def test_resolve_latest_release_tag_missing_tag_name(monkeypatch) -> None:
    _patch_urlopen(monkeypatch, b"{}")
    with pytest.raises(click.ClickException, match="Could not resolve latest"):
        workspace_init_mod._resolve_latest_release_tag(
            "https://github.com/railab/dawn"
        )


def test_resolve_default_branch_falls_back_when_no_symref(monkeypatch):
    class Result:
        stdout = "abc1234\trefs/heads/master\n"

    monkeypatch.setattr(
        workspace_init_mod.subprocess, "run", lambda *a, **k: Result()
    )
    assert (
        workspace_init_mod._resolve_default_branch("https://example.org/repo")
        == "master"
    )


def test_resolve_default_branch_defaults_when_empty(monkeypatch):
    class Result:
        stdout = ""

    monkeypatch.setattr(
        workspace_init_mod.subprocess, "run", lambda *a, **k: Result()
    )
    assert (
        workspace_init_mod._resolve_default_branch("https://example.org/repo")
        == "master"
    )


def test_resolve_default_branch_raises_on_git_failure(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(workspace_init_mod.subprocess, "run", fake_run)
    with pytest.raises(click.ClickException, match="Failed to resolve"):
        workspace_init_mod._resolve_default_branch("https://example.org/repo")


def test_clone_git_invokes_subprocess(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(workspace_init_mod.subprocess, "run", fake_run)
    workspace_init_mod._clone_git(
        "https://example.org/repo.git", "main", tmp_path / "dest"
    )
    assert captured["cmd"][0:2] == ["git", "clone"]
    assert "main" in captured["cmd"]


def test_fetch_tree_dispatches_on_source(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_clone_git(url, ref, dest_dir):
        calls.append("clone")

    def fake_download(url, ref, dest_dir):
        calls.append("download")

    monkeypatch.setattr(workspace_init_mod, "_clone_git", fake_clone_git)
    monkeypatch.setattr(
        workspace_init_mod, "_download_github_tarball", fake_download
    )

    workspace_init_mod._fetch_tree(
        source="git", url="u", ref="r", dest_dir=tmp_path / "a"
    )
    workspace_init_mod._fetch_tree(
        source="release", url="u", ref="r", dest_dir=tmp_path / "b"
    )
    assert calls == ["clone", "download"]


def test_download_github_tarball_extracts_into_dest(
    tmp_path: Path, monkeypatch
) -> None:
    extracted_root = tmp_path / "src"
    (extracted_root / "dawn").mkdir(parents=True)
    (extracted_root / "README").write_text("hi", encoding="utf-8")

    archive_path = tmp_path / "archive.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(extracted_root, arcname="repo-tag")

    def fake_urlretrieve(url, target):
        with archive_path.open("rb") as src, open(target, "wb") as dst:
            dst.write(src.read())

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlretrieve", fake_urlretrieve
    )

    dest = tmp_path / "dest"
    dest.mkdir()
    workspace_init_mod._download_github_tarball(
        "https://github.com/railab/dawn", "tag", dest
    )

    assert (dest / "dawn").is_dir()
    assert (dest / "README").read_text(encoding="utf-8") == "hi"


def test_download_github_tarball_refuses_to_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    extracted_root = tmp_path / "src"
    (extracted_root / "dawn").mkdir(parents=True)
    archive_path = tmp_path / "archive.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(extracted_root, arcname="repo-tag")

    def fake_urlretrieve(url, target):
        with archive_path.open("rb") as src, open(target, "wb") as dst:
            dst.write(src.read())

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlretrieve", fake_urlretrieve
    )

    dest = tmp_path / "dest"
    (dest / "dawn").mkdir(parents=True)

    with pytest.raises(click.ClickException, match="Refusing to overwrite"):
        workspace_init_mod._download_github_tarball(
            "https://github.com/railab/dawn", "tag", dest
        )


def test_download_github_tarball_rejects_empty_archive(
    tmp_path: Path, monkeypatch
) -> None:
    archive_path = tmp_path / "archive.tar.gz"
    with tarfile.open(archive_path, "w:gz"):
        pass

    def fake_urlretrieve(url, target):
        with archive_path.open("rb") as src, open(target, "wb") as dst:
            dst.write(src.read())

    monkeypatch.setattr(
        workspace_init_mod.urllib.request, "urlretrieve", fake_urlretrieve
    )

    with pytest.raises(
        click.ClickException, match="did not contain a root directory"
    ):
        workspace_init_mod._download_github_tarball(
            "https://github.com/railab/dawn", "tag", tmp_path / "dest"
        )


def test_prepare_target_refuses_non_empty_without_force(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tree"
    target.mkdir()
    (target / "stale").write_text("hi", encoding="utf-8")
    with pytest.raises(
        click.ClickException, match="Refusing to populate non-empty"
    ):
        workspace_init_mod._prepare_target(target, force=False)


def test_prepare_target_force_clears_existing(tmp_path: Path) -> None:
    target = tmp_path / "tree"
    target.mkdir()
    (target / "stale").write_text("hi", encoding="utf-8")
    workspace_init_mod._prepare_target(target, force=True)
    assert target.is_dir()
    assert not (target / "stale").exists()


def test_create_dawn_apps_symlink_missing_dawn_dir(tmp_path: Path) -> None:
    dawn_root = tmp_path / "dawn-src"
    apps_dir = dawn_root / "external" / "apps"
    apps_dir.mkdir(parents=True)
    with pytest.raises(
        click.ClickException, match="Dawn apps source directory not found"
    ):
        workspace_init_mod._create_dawn_apps_symlink(dawn_root, apps_dir)


def test_create_dawn_apps_symlink_idempotent(tmp_path: Path) -> None:
    dawn_root = tmp_path / "dawn-src"
    apps_dir = dawn_root / "external" / "apps"
    (dawn_root / "dawn").mkdir(parents=True)
    apps_dir.mkdir(parents=True)
    workspace_init_mod._create_dawn_apps_symlink(dawn_root, apps_dir)
    # Second call must succeed without error and leave the link intact.
    workspace_init_mod._create_dawn_apps_symlink(dawn_root, apps_dir)
    assert (apps_dir / "external").is_symlink()


def test_create_dawn_apps_symlink_refuses_existing_other_target(
    tmp_path: Path,
) -> None:
    dawn_root = tmp_path / "dawn-src"
    apps_dir = dawn_root / "external" / "apps"
    (dawn_root / "dawn").mkdir(parents=True)
    apps_dir.mkdir(parents=True)
    (apps_dir / "external").write_text("conflicting", encoding="utf-8")
    with pytest.raises(click.ClickException, match="Refusing to overwrite"):
        workspace_init_mod._create_dawn_apps_symlink(dawn_root, apps_dir)


def test_init_reports_missing_latest_release(
    tmp_path: Path, monkeypatch
) -> None:
    def raise_404(repo_url: str) -> str:
        raise click.ClickException(
            "Could not resolve `--dawn-ref=latest`: the repository has no "
            "GitHub latest release. Pass `--dawn-ref <tag>` explicitly or "
            "use `--dawn-source git`."
        )

    monkeypatch.setattr(
        workspace_init_mod, "_resolve_latest_release_tag", raise_404
    )

    runner = CliRunner()
    result = runner.invoke(
        cmd_init,
        [str(tmp_path / "ws"), "--dawn-source", "release"],
    )

    assert result.exit_code != 0
    assert "has no GitHub latest release" in result.output
