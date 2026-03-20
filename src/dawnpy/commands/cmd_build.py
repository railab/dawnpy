# tools/dawnpy/src/dawnpy/commands/cmd_build.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containing the build command for Dawn."""

import click

from dawnpy.dawn.workflows import BuildRequest, run_build_request


@click.command(name="build")
@click.argument("build_dir", type=click.Path())
@click.argument("confpath", required=False)
@click.option(
    "-g",
    "--generator",
    default="Ninja",
    show_default=True,
    type=click.Choice(["Ninja", "Unix Makefiles"], case_sensitive=False),
    help="CMake generator to use",
)
@click.option(
    "-e",
    "--env",
    "env_vars",
    multiple=True,
    help="Environment variables (e.g., -e CXX=g++-14 -e CC=gcc-14)",
)
@click.option(
    "-D",
    "--define",
    "cmake_defines",
    multiple=True,
    help="Additional CMake defines (e.g., -D CMAKE_BUILD_TYPE=Debug)",
)
@click.option(
    "-k",
    "--kconfig",
    "kconfig_overrides",
    multiple=True,
    help="Kconfig overrides (e.g., -k CONFIG_SIM_CAN_NODEID=0x100)",
)
@click.option(
    "-j",
    "--jobs",
    type=int,
    help="Number of parallel build jobs",
)
@click.option(
    "--dawn-root",
    type=click.Path(path_type=str),
    help="Override Dawn source root",
)
@click.option(
    "--nuttx-dir",
    type=click.Path(path_type=str),
    help="Override NuttX source directory",
)
@click.option(
    "--nuttx-apps-dir",
    type=click.Path(path_type=str),
    help="Override NuttX apps directory",
)
@click.option(
    "--config-only",
    is_flag=True,
    help="Only configure, do not build",
)
@click.option(
    "--build-only",
    is_flag=True,
    help="Only build, skip configuration",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output",
)
def cmd_build(
    build_dir: str,
    confpath: str | None,
    generator: str,
    env_vars: tuple[str, ...],
    cmake_defines: tuple[str, ...],
    kconfig_overrides: tuple[str, ...],
    jobs: int | None,
    dawn_root: str | None,
    nuttx_dir: str | None,
    nuttx_apps_dir: str | None,
    config_only: bool,
    build_only: bool,
    verbose: bool,
) -> None:
    """Configure and build Dawn project with CMake."""
    run_build_request(
        BuildRequest(
            build_dir=build_dir,
            confpath=confpath,
            generator=generator,
            env_vars=env_vars,
            cmake_defines=cmake_defines,
            kconfig_overrides=kconfig_overrides,
            jobs=jobs,
            dawn_root=dawn_root,
            nuttx_dir=nuttx_dir,
            nuttx_apps_dir=nuttx_apps_dir,
            config_only=config_only,
            build_only=build_only,
            verbose=verbose,
        )
    )
