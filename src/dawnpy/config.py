# tools/dawnpy/src/dawnpy/config.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""`.dawnrc` discovery and path resolution helpers."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w


def _normalize_search_path(start_path: Path | None) -> Path:
    search_path = Path.cwd() if start_path is None else Path(start_path)
    if search_path.is_file():
        return search_path.parent.resolve()
    return search_path.resolve()


def _walk_up_for_dawnrc(start_path: Path | None) -> Path | None:
    search_path = _normalize_search_path(start_path)
    for parent in [search_path] + list(search_path.parents):
        candidate = parent / ".dawnrc"
        if candidate.is_file():
            return candidate
    return None


def _global_dawnrc_path() -> Path:
    return Path.home() / ".config" / "dawn" / "dawnrc"


@dataclass(frozen=True)
class DawnRC:
    """Resolved `.dawnrc` view with helper accessors."""

    path: Path | None
    data: dict[str, Any]

    @property
    def root_dir(self) -> Path | None:
        """Directory containing this `.dawnrc`."""
        if self.path is None:
            return None
        return self.path.parent

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Return a config value from `section.key` or `default`."""
        section_data = self.data.get(section, {})
        if not isinstance(section_data, dict):
            return default
        return section_data.get(key, default)

    def get_path(self, section: str, key: str) -> Path | None:
        """Return a path value resolved relative to the `.dawnrc` root."""
        raw_value = self.get(section, key)
        if raw_value in (None, ""):
            return None

        candidate = Path(str(raw_value))
        if candidate.is_absolute():
            return candidate.resolve()

        if self.root_dir is None:
            return candidate.resolve()
        return (self.root_dir / candidate).resolve()

    def resolve_path(
        self,
        *,
        cli_value: str | None = None,
        env_var: str | None = None,
        section: str,
        key: str,
        default: Path | None = None,
    ) -> Path | None:
        """Resolve a path using CLI > env > `.dawnrc` > `default`."""
        if cli_value:
            return Path(cli_value).resolve()

        if env_var:
            env_value = os.environ.get(env_var)
            if env_value:
                return Path(env_value).resolve()

        config_value = self.get_path(section, key)
        if config_value is not None:
            return config_value

        if default is None:
            return None
        return default.resolve()

    def implicit_types_from(self) -> list[Path]:
        """Return `project.types_from` entries as resolved paths."""
        value = self.get("project", "types_from")
        if value in (None, ""):
            return []
        values = value if isinstance(value, list) else [value]
        resolved: list[Path] = []
        for item in values:
            if item in (None, ""):
                continue
            candidate = Path(str(item))
            if not candidate.is_absolute() and self.root_dir is not None:
                candidate = self.root_dir / candidate
            resolved.append(candidate.resolve())
        return resolved


def load_dawnrc(start_path: Path | None = None) -> DawnRC:
    """Load project-local or global `.dawnrc`; return empty config if none."""
    config_path = _walk_up_for_dawnrc(start_path)
    if config_path is None:
        global_path = _global_dawnrc_path()
        config_path = global_path if global_path.is_file() else None

    if config_path is None:
        return DawnRC(path=None, data={})

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return DawnRC(path=config_path.resolve(), data=data)


def write_dawnrc(path: Path, data: dict[str, Any]) -> None:
    """Write a compact TOML `.dawnrc` file."""
    ordered: dict[str, dict[str, Any]] = {}
    for section in ("paths", "project", "build", "templates"):
        values = data.get(section)
        if isinstance(values, dict) and values:
            ordered[section] = values

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"# Managed by dawnpy.\n\n")
        tomli_w.dump(ordered, handle)
