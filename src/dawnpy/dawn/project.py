# tools/dawnpy/src/dawnpy/dawn/project.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Project root discovery, OOT detection, and CMake/CMake-env export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dawnpy.config import DawnRC, load_dawnrc
from dawnpy.sources import DawnSourcesMissing

# A project root is any directory containing `boards/`. Out-of-tree projects
# may provide only board/config overlays and no optional `external/` content.


def _walk_up_for_project_root(start_path: Path) -> Path | None:
    search_path = start_path
    if search_path.is_file():
        search_path = search_path.parent
    for parent in [search_path] + list(search_path.parents):
        if (parent / "boards").is_dir():
            return parent
    return None


def _walk_up_for_dawn_root(start_path: Path) -> Path | None:
    # The upstream Dawn repo additionally has a top-level `dawn/` directory
    # (the library) and `Documentation/`. This distinguishes it from a typical
    # out-of-tree project that only has `boards/` and optional overlays.
    search_path = start_path
    if search_path.is_file():
        search_path = search_path.parent
    for parent in [search_path] + list(search_path.parents):
        if (
            (parent / "boards").is_dir()
            and (parent / "dawn").is_dir()
            and (parent / "Documentation").is_dir()
        ):
            return parent
    return None


@dataclass(frozen=True)
class Project:
    """Resolved Dawn project paths.

    :ivar project_root: Directory containing ``boards/`` and ``external/``.
        For an out-of-tree project this is the OOT root; for an in-tree
        build this equals ``dawn_root``.
    :ivar dawn_root: The upstream Dawn repository root (where the ``dawn/``
        library, ``Documentation/`` and dawnpy live).
    :ivar is_oot: ``True`` iff ``project_root`` differs from ``dawn_root``.
    """

    project_root: Path
    dawn_root: Path
    nuttx_dir: Path
    nuttx_apps_dir: Path
    is_oot: bool
    dawnrc: DawnRC

    @classmethod
    def resolve(
        cls,
        start_path: Path | None = None,
        *,
        dawn_root_override: str | None = None,
        nuttx_dir_override: str | None = None,
        nuttx_apps_dir_override: str | None = None,
    ) -> Project:
        """Resolve a Project from a starting path.

        :param start_path: A file or directory to walk up from. ``None``
            means use dawnpy's own install location, which always gives the
            upstream Dawn root.
        :return: A populated :class:`Project`.
        :raises DawnSourcesMissing: If no Dawn checkout can be located.
        """
        resolved_start = Path.cwd() if start_path is None else Path(start_path)
        resolved_start = resolved_start.resolve()
        dawnrc = load_dawnrc(resolved_start)

        discovered_dawn_root = _walk_up_for_dawn_root(resolved_start)
        install_dawn_root = _walk_up_for_dawn_root(Path(__file__).resolve())
        dawn_root = dawnrc.resolve_path(
            cli_value=dawn_root_override,
            env_var="DAWN_ROOT",
            section="paths",
            key="dawn_root",
            default=discovered_dawn_root or install_dawn_root,
        )
        if dawn_root is None:
            raise DawnSourcesMissing("Could not resolve Dawn root.")

        found_project_root = _walk_up_for_project_root(resolved_start)
        if found_project_root is not None:
            project_root = found_project_root
        elif dawnrc.root_dir is not None and dawnrc.get(
            "project", "oot", False
        ):
            project_root = dawnrc.root_dir
        else:
            project_root = dawn_root

        nuttx_dir = dawnrc.resolve_path(
            cli_value=nuttx_dir_override,
            env_var="NUTTX_DIR",
            section="paths",
            key="nuttx_dir",
            default=dawn_root / "external" / "nuttx",
        )
        nuttx_apps_dir = dawnrc.resolve_path(
            cli_value=nuttx_apps_dir_override,
            env_var="NUTTX_APPS_DIR",
            section="paths",
            key="nuttx_apps_dir",
            default=dawn_root / "external" / "apps",
        )
        if nuttx_dir is None or nuttx_apps_dir is None:  # pragma: no cover
            raise DawnSourcesMissing("Could not resolve NuttX paths.")

        return cls(
            project_root=project_root,
            dawn_root=dawn_root,
            nuttx_dir=nuttx_dir,
            nuttx_apps_dir=nuttx_apps_dir,
            is_oot=(project_root != dawn_root),
            dawnrc=dawnrc,
        )

    def cmake_env(self) -> dict[str, str]:
        """Environment variables to inject into the cmake/Kconfig invocation.

        :return: Mapping of env-var names to absolute paths. ``DAWN_OOT_ROOT``
            is included only for out-of-tree builds; ``DAWN_BOARDS_COMMON``
            always points at the upstream ``boards/common/``.
        """
        extension_apps_kconfig = (
            self.dawn_root / ".dawn-no-extension-apps.Kconfig"
        )
        env: dict[str, str] = {
            "DAWN_BOARDS_COMMON": str(self.dawn_root / "boards" / "common"),
            "DAWN_EXTENSION_APPS_KCONFIG": str(extension_apps_kconfig),
        }
        if self.is_oot:
            env["DAWN_OOT_ROOT"] = str(self.project_root)
            apps_kconfig = self.project_root / "external" / "apps" / "Kconfig"
            if apps_kconfig.is_file():
                env["DAWN_EXTENSION_APPS_KCONFIG"] = str(apps_kconfig)
        return env

    def oot_cmake_file(self) -> Path | None:
        """Return the OOT CMake extension entry point when it exists."""
        if not self.is_oot:
            return None

        candidate = self.project_root / "external" / "dawn_oot.cmake"
        if candidate.is_file():
            return candidate
        return None
