# tools/dawnpy/src/dawnpy/commands/cmd_batch.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containing the batch command for Dawn."""

import click

from dawnpy.dawn.workflows import BatchRequest, run_batch_request


@click.command(name="batch")
@click.argument("config_file", type=click.Path(exists=True))
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
def cmd_batch(
    config_file: str,
    generator: str,
    env_vars: tuple[str, ...],
    cmake_defines: tuple[str, ...],
    jobs: int | None,
    build_root: str,
    continue_on_error: bool,
    config_only: bool,
    verbose: bool,
) -> None:
    """Configure and build multiple configurations from a file."""
    run_batch_request(
        BatchRequest(
            config_file=config_file,
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
