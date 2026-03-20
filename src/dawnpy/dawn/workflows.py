# tools/dawnpy/src/dawnpy/dawn/workflows.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Workflow helpers for Dawn CLI commands."""

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import click

from dawnpy.dawn.build_dir import (
    generate_build_dir_name,
    is_build_configured,
    sanitize_build_component,
)
from dawnpy.dawn.cmake import build_cmake, configure_cmake
from dawnpy.dawn.kconfig import set_kconfig_value, set_kconfig_values
from dawnpy.dawn.output import (
    colored,
    print_error,
    print_header,
    print_info,
    print_success,
    print_verbose,
    print_warning,
)
from dawnpy.dawn.project import Project
from dawnpy.descriptor.validation.validator import DescriptorValidator


@dataclass(frozen=True)
class BatchConfig:
    """Batch build configuration entry."""

    path: str
    env: list[str]
    defines: list[str]


@dataclass(frozen=True)
class BuildRequest:
    """Single-target build request."""

    build_dir: str
    confpath: str | None
    generator: str
    env_vars: tuple[str, ...]
    cmake_defines: tuple[str, ...]
    kconfig_overrides: tuple[str, ...]
    jobs: int | None
    dawn_root: str | None
    nuttx_dir: str | None
    nuttx_apps_dir: str | None
    config_only: bool
    build_only: bool
    verbose: bool


@dataclass(frozen=True)
class BatchRequest:
    """Batch build request."""

    config_file: str
    generator: str
    env_vars: tuple[str, ...]
    cmake_defines: tuple[str, ...]
    jobs: int | None
    build_root: str
    continue_on_error: bool
    config_only: bool
    verbose: bool


@dataclass(frozen=True)
class KconfigSweepRequest:
    """Kconfig sweep build request."""

    confpath: str
    kconfig_symbol: str
    values: str
    generator: str
    env_vars: tuple[str, ...]
    cmake_defines: tuple[str, ...]
    jobs: int | None
    build_root: str
    continue_on_error: bool
    config_only: bool
    verbose: bool


_ItemT = TypeVar("_ItemT")


def parse_env_vars(env_vars: tuple[str, ...]) -> dict[str, str]:
    """Parse environment variable overrides into a dictionary."""
    env_dict: dict[str, str] = {}
    for env_var in env_vars:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env_dict[key] = value
        else:
            print_warning(
                f"Ignoring invalid environment variable format: {env_var}"
            )
    return env_dict


def parse_cmake_defines(cmake_defines: tuple[str, ...]) -> list[str]:
    """Prefix CMake defines with -D."""
    return [f"-D{define}" for define in cmake_defines]


def _project_cmake_flags(project: Project) -> list[str]:
    """Auto-populate CMake cache entries derived from the resolved project."""
    oot_cmake_file = project.oot_cmake_file()
    if oot_cmake_file is None:
        return []
    return [f"-DDAWN_OOT_CMAKE_FILE={oot_cmake_file}"]


def _ensure_configured(build_path: Path) -> bool:
    if not build_path.is_dir():
        print_error(f"Build directory not found: {build_path}")
        print_info("Please configure the build directory first")
        return False
    if not is_build_configured(build_path):
        print_error(f"Build directory not configured: {build_path}")
        print_info("Please configure the build directory first")
        return False
    return True


def _maybe_configure(
    build_path: Path,
    confpath: str | None,
    project: Project,
    generator: str,
    env_dict: dict[str, str],
    cmake_flags: list[str],
    verbose: bool,
) -> bool:
    if not confpath:
        return True
    return configure_cmake(
        build_path,
        confpath,
        project.dawn_root,
        generator,
        env_dict if env_dict else None,
        cmake_flags if cmake_flags else None,
        verbose,
        dawn_root=project.dawn_root,
        boards_search_root=project.project_root,
        nuttx_dir=project.nuttx_dir,
    )


