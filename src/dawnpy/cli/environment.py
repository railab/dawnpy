# tools/dawnpy/src/dawnpy/cli/environment.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containint the Click environmet."""

from dataclasses import dataclass
from typing import Callable, TypeVar, cast

import click

F = TypeVar("F", bound=Callable[..., object])

###############################################################################
# Class: DEnvironmentData
###############################################################################


@dataclass
class DEnvironmentData:
    """Environment data."""

    debug: bool = False


###############################################################################
# Class: Environment
###############################################################################


class Environment(DEnvironmentData):
    """A class with application environmet."""

    def __init__(self) -> None:
        """Initialize environmet."""
        super().__init__()


###############################################################################
# Decorator: pass_environment
###############################################################################


# custom environmet decorator
pass_environment = cast(
    Callable[[F], F],
    click.make_pass_decorator(Environment, ensure=True),
)
