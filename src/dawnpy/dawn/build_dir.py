# tools/dawnpy/src/dawnpy/dawn/build_dir.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Build directory helpers."""

import hashlib
from pathlib import Path


def _oot_suffix(project_root: Path | None, dawn_root: Path | None) -> str:
    if project_root is None:
        return ""
    if dawn_root is not None and project_root == dawn_root:
        return ""

    digest = hashlib.sha1(str(project_root).encode("utf-8")).hexdigest()[:8]
    return f"-oot-{digest}"


def generate_build_dir_name(
    confpath: str,
    project_root: Path | None = None,
    dawn_root: Path | None = None,
) -> str:
    """Generate build directory name from configuration path."""
    parts = Path(confpath).parts

    arch = "unknown"
    if "boards" in parts:
        boards_idx = parts.index("boards")
        if boards_idx + 1 < len(parts):
            arch = parts[boards_idx + 1]

    if "configs" in parts:
        configs_idx = parts.index("configs")
        board = parts[configs_idx - 1] if configs_idx > 0 else "unknown"
        config_parts = parts[configs_idx + 1 :]
        config = "-".join(config_parts) if config_parts else "default"
    else:
        board = parts[-2] if len(parts) >= 2 else "unknown"
        config = parts[-1] if parts else "default"

    board = board.replace("_", "-")
    config = config.replace("_", "-")
    arch = arch.replace("_", "-")

    return (
        f"build-{arch}-{board}-{config}{_oot_suffix(project_root, dawn_root)}"
    )


def is_build_configured(build_dir: Path) -> bool:
    """Check if a build directory has been configured by CMake."""
    return (build_dir / "CMakeCache.txt").is_file()


def sanitize_build_component(value: str) -> str:
    """Sanitize value for use in build directory names."""
    sanitized = []
    for char in value:
        if char.isalnum():
            sanitized.append(char.lower())
        elif char in ("-", "."):
            sanitized.append(char)
        else:
            sanitized.append("-")
    result = "".join(sanitized).strip("-")
    return result or "value"