def _print_build_result(build_path: Path) -> None:
    binary_path = build_path / "nuttx"
    click.echo()
    print_success("Build complete!")
    click.echo()
    if binary_path.exists():
        click.echo("ELF file:")
        click.echo(f"  {binary_path}")
        click.echo()


def _resolve_descriptor_yaml_from_config(
    build_path: Path, project: Project
) -> Path | None:
    """Return descriptor YAML path selected in generated .config."""
    kconfig_path = build_path / ".config"
    if not kconfig_path.exists():
        return None

    validator = DescriptorValidator()
    values = validator._parse_kconfig_values(kconfig_path)
    if values.get("CONFIG_DAWN_APPS_EXAMPLE_DESC_FORMAT_YAML") is not True:
        return None

    raw_path = values.get("CONFIG_DAWN_APPS_EXAMPLE_DESC_YAML_PATH")
    if not raw_path:
        return None

    rel_path = str(raw_path)
    while rel_path.startswith("../"):
        rel_path = rel_path[3:]

    candidates = []
    if project.is_oot:
        candidates.append(project.project_root / rel_path)
    candidates.append(project.dawn_root / rel_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _validate_generated_config(build_path: Path, project: Project) -> bool:
    """Validate descriptor-selected Dawn objects against build/.config."""
    kconfig_path = build_path / ".config"
    if not kconfig_path.exists():
        print_verbose(
            f"Skipping Dawn config validation; {kconfig_path} not found",
            False,
        )
        return True

    yaml_path = _resolve_descriptor_yaml_from_config(build_path, project)
    if yaml_path is None:
        return True

    print_info("Validating Dawn descriptor against generated .config...")
    validator = DescriptorValidator()
    result = validator.validate_generated_config(yaml_path, kconfig_path)
    if result.valid:
        print_success("Dawn descriptor config validation passed")
        return True

    click.echo(validator.format_report(result), err=True)
    print_error("Dawn descriptor config validation failed")
    return False


def _run_build_only(
    build_path: Path,
    confpath: str | None,
    project: Project,
    jobs: int | None,
    verbose: bool,
) -> None:
    if confpath:
        print_warning("Ignoring CONFPATH because --build-only is set")
    if not _ensure_configured(build_path):
        raise SystemExit(1)
    if not _validate_generated_config(build_path, project):
        raise SystemExit(1)
    if not build_cmake(build_path, project.dawn_root, jobs, verbose):
        raise SystemExit(1)
    _print_build_result(build_path)


def _apply_kconfig_overrides_for_build(  # pragma: no cover
    build_path: Path,
    project: Project,
    kconfig_overrides: tuple[str, ...],
    verbose: bool,
) -> None:
    if not kconfig_overrides:
        return
    if not set_kconfig_values(build_path, project, kconfig_overrides, verbose):
        raise SystemExit(1)


def _print_config_only_next_step(build_path: Path) -> None:  # pragma: no cover
    click.echo()
    print_success("Configuration complete!")
    click.echo()
    click.echo("Next step:")
    click.echo(f"  python -m dawnpy build {build_path} --build-only")
    click.echo()


def _run_configure_build(  # pragma: no cover
    build_path: Path,
    confpath: str | None,
    project: Project,
    generator: str,
    env_dict: dict[str, str],
    cmake_flags: list[str],
    kconfig_overrides: tuple[str, ...],
    jobs: int | None,
    config_only: bool,
    verbose: bool,
) -> None:
    if confpath:
        if not _maybe_configure(
            build_path,
            confpath,
            project,
            generator,
            env_dict,
            cmake_flags,
            verbose,
        ):
            raise SystemExit(1)

        _apply_kconfig_overrides_for_build(
            build_path, project, kconfig_overrides, verbose
        )

        if not _validate_generated_config(build_path, project):
            raise SystemExit(1)

        if config_only:
            _print_config_only_next_step(build_path)
            return
    else:
        _apply_kconfig_overrides_for_build(
            build_path, project, kconfig_overrides, verbose
        )

        if config_only:
            print_error("CONFPATH is required when using --config-only")
            raise SystemExit(1)
        if not _ensure_configured(build_path):
            raise SystemExit(1)
        if not _validate_generated_config(build_path, project):
            raise SystemExit(1)

    if not build_cmake(build_path, project.dawn_root, jobs, verbose):
        raise SystemExit(1)

    _print_build_result(build_path)


def _resolve_project_for_build(request: BuildRequest) -> Project:
    """Resolve a Project, walking up from the confpath when provided."""
    if request.confpath:
        return Project.resolve(
            Path(request.confpath),
            dawn_root_override=request.dawn_root,
            nuttx_dir_override=request.nuttx_dir,
            nuttx_apps_dir_override=request.nuttx_apps_dir,
        )
    return Project.resolve(
        dawn_root_override=request.dawn_root,
        nuttx_dir_override=request.nuttx_dir,
        nuttx_apps_dir_override=request.nuttx_apps_dir,
    )


def _normalize_confpath(confpath: str, base_dir: Path) -> str:
    """Resolve config-file-relative paths without breaking shorthand refs."""
    candidate = (base_dir / confpath).resolve()
    if candidate.exists():
        return str(candidate)
    return confpath


def _display_path(path: Path, anchor: Path) -> str:
    """Return ``path`` relative to ``anchor`` when possible, else absolute."""
    try:
        return str(path.relative_to(anchor))
    except ValueError:
        return str(path)


def _resolve_build_path(build_dir: str, base_dir: Path) -> Path:
    """Resolve relative build directories against the invocation cwd."""
    candidate = Path(build_dir)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def run_build_request(request: BuildRequest) -> None:
    """Configure and build a single target from request DTO."""
    print_header("Dawn CMake Build")

    if request.config_only and request.build_only:
        print_error("Cannot use --config-only and --build-only together")
        raise SystemExit(1)

    project = _resolve_project_for_build(request)
    build_path = _resolve_build_path(request.build_dir, Path.cwd().resolve())

    if project.is_oot:
        print_info(f"Out-of-tree project: {project.project_root}")
        print_info(f"Upstream Dawn:       {project.dawn_root}")

    # Project-derived env (DAWN_BOARDS_COMMON, DAWN_OOT_ROOT) is the base;
    # CLI -e overrides take precedence.
    env_dict = {**project.cmake_env(), **parse_env_vars(request.env_vars)}
    cmake_flags = [
        *_project_cmake_flags(project),
        *parse_cmake_defines(request.cmake_defines),
    ]

    if request.build_only:
        _run_build_only(
            build_path,
            request.confpath,
            project,
            request.jobs,
            request.verbose,
        )
        return

    _run_configure_build(
        build_path,
        request.confpath,
        project,
        request.generator,
        env_dict,
        cmake_flags,
        request.kconfig_overrides,
        request.jobs,
        request.config_only,
        request.verbose,
    )


def _parse_batch_line(  # pragma: no cover
    line: str, line_num: int
) -> BatchConfig | None:
    try:
        parts = shlex.split(line)
    except ValueError as exc:
        print_error(f"Failed to parse line {line_num}: {exc}")
        raise SystemExit(1)

    if not parts:
        return None

    confpath = parts[0]
    per_config_env: list[str] = []
    per_config_defines: list[str] = []

    idx = 1
    while idx < len(parts):
        if parts[idx] == "-e" and idx + 1 < len(parts):
            per_config_env.append(parts[idx + 1])
            idx += 2
        elif parts[idx] == "-D" and idx + 1 < len(parts):
            per_config_defines.append(parts[idx + 1])
            idx += 2
        else:
            print_warning(
                f"Ignoring unknown flag in line {line_num}: {parts[idx]}"
            )
            idx += 1

    return BatchConfig(confpath, per_config_env, per_config_defines)


def parse_batch_config_file(  # pragma: no cover
    config_file: str,
) -> list[BatchConfig]:
    """Parse batch build configuration file."""
    config_path = Path(config_file)
    try:
        with open(config_path) as handle:
            lines = [
                line.strip()
                for line in handle
                if line.strip() and not line.strip().startswith("#")
            ]
    except Exception as exc:
        print_error(f"Failed to read configuration file: {exc}")
        raise SystemExit(1)

    if not lines:
        print_error("No configurations found in file")
        raise SystemExit(1)

    configs: list[BatchConfig] = []
    for line_num, line in enumerate(lines, 1):
        config = _parse_batch_line(line, line_num)
        if config is not None:
            configs.append(config)

    if not configs:
        print_error("No valid configurations found in file")
        raise SystemExit(1)

    return configs


def _merge_env_vars(  # pragma: no cover
    base_env: dict[str, str], extra_env: list[str]
) -> dict[str, str]:
    merged_env = {**base_env}
    for env_var in extra_env:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            merged_env[key] = value
        else:
            print_warning(
                f"Ignoring invalid environment variable format: {env_var}"
            )
    return merged_env


def _merge_cmake_flags(  # pragma: no cover
    base_flags: list[str], extra_flags: list[str]
) -> list[str]:
    merged_flags = list(base_flags)
    for define in extra_flags:
        merged_flags.append(f"-D{define}")
    return merged_flags


def _run_batch_config(  # pragma: no cover
    config: BatchConfig,
    build_path: Path,
    project_root: Path,
    generator: str,
    global_env_dict: dict[str, str],
    global_cmake_flags: list[str],
    jobs: int | None,
    config_only: bool,
    verbose: bool,
) -> tuple[bool, str | None]:
    # Per-config project resolution: a batch may mix in-tree and OOT entries.
    config_project = Project.resolve(Path(config.path))

    if config_project.is_oot:
        print_info(
            f"OOT project for {config.path}: {config_project.project_root}"
        )

    base_env = {**config_project.cmake_env(), **global_env_dict}
    merged_env = _merge_env_vars(base_env, config.env)
    merged_cmake_flags = [
        *_project_cmake_flags(config_project),
        *_merge_cmake_flags(global_cmake_flags, config.defines),
    ]

    if verbose:
        if config.env:
            print_verbose(f"Per-config environment: {config.env}", verbose)
        if config.defines:
            print_verbose(
                f"Per-config CMake defines: {config.defines}", verbose
            )

    if not configure_cmake(
        build_path,
        config.path,
        config_project.dawn_root,
        generator,
        merged_env if merged_env else None,
        merged_cmake_flags if merged_cmake_flags else None,
        verbose,
        dawn_root=config_project.dawn_root,
        boards_search_root=config_project.project_root,
        nuttx_dir=config_project.nuttx_dir,
    ):
        return False, "Configuration failed"

    if not _validate_generated_config(build_path, config_project):
        return False, "Dawn descriptor config validation failed"

    if config_only:
        return True, None

    if not build_cmake(build_path, config_project.dawn_root, jobs, verbose):
        return False, "Build failed"

    return True, None


def _run_build_sequence(
    items: list[_ItemT],
    continue_message: str,
    stop_message: str,
    run_item: Callable[[int, int, _ItemT], tuple[bool, str | None]],
    item_key: Callable[[_ItemT], str],
    continue_on_error: bool,
) -> tuple[int, int, list[tuple[str, str]]]:
    total = len(items)
    succeeded = 0
    failed = 0
    failed_items: list[tuple[str, str]] = []

    for idx, item in enumerate(items, 1):
        success, reason = run_item(idx, total, item)
        if not success:
            failed += 1
            failed_items.append((item_key(item), reason or "Build failed"))
            if continue_on_error:
                print_warning(f"{reason}, {continue_message}")
                click.echo()
                continue
            print_error(f"{reason}, {stop_message}")
            click.echo()
            break

        succeeded += 1
        click.echo()

    return succeeded, failed, failed_items


def run_batch_request(request: BatchRequest) -> None:
    """Configure and build multiple configs from request DTO."""
    print_header("Dawn Batch Build")

    invocation_root = Path.cwd().resolve()
    request_base = Path(request.config_file).resolve().parent
    project_root = invocation_root
    build_root_arg = Path(request.build_root)
    if build_root_arg.is_absolute():
        build_root_path = build_root_arg.resolve()
    else:
        build_root_path = (invocation_root / build_root_arg).resolve()
    if not build_root_path.exists():
        build_root_path.mkdir(parents=True, exist_ok=True)
        print_verbose(
            f"Created build root directory: {build_root_path}",
            request.verbose,
        )

    configs = parse_batch_config_file(request.config_file)

    global_env_dict = parse_env_vars(request.env_vars)
    global_cmake_flags = parse_cmake_defines(request.cmake_defines)

    total = len(configs)

    click.echo()
    print_info(f"Found {total} configuration(s) to process")
    print_info(
        "Action: "
        f"{'Configure only' if request.config_only else 'Configure and build'}"
    )
    print_info(f"Build root directory: {build_root_path}")
    if global_env_dict:
        print_info(f"Global environment variables: {global_env_dict}")
    if global_cmake_flags:
        print_info(f"Global CMake flags: {' '.join(global_cmake_flags)}")
    click.echo()

    def run_one_batch(
        idx: int, total_items: int, config: BatchConfig
    ) -> tuple[bool, str | None]:
        config_path = _normalize_confpath(config.path, request_base)
        config_project = Project.resolve(Path(config_path))
        build_dir_name = generate_build_dir_name(
            config_path,
            project_root=config_project.project_root,
            dawn_root=config_project.dawn_root,
        )
        build_path = build_root_path / build_dir_name

        click.echo(
            f"{colored(f'[{idx}/{total_items}]', 'blue')} Processing: "
            f"{config.path}"
        )
        rel_build = _display_path(build_path, project_root)
        click.echo(f"           Build directory: {rel_build}")

        return _run_batch_config(
            BatchConfig(config_path, config.env, config.defines),
            build_path,
            project_root,
            request.generator,
            global_env_dict,
            global_cmake_flags,
            request.jobs,
            request.config_only,
            request.verbose,
        )

    succeeded, failed, failed_configs = _run_build_sequence(
        items=configs,
        continue_message="continuing with next configuration...",
        stop_message="stopping batch build",
        run_item=run_one_batch,
        item_key=lambda config: config.path,
        continue_on_error=request.continue_on_error,
    )

    _print_batch_summary(total, succeeded, failed, failed_configs)


def _print_batch_summary(  # pragma: no cover
    total: int,
    succeeded: int,
    failed: int,
    failed_configs: list[tuple[str, str]],
) -> None:
    click.echo()
    print_header("Batch Build Summary")
    click.echo(f"Total configurations: {total}")
    click.echo(colored(f"Succeeded: {succeeded}", "green"))
    if failed > 0:
        click.echo(colored(f"Failed: {failed}", "red"))
        click.echo()
        click.echo("Failed configurations:")
        for confpath, reason in failed_configs:
            click.echo(f"  {colored('[ERR]', 'red')} {confpath} - {reason}")
    click.echo()

    if failed > 0:
        raise SystemExit(1)


def _run_kconfig_value(  # pragma: no cover
    build_path: Path,
    confpath: str,
    project: Project | Path,
    kconfig_symbol: str,
    value: str,
    generator: str,
    env_dict: dict[str, str],
    cmake_flags: list[str],
    jobs: int | None,
    config_only: bool,
    verbose: bool,
) -> tuple[bool, str | None]:
    if isinstance(project, Path):
        project = Project.resolve(project)

    if not configure_cmake(
        build_path,
        confpath,
        project.dawn_root,
        generator,
        env_dict if env_dict else None,
        cmake_flags if cmake_flags else None,
        verbose,
        dawn_root=project.dawn_root,
        boards_search_root=project.project_root,
        nuttx_dir=project.nuttx_dir,
    ):
        return False, "Configuration failed"

    if not set_kconfig_value(
        build_path, project, kconfig_symbol, value, verbose
    ):
        return False, "Kconfig update failed"

    if not _validate_generated_config(build_path, project):
        return False, "Dawn descriptor config validation failed"

    if config_only:
        return True, None

    if not build_cmake(build_path, project.dawn_root, jobs, verbose):
        return False, "Build failed"

    return True, None


def run_kconfig_request(request: KconfigSweepRequest) -> None:
    """Configure/build kconfig values from request DTO."""
    print_header("Dawn Kconfig Batch Build")

    invocation_root = Path.cwd().resolve()
    normalized_confpath = _normalize_confpath(
        request.confpath, Path.cwd().resolve()
    )
    project = Project.resolve(Path(normalized_confpath))
    project_root = invocation_root
    build_root_arg = Path(request.build_root)
    if build_root_arg.is_absolute():
        build_root_path = build_root_arg.resolve()
    else:
        build_root_path = (invocation_root / build_root_arg).resolve()
    if not build_root_path.exists():
        build_root_path.mkdir(parents=True, exist_ok=True)
        print_verbose(
            f"Created build root directory: {build_root_path}",
            request.verbose,
        )

    value_list = [
        value.strip() for value in request.values.split(",") if value.strip()
    ]
    if not value_list:
        print_error("No Kconfig values provided")
        raise SystemExit(1)

    env_dict = parse_env_vars(request.env_vars)
    cmake_flags = [
        *_project_cmake_flags(project),
        *parse_cmake_defines(request.cmake_defines),
    ]

    total = len(value_list)

    click.echo()
    print_info(f"Config: {request.confpath}")
    print_info(f"Kconfig symbol: {request.kconfig_symbol}")
    print_info(f"Values: {', '.join(value_list)}")
    print_info(
        "Action: "
        f"{'Configure only' if request.config_only else 'Configure and build'}"
    )
    print_info(f"Build root directory: {build_root_path}")
    if env_dict:
        print_info(f"Environment variables: {env_dict}")
    if cmake_flags:
        print_info(f"CMake flags: {' '.join(cmake_flags)}")
    click.echo()

    build_dir_name = generate_build_dir_name(
        normalized_confpath,
        project_root=project.project_root,
        dawn_root=project.dawn_root,
    )
    symbol_component = sanitize_build_component(request.kconfig_symbol)

    def run_one_value(
        idx: int, total_items: int, value: str
    ) -> tuple[bool, str | None]:
        value_component = sanitize_build_component(value)
        build_path = build_root_path / (
            f"{build_dir_name}-{symbol_component}-{value_component}"
        )

        click.echo(
            f"{colored(f'[{idx}/{total_items}]', 'blue')} Value: {value}"
        )
        rel_build = _display_path(build_path, project_root)
        click.echo(f"           Build directory: {rel_build}")

        return _run_kconfig_value(
            build_path,
            normalized_confpath,
            project,
            request.kconfig_symbol,
            value,
            request.generator,
            env_dict,
            cmake_flags,
            request.jobs,
            request.config_only,
            request.verbose,
        )

    succeeded, failed, failed_configs = _run_build_sequence(
        items=value_list,
        continue_message="continuing with next value...",
        stop_message="stopping kconfig build",
        run_item=run_one_value,
        item_key=lambda value: value,
        continue_on_error=request.continue_on_error,
    )

    _print_kconfig_summary(total, succeeded, failed, failed_configs)


def _print_kconfig_summary(  # pragma: no cover
    total: int,
    succeeded: int,
    failed: int,
    failed_configs: list[tuple[str, str]],
) -> None:
    click.echo()
    print_header("Kconfig Build Summary")
    click.echo(f"Total values: {total}")
    click.echo(colored(f"Succeeded: {succeeded}", "green"))
    if failed > 0:
        click.echo(colored(f"Failed: {failed}", "red"))
        click.echo()
        click.echo("Failed values:")
        for value, reason in failed_configs:
            click.echo(f"  {colored('[ERR]', 'red')} {value} - {reason}")
    click.echo()

    if failed > 0:
        raise SystemExit(1)
