# tools/dawnpy/src/dawnpy/headerdefs/_paths.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Repository root discovery for header-backed descriptor metadata."""

from pathlib import Path

from dawnpy.sources import DawnSourcesMissing, HeaderDefsError

__all__ = ["HeaderDefsError", "find_repo_root"]


def _repo_root_from_here() -> Path | None:
    """Locate repository root by searching for Dawn headers."""

    def _resolve_repo_root(base: Path) -> Path | None:
        primary = base / "dawn/include/dawn/common/objectid.hxx"
        if primary.exists():
            return base
        nested = base / "dawn/dawn/include/dawn/common/objectid.hxx"
        if nested.exists():
            return base / "dawn"
        return None

    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        resolved = _resolve_repo_root(parent)
        if resolved is not None:
            return resolved

    cur = Path(__file__).resolve()
    for parent in [cur] + list(cur.parents):
        resolved = _resolve_repo_root(parent)
        if resolved is not None:
            return resolved

    return None


def find_repo_root() -> Path | None:
    """Return detected Dawn repository root if available."""
    return _repo_root_from_here()


def _require_repo_root() -> Path:
    """Return repository root or raise descriptive error."""
    root = _repo_root_from_here()
    if root is None:
        raise DawnSourcesMissing("Could not locate Dawn repository root.")
    return root
