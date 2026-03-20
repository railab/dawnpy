# tools/dawnpy/src/dawnpy/plugins_loader.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Built-in dawnpy command list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.commands.cmd_batch import cmd_batch
from dawnpy.commands.cmd_build import cmd_build
from dawnpy.commands.cmd_desc_bin import cmd_desc_bin
from dawnpy.commands.cmd_desc_decode_caps import cmd_desc_decode_caps
from dawnpy.commands.cmd_desc_gen import cmd_desc_gen
from dawnpy.commands.cmd_desc_headers_check import cmd_desc_headers_check
from dawnpy.commands.cmd_desc_new import cmd_desc_new
from dawnpy.commands.cmd_desc_valid import cmd_desc_valid
from dawnpy.commands.cmd_init import cmd_init
from dawnpy.commands.cmd_kconfig import cmd_kconfig
from dawnpy.commands.cmd_project import cmd_project

if TYPE_CHECKING:
    import click

commands_list: list["click.Command"] = [
    cmd_build,
    cmd_batch,
    cmd_kconfig,
    cmd_desc_valid,
    cmd_desc_gen,
    cmd_desc_bin,
    cmd_desc_decode_caps,
    cmd_desc_headers_check,
    cmd_desc_new,
    cmd_init,
    cmd_project,
]
