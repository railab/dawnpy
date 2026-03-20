# tools/dawnpy/src/dawnpy/commands/cmd_kconfig.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containing the kconfig command for Dawn."""

import click

from dawnpy.dawn.workflows import KconfigSweepRequest, run_kconfig_request


@click.command(name="kconfig")
@click.argument("confpath")
@click.option(
    "--kconfig",
    "kconfig_symbol",
    required=True,
    help="Kconfig symbol to override (e.g., CONFIG_SIM_CAN_NODEID)",
)
@click.option(
    "--values",
    required=True,
    help="Comma-separated list of values (e.g., 0x100,0x500,0x600)",
)
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
    "-j",
    "--jobs",
    type=int,
    help="Number of parallel build jobs",
)
@click.option(
    "--build-root",
    default="build",
    show_default=True,
    help="Root directory for all build directories",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue building remaining configurations if one fails",
)
@click.option(
    "--config-only",
    is_flag=True,
    help="Only configure, do not build",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output",
)
def cmd_kconfig(
    confpath: str,
    kconfig_symbol: str,
    values: str,
    generator: str,
    env_vars: tuple[str, ...],
    cmake_defines: tuple[str, ...],
    jobs: int | None,
    build_root: str,
    continue_on_error: bool,
    config_only: bool,
    verbose: bool,
) -> None:
    """Configure and build multiple values for a Kconfig option."""
    run_kconfig_request(
        KconfigSweepRequest(
            confpath=confpath,
            kconfig_symbol=kconfig_symbol,
            values=values,
            generator=generator,
            env_vars=env_vars,
            cmake_defines=cmake_defines,
            jobs=jobs,
            build_root=build_root,
            continue_on_error=continue_on_error,
            config_only=config_only,
            verbose=verbose,
        )
    )
