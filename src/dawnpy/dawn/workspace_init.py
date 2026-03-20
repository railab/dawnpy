# tools/dawnpy/src/dawnpy/dawn/workspace_init.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Workspace bootstrap workflow (Dawn + NuttX + apps fetch)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError

import click

from dawnpy.config import _global_dawnrc_path, write_dawnrc


@dataclass(frozen=True)
class InitRequest:
    """Workspace-init request."""

    path: Path
    layout: str
    dawn_ref: str
    dawn_url: str
    dawn_source: str
    with_nuttx: bool
    nuttx_ref: str
    nuttx_url: str
    nuttx_apps_url: str
    nuttx_apps_ref: str
    write_global_dawnrc: bool
    force: bool


def _github_repo_path(repo_url: str) -> str:
    repo_path = repo_url.rstrip("/")
    if repo_path.endswith(".git"):
        repo_path = repo_path[: -len(".git")]
    return repo_path.replace("https://github.com/", "")


def _resolve_latest_release_tag(repo_url: str) -> str:
    repo_path = _github_repo_path(repo_url)
    api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
    try:
        with urllib.request.urlopen(api_url) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            raise click.ClickException(
                "Could not resolve `--dawn-ref=latest`: the repository has "
                "no GitHub latest release. Pass `--dawn-ref <tag>` "
                "explicitly or use `--dawn-source git`."
            ) from exc
        raise click.ClickException(
            f"Failed to resolve latest Dawn release tag: HTTP {exc.code}"
        ) from exc

    tag_name = payload.get("tag_name")
    if not tag_name:
        raise click.ClickException(
            "Could not resolve latest Dawn release tag from GitHub response"
        )
    return str(tag_name)


def _resolve_default_branch(repo_url: str) -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            f"Failed to resolve default branch for {repo_url} via git"
        ) from exc

    for line in result.stdout.splitlines():
        if line.startswith("ref: ") and line.endswith("\tHEAD"):
            ref_name = line.split()[1]
            prefix = "refs/heads/"
            if ref_name.startswith(prefix):
                return ref_name[len(prefix) :]

    if result.stdout.strip():
        for fallback in ("master", "main"):
            if f"refs/heads/{fallback}" in result.stdout:
                return fallback

    return "master"


def _download_github_tarball(repo_url: str, ref: str, dest_dir: Path) -> None:
    owner_repo = _github_repo_path(repo_url)
    tarball_url = (
        f"https://github.com/{owner_repo}/archive/refs/tags/{ref}.tar.gz"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "archive.tar.gz"
        urllib.request.urlretrieve(tarball_url, archive_path)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(tmpdir, filter="data")

        extracted_dirs = [
            path for path in Path(tmpdir).iterdir() if path.is_dir()
        ]
        if not extracted_dirs:
            raise click.ClickException(
                f"Archive for {repo_url}@{ref} did not contain a root "
                "directory"
            )

        extracted_root = extracted_dirs[0]
        for child in extracted_root.iterdir():
            target = dest_dir / child.name
            if target.exists():
                raise click.ClickException(
                    f"Refusing to overwrite existing path: {target}"
                )
            shutil.move(str(child), target)


def _clone_git(url: str, ref: str, dest_dir: Path) -> None:
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            ref,
            "--recurse-submodules=false",
            url,
            str(dest_dir),
        ],
        check=True,
    )


def _prepare_target(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()) and not force:
        raise click.ClickException(
            f"Refusing to populate non-empty directory without --force: "
            f"{path}"
        )
    if force and path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _fetch_tree(*, source: str, url: str, ref: str, dest_dir: Path) -> None:
    if source == "git":
        _clone_git(url, ref, dest_dir)
        return
    _download_github_tarball(url, ref, dest_dir)


def _create_dawn_apps_symlink(dawn_root: Path, nuttx_apps_dir: Path) -> None:
    """Mirror repo_init.sh: expose Dawn as an out-of-tree apps package."""
    external_link = nuttx_apps_dir / "external"
    dawn_apps_root = (dawn_root / "dawn").resolve()

    if not dawn_apps_root.is_dir():
        raise click.ClickException(
            f"Dawn apps source directory not found: {dawn_apps_root}"
        )

    if external_link.exists() or external_link.is_symlink():
        if (
            external_link.is_symlink()
            and external_link.resolve() == dawn_apps_root
        ):
            return
        raise click.ClickException(
            "Refusing to overwrite existing apps symlink target: "
            f"{external_link}"
        )

    external_link.symlink_to(dawn_apps_root, target_is_directory=True)


def _resolve_dawn_ref(req: InitRequest) -> str:
    if req.dawn_ref != "latest":
        return req.dawn_ref  # pragma: no cover
    if req.dawn_source == "release":
        return _resolve_latest_release_tag(req.dawn_url)
    return _resolve_default_branch(req.dawn_url)


def _fetch_nuttx_trees(
    req: InitRequest,
    dawn_root: Path,
    nuttx_dir: Path,
    nuttx_apps_dir: Path,
) -> None:
    click.echo(f"Fetching NuttX into {nuttx_dir} ...")
    _prepare_target(nuttx_dir, req.force)
    _clone_git(req.nuttx_url, req.nuttx_ref, nuttx_dir)

    click.echo(f"Fetching NuttX apps into {nuttx_apps_dir} ...")
    _prepare_target(nuttx_apps_dir, req.force)
    _clone_git(req.nuttx_apps_url, req.nuttx_apps_ref, nuttx_apps_dir)
    _create_dawn_apps_symlink(dawn_root, nuttx_apps_dir)


def _write_global_dawnrc(
    req: InitRequest,
    dawn_root: Path,
    nuttx_dir: Path,
    nuttx_apps_dir: Path,
) -> None:
    rc_data: dict[str, dict[str, object]] = {
        "paths": {
            "dawn_root": str(dawn_root),
        }
    }
    if req.with_nuttx:
        rc_data["paths"]["nuttx_dir"] = str(nuttx_dir)
        rc_data["paths"]["nuttx_apps_dir"] = str(nuttx_apps_dir)

    rc_path = _global_dawnrc_path()
    write_dawnrc(rc_path, rc_data)
    click.echo(f"Wrote {rc_path}")


def run_init_request(req: InitRequest) -> None:
    """Bootstrap a Dawn workspace or inline install."""
    workspace_root = req.path.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    dawn_root = (
        workspace_root / "dawn-src"
        if req.layout == "workspace"
        else workspace_root
    )

    dawn_ref = _resolve_dawn_ref(req)

    _prepare_target(dawn_root, req.force)
    click.echo(f"Fetching Dawn into {dawn_root} ...")
    _fetch_tree(
        source=req.dawn_source,
        url=req.dawn_url,
        ref=dawn_ref,
        dest_dir=dawn_root,
    )

    nuttx_dir = dawn_root / "external" / "nuttx"
    nuttx_apps_dir = dawn_root / "external" / "apps"

    if req.with_nuttx:
        _fetch_nuttx_trees(req, dawn_root, nuttx_dir, nuttx_apps_dir)

    if req.write_global_dawnrc:
        _write_global_dawnrc(req, dawn_root, nuttx_dir, nuttx_apps_dir)
